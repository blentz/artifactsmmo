"""Tests for WorldState."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from artifactsmmo_cli.ai.world_state import SKILL_NAMES, EQUIPMENT_SLOTS, WorldState
from tests.test_ai.fixtures import make_state


class TestWorldStateProperties:
    def test_inventory_used_sums_quantities(self):
        state = make_state(inventory={"copper_ore": 5, "iron_ore": 3})
        assert state.inventory_used == 8

    def test_inventory_used_empty(self):
        state = make_state(inventory={})
        assert state.inventory_used == 0

    def test_inventory_free(self):
        state = make_state(inventory={"copper_ore": 5}, inventory_max=10)
        assert state.inventory_free == 5

    def test_hp_percent_full(self):
        state = make_state(hp=150, max_hp=150)
        assert state.hp_percent == pytest.approx(1.0)

    def test_hp_percent_half(self):
        state = make_state(hp=75, max_hp=150)
        assert state.hp_percent == pytest.approx(0.5)

    def test_hp_percent_zero_max_hp(self):
        state = make_state(hp=0, max_hp=0)
        assert state.hp_percent == pytest.approx(1.0)

    def test_frozen(self):
        state = make_state()
        with pytest.raises((AttributeError, TypeError)):
            state.x = 99  # type: ignore[misc]


def test_active_events_defaults_empty():
    assert make_state().active_events == {}


def test_active_events_round_trips():
    exp = datetime(2026, 5, 20, 22, 30, tzinfo=timezone.utc)
    state = make_state(active_events={"gemstone_merchant": exp})
    assert state.active_events["gemstone_merchant"] == exp


def test_from_character_schema_captures_per_skill_xp():
    """G-A: WorldState.skill_xp populated from `<skill>_xp` on schema."""
    char = MagicMock()
    char.name = "hero"; char.level = 1; char.xp = 0; char.max_xp = 100
    char.hp = 100; char.max_hp = 100; char.gold = 0; char.x = 0; char.y = 0
    char.cooldown_expiration = None
    char.task = ""; char.task_type = ""; char.task_progress = 0; char.task_total = 0
    char.inventory = []; char.inventory_max_items = 100
    for slot in EQUIPMENT_SLOTS:
        setattr(char, slot, "")
    for s in SKILL_NAMES:
        setattr(char, f"{s}_level", 1)
        setattr(char, f"{s}_xp", 0)
    char.weaponcrafting_xp = 42
    char.fishing_xp = 7

    state = WorldState.from_character_schema(char)
    assert state.skill_xp["weaponcrafting"] == 42
    assert state.skill_xp["fishing"] == 7
    assert state.skill_xp["mining"] == 0
