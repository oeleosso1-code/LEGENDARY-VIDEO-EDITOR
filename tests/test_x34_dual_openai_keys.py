import asyncio
import httpx
import pytest
from app import config
from app.openai_keys import configured_openai_keys, openai_chat_json
from app.director import plan_queries
from app.vision_director import assess_frame


def test_two_keys_are_unique_and_ordered(monkeypatch):
    monkeypatch.setattr(config, 'OPENAI_API_KEY', 'primary')
    monkeypatch.setattr(config, 'OPENAI_API_KEY_SECONDARY', 'secondary')
    assert configured_openai_keys() == ['primary', 'secondary']
    monkeypatch.setattr(config, 'OPENAI_API_KEY_SECONDARY', 'primary')
    assert configured_openai_keys() == ['primary']


def test_first_key_is_not_duplicated_on_success(monkeypatch):
    monkeypatch.setattr(config, 'OPENAI_API_KEY', 'primary')
    monkeypatch.setattr(config, 'OPENAI_API_KEY_SECONDARY', 'secondary')
    seen=[]
    def handler(request):
        seen.append(request.headers['Authorization'])
        return httpx.Response(200, json={'choices':[{'message':{'content':'ok'}}]})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            return await openai_chat_json(c, {'model':'example', 'messages':[]})
    assert asyncio.run(run())['choices'][0]['message']['content'] == 'ok'
    assert seen == ['Bearer primary']


def test_retry_on_429_uses_second_key_for_shot_planning(monkeypatch):
    monkeypatch.setattr(config, 'OPENAI_API_KEY', 'primary')
    monkeypatch.setattr(config, 'OPENAI_API_KEY_SECONDARY', 'secondary')
    seen=[]
    def handler(request):
        seen.append(request.headers['Authorization'])
        if request.headers['Authorization']=='Bearer primary':
            return httpx.Response(429, json={'error':{'message':'limit reached'}})
        return httpx.Response(200, json={'choices':[{'message':{'content':'{"queries":["football pitch"]}'}}]})
    original=httpx.AsyncClient
    class FakeClient(original):
        def __init__(self, *args, **kwargs):
            kwargs['transport']=httpx.MockTransport(handler)
            super().__init__(*args,**kwargs)
    monkeypatch.setattr('app.director.httpx.AsyncClient', FakeClient)
    result=asyncio.run(plan_queries('football match',3))
    assert result==['football pitch']
    assert seen==['Bearer primary','Bearer secondary']


def test_non_retryable_400_does_not_use_secondary(monkeypatch):
    monkeypatch.setattr(config,'OPENAI_API_KEY','primary')
    monkeypatch.setattr(config,'OPENAI_API_KEY_SECONDARY','secondary')
    seen=[]
    def handler(request):
        seen.append(request.headers['Authorization'])
        return httpx.Response(400,json={'error':{'message':'invalid request'}})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            with pytest.raises(RuntimeError,match='HTTP 400'):
                await openai_chat_json(c, {'model':'example'})
    asyncio.run(run())
    assert seen == ['Bearer primary']


def test_vision_failover_preserves_required_consent(monkeypatch):
    monkeypatch.setattr(config,'OPENAI_API_KEY','primary')
    monkeypatch.setattr(config,'OPENAI_API_KEY_SECONDARY','secondary')
    seen=[]
    def handler(request):
        seen.append(request.headers['Authorization'])
        if len(seen)==1:
            return httpx.Response(503,json={'error':'temporarily unavailable'})
        return httpx.Response(200,json={'choices':[{'message':{'content':'{"category":"sports","relevance":0.7,"confidence":0.5}'}}]})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            with pytest.raises(PermissionError):
                await assess_frame(b'image',prompt='football',provider='openai',consent=False,client=c)
            return await assess_frame(b'image',prompt='football',provider='openai',consent=True,client=c)
    data=asyncio.run(run())
    assert data['category']=='sports'
    assert seen == ['Bearer primary','Bearer secondary']


def test_none_key_configured_does_not_call_http(monkeypatch):
    monkeypatch.setattr(config,'OPENAI_API_KEY','')
    monkeypatch.setattr(config,'OPENAI_API_KEY_SECONDARY','')
    def handler(request):
        raise AssertionError('should not call HTTP')
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            with pytest.raises(RuntimeError,match='No OpenAI API key'):
                await openai_chat_json(c,{})
    asyncio.run(run())
