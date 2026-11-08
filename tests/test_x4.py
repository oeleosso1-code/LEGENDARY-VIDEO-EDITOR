import asyncio
from pathlib import Path
import pytest
from app.editor_pro import COLOR_PRESETS, render_pro, subtitle_filter
from app.store import blank


def test_color_presets_are_declared():
    assert {'natural','cinematic','vivid','noir','warm','cool'} == set(COLOR_PRESETS)
    assert COLOR_PRESETS['natural'] == ''


def test_subtitle_filter_escaping(tmp_path):
    name = tmp_path / 'a,b.srt'
    assert '\\,' in subtitle_filter(name)
    assert 'subtitles=filename=' in subtitle_filter(name)


def test_user_defaults_include_new_options():
    data=blank()
    assert data['color']=='natural'
    assert data['subtitles'] is None


def test_invalid_color_rejected(tmp_path):
    with pytest.raises(ValueError,match='color'):
        asyncio.run(render_pro([tmp_path/'none.mp4'],None,tmp_path/'out.mp4',6,color='bad'))


def test_missing_subtitle_rejected(tmp_path):
    with pytest.raises(ValueError,match='Subtitles'):
        asyncio.run(render_pro([tmp_path/'none.mp4'],None,tmp_path/'out.mp4',6,subtitles=tmp_path/'missing.srt'))
