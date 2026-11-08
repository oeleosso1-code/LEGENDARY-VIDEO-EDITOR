import asyncio
import json
import subprocess
from pathlib import Path
import pytest
from app.quality_check import delivery_check
from app.timeline_render import render_timeline


def make_video(video,col='red',seconds=2):
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',
        f'color=c={col}:s=160x90:r=25','-t',str(seconds),'-c:v','libx264',str(video)],check=True)


def test_delivery_check_reports_technical_issues(tmp_path):
    clip=tmp_path/'clip.mp4';make_video(clip)
    report=asyncio.run(delivery_check(clip,expected_seconds=3,require_audio=True,width=160,height=90,sample_seconds=0))
    assert not report['ok']
    assert any('duration' in item for item in report['issues'])
    assert not report['has_audio']


def test_black_sequence_generates_warning_not_failure(tmp_path):
    clip=tmp_path/'dark.mp4';make_video(clip,'black')
    report=asyncio.run(delivery_check(clip,expected_seconds=2,width=160,height=90,sample_seconds=2))
    assert report['ok'] and report['black_intervals']
    assert report['warnings']


def test_approved_timeline_writes_quality_report(tmp_path):
    video=tmp_path/'v.mp4';make_video(video)
    plan=tmp_path/'shots.json';plan.write_text(json.dumps({'shots':[{'clip':0,'duration':1,'start':0,'speed':1}]}))
    output=tmp_path/'out.mp4'
    result=asyncio.run(render_timeline([video],plan,output))
    assert result['quality_ok']
    data=json.loads((tmp_path/'out_quality_report.json').read_text())
    assert data['ok'] and data['dimensions']==[360,640]
