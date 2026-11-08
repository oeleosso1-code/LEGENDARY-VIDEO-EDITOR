import asyncio
import json
import subprocess
from pathlib import Path
import pytest
from app.timeline_render import OUTPUT_SIZES,render_timeline
from app import config,long_jobs


def test_quality_sizes_and_mode_validation(tmp_path,monkeypatch):
    assert OUTPUT_SIZES['hd']['horizontal']==(1280,720)
    assert OUTPUT_SIZES['fullhd']['vertical']==(1080,1920)
    monkeypatch.setattr(config,'OUTPUT_DIR',tmp_path)
    home=tmp_path/'users'/'10';home.mkdir(parents=True)
    (home/'clip.mp4').write_bytes(b'placeholder')
    bad={'clips':[str(home/'clip.mp4')],'seconds':5,'quality':'hd'}
    with pytest.raises(ValueError,match='fixed shotlist'):long_jobs.create(10,bad)


def test_hd_render_real_mp4(tmp_path):
    video=tmp_path/'src.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=blue:s=160x90:r=25',
                    '-t','1.5','-c:v','libx264',str(video)],check=True)
    plan=tmp_path/'plan.json'
    plan.write_text(json.dumps({'shots':[{'clip':0,'start':0,'duration':1,'speed':1}]}))
    dest=tmp_path/'hd.mp4'
    result=asyncio.run(render_timeline([video],plan,dest,orientation='horizontal',quality='hd',preset='ultrafast'))
    assert result['quality']=='hd' and result['width']==1280 and result['height']==720
    raw=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0',
                    '-show_entries','stream=width,height','-of','json',str(dest)]))
    assert raw['streams'][0]['width']==1280
    assert raw['streams'][0]['height']==720

def test_hd_snapshot_can_resume(tmp_path,monkeypatch):
    monkeypatch.setattr(config,'OUTPUT_DIR',tmp_path)
    home=tmp_path/'users'/'11';home.mkdir(parents=True)
    (home/'clip.mp4').write_bytes(b'placeholder')
    shots=home/'shots.json'
    shots.write_text(json.dumps({'shots':[{'clip':0,'start':0,'duration':5,'speed':1}]}))
    request={'clips':[str(home/'clip.mp4')],'seconds':5,'shotlist':str(shots),'quality':'hd'}
    long_jobs.create(11,request)
    assert long_jobs.load(11)['quality']=='hd'
