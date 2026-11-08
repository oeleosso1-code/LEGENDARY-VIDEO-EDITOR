import asyncio
import json
import math
import shutil
import struct
import subprocess
from pathlib import Path
import pytest
from app.music_director import analyze_pcm, analyze_music
from app.reference_style import analyze_rgb_frames, inspect_reference,FRAME_BYTES
from app.auto_timeline import build_timeline,write_edit_plan,plan_uploaded_sources
from app.shotlist import parse_shotlist
from app.timeline_render import render_timeline


def test_pcm_onset_detects_transient_and_handles_silence():
    silence=struct.pack('<h',0)*8000
    assert analyze_pcm(silence)['onsets']==[]
    raw=[0]* (8000*4)
    for second in [0.4,1.0,1.6,2.2,2.8,3.4]:
        a=round(second*8000)
        for i in range(a,a+500):raw[i]=12000
    pcm=struct.pack('<'+'h'*len(raw),*raw)
    profile=analyze_pcm(pcm)
    assert len(profile['onsets'])>=4
    assert any(abs(v['time']-.4)<.12 for v in profile['onsets'])


def test_reference_frame_sampling_and_cuts():
    solid_red=bytes([220,25,20])*(64*64)
    solid_blue=bytes([12,40,230])*(64*64)
    profile=analyze_rgb_frames(solid_red*2+solid_blue*2,fps=2)
    assert profile['coarse_cut_times']==[1.0]
    assert 85 < profile['brightness'] < 100
    assert profile['suggested_grade'] in ('vivid','natural','warm','cool')


def test_timeline_beats_and_fallback():
    result=build_timeline([4,6],8,style='fast',onsets=[1.61,3.25,4.8,6.4])
    shots=result['shots'];assert abs(sum(s['duration'] for s in shots)-8)<.0001
    assert len(shots)>3
    assert shots[0]['duration'] in (1.6, 1.64)
    assert len({s['clip'] for s in shots})==2
    compact=build_timeline([.8],3,style='smooth')
    assert abs(sum(s['duration'] for s in compact['shots'])-3)<.001


def test_invalid_reference_pace():
    with pytest.raises(ValueError):build_timeline([3],3,reference_pace=float('nan'))

@pytest.mark.skipif(not shutil.which('ffmpeg'),reason='FFmpeg required')
def test_music_reference_and_auto_plan_end_to_end(tmp_path):
    ref=tmp_path/'reference.mp4';a=tmp_path/'a.mp4';b=tmp_path/'b.mp4'
    for path,col in [(ref,'blue'),(a,'red'),(b,'green')]:
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',f'color=c={col}:s=160x90:r=25',
                        '-t','4','-c:v','libx264','-pix_fmt','yuv420p',str(path)],check=True)
    audio=tmp_path/'song.wav'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=440:sample_rate=8000',
                    '-t','7',str(audio)],check=True)
    async def run():
        profile=await inspect_reference(ref)
        music=await analyze_music(audio,music_start=1,duration=5)
        plan=await plan_uploaded_sources([a,b],5,style='fast',song=audio,music_start=1,reference_profile=profile)
        path=write_edit_plan(tmp_path/'plan.json',plan,[4,4],5)
        output=tmp_path/'result.mp4'
        render=await render_timeline([a,b],path,output,music=audio,music_start=1,chunk_seconds=2)
        return profile,music,plan,render
    reference,music,plan,result=asyncio.run(run())
    assert reference['is_reference_only'] and reference['source_duration']>=3.9
    assert music['music_start']==1 and music['duration_analyzed']>=4.9
    assert plan['music_analysis']['music_start']==1
    assert result['music'] and abs(result['seconds']-5)<.01
    assert all('reference' not in str(x) for x in plan['shots'])
