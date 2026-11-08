import asyncio
import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from app.shotlist import trim_shotlist
from app import store
# In CI, controller unit tests use stubs if the Telegram SDK is not installed.
# Runtime installations load the real dependency from requirements.txt.
import importlib.util
import sys
import types
if importlib.util.find_spec('telegram') is None:
    telegram=types.ModuleType('telegram'); telegram.Update=type('Update',(),{})
    ext=types.ModuleType('telegram.ext')
    for name in ('Application','CommandHandler','MessageHandler','ContextTypes'):
        setattr(ext,name,type(name,(),{}))
    ext.ContextTypes.DEFAULT_TYPE=object
    ext.filters=types.SimpleNamespace(VIDEO=0,AUDIO=0,Document=types.SimpleNamespace(ALL=0))
    sys.modules['telegram']=telegram;sys.modules['telegram.ext']=ext
from app import bot_pro


def test_trim_mid_shot():
    shots=[{'clip':0,'start':0,'duration':8,'speed':1}, {'clip':1,'start':2,'duration':5,'speed':0.5}]
    cropped=trim_shotlist(shots,10)
    assert len(cropped)==2
    assert cropped[0]['duration']==8
    assert cropped[1]['duration']==2
    assert sum(x['duration'] for x in cropped)==10


def test_trim_invalid():
    with pytest.raises(ValueError): trim_shotlist([{'duration':1}], 2)


def test_blank_has_shotlist():
    assert store.blank()['shotlist'] is None
    assert store.blank()['version']==7


def fake_update(uid=123456):
    msg=SimpleNamespace(reply_text=AsyncMock())
    return SimpleNamespace(effective_user=SimpleNamespace(id=uid), effective_message=msg, message=msg)


def make_video(path, seconds=5):
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=blue:s=160x90:r=25',
                    '-t',str(seconds),'-c:v','libx264','-preset','ultrafast',str(path)],check=True)


def test_telegram_shotadd_and_validate(tmp_path, monkeypatch):
    if not shutil.which('ffmpeg'):pytest.skip('ffmpeg missing')
    monkeypatch.setattr(store.config,'OUTPUT_DIR',tmp_path)
    monkeypatch.setattr(bot_pro.config,'ALLOWED_USER_IDS',set())
    uid=123456
    f=store.root(uid)/'clip.mp4'
    make_video(f)
    data=store.blank();data['seconds']=5;data['clips']=[str(f)];store.save(uid,data)
    update=fake_update(uid)
    ctx=SimpleNamespace(args=['1','0','2','1.0'])
    asyncio.run(bot_pro.shotadd(update,ctx))
    ctx.args=['1','2','3','1.0']
    asyncio.run(bot_pro.shotadd(update,ctx))
    data=store.load(uid)
    assert len(json.loads(Path(data['shotlist']).read_text())['shots'])==2
    assert len(asyncio.run(bot_pro.validate_user_shotlist(uid,data)))==2
    asyncio.run(bot_pro.shots(update,SimpleNamespace(args=[])))
    assert '5.00' in update.message.reply_text.call_args.args[0]
    asyncio.run(bot_pro.shotclear(update,SimpleNamespace(args=[])))
    assert store.load(uid)['shotlist'] is None


def test_telegram_rejects_invalid_shotadd(tmp_path,monkeypatch):
    monkeypatch.setattr(store.config,'OUTPUT_DIR',tmp_path)
    monkeypatch.setattr(bot_pro.config,'ALLOWED_USER_IDS',set())
    update=fake_update(123456)
    asyncio.run(bot_pro.shotadd(update,SimpleNamespace(args=['1','nan','2'])))
    assert 'الاستخدام' in update.message.reply_text.call_args.args[0]


def test_real_preview_from_long_manual_timeline(tmp_path):
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        pytest.skip('ffmpeg unavailable')
    from app.editor_pro import render_pro
    clip=tmp_path/'sample.mp4';make_video(clip, seconds=10)
    original=[{'clip':0,'start':0,'duration':5,'speed':1.0},
              {'clip':0,'start':5,'duration':3,'speed':1.0}]
    preview=tmp_path/'preview_shotlist.json'
    preview.write_text(json.dumps({'shots':trim_shotlist(original,6)}))
    dest=tmp_path/'preview.mp4'
    info=asyncio.run(render_pro([clip],None,dest,6,'horizontal','cinematic',preview=True,shotlist=preview))
    assert len(info['timeline'])==2
    assert dest.stat().st_size>1024
    d=subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration',
                                '-of','default=noprint_wrappers=1:nokey=1',str(dest)])
    assert abs(float(d)-6)<0.3
