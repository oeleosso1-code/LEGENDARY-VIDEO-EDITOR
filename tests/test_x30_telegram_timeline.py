"""Integration verification for an immutable Telegram timeline long-render request."""
import asyncio
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
import shutil
import pytest
from app import config, long_jobs
# Use the existing test suite's SDK stubs if python-telegram-bot is unavailable.
import importlib.util
import sys
import types
if importlib.util.find_spec('telegram') is None and 'telegram' not in sys.modules:
    telegram = types.ModuleType('telegram')
    from importlib.machinery import ModuleSpec
    telegram.__spec__ = ModuleSpec('telegram', loader=None)
    telegram.Update = type('Update', (), {})
    ext = types.ModuleType('telegram.ext')
    for name in ('Application', 'CommandHandler', 'MessageHandler', 'ContextTypes'):
        setattr(ext, name, type(name, (), {}))
    ext.ContextTypes.DEFAULT_TYPE = object
    ext.filters = types.SimpleNamespace(VIDEO=0, AUDIO=0, Document=types.SimpleNamespace(ALL=0))
    sys.modules['telegram'] = telegram
    sys.modules['telegram.ext'] = ext
from app import bot_pro


def generate(path: Path, color='red', duration=4):
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                    f'color=c={color}:s=160x90:r=25', '-t', str(duration),
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(path)], check=True)


@pytest.fixture
def user(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'OUTPUT_DIR', tmp_path)
    uid = 33219
    home = tmp_path / 'users' / str(uid)
    home.mkdir(parents=True)
    return uid, home


def request(uid, home):
    return dict(clips=[str(home / 'clip1.mp4'), str(home / 'clip2.mp4')],
                music=None, seconds=5, orientation='vertical', style='cinematic',
                color='natural', music_start=0., music_volume=.85,
                shotlist=str(home / 'shotlist.json'))


def write_plan(home):
    (home / 'shotlist.json').write_text(json.dumps({'shots': [
        {'clip': 0, 'start': 0, 'duration': 2, 'speed': 1},
        {'clip': 1, 'start': 0, 'duration': 2, 'speed': 1},
        {'clip': 0, 'start': 1, 'duration': 1, 'speed': 1}]}))


def test_immutable_timeline_and_integrity(user):
    uid, home = user
    (home / 'clip1.mp4').write_bytes(b'placeholder')
    (home / 'clip2.mp4').write_bytes(b'placeholder')
    write_plan(home)
    saved = long_jobs.create(uid, request(uid, home))
    assert saved['shotlist'] != str(home / 'shotlist.json')
    assert Path(saved['shotlist']).is_file()
    (home / 'shotlist.json').write_text('broken new plan')
    loaded = long_jobs.load(uid)
    assert loaded['shotlist'] == saved['shotlist']
    assert len(json.loads(Path(loaded['shotlist']).read_text())['shots']) == 3
    Path(saved['shotlist']).write_text('{"shots": []}')
    with pytest.raises(ValueError, match='integrity'):
        long_jobs.load(uid)


def test_timeline_rejects_bad_owner_and_duration(user):
    uid, home = user
    (home / 'clip1.mp4').write_bytes(b'x')
    (home / 'clip2.mp4').write_bytes(b'x')
    write_plan(home)
    d = request(uid, home)
    d['seconds'] = 6
    with pytest.raises(ValueError, match='duration'):
        long_jobs.create(uid, d)
    d['seconds'] = 5
    d['shotlist'] = str(home.parent / 'other.json')
    with pytest.raises(ValueError, match='user directory'):
        long_jobs.create(uid, d)


@pytest.mark.skipif(not shutil.which('ffmpeg'), reason='FFmpeg required')
def test_bot_end_to_end_and_resume(user, monkeypatch):
    uid, home = user
    generate(home / 'clip1.mp4')
    generate(home / 'clip2.mp4', 'blue')
    write_plan(home)
    saved = long_jobs.create(uid, request(uid, home))
    messages=[]
    class Bot:
        async def send_message(self, chat_id, message):
            messages.append(message)
        async def send_video(self, chat_id, video, caption=None):
            assert video.read(12)
            messages.append(caption)
    async def do():
        await bot_pro.process_long_job(Bot(), uid, uid, saved)
        status = long_jobs.status(uid)
        assert status['state'] == 'completed'
        assert (status['finished'], status['total']) == (1, 1)
        assert status['output_exists']
        await bot_pro.process_long_job(Bot(), uid, uid, long_jobs.load(uid))
    asyncio.run(do())
    out, _ = long_jobs.paths(uid, saved)
    report = json.loads((out.parent / 'final_render_report.json').read_text())
    assert report['reused_chunks'] == 1
    assert messages.count('تم التصدير بنجاح') == 2
