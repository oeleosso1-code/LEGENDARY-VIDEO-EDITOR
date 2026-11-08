import asyncio
import json
from pathlib import Path
import pytest
from app.store import blank
from app.editor_pro import render_pro


def test_x5_defaults():
    assert blank()['music_volume']==0.85


def test_volume_validation(tmp_path):
    with pytest.raises(ValueError, match='Music volume'):
        asyncio.run(render_pro([tmp_path/'no.mp4'],None,tmp_path/'out.mp4',6,music_volume=2))


def test_preview_render(tmp_path):
    # Use a checked-in smoke fixture if available; otherwise do not rely on test media.
    import shutil, subprocess
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        pytest.skip('ffmpeg not installed')
    source=tmp_path/'source.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=size=320x180:rate=25','-t','3','-c:v','libx264','-preset','ultrafast',str(source)],check=True)
    out=tmp_path/'draft.mp4'
    info=asyncio.run(render_pro([source],None,out,5,orientation='horizontal',music_volume=0.6,preview=True))
    assert out.is_file() and out.stat().st_size>100
    assert info['preview'] is True
    assert info['music_volume']==0.6
    metadata=json.loads((tmp_path/'edit_decisions.json').read_text())
    assert metadata['seconds']==5
