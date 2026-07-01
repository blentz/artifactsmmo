"""Tests for GamePlayer._fetch_raids."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

from artifactsmmo_cli.ai.player import GamePlayer


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
