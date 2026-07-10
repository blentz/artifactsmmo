"""ScenarioCharacter -> WorldState + the named golden registry."""

import json
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import (
    FAR_FUTURE,
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


def test_registry_event_codes_exist_in_live_catalog() -> None:
    """Every event code any scenario declares active must exist in the
    bundle's event registry — the same no-drift rule as item codes."""
    bundle_events = {e["code"] for e in json.loads(BUNDLE.read_text())["events"]}
    for sc in SCENARIOS.values():
        for code in sc.active_events:
            assert code in bundle_events, (sc.name, code)


def test_active_events_thread_into_world_state() -> None:
    sc = ScenarioCharacter(name="t", level=5,
                           active_events=("bandit_camp", "corrupted_ogre"))
    w = scenario_state(sc)
    assert w.active_events == {"bandit_camp": FAR_FUTURE,
                               "corrupted_ogre": FAR_FUTURE}
    assert FAR_FUTURE.tzinfo is not None  # tz-aware, matching the live fetch


def test_active_events_default_empty() -> None:
    assert scenario_state(ScenarioCharacter(name="t", level=5)).active_events == {}


def test_derive_combat_stats_requires_game_data() -> None:
    sc = ScenarioCharacter(name="t", level=5, derive_combat_stats=True,
                           equipment={"weapon_slot": "copper_dagger"})
    with pytest.raises(ValueError, match="derive_combat_stats"):
        scenario_state(sc)


def test_derive_combat_stats_unknown_item_raises() -> None:
    gd = load_bundle_game_data(BUNDLE)
    sc = ScenarioCharacter(name="t", level=5, derive_combat_stats=True,
                           equipment={"weapon_slot": "no_such_item_xyz"})
    with pytest.raises(ValueError, match="no_such_item_xyz"):
        scenario_state(sc, gd)


def test_derive_combat_stats_sums_equipped_catalog_stats() -> None:
    """Server totals = base 0 + gear sum: a two-item loadout's derived state
    must carry exactly the item-stat sums from the catalog."""
    gd = load_bundle_game_data(BUNDLE)
    sc = ScenarioCharacter(
        name="t", level=10, derive_combat_stats=True,
        equipment={"weapon_slot": "iron_dagger", "ring1_slot": "iron_ring"})
    w = scenario_state(sc, gd)
    dagger = gd.item_stats("iron_dagger")
    ring = gd.item_stats("iron_ring")
    assert dagger is not None and ring is not None
    for elem, total in w.attack.items():
        assert total == dagger.attack.get(elem, 0) + ring.attack.get(elem, 0)
    assert sum(w.attack.values()) > 0  # a real weapon: derived state can fight
    assert w.dmg == dagger.dmg + ring.dmg
    assert w.critical_strike == dagger.critical_strike + ring.critical_strike
    # zero-stat scenarios stay zero-stat (opt-in flag, default off)
    bare = scenario_state(ScenarioCharacter(
        name="t", level=10, equipment={"weapon_slot": "iron_dagger"}))
    assert bare.attack == {} and bare.dmg == 0


def test_slots_max_defaults_to_quantity_cap_not_stack_count() -> None:
    """Task 0+1 review fix: `inventory_slots_max` must default to
    `inventory_max` (the quantity cap), NOT `len(sc.inventory)` — the latter
    made every scenario read slots_used == slots_max (0 free) by
    construction, spuriously gating any consumer that reads
    inventory_slots_free. Defaulting to the quantity cap (always >=
    distinct-stack count) means slots never bind before quantity, preserving
    every existing scenario's exact pre-slot behavior."""
    sc = ScenarioCharacter(name="t", level=5,
                           inventory={"feather": 2, "copper_ore": 5},
                           inventory_max=100)
    w = scenario_state(sc)
    assert w.inventory_slots_max == 100
    assert w.inventory_slots_free >= w.inventory_free
    assert w.inventory_slots_free > 0


def test_slots_max_explicit_override_is_honored() -> None:
    """A scenario that wants to test slot limits sets inventory_slots_max
    explicitly, overriding the quantity-cap default."""
    sc = ScenarioCharacter(name="t", level=5,
                           inventory={"feather": 2, "copper_ore": 5},
                           inventory_max=100, inventory_slots_max=2)
    w = scenario_state(sc)
    assert w.inventory_slots_max == 2
    assert w.inventory_slots_free == 0  # 2 distinct stacks == 2 slots


def test_seed_offline_seeds_active_event_codes_from_state() -> None:
    """seed_offline must mirror the live per-cycle overlay: the offline
    game_data's active_event_codes come from the state's active_events, so
    event spawns surface to the planner exactly as they do live."""
    gd = load_bundle_game_data(BUNDLE)
    sc = ScenarioCharacter(name="t", level=5, active_events=("corrupted_ogre",))
    player = GamePlayer(character="t", history=None)
    player.seed_offline(scenario_state(sc), gd)
    assert gd.active_event_codes == {"corrupted_ogre"}
    # and an event-less state clears any stale overlay
    player2 = GamePlayer(character="t", history=None)
    player2.seed_offline(scenario_state(ScenarioCharacter(name="t", level=5)), gd)
    assert gd.active_event_codes == set()
