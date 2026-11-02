"""Wisdom reaches the loadout projection (unified-acquisition increment 3).

This file used to open with a characterisation of `ai/min_plan_length`, the
three-action cost model that priced any recipe-less item as one gather. That
model and its tests were retired with the `is_plannable` gate it served (Phase
3-2 of docs/PLAN_decision_architecture_redesign.md). The second wisdom test,
on the level-path projection, went with `cheapest_path_to_level` (Plan C Task 5).
"""

from dataclasses import replace
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.equipment.loadout_cache import pick_loadout_cached
from artifactsmmo_cli.ai.equipment.projection import project_loadout_stats
from artifactsmmo_cli.ai.gear_value_core import Rank
from artifactsmmo_cli.ai.learning.fight_seconds_model import committed_timing
from artifactsmmo_cli.ai.scenario import SCENARIOS, load_bundle_game_data, scenario_state

TIMING = committed_timing()[0]
"""The committed live capture's fight-seconds fit (spec 2026-10-18 §2.9)."""

_BUNDLE = (Path(__file__).resolve().parent / "scenarios" / "fixtures"
           / "gamedata_bundle.json")


@pytest.fixture(scope="module")
def game_data():  # type: ignore[no-untyped-def]
    return load_bundle_game_data(_BUNDLE)


def test_a_wisdom_ITEM_NOW_REACHES_THE_PROJECTION(game_data) -> None:
    """INCREMENT 3, and a CORRECTION to how it was first demonstrated.

    The original version of this test used `wisdom_amulet` and concluded that
    its wisdom 60 projected as zero because `ProjectedStats` had no `wisdom`
    field. The code claim was true — `cheapest_path_to_level` read
    `state.wisdom`, the total for gear already WORN — but the DEMONSTRATION was
    confounded: `wisdom_amulet` carries `conditions [('level', 14)]` and the
    scenario character is level 12, so `pick_loadout_cached` correctly refused to
    wear it. It would have projected zero whatever `ProjectedStats` contained.

    A measurement that cannot distinguish two explanations is not evidence for
    either. This version uses `adventurer_vest` — level 10, wisdom 20, actually
    wearable — so the only thing under test is whether the stat reaches the
    projection.

    Before increment 3 this was 0. It is now 20.

    RE-DERIVED 2026-10-18 (ruling R): the scenario's sheet now carries its
    worn gear's wisdom too (`copper_boots`, 10), so the projection reads the
    worn 10 plus the vest's 20 (it replaces copper_armor, which has none)."""
    state = scenario_state(SCENARIOS["l12_deep_chain_grind"], game_data)
    vest = game_data.item_stats("adventurer_vest")
    assert vest.wisdom == 20
    assert vest.level <= state.level, "fixture drift: the vest must be wearable"

    holding = replace(state, inventory={**state.inventory, "adventurer_vest": 1},
                      hp=state.max_hp)
    projected = project_loadout_stats(
        holding, pick_loadout_cached(Rank(), holding, game_data), game_data)
    assert state.wisdom == 10
    assert projected.wisdom == 30
