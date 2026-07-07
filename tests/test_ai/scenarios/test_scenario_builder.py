"""ScenarioCharacter -> WorldState + the named golden registry."""

import json
from pathlib import Path

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.scenario import (
    SCENARIOS,
    ScenarioCharacter,
    load_bundle_game_data,
    scenario_state,
)
from artifactsmmo_cli.ai.world_state import EQUIPMENT_SLOTS

BUNDLE = Path(__file__).parent / "fixtures" / "gamedata_bundle.json"


def test_scenario_state_builds_world_state() -> None:
    sc = ScenarioCharacter(name="t", level=5, gold=10,
                           equipment={"weapon_slot": "copper_dagger"},
                           inventory={"feather": 2},
                           task=("chickens", "monsters", 3, 10))
    w = scenario_state(sc)
    assert w.level == 5 and w.gold == 10
    assert w.hp == w.max_hp  # hp None -> full
    assert w.equipment["weapon_slot"] == "copper_dagger"
    assert all(slot in w.equipment for slot in EQUIPMENT_SLOTS)
    assert w.inventory == {"feather": 2}
    assert (w.task_code, w.task_type, w.task_progress, w.task_total) == (
        "chickens", "monsters", 3, 10)


def test_registry_names_are_the_golden_set() -> None:
    assert set(SCENARIOS) >= {
        "l1_fresh", "l8_overstocked", "l10_copper_adequate",
        "l10_weapon_upgrade", "l3_low_hp", "l12_taskgated_bag"}


def test_registry_item_codes_exist_in_live_catalog() -> None:
    """Every item code any scenario references must exist in the bundle —
    scenarios must never drift from the real game."""
    gd = GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))
    for sc in SCENARIOS.values():
        codes = (set(sc.inventory) | set(sc.bank or {})
                 | set(sc.equipment.values()))
        for code in codes:
            assert gd.item_stats(code) is not None, (sc.name, code)


def test_load_bundle_game_data_wraps_from_cache_bundle() -> None:
    gd = load_bundle_game_data(BUNDLE)
    assert gd.item_stats("copper_dagger") is not None
