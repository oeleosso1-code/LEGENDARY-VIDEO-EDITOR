"""Optional LLM shot-search planning; edit engine never fabricates video footage."""
import json
import re
import httpx
from . import config
from .openai_keys import openai_chat_json, configured_openai_keys


def safe_search_terms(raw: str) -> list[str]:
    return [raw.strip()[:110]] if raw.strip() else []

async def plan_queries(prompt: str, count: int) -> list[str]:
    """Works with OpenAI or Gemini. Fallback to input when no key or provider error."""
    system = ('You are a stock-footage video editor. Return JSON exactly: {"queries": ["...", ...]}. '
              'Produce up to 5 short concrete ENGLISH search terms for REAL stock footage. '
              'Do not invent source URLs or claim permissions. No extra prose.')
    message = f'{system}\nUser request: {prompt[:800]}'
    raw=None
    try:
        async with httpx.AsyncClient(timeout=22) as client:
            if configured_openai_keys():
                data=await openai_chat_json(client,{'model':config.OPENAI_MODEL,'temperature':0.2,'messages':[{'role':'user','content':message}]})
                raw=data['choices'][0]['message']['content']
            elif config.GEMINI_API_KEY:
                r=await client.post(f'https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent',headers={'x-goog-api-key':config.GEMINI_API_KEY},json={'contents':[{'parts':[{'text':message}]}]});r.raise_for_status()
                raw=r.json()['candidates'][0]['content']['parts'][0]['text']
    except (httpx.HTTPError,RuntimeError,KeyError,IndexError,ValueError):
        pass
    if raw:
        try:
            parsed=json.loads(re.search(r'\{[\s\S]*\}',raw).group(0))
            q=[x.strip()[:100] for x in parsed.get('queries',[]) if isinstance(x,str) and x.strip()]
            if q: return q[:min(count,5)]
        except (ValueError,AttributeError,TypeError): pass
    return safe_search_terms(prompt)
