from pathlib import Path
from app.audio import duration_segments
from app.store import blank,ALLOWED_STYLES
from app.director import safe_search_terms

def test_segments_sum():
    assert abs(sum(duration_segments(10,[1.5,3,8.5]))-10)<.001

def test_bad_boundaries():
    assert duration_segments(5,[-1,2,2,8]) == [2,3]

def test_default_session():
    d=blank()
    assert d['clips']==[] and d['seconds']==30

def test_style_whitelist():
    assert {'cinematic','fast','smooth','documentary'}==ALLOWED_STYLES

def test_fallback_query():
    assert safe_search_terms('ocean')==['ocean']
