"""Tests for WorldState."""

import pytest

from artifactsmmo_cli.ai.world_state import WorldState
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
