"""Tests for event-availability gate in NpcBuyAction.is_applicable."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from artifactsmmo_cli.ai.actions.npc import NpcBuyAction
from artifactsmmo_cli.ai.game_data import GameData
from tests.test_ai.fixtures import make_state

FIXED_NOW = datetime(2026, 5, 20, 21, 0, tzinfo=timezone.utc)


def _event_gd() -> GameData:
    """GameData wired up with an event NPC: gemstone_merchant."""
    gd = GameData()
    gd._npc_event_code["gemstone_merchant"] = "gemstone_merchant"
    gd._event_npc_spawns["gemstone_merchant"] = (6, -1)
    gd._npc_stock["gemstone_merchant"] = {"copper_ore": 10}
    return gd


def _non_event_gd() -> GameData:
    """GameData with a regular (non-event) NPC: cook."""
    gd = GameData()
    gd._npc_stock["cook"] = {"cooked_chicken": 5}
    return gd


def _event_action() -> NpcBuyAction:
    return NpcBuyAction(
        npc_code="gemstone_merchant",
        item_code="copper_ore",
        quantity=1,
        npc_location=(6, -1),
    )


def _non_event_action() -> NpcBuyAction:
    return NpcBuyAction(
        npc_code="cook",
        item_code="cooked_chicken",
        quantity=1,
        npc_location=(2, 1),
    )


class TestNpcBuyEventGate:
    def test_applicable_when_event_active_and_reachable(self):
        gd = _event_gd()
        state = make_state(
            x=6,
            y=-1,
            gold=1000,
            active_events={"gemstone_merchant": FIXED_NOW + timedelta(minutes=30)},
        )
        with patch("artifactsmmo_cli.ai.actions.npc.datetime") as dt:
            dt.now.return_value = FIXED_NOW
            assert _event_action().is_applicable(state, gd) is True

    def test_not_applicable_when_event_inactive(self):
        gd = _event_gd()
        state = make_state(x=6, y=-1, gold=1000, active_events={})
        with patch("artifactsmmo_cli.ai.actions.npc.datetime") as dt:
            dt.now.return_value = FIXED_NOW
            assert _event_action().is_applicable(state, gd) is False

    def test_not_applicable_when_event_expired(self):
        gd = _event_gd()
        state = make_state(
            x=6,
            y=-1,
            gold=1000,
            active_events={"gemstone_merchant": FIXED_NOW - timedelta(seconds=1)},
        )
        with patch("artifactsmmo_cli.ai.actions.npc.datetime") as dt:
            dt.now.return_value = FIXED_NOW
            assert _event_action().is_applicable(state, gd) is False

    def test_not_applicable_when_event_active_but_too_far_to_reach(self):
        gd = _event_gd()
        # Character is 1000 tiles away; event expires in 1 second — unreachable.
        state = make_state(
            x=1006,
            y=-1,
            gold=1000,
            active_events={"gemstone_merchant": FIXED_NOW + timedelta(seconds=1)},
        )
        with patch("artifactsmmo_cli.ai.actions.npc.datetime") as dt:
            dt.now.return_value = FIXED_NOW
            assert _event_action().is_applicable(state, gd) is False

    def test_not_applicable_when_insufficient_gold(self):
        """Gold check still applies even when event is active."""
        gd = _event_gd()
        state = make_state(
            x=6,
            y=-1,
            gold=0,
            active_events={"gemstone_merchant": FIXED_NOW + timedelta(minutes=30)},
        )
        with patch("artifactsmmo_cli.ai.actions.npc.datetime") as dt:
            dt.now.return_value = FIXED_NOW
            assert _event_action().is_applicable(state, gd) is False

    def test_non_event_npc_applicable_without_active_events(self):
        """Non-event NPCs must not be gated on active_events (regression guard)."""
        gd = _non_event_gd()
        state = make_state(gold=100, active_events={})
        with patch("artifactsmmo_cli.ai.actions.npc.datetime") as dt:
            dt.now.return_value = FIXED_NOW
            assert _non_event_action().is_applicable(state, gd) is True

    def test_non_event_npc_not_applicable_without_gold(self):
        """Non-event NPC buy still requires sufficient gold (regression guard)."""
        gd = _non_event_gd()
        state = make_state(gold=0, active_events={})
        with patch("artifactsmmo_cli.ai.actions.npc.datetime") as dt:
            dt.now.return_value = FIXED_NOW
            assert _non_event_action().is_applicable(state, gd) is False
