"""Real FFmpeg render verifies SRT after chunk merge; immutability on resume."""
import asyncio
import json
import subprocess
from pathlib import Path
import shutil
import pytest
from app import config, long_jobs
from app.timeline_render import render_timeline


def video(p, color):
    subprocess.run(['ffmpeg', '-hide_banner','-v','error','-y','-f','lavfi',
        '-i',f'color=c={color}:s=160x90:r=25','-t','3','-c:v','libx264',
        '-pix_fmt','yuv420p',str(p)], check=True)


def audio(p):
    subprocess.run(['ffmpeg','-hide_banner','-v','error','-y','-f','lavfi',
        '-i','sine=frequency=470:sample_rate=44100','-t','6',str(p)],check=True)


@pytest.mark.skipif(not shutil.which('ffmpeg') or not shutil.which('ffprobe'), reason='FFmpeg required')
def test_timeline_srt_and_music_with_cached_chunks(tmp_path):
    a,b=tmp_path/'a.mp4',tmp_path/'b.mp4'
    video(a,'red');video(b,'blue')
    plan=tmp_path/'shots.json'
    plan.write_text(json.dumps({'shots':[
      {'clip':0,'start':0,'duration':2,'speed':1},
      {'clip':1,'start':0,'duration':2,'speed':1}]}))
    srt=tmp_path/'captions.srt'
    srt.write_text('1\n00:00:02,100 --> 00:00:03,700\nTEST X31 SUBTITLE\n',encoding='utf-8')
    song=tmp_path/'music.wav';audio(song)
    out=tmp_path/'output.mp4'
    async def run():
        return await render_timeline([a,b],plan,out,music=song,subtitles=srt,chunk_seconds=2)
    try:
        first=asyncio.run(run())
    except RuntimeError as exc:
        if 'No such filter' in str(exc) or 'subtitles' in str(exc).lower() and 'not found' in str(exc).lower():
            pytest.skip('FFmpeg libass subtitles filter unavailable')
        raise
    assert first['chunks']==2 and first['subtitles'] and first['music']
    assert asyncio.run(run())['reused_chunks']==2
    probe=subprocess.run(['ffprobe','-v','error','-show_entries','stream=codec_type',
       '-of','csv=p=0',str(out)],capture_output=True,text=True,check=True).stdout
    assert 'audio' in probe and 'video' in probe
    def frame(sec):
        return subprocess.run(['ffmpeg','-v','error','-ss',str(sec),'-i',str(out),
         '-frames:v','1','-f','rawvideo','-pix_fmt','gray','-'],
         capture_output=True,check=True).stdout
    # Text must produce a visible difference in a frame while the same-color shot is displayed.
    assert frame(2.4) != frame(3.9)


def test_subtitle_snapshot_and_tamper(tmp_path,monkeypatch):
    monkeypatch.setattr(config,'OUTPUT_DIR',tmp_path)
    uid=98731;home=tmp_path/'users'/str(uid);home.mkdir(parents=True)
    (home/'c.mp4').write_bytes(b'placeholder')
    plan=home/'shots.json'
    plan.write_text(json.dumps({'shots':[{'clip':0,'start':0,'duration':5,'speed':1}]}))
    srt=home/'captions.srt';srt.write_text('1\n00:00:00,500 --> 00:00:02,000\nHi\n')
    saved=long_jobs.create(uid, {'clips':[str(home/'c.mp4')], 'shotlist':str(plan),
             'subtitles':str(srt),'seconds':5,'orientation':'vertical','style':'cinematic'})
    srt.write_text('changed')
    assert Path(long_jobs.load(uid)['subtitles']).read_text().endswith('Hi\n')
    Path(saved['subtitles']).write_text('malicious modification')
    with pytest.raises(ValueError,match='integrity'):
        long_jobs.load(uid)


def test_srt_disallowed_without_plan(tmp_path,monkeypatch):
    monkeypatch.setattr(config,'OUTPUT_DIR',tmp_path)
    uid=98732;home=tmp_path/'users'/str(uid);home.mkdir(parents=True)
    (home/'c.mp4').write_bytes(b'placeholder');(home/'s.srt').write_text('test')
    with pytest.raises(ValueError,match='fixed shotlist'):
        long_jobs.create(uid, {'clips':[str(home/'c.mp4')], 'subtitles':str(home/'s.srt'),
                   'seconds':5,'orientation':'vertical','style':'cinematic'})
