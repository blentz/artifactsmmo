"""Tests for GamePlayer._fetch_raids and _log_active_raids."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import httpx

from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.raid_info import RaidInfo


class _Status:
    def __init__(self, value): self.value = value


def _raid_schema(status, instance):
    r = MagicMock()
    r.code, r.name, r.monster = "slime_raid", "Slime Raid", "giant_slime"
    r.status = _Status(status)
    r.next_start_at = datetime(2026, 6, 30, 18, tzinfo=timezone.utc)
    r.active_instance = instance
    return r


def _instance():
    inst = MagicMock()
    inst.remaining_hp, inst.total_hp = 400, 1000
    inst.ends_at = datetime(2026, 6, 30, 13, tzinfo=timezone.utc)
    return inst


def test_fetch_raids_maps_active_and_upcoming(monkeypatch):
    page = MagicMock()
    page.data = [_raid_schema("active", _instance()),
                 _raid_schema("upcoming", None)]
    monkeypatch.setattr("artifactsmmo_cli.ai.player.get_all_raids",
                        lambda **kw: page if kw["page"] == 1 else MagicMock(data=[]))
    player = GamePlayer(character="hero")
    raids = player._fetch_raids(MagicMock())
    assert [r.status for r in raids] == ["active", "upcoming"]
    active = next(r for r in raids if r.status == "active")
    assert (active.remaining_hp, active.total_hp) == (400, 1000)
    upcoming = next(r for r in raids if r.status == "upcoming")
    assert upcoming.remaining_hp is None and upcoming.window_ends_at is None


def _ri(status):
    t = datetime(2026, 6, 30, 13, tzinfo=timezone.utc)
    return RaidInfo(code="r", name="R", monster="giant_slime", status=status,
                    next_start_at=t, remaining_hp=400 if status == "active" else None,
                    total_hp=1000 if status == "active" else None,
                    window_ends_at=t if status == "active" else None)


def test_log_active_raids_prints_only_active(capsys):
    player = GamePlayer(character="hero")
    player._log_active_raids([_ri("active"), _ri("upcoming")])
    out = capsys.readouterr().out
    assert "raid active: giant_slime 400/1000 hp" in out
    assert out.count("raid active:") == 1


def test_log_active_raids_silent_when_none(capsys):
    GamePlayer(character="hero")._log_active_raids([_ri("upcoming")])
    assert capsys.readouterr().out == ""


def test_fetch_raids_retries_on_http_error(monkeypatch):
    """Cover lines 887-892: except httpx.HTTPError retry branch in _fetch_raids."""
    call_count = 0
    empty_page = MagicMock()
    empty_page.data = []

    def mock_get_all_raids(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise httpx.ConnectError("boom")
        return empty_page

    monkeypatch.setattr("artifactsmmo_cli.ai.player.get_all_raids", mock_get_all_raids)
    monkeypatch.setattr("artifactsmmo_cli.ai.player.time.sleep", lambda _: None)

    raids = GamePlayer(character="hero")._fetch_raids(MagicMock())
    assert raids == []
    assert call_count == 2


def test_fetch_raids_multi_page(monkeypatch):
    """Cover line 915: page += 1 when first page is full (100 items)."""
    pages_requested = []

    def mock_get_all_raids(**kwargs):
        pages_requested.append(kwargs["page"])
        page = MagicMock()
        page.data = [_raid_schema("upcoming", None) for _ in range(100)] if kwargs["page"] == 1 else []
        return page

    monkeypatch.setattr("artifactsmmo_cli.ai.player.get_all_raids", mock_get_all_raids)

    raids = GamePlayer(character="hero")._fetch_raids(MagicMock())
    assert len(raids) == 100
    assert 2 in pages_requested
