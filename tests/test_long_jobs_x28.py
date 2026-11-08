import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from app import long_jobs, config

@pytest.fixture
def user(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'OUTPUT_DIR', tmp_path)
    uid = 12345
    path = tmp_path / 'users' / str(uid)
    path.mkdir(parents=True)
    clip = path / 'scene.mp4'
    clip.write_bytes(b'fixture video placeholder')
    song = path / 'audio.mp3'
    song.write_bytes(b'fixture audio placeholder')
    return uid, clip, song


def make(uid, clip, song):
    return {'clips':[str(clip)], 'music':str(song), 'seconds':20,
            'orientation':'vertical', 'style':'cinematic', 'color':'natural',
            'music_start': 2.5, 'music_volume':0.8}


def test_snapshot_survives_session_changes(user):
    uid, clip, song=user
    req=long_jobs.create(uid,make(uid,clip,song))
    updated=make(uid,clip,song)
    updated['seconds']=25
    updated['clips'].clear()
    loaded=long_jobs.load(uid)
    assert loaded['seconds']==20 and loaded['clips']==[str(clip)]
    assert loaded['job_id']==req['job_id']
    assert long_jobs.status(uid)['state']=='not_started'


def test_requires_uploads_and_rejects_symlinks(user,tmp_path):
    uid,clip,song=user
    outside=tmp_path/'external.mp4'
    outside.write_bytes(b'not owned')
    with pytest.raises(ValueError):long_jobs.create(uid,make(uid,outside,song))
    shortcut=clip.parent/'shortcut.mp4'
    shortcut.symlink_to(outside)
    with pytest.raises(ValueError):long_jobs.create(uid,make(uid,shortcut,song))


def test_rejects_unsupported_modes(user):
    uid,clip,song=user
    d=make(uid,clip,song)
    d['subtitles']=str(clip)
    with pytest.raises(ValueError):long_jobs.create(uid,d)
    d=make(uid,clip,song)
    d['music_volume']=float('nan')
    with pytest.raises(ValueError):long_jobs.create(uid,d)
    d=make(uid,clip,song)
    d['seconds']=12000
    with pytest.raises(ValueError):long_jobs.create(uid,d)


def test_reports_checkpoint_state(user):
    uid,clip,song=user
    req=long_jobs.create(uid,make(uid,clip,song))
    output,work=long_jobs.paths(uid,req)
    work.mkdir(parents=True)
    (work/'status.json').write_text(json.dumps({'state':'interrupted','finished':1,'total':2}))
    assert long_jobs.status(uid)['finished']==1
    assert long_jobs.status(uid)['state']=='interrupted'


def test_detects_deleted_music_on_resume(user):
    uid,clip,song=user
    long_jobs.create(uid,make(uid,clip,song))
    song.unlink()
    with pytest.raises(ValueError):long_jobs.load(uid)


def test_long_bot_handler_simulated(user, monkeypatch):
    # Test Telegram handler logic with lightweight message/context doubles.
    from app import bot_pro,store
    uid, clip, song = user
    store.save(uid,make(uid,clip,song))
    monkeypatch.setattr(bot_pro,'authorized',lambda update: True)
    messages=[]
    async def reply(msg): messages.append(msg)
    update=SimpleNamespace(effective_user=SimpleNamespace(id=uid),
        effective_chat=SimpleNamespace(id=uid),message=SimpleNamespace(reply_text=reply))
    async def fake_process(bot, chat_id, uid, req):
        await asyncio.sleep(0)
    monkeypatch.setattr(bot_pro,'process_long_job',fake_process)
    context=SimpleNamespace(bot=object())
    async def scenario():
        await bot_pro.longmake(update,context)
        await asyncio.sleep(0.01)
        assert long_jobs.load(uid)['seconds']==20
        await bot_pro.longstatus(update,context)
        await bot_pro.longresume(update,context)
        await asyncio.sleep(0.01)
    asyncio.run(scenario())
    assert any('تم حفظ' in x for x in messages)
    assert any('حالة المهمة' in x for x in messages)
    assert any('استئناف' in x for x in messages)
    bot_pro.RUNNING.pop(uid,None)
