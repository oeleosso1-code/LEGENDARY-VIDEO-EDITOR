import asyncio
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from app.shotlist import parse_shotlist
from app.editor_pro import render_pro
from app.store import blank


def test_shotlist_valid(tmp_path):
    p = tmp_path / 'timeline.json'
    p.write_text(json.dumps({'shots': [
        {'clip': 1, 'start': 2, 'duration': 2, 'speed': 1.5},
        {'clip': 0, 'start': 0, 'duration': 3, 'speed': 0.5}
    ]}))
    shots = parse_shotlist(p, [6, 6], 5)
    assert [s['clip'] for s in shots] == [1, 0]
    assert shots[0]['speed'] == 1.5


@pytest.mark.parametrize('shots,duration', [
    ([{'clip': 2, 'duration': 5}], 5),
    ([{'clip': 0, 'duration': 5, 'speed': 0}], 5),
    ([{'clip': 0, 'duration': 10}], 10),
    ([{'clip': 0, 'duration': 2}], 5),
    ([{'clip': 0, 'duration': float('nan')}], 5),
])
def test_shotlist_rejects_bad_values(tmp_path, shots, duration):
    p = tmp_path/'bad.json'
    p.write_text(json.dumps({'shots': shots}))
    with pytest.raises(ValueError):
        parse_shotlist(p, [6], duration)


def test_default_music_start():
    assert blank()['music_start'] == 0.0


def test_real_manual_timeline_render(tmp_path):
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        pytest.skip('ffmpeg unavailable')
    clips=[]
    for n in (0, 1):
        p=tmp_path/f'clip{n}.mp4'
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',f'testsrc2=size=256x144:rate=25',
                        '-t','5','-c:v','libx264','-preset','ultrafast',str(p)],check=True)
        clips.append(p)
    # Fast shot and slow shot should play for 2.5 seconds each.
    plan=tmp_path/'shotlist.json'
    plan.write_text(json.dumps({'shots': [
        {'clip':0,'start':0.5,'duration':2.5,'speed':1.5},
        {'clip':1,'start':0.3,'duration':2.5,'speed':0.5}
    ]}))
    output=tmp_path/'final.mp4'
    result=asyncio.run(render_pro(clips,None,output,5,orientation='horizontal',shotlist=plan,preview=True))
    assert output.stat().st_size > 1000
    assert result['shotlist']=='shotlist.json'
    assert [s['speed'] for s in result['timeline']] == [1.5,0.5]
    duration=subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration',
                                      '-of','default=noprint_wrappers=1:nokey=1',str(output)])
    assert abs(float(duration)-5)<0.20
