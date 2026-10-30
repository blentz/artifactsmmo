"""A planned equip, unequip or re-arm keeps the sheet's invariant (Task 14f,
ruling T14d-7b): totals = base + the worn NON-utility gear (measured live,
Task 14b). The transitions move the totals through `project_loadout_stats`
(`equipment.projection.wear_gear`); a utility slot moves none."""

import dataclasses

from artifactsmmo_cli.ai.actions.equip import EquipAction
from artifactsmmo_cli.ai.actions.optimize_loadout import OptimizeLoadoutAction
from artifactsmmo_cli.ai.actions.unequip import UnequipAction
from artifactsmmo_cli.ai.attempt_prospecting import loadout_prospecting
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.gear_value_core import Gather
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.fixtures import make_state

TOTALS = ("attack", "dmg", "dmg_elements", "resistance", "critical_strike", "initiative",
          "max_hp", "wisdom", "prospecting", "haste", "inventory_max")


def _totals(state: WorldState) -> dict[str, object]:
    return {name: getattr(state, name) for name in TOTALS}


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "plate": ItemStats(code="plate", level=1, type_="body_armor",
                           attack={"fire": 4}, resistance={"earth": 7}, dmg=3,
                           dmg_elements={"water": 5}, critical_strike=2, initiative=6,
                           hp_bonus=40, wisdom=8, prospecting=30, haste=9,
                           inventory_space=11),
        "vest": ItemStats(code="vest", level=1, type_="body_armor",
                          resistance={"earth": 2}, hp_bonus=10, prospecting=5),
        "elixir": ItemStats(code="elixir", level=1, type_="utility", hp_bonus=250),
        "copper_pickaxe": ItemStats(code="copper_pickaxe", level=1, type_="weapon",
                                    attack={"earth": 5}, skill_effects={"mining": -10},
                                    prospecting=20),
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                   attack={"air": 6}, critical_strike=35),
    }
    gd._resource_drops = {"copper_rocks": "copper_ore"}
    gd._resource_skill = {"copper_rocks": ("mining", 1)}
    gd._resource_locations = {"copper_rocks": [(2, 0)]}
    return gd


def _base(**overrides) -> WorldState:
    return make_state(attack={"fire": 10, "air": 6}, resistance={"earth": 1}, dmg=2,
                      dmg_elements={"fire": 1}, critical_strike=40, initiative=100,
                      max_hp=150, wisdom=3, prospecting=12, haste=1, inventory_max=100,
                      **overrides)


def test_an_equip_moves_the_totals_by_the_items_stats() -> None:
    state = _base(inventory={"plate": 1})
    worn = EquipAction(code="plate", slot="body_armor_slot").apply(state, _gd())
    assert _totals(worn) == {
        "attack": {"fire": 14, "air": 6}, "dmg": 5, "dmg_elements": {"fire": 1, "water": 5},
        "resistance": {"earth": 8}, "critical_strike": 42, "initiative": 106,
        "max_hp": 190, "wisdom": 11, "prospecting": 42, "haste": 10, "inventory_max": 111,
    }


def test_equip_then_unequip_round_trips_the_totals() -> None:
    state = _base(inventory={"plate": 1})
    gd = _gd()
    worn = EquipAction(code="plate", slot="body_armor_slot").apply(state, gd)
    back = UnequipAction(slot="body_armor_slot").apply(worn, gd)
    assert _totals(back) == _totals(state)
    assert back.equipment == state.equipment


def test_a_swap_and_its_reverse_round_trip_the_totals() -> None:
    """The vest worn, the plate equipped over it, then the vest again: each swap
    takes the displaced item's stats off."""
    state = _base(inventory={"plate": 1}, equipment={**make_state().equipment,
                                                     "body_armor_slot": "vest"})
    gd = _gd()
    plated = EquipAction(code="plate", slot="body_armor_slot").apply(state, gd)
    assert plated.prospecting == 12 - 5 + 30
    back = EquipAction(code="vest", slot="body_armor_slot").apply(plated, gd)
    assert _totals(back) == _totals(state)


def test_a_utility_equip_moves_no_total() -> None:
    """A worn potion is not in the sheet (Task 14b): its slot and stock change,
    the totals do not."""
    state = _base(inventory={"elixir": 3})
    worn = EquipAction(code="elixir", slot="utility1_slot", quantity=3).apply(state, _gd())
    assert _totals(worn) == _totals(state)
    assert worn.equipment["utility1_slot"] == "elixir"
    assert worn.utility1_slot_quantity == 3


def test_a_planned_rearm_carries_the_gather_loadouts_prospecting() -> None:
    """Task 14d census (b): the re-arm moved the equipment but not the totals,
    so the planned state kept the worn prospecting. After it, the state's
    prospecting is the gather loadout's, and its reverse round-trips."""
    state = _base(inventory={"copper_pickaxe": 1},
                  equipment={**make_state().equipment, "weapon_slot": "copper_dagger"},
                  skills={**make_state().skills, "mining": 12})
    gd = _gd()
    expected = loadout_prospecting(Gather("mining"), state, gd)
    rearmed = OptimizeLoadoutAction(target_skill="mining").apply(state, gd)
    assert rearmed.equipment["weapon_slot"] == "copper_pickaxe"
    assert rearmed.prospecting == expected == 12 + 20
    assert rearmed.attack == {"fire": 10, "earth": 5}
    assert rearmed.critical_strike == 5
    back = EquipAction(code="copper_dagger", slot="weapon_slot").apply(rearmed, gd)
    assert _totals(back) == _totals(state)


def test_a_planned_downgrade_clamps_hp_to_the_lowered_max() -> None:
    """The server clamps HP when max HP falls below it (learning.db: no sheet
    reads hp > max_hp). Taking off the +40 HP plate at 185/190 HP leaves
    150/150; at 120/190 it leaves 120/150."""
    gd = _gd()
    state = _base(inventory={"plate": 1})
    worn = EquipAction(code="plate", slot="body_armor_slot").apply(state, gd)
    full = dataclasses.replace(worn, hp=185)
    assert UnequipAction(slot="body_armor_slot").apply(full, gd).hp == 150
    hurt = dataclasses.replace(worn, hp=120)
    assert UnequipAction(slot="body_armor_slot").apply(hurt, gd).hp == 120
