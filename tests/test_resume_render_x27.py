import asyncio
import json
import shutil
import subprocess
from pathlib import Path
import pytest
from app.resume_render import _chunks, render_resumable
from app.editor_pro import probe


def test_chunk_partition():
    assert _chunks(12, 6) == [6, 6]
    assert _chunks(11, 6) == [6, 5]
    assert sum(_chunks(35, 10)) == 35
    assert min(_chunks(35, 10)) >= 5
    with pytest.raises(ValueError): _chunks(4, 10)


def test_missing_inputs(tmp_path):
    with pytest.raises(ValueError):
        asyncio.run(render_resumable([tmp_path/'absent.mp4'], None, tmp_path/'out.mp4', 10, tmp_path/'work'))


def make_source(path, duration=11):
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=size=160x90:rate=25',
                    '-t',str(duration),'-c:v','libx264','-preset','ultrafast',str(path)],check=True)


def make_music(path):
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=440:sample_rate=44100',
                    '-t','12','-c:a','aac',str(path)],check=True)


def test_resume_real_render_and_invalidation(tmp_path):
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        pytest.skip('ffmpeg not installed')
    clip, music = tmp_path/'source.mp4', tmp_path/'song.m4a'
    make_source(clip); make_music(music)
    out, work = tmp_path/'final.mp4', tmp_path/'work'
    async def run(color='natural'):
        return await render_resumable([clip], music, out, 10, work, chunk_seconds=5,
                                      color=color, preview=True)
    a = asyncio.run(run())
    assert a['rendered'] == 2 and a['reused'] == 0
    assert a['state'] == 'completed'
    dur, has_video = asyncio.run(probe(out))
    assert has_video and abs(dur - 10) <= 0.2
    streams = json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(out)]))['streams']
    assert any(s['codec_type'] == 'audio' for s in streams)
    b = asyncio.run(run())
    assert b['rendered'] == 0 and b['reused'] == 2
    c = asyncio.run(run('warm'))
    assert c['rendered'] == 2 and c['reused'] == 0
    assert json.loads((work/'status.json').read_text())['state'] == 'completed'


def test_interruption_resumes_first_complete_chunk(tmp_path, monkeypatch):
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        pytest.skip('ffmpeg not installed')
    import app.resume_render as rr
    clip = tmp_path / 'footage.mp4'
    make_source(clip)
    original = rr.render_pro
    call_count = 0

    async def fails_second(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError('Simulated worker interruption')
        return await original(*args, **kwargs)

    monkeypatch.setattr(rr, 'render_pro', fails_second)
    out, work = tmp_path / 'finished.mp4', tmp_path / 'checkpoints'
    with pytest.raises(RuntimeError, match='Simulated'):
        asyncio.run(rr.render_resumable([clip], None, out, 10, work,
                                       chunk_seconds=5, preview=True))
    assert not out.exists()
    assert json.loads((work / 'status.json').read_text())['state'] == 'interrupted'
    monkeypatch.setattr(rr, 'render_pro', original)
    result = asyncio.run(rr.render_resumable([clip], None, out, 10, work,
                                            chunk_seconds=5, preview=True))
    assert result['reused'] == 1 and result['rendered'] == 1
    assert out.is_file()
