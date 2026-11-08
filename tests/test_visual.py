import pytest
from app.visual import SAMPLE_W,SAMPLE_H,image_metrics,quality_score,balanced_clip_order

def test_gray_metrics():
    f=bytes([120])*(SAMPLE_W*SAMPLE_H)
    m=image_metrics(f)
    assert m['brightness']==120
    assert m['contrast']==0
    assert m['motion']==0

def test_motion_detected():
    f=bytes([0])*(SAMPLE_W*SAMPLE_H)
    m=image_metrics(bytes([255])*len(f),f)
    assert m['motion']==255

def test_invalid_frame():
    with pytest.raises(ValueError):image_metrics(bytes(8))

def test_quality_prefers_visible_sharp():
    good={'brightness':118,'contrast':55,'detail':26,'motion':12}
    poor={'brightness':3,'contrast':1,'detail':0,'motion':0}
    assert quality_score(good)>quality_score(poor)

def test_balanced_order_uses_every_source():
    out=balanced_clip_order([.1,.9,.4],9)
    assert set(out)=={0,1,2}
    assert len(out)==9
    assert out[0]==1
