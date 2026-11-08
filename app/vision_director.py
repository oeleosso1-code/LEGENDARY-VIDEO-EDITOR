"""Explicit opt-in image analysis for user-owned video keyframes.

No full videos or user-supplied keys are posted by default. One still image per
source is an incomplete observation, not reliable event recognition.
"""
from __future__ import annotations
import asyncio
import base64
import hashlib
import json
import math
import re
from pathlib import Path
import httpx
from . import config
from .openai_keys import openai_chat_json, configured_openai_keys

CATEGORY={'sports','portrait','nature','city','product','gaming','dialogue','action','other'}


def parse_vision_reply(text: str) -> dict:
    if not isinstance(text,str) or len(text)>12000:
        raise ValueError('Invalid model reply')
    match=re.search(r'\{[\s\S]*\}',text)
    if not match:raise ValueError('Model did not return JSON')
    payload=json.loads(match.group(0))
    if not isinstance(payload,dict):raise ValueError('Invalid vision JSON')
    category=str(payload.get('category','other')).lower()
    if category not in CATEGORY:category='other'
    try:
        relevance=float(payload.get('relevance',.5))
        confidence=float(payload.get('confidence',.2))
    except (ValueError,TypeError):raise ValueError('Invalid vision scores') from None
    if not all(math.isfinite(x) and 0<=x<=1 for x in (relevance,confidence)):
        raise ValueError('Vision scores outside 0 to 1')
    return {'category':category,'relevance':round(relevance,3),'confidence':round(confidence,3),
            'description':str(payload.get('description',''))[:240],
            'reason':str(payload.get('reason',''))[:180],
            'limitation':'Single still frame; important events may be invisible.'}


async def extract_keyframe(video: Path, second: float=1.) -> bytes:
    if not video.is_file() or not math.isfinite(second) or second<0:
        raise ValueError('Invalid source')
    p=await asyncio.create_subprocess_exec('ffmpeg','-nostdin','-v','error',
      '-ss',f'{second:.3f}','-i',str(video),'-frames:v','1',
      '-vf','scale=320:-2','-q:v','5','-f','image2pipe','-vcodec','mjpeg','pipe:1',
      stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
    try:content,error=await asyncio.wait_for(p.communicate(),30)
    except asyncio.TimeoutError:
        p.kill();await p.communicate();raise RuntimeError('Vision frame decode timed out')
    except asyncio.CancelledError:
        p.kill();await p.communicate();raise
    if p.returncode or not content or len(content)>1000000:
        raise RuntimeError('Could not extract a valid small keyframe')
    return content


def _prompt(user_prompt: str) -> str:
    return ("You are assessing ONE STILL FRAME for an editor working only with real footage. "
      "Avoid guessing events that require temporal context (e.g. a soccer goal). "
      "Return JSON with description, category (sports, portrait, nature, city, product, "
      "gaming, dialogue, action, other), relevance (0..1), confidence (0..1), reason. "
      "Do not provide invented timestamps, authorship, permissions, or identities. "
      "Requested topic: "+user_prompt[:500])


async def assess_frame(jpeg: bytes, *, prompt: str, provider: str,
                       consent: bool=False, client: httpx.AsyncClient | None=None) -> dict:
    if not consent:
        raise PermissionError('Explicit user opt-in is required before uploading video frames')
    if provider not in ('openai','gemini') or len(jpeg)>1000000 or not jpeg:
        raise ValueError('Unsupported provider or frame payload')
    if provider=='openai':
        if not configured_openai_keys():
            raise RuntimeError('OpenAI key is not configured')
        body={'model':config.OPENAI_MODEL,'max_tokens':250,
          'messages':[{'role':'user','content':[
            {'type':'text','text':_prompt(prompt)},
            {'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+base64.b64encode(jpeg).decode(), 'detail':'low'}}]}]}
    else:
        key=config.GEMINI_API_KEY
        url=f'https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent'
        headers={'x-goog-api-key':key}
        body={'contents':[{'parts':[{'text':_prompt(prompt)},
            {'inline_data':{'mime_type':'image/jpeg','data':base64.b64encode(jpeg).decode()}}]}]}
    if provider=='gemini' and not key:
        raise RuntimeError('The selected provider key is not configured')
    if client is None:
        async with httpx.AsyncClient(timeout=30) as local:
            if provider=='openai':
                raw=await openai_chat_json(local,body)
            else:
                response=await local.post(url,headers=headers,json=body)
                response.raise_for_status()
                raw=response.json()
    elif provider=='openai':
        raw=await openai_chat_json(client,body)
    else:
        response=await client.post(url,headers=headers,json=body)
        response.raise_for_status()
        raw=response.json()
    try:
        text=(raw['choices'][0]['message']['content'] if provider=='openai'
              else raw['candidates'][0]['content']['parts'][0]['text'])
    except (KeyError,IndexError,TypeError):
        raise ValueError('Provider did not return usable text') from None
    return parse_vision_reply(text)


def file_digest(path: Path) -> str:
    digest=hashlib.sha256()
    with Path(path).open('rb') as fp:
        for part in iter(lambda:fp.read(1024*1024),b''):
            digest.update(part)
    return digest.hexdigest()


async def scan_clips(paths: list[Path], *, prompt: str, provider: str,
                     consent: bool, max_images: int=6) -> list[dict]:
    if not consent:raise PermissionError('Explicit opt-in required')
    if max_images<1 or max_images>8:raise ValueError('Maximum 8 charged frames per request')
    output=[]
    for path in paths[:max_images]:
        path=Path(path)
        frame=await extract_keyframe(path)
        result=await assess_frame(frame,prompt=prompt,provider=provider,consent=True)
        output.append({'source_hash':file_digest(path),**result})
    return output
