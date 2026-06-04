"""Item 9c diff test: event_availability.event_npc_tradeable.

Production: gates event-NPC trades on active event + travel-time margin.
Closes diff-coverage gap for src/artifactsmmo_cli/ai/event_availability.py.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest

from artifactsmmo_cli.ai.event_availability import event_npc_tradeable
from artifactsmmo_cli.ai.game_data import GameData


def _gd_non_event(npc_code: str) -> GameData:
    gd = GameData()
    # No event code wired → npc_event_code returns None.
    gd._npc_event_code = {}
    return gd


def _gd_event(npc_code: str, event_code: str, spawn: tuple[int, int]) -> GameData:
    gd = GameData()
    gd._npc_event_code = {npc_code: event_code}
    gd._npc_locations = {npc_code: spawn}
    return gd


def test_non_event_npc_always_tradeable():
    gd = _gd_non_event("merchant_a")
    now = datetime(2026, 6, 4, 12, 0, 0, tzinfo=timezone.utc)
    assert event_npc_tradeable(
        "merchant_a", gd, x=0, y=0, active_events={}, now=now,
    ) is True


def test_event_npc_not_tradeable_when_event_inactive():
    gd = _gd_event("gold_merchant", "gold_event", (5, 0))
    now = datetime(2026, 6, 4, 12, 0, 0, tzinfo=timezone.utc)
    # active_events doesn't contain "gold_event" → not tradeable.
    assert event_npc_tradeable(
        "gold_merchant", gd, x=0, y=0, active_events={}, now=now,
    ) is False


def test_event_npc_tradeable_when_event_active_and_reachable():
    gd = _gd_event("gold_merchant", "gold_event", (5, 0))
    now = datetime(2026, 6, 4, 12, 0, 0, tzinfo=timezone.utc)
    expiration = now + timedelta(hours=1)
    assert event_npc_tradeable(
        "gold_merchant", gd, x=0, y=0,
        active_events={"gold_event": expiration}, now=now,
    ) is True


def test_event_npc_not_tradeable_when_event_expires_before_arrival():
    gd = _gd_event("gold_merchant", "gold_event", (100, 100))
    now = datetime(2026, 6, 4, 12, 0, 0, tzinfo=timezone.utc)
    # expiration in 1 second; far away → travel margin exceeds remaining.
    expiration = now + timedelta(seconds=1)
    assert event_npc_tradeable(
        "gold_merchant", gd, x=0, y=0,
        active_events={"gold_event": expiration}, now=now,
    ) is False


def test_naive_now_raises():
    gd = _gd_non_event("merchant_a")
    naive_now = datetime(2026, 6, 4, 12, 0, 0)  # no tzinfo
    with pytest.raises(ValueError, match="timezone-aware"):
        event_npc_tradeable(
            "merchant_a", gd, x=0, y=0, active_events={}, now=naive_now,
        )
