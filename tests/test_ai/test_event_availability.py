"""event_npc_tradeable: event NPC must be active AND reachable before expiry."""
from datetime import datetime, timedelta, timezone

from artifactsmmo_cli.ai.event_availability import event_npc_tradeable
from artifactsmmo_cli.ai.game_data import GameData


def _gd_with_event(spawn=(6, -1)):
    gd = GameData()
    gd._npc_event_code["gemstone_merchant"] = "gemstone_merchant"
    gd._event_npc_spawns["gemstone_merchant"] = spawn
    return gd


def test_active_and_reachable_is_true():
    now = datetime(2026, 5, 20, 21, 0, tzinfo=timezone.utc)
    gd = _gd_with_event()
    active = {"gemstone_merchant": now + timedelta(minutes=30)}
    assert event_npc_tradeable("gemstone_merchant", gd, x=6, y=-1, active_events=active, now=now) is True


def test_inactive_is_false():
    now = datetime(2026, 5, 20, 21, 0, tzinfo=timezone.utc)
    gd = _gd_with_event()
    assert event_npc_tradeable("gemstone_merchant", gd, x=6, y=-1, active_events={}, now=now) is False


def test_active_but_expiring_before_arrival_is_false():
    now = datetime(2026, 5, 20, 21, 0, tzinfo=timezone.utc)
    gd = _gd_with_event(spawn=(100, 100))
    active = {"gemstone_merchant": now + timedelta(seconds=5)}
    assert event_npc_tradeable("gemstone_merchant", gd, x=0, y=0, active_events=active, now=now) is False


def test_non_event_npc_is_true_passthrough():
    now = datetime(2026, 5, 20, 21, 0, tzinfo=timezone.utc)
    gd = GameData()
    assert event_npc_tradeable("tailor", gd, x=0, y=0, active_events={}, now=now) is True


def test_event_npc_with_no_known_spawn_is_false():
    now = datetime(2026, 5, 20, 21, 0, tzinfo=timezone.utc)
    gd = GameData()
    gd._npc_event_code["ghost_merchant"] = "ghost_merchant"  # registered but no spawn tile
    active = {"ghost_merchant": now + timedelta(minutes=30)}
    assert event_npc_tradeable("ghost_merchant", gd, x=0, y=0, active_events=active, now=now) is False
