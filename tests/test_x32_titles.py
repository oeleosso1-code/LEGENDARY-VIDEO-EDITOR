"""Actual Arabic titles rendered over the complete long video timeline."""
import asyncio
import json
import shutil
import subprocess
from pathlib import Path
import pytest
from app import config, long_jobs
from app.timeline_render import render_timeline
from app.titles import load_titles


def color_video(path, color):
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',
        f'color=c={color}:s=160x90:r=25','-t','2','-c:v','libx264','-pix_fmt','yuv420p',str(path)],check=True)


def sample(path, second):
    return subprocess.run(['ffmpeg','-v','error','-ss',str(second),'-i',str(path),
        '-frames:v','1','-f','rawvideo','-pix_fmt','gray','-'],capture_output=True,check=True).stdout


@pytest.mark.skipif(not shutil.which('ffmpeg') or not shutil.which('ffprobe'),reason='FFmpeg required')
def test_render_arabic_titles_and_srt_and_music_cache(tmp_path):
    a,b=tmp_path/'a.mp4',tmp_path/'b.mp4'
    color_video(a,'red');color_video(b,'blue')
    shots=tmp_path/'shots.json'
    shots.write_text(json.dumps({'shots':[{'clip':0,'start':0,'duration':2,'speed':1},
                                            {'clip':1,'start':0,'duration':2,'speed':1}]}))
    titles=tmp_path/'titles.json'
    titles.write_text(json.dumps({'titles':[{'text':'مونتاج أسطوري','start':.3,'end':1.5,
                        'color':'gold','position':'center'},
                       {'text':'العراق','start':2.4,'end':3.4,'color':'cyan','position':'top'}]},ensure_ascii=False))
    srt=tmp_path/'subtitles.srt';srt.write_text('1\n00:00:02,100 --> 00:00:03,700\nTEST SUBTITLE\n')
    audio=tmp_path/'audio.wav'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi',
          '-i','sine=frequency=430:sample_rate=44100','-t','5',str(audio)],check=True)
    out=tmp_path/'final.mp4'
    async def go():
        return await render_timeline([a,b],shots,out,music=audio,subtitles=srt,
                                     titles=titles,chunk_seconds=2)
    report=asyncio.run(go())
    assert report['titles']==2 and report['music'] and report['subtitles']
    assert report['chunks']==2
    assert sample(out,.8)!=sample(out,1.8)
    assert sample(out,2.7)!=sample(out,3.8)
    assert asyncio.run(go())['reused_chunks']==2
    probe=subprocess.run(['ffprobe','-v','error','-show_entries','stream=codec_type',
         '-of','csv=p=0',str(out)],capture_output=True,text=True,check=True).stdout
    assert 'audio' in probe and 'video' in probe


def test_title_validation(tmp_path):
    p=tmp_path/'titles.json'
    p.write_text(json.dumps({'titles':[{'text':'مرحبا','start':.2,'end':6}]}))
    with pytest.raises(ValueError,match='timing'):
        load_titles(p,5)
    p.write_text(json.dumps({'titles':[{'text':'x\nq','start':.2,'end':2}]}))
    with pytest.raises(ValueError,match='invalid text'):
        load_titles(p,5)


def test_immutable_titles_for_telegram_long_job(tmp_path,monkeypatch):
    monkeypatch.setattr(config,'OUTPUT_DIR',tmp_path)
    uid=55512;home=tmp_path/'users'/str(uid);home.mkdir(parents=True)
    (home/'v.mp4').write_bytes(b'video')
    (home/'shotlist.json').write_text(json.dumps({'shots':[{'clip':0,'start':0,'duration':5,'speed':1}]}))
    original=home/'titles.json';original.write_text(json.dumps({'titles':[{'text':'عنوان','start':1,'end':2}]}))
    req=long_jobs.create(uid,{'clips':[str(home/'v.mp4')],'shotlist':str(home/'shotlist.json'),
                              'titles':str(original),'seconds':5})
    original.write_text('{"titles":[]}')
    assert len(load_titles(Path(long_jobs.load(uid)['titles']),5))==1
    Path(req['titles']).write_text('{"titles":[]}')
    with pytest.raises(ValueError,match='integrity'):
        long_jobs.load(uid)
