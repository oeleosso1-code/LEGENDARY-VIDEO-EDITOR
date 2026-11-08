import asyncio
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
import pytest
from app import config,store,long_jobs
import importlib.util
import sys
import types
if importlib.util.find_spec('telegram') is None and 'telegram' not in sys.modules:
    from importlib.machinery import ModuleSpec
    telegram=types.ModuleType('telegram');telegram.__spec__=ModuleSpec('telegram',loader=None)
    telegram.Update=type('Update',(),{})
    ext=types.ModuleType('telegram.ext')
    for name in ('Application','CommandHandler','MessageHandler','ContextTypes'):
        setattr(ext,name,type(name,(),{}))
    ext.ContextTypes.DEFAULT_TYPE=object
    ext.filters=types.SimpleNamespace(VIDEO=0,AUDIO=0,Document=types.SimpleNamespace(ALL=0))
    sys.modules['telegram']=telegram;sys.modules['telegram.ext']=ext
from app.bot_pro import referencelast,refinspect,usegrade,musicmap,autoplan

@pytest.fixture
def setup_user(tmp_path,monkeypatch):
    monkeypatch.setattr(config,'OUTPUT_DIR',tmp_path)
    uid=7722
    home=store.root(uid)
    for filename,color in [('source1.mp4','red'),('source2.mp4','green'),('reference.mp4','blue')]:
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',
          f'color=c={color}:s=160x90:r=25','-t','4',
          '-c:v','libx264','-pix_fmt','yuv420p',str(home/filename)],check=True)
    song=home/'song.wav'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',
       'sine=frequency=420:sample_rate=16000','-t','6',str(song)],check=True)
    d=store.blank()
    d.update({'clips':[str(home/'source1.mp4'),str(home/'source2.mp4'),str(home/'reference.mp4')],
              'music':str(song),'seconds':5,'music_start':.5,'style':'fast'})
    store.save(uid,d)
    return uid,home


def test_real_footage_reference_music_plan_and_long_render(setup_user,monkeypatch):
    uid,home=setup_user
    from app import bot_pro
    monkeypatch.setattr(bot_pro,'authorized',lambda update: True)
    messages=[]
    async def reply(s):messages.append(s)
    update=SimpleNamespace(effective_user=SimpleNamespace(id=uid),
         effective_chat=SimpleNamespace(id=uid),message=SimpleNamespace(reply_text=reply))
    context=SimpleNamespace(args=[],bot=None)
    async def do():
        await referencelast(update,context)
        assert len(store.load(uid)['clips'])==2
        await refinspect(update,context)
        await usegrade(update,context)
        await musicmap(update,context)
        await autoplan(update,context)
        d=store.load(uid)
        assert d['reference_profile'] is not None
        assert d['reference'] not in d['clips']
        assert Path(d['shotlist']).is_file()
        req=long_jobs.create(uid,d)
        class Bot:
            async def send_message(self, chat_id, message): messages.append(message)
            async def send_video(self,chat_id,video,caption=None):
                assert video.read(10);messages.append(caption)
        await bot_pro.process_long_job(Bot(),uid,uid,req)
        await bot_pro.process_long_job(Bot(),uid,uid,long_jobs.load(uid))
        result,cache=long_jobs.paths(uid,req)
        assert result.is_file()
        report=json.loads((result.parent/'final_render_report.json').read_text())
        assert report['reused_chunks']>=1
        assert report['seconds']==5
    asyncio.run(do())
    assert any('مرجعاً' in s for s in messages)
    assert any('🎞️ أُنشئ جدول' in s for s in messages)
    assert any('تم التصدير بنجاح' in s for s in messages)
