"""Private OpenAI API key rotation with *limited* failure-based fallback.

No secret values or provider response bodies are written to logs. Requests are
not sent to both keys unless the first request fails in a retryable way.
"""
from __future__ import annotations

from collections.abc import Mapping
import httpx
from . import config

OPENAI_CHAT_URL = 'https://api.openai.com/v1/chat/completions'
RETRYABLE_STATUS = frozenset({401, 403, 408, 409, 429, 500, 502, 503, 504})


def configured_openai_keys() -> list[str]:
    """Return at most two unique keys, primary then secondary; never print them."""
    keys = [getattr(config, 'OPENAI_API_KEY', ''),
            getattr(config, 'OPENAI_API_KEY_SECONDARY', '')]
    result: list[str] = []
    for key in keys:
        if key and key not in result:
            result.append(key)
    return result


async def openai_chat_json(client: httpx.AsyncClient, payload: Mapping) -> dict:
    """Call OpenAI using primary; use secondary only for retryable failures.

    A failed request on the first key may still incur billing; fallback is
    conservative but cannot guarantee no duplicate charges on transport errors.
    """
    keys = configured_openai_keys()
    if not keys:
        raise RuntimeError('No OpenAI API key configured')
    for index, key in enumerate(keys):
        try:
            response = await client.post(
                OPENAI_CHAT_URL, headers={'Authorization': f'Bearer {key}'},
                json=dict(payload),
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError('Invalid provider response')
            return data
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if index + 1 < len(keys) and status in RETRYABLE_STATUS:
                continue
            raise RuntimeError(f'OpenAI request failed (HTTP {status})') from None
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            if index + 1 < len(keys):
                continue
            raise RuntimeError('OpenAI network connection or timeout failure') from None
    raise RuntimeError('All OpenAI keys unavailable')
