import asyncio
import json
import shutil
import subprocess
from pathlib import Path
import pytest
from app.timeline_render import partition_shots,render_timeline


def test_groups_preserve_order_and_avoid_split():
    shots=[{'duration':3},{'duration':4},{'duration':7},{'duration':2}]
    grouped=partition_shots(shots,8)
    assert [[s['duration'] for s in group] for group in grouped]==[[3,4],[7],[2]]
    assert sum(len(g) for g in grouped)==4


def test_invalid_chunk_size():
    with pytest.raises(ValueError): partition_shots([],float('nan'))


def make_sample(path:Path, duration=4, color='red'):
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',f'color=c={color}:s=160x90:r=25',
                    '-t',str(duration),'-c:v','libx264','-pix_fmt','yuv420p',str(path)],check=True)


@pytest.mark.skipif(not shutil.which('ffmpeg'), reason='FFmpeg required')
def test_timeline_video_and_cache(tmp_path):
    src1,src2=tmp_path/'one.mp4',tmp_path/'two.mp4'
    make_sample(src1,color='red');make_sample(src2,color='blue')
    song=tmp_path/'music.wav'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=320:sample_rate=44100','-t','5',str(song)],check=True)
    shotlist=tmp_path/'shots.json'
    shotlist.write_text(json.dumps({'shots':[
        {'clip':0,'start':.2,'duration':2.,'speed':1},
        {'clip':1,'start':.1,'duration':2.,'speed':1},
        {'clip':0,'start':.5,'duration':1.,'speed':1}]}))
    output=tmp_path/'final.mp4'
    options=dict(music=song,chunk_seconds=2.5,preset='ultrafast')
    r1=asyncio.run(render_timeline([src1,src2],shotlist,output,**options))
    assert r1['chunks']==3 and r1['reused_chunks']==0
    assert abs(r1['seconds']-5)<.05
    streams=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(output)]))['streams']
    assert {'video','audio'} <= {s['codec_type'] for s in streams}
    r2=asyncio.run(render_timeline([src1,src2],shotlist,output,**options))
    assert r2['reused_chunks']==3
    # Changing one source invalidates any chunk referencing it.
    make_sample(src2,color='green')
    r3=asyncio.run(render_timeline([src1,src2],shotlist,output,**options))
    assert r3['reused_chunks']==2


@pytest.mark.skipif(not shutil.which('ffmpeg'), reason='FFmpeg required')
def test_invalid_source_range(tmp_path):
    src=tmp_path/'a.mp4';make_sample(src,duration=2)
    plan=tmp_path/'shots.json';plan.write_text(json.dumps({'shots':[{'clip':0,'start':1.5,'duration':2}]}))
    with pytest.raises(ValueError):
        asyncio.run(render_timeline([src],plan,tmp_path/'out.mp4'))
