import asyncio
import json
import shutil
import subprocess
from pathlib import Path
import pytest
from app.shotlist import parse_shotlist
from app.motion_track import track_frames, crop_filter,FRAME,WIDTH,HEIGHT,estimate_motion
from app.timeline_render import render_timeline


def test_motion_detector_moves_right_on_synthetic_frames():
    frames=[]
    for x in (8,11,14,18,23,28,32):
        frame=bytearray(FRAME)
        for y in range(12,21):
            for dx in range(5):frame[y*WIDTH+x+dx]=255
        frames.append(bytes(frame))
    report=track_frames(b''.join(frames))
    assert report['frames']==7
    assert report['confidence']>0
    assert report['end_x']>report['start_x']
    assert 'crop=' in crop_filter(360,640,report,2.)


def test_shotlist_ramp_validation(tmp_path):
    path=tmp_path/'shotlist.json'
    good={'shots':[{'clip':0,'start':1,'duration':3,'ramp':[.5,1,1.5], 'follow_motion':True}]}
    path.write_text(json.dumps(good))
    shots=parse_shotlist(path,[8],3)
    assert shots[0]['follow_motion'] and shots[0]['ramp']==[.5,1,1.5]
    good['shots'][0]['ramp']=[.1,1,2]
    path.write_text(json.dumps(good))
    with pytest.raises(ValueError,match='ramp'):parse_shotlist(path,[8],3)
    good['shots'][0]['ramp']=[4,4,4]
    path.write_text(json.dumps(good))
    with pytest.raises(ValueError,match='source too short'):parse_shotlist(path,[8],3)


@pytest.mark.skipif(not shutil.which('ffmpeg'), reason='FFmpeg required')
def test_render_ramp_and_auto_motion_with_sound(tmp_path):
    src=tmp_path/'moving.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',
       'testsrc2=s=320x180:r=25','-t','5','-c:v','libx264','-pix_fmt','yuv420p',str(src)],check=True)
    song=tmp_path/'music.wav'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',
       'sine=frequency=350:sample_rate=16000','-t','4',str(song)],check=True)
    plan=tmp_path/'plan.json'
    plan.write_text(json.dumps({'shots':[{'clip':0,'start':0,'duration':3,'ramp':[.5,1,1.5],
                                         'follow_motion':True}]}))
    dest=tmp_path/'output.mp4'
    result=asyncio.run(render_timeline([src],plan,dest,music=song,chunk_seconds=4))
    assert result['seconds']==3 and result['music']
    assert dest.is_file() and dest.stat().st_size>1000
    second=asyncio.run(render_timeline([src],plan,dest,music=song,chunk_seconds=4))
    assert second['reused_chunks']==1
    frame=subprocess.check_output(['ffmpeg','-v','error','-ss','1.5','-i',str(dest),'-frames:v','1',
                                  '-f','rawvideo','-pix_fmt','gray','-'])
    assert len(frame)==360*640
