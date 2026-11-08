import asyncio
import json
from types import SimpleNamespace
import pytest
from app.vision_director import assess_frame,parse_vision_reply
from app.auto_timeline import build_timeline
from app import config


def test_strict_scores_and_clip_priority():
    with pytest.raises(ValueError):parse_vision_reply('{"category":"sports","relevance":4,"confidence":1}')
    data=parse_vision_reply('Results: {"category":"sports","relevance":0.8,"confidence":0.6,"description":"game action"}')
    assert data['category']=='sports' and data['relevance']==.8
    plan=build_timeline([4,4],4,style='fast',priority=[1,0])
    assert plan['shots'][0]['clip']==1


def test_cloud_upload_requires_optin():
    with pytest.raises(PermissionError):
        asyncio.run(assess_frame(b'fake',prompt='football',provider='openai',consent=False))


def test_openai_and_gemini_payload_with_fake_responses(monkeypatch):
    calls=[]
    class Client:
        async def post(self,url,headers,json):
            calls.append((url,headers,json))
            if 'openai' in url:
                result={'choices':[{'message':{'content':json_string}}]}
            else:
                result={'candidates':[{'content':{'parts':[{'text':json_string}]}}]}
            return SimpleNamespace(raise_for_status=lambda:None,json=lambda:result)
    json_string='{"category":"sports","relevance":0.92,"confidence":0.55,"description":"pitch"}'
    monkeypatch.setattr(config,'OPENAI_API_KEY','test-openai-key')
    monkeypatch.setattr(config,'GEMINI_API_KEY','test-gemini-key')
    async def go():
        x=await assess_frame(b'fake JPEG image',prompt='football',provider='openai',consent=True,client=Client())
        y=await assess_frame(b'fake JPEG image',prompt='football',provider='gemini',consent=True,client=Client())
        return x,y
    a,b=asyncio.run(go())
    assert a['relevance']==b['relevance']==.92
    assert 'api.openai.com' in calls[0][0]
    assert 'generativelanguage.googleapis.com' in calls[1][0]
    assert calls[0][1]['Authorization']=='Bearer test-openai-key'
