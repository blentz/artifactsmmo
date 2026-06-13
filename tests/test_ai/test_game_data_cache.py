import json
from datetime import datetime, timedelta, timezone

from artifactsmmo_cli.ai.game_data_cache import CACHE_VERSION, GameDataCache

_T0 = datetime(2026, 6, 13, 8, 0, 0, tzinfo=timezone.utc)
_PAGES = {"maps": [{"x": 1, "y": 2}], "items": [{"code": "ash"}], "bank": {"slots": 30}}


def _cache(tmp_path):
    return GameDataCache(api_base_url="https://api.artifactsmmo.com", cache_dir=tmp_path)


def test_write_then_read_roundtrip(tmp_path):
    c = _cache(tmp_path)
    c.write(_PAGES, now=_T0)
    got = c.read(ttl_minutes=30, now=_T0 + timedelta(minutes=29))
    assert got == _PAGES


def test_read_expired_returns_none(tmp_path):
    c = _cache(tmp_path)
    c.write(_PAGES, now=_T0)
    assert c.read(ttl_minutes=30, now=_T0 + timedelta(minutes=31)) is None


def test_read_at_ttl_boundary_is_expired(tmp_path):
    c = _cache(tmp_path)
    c.write(_PAGES, now=_T0)
    # exactly ttl elapsed -> NOT fresh (strict <)
    assert c.read(ttl_minutes=30, now=_T0 + timedelta(minutes=30)) is None


def test_read_missing_file_returns_none(tmp_path):
    assert _cache(tmp_path).read(ttl_minutes=30, now=_T0) is None


def test_read_version_mismatch_returns_none(tmp_path):
    c = _cache(tmp_path)
    c.write(_PAGES, now=_T0)
    raw = json.loads(c.path.read_text())
    raw["version"] = CACHE_VERSION + 1
    c.path.write_text(json.dumps(raw))
    assert c.read(ttl_minutes=30, now=_T0 + timedelta(minutes=1)) is None


def test_read_corrupt_json_returns_none(tmp_path):
    c = _cache(tmp_path)
    c.path.parent.mkdir(parents=True, exist_ok=True)
    c.path.write_text("{not json")
    assert c.read(ttl_minutes=30, now=_T0) is None


def test_write_is_atomic_no_tmp_left(tmp_path):
    c = _cache(tmp_path)
    c.write(_PAGES, now=_T0)
    assert c.path.exists()
    assert not c.path.with_suffix(c.path.suffix + ".tmp").exists()


def test_path_keyed_by_host(tmp_path):
    a = GameDataCache("https://api.artifactsmmo.com", cache_dir=tmp_path).path
    b = GameDataCache("https://sandbox.artifactsmmo.com", cache_dir=tmp_path).path
    assert a != b
