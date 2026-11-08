import pytest
from app.planner import parse_request

def test_vertical():
    r = parse_request('/make ocean waves | 30 | vertical')
    assert (r.search, r.duration, r.vertical) == ('ocean waves',30,True)

def test_arabic():
    r = parse_request('/make بحر | 20 | عمودي')
    assert r.vertical and r.duration == 20

def test_invalid():
    with pytest.raises(ValueError):
        parse_request('/make sea | 9999')
