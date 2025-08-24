# tests/test_utils_parse_dt.py
from app.utils import _parse_dt

def test_parse_iso():
    assert _parse_dt("2025-08-24T10:15:30Z") is not None

def test_parse_epoch():
    assert _parse_dt(1724490930) is not None

def test_parse_invalid():
    assert _parse_dt("not a date") is None
