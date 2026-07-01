"""Tests for Task 6 (spec 2026-06-30-potion-supply): CraftPotionsGoal.

Covers target-potion selection, the state-only baseline `is_satisfied`, the
`value` deficit, and the three-tier action ladder (craft-from-held > buy-mix >
gather-5) that tops the equipped utility-slot potion stack toward a level-scaled
baseline.
"""

import dataclasses

from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.equip import EquipAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.actions.npc import NpcBuyAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.craft_potions import CraftPotionsGoal
from tests.test_ai.fixtures import make_state

_POTION = "small_health_potion"
_INGREDIENT = "sunflower"
_INGREDIENT2 = "herb"
_RESOURCE = "sunflower_field"


def _gd_potion(*, hp_restore: int = 30, craft_level: int = 1) -> GameData:
    """GameData where `small_health_potion` is the one alchemy-craftable,
    utility-slot-equippable heal (its ingredient `sunflower` drops from
    `sunflower_field`)."""
    gd = GameData()
    gd._item_stats = {
        _POTION: ItemStats(code=_POTION, level=1, type_="utility", hp_restore=hp_restore,
                           crafting_skill="alchemy", crafting_level=craft_level),
        _INGREDIENT: ItemStats(code=_INGREDIENT, level=1, type_="resource"),
    }
    gd._crafting_recipes = {_POTION: {_INGREDIENT: 1}}
    gd._resource_drops = {_RESOURCE: _INGREDIENT}
    gd._resource_locations = {_RESOURCE: [(2, 0)]}
    gd._workshop_locations = {"alchemy": (3, 0)}
    return gd


def _gd_no_alchemy_heal() -> GameData:
    """GameData with NO alchemy utility heal — only a cooking food (the wrong
    type/skill for a utility slot), so `_target_potion` is None."""
    gd = GameData()
    gd._item_stats = {
        "cooked_fish": ItemStats(code="cooked_fish", level=1, type_="consumable",
                                 hp_restore=50, crafting_skill="cooking", crafting_level=1),
    }
    gd._crafting_recipes = {"cooked_fish": {"raw_fish": 1}}
    return gd


def _craft_action() -> CraftAction:
    return CraftAction(code=_POTION, quantity=1, workshop_location=(3, 0))


# ── target-potion selection ──────────────────────────────────────────────────

def test_target_potion_picks_alchemy_utility_heal():
    gd = _gd_potion()
    assert CraftPotionsGoal()._target_potion(make_state(), gd) == _POTION


def test_target_potion_none_without_craftable_utility_heal():
    gd = _gd_no_alchemy_heal()
    assert CraftPotionsGoal()._target_potion(make_state(), gd) is None


def test_target_potion_none_when_skill_gate_unmet():
    gd = _gd_potion(craft_level=10)
    state = make_state(skills={"alchemy": 1})
    assert CraftPotionsGoal()._target_potion(state, gd) is None


def test_target_potion_skips_non_alchemy_utility_heal():
    gd = _gd_potion()
    # A utility-slot heal crafted by a DIFFERENT skill is not alchemy-craftable.
    gd._item_stats["cook_potion"] = ItemStats(code="cook_potion", level=1, type_="utility",
                                              hp_restore=99, crafting_skill="cooking", crafting_level=1)
    gd._crafting_recipes["cook_potion"] = {_INGREDIENT: 1}
    assert CraftPotionsGoal()._target_potion(make_state(), gd) == _POTION


def test_target_potion_highest_restore_then_smallest_code():
    gd = _gd_potion()
    gd._item_stats["aaa_potion"] = ItemStats(code="aaa_potion", level=1, type_="utility",
                                             hp_restore=30, crafting_skill="alchemy", crafting_level=1)
    gd._item_stats["big_potion"] = ItemStats(code="big_potion", level=1, type_="utility",
                                             hp_restore=80, crafting_skill="alchemy", crafting_level=1)
    gd._crafting_recipes["aaa_potion"] = {_INGREDIENT: 1}
    gd._crafting_recipes["big_potion"] = {_INGREDIENT: 1}
    # big_potion (80) beats the two 30s; among equal restore the lexically first wins.
    assert CraftPotionsGoal()._target_potion(make_state(), gd) == "big_potion"


# ── is_satisfied (state-only baseline check) ─────────────────────────────────

def test_satisfied_when_slot_meets_baseline():
    # State-only: a utility slot stocked to this level's baseline (5 at level 1).
    state = make_state(level=1, equipment={"utility1_slot": _POTION})
    state = dataclasses.replace(state, utility1_slot_quantity=5)
    assert CraftPotionsGoal().is_satisfied(state) is True


def test_unsatisfied_when_understocked():
    assert CraftPotionsGoal().is_satisfied(make_state(level=1)) is False


# ── value ────────────────────────────────────────────────────────────────────

def test_value_is_baseline_deficit_when_understocked():
    gd = _gd_potion()
    state = make_state(level=1)  # baseline(1)=5, equipped 0 -> deficit 5
    assert CraftPotionsGoal().value(state, gd) == 5.0


def test_value_zero_when_satisfied():
    gd = _gd_potion()
    state = make_state(level=1, equipment={"utility1_slot": _POTION})
    state = dataclasses.replace(state, utility1_slot_quantity=5)
    assert CraftPotionsGoal().value(state, gd) == 0.0


# ── relevant_actions ladder ──────────────────────────────────────────────────

def test_relevant_actions_empty_when_no_target():
    gd = _gd_no_alchemy_heal()
    out = CraftPotionsGoal().relevant_actions([MoveAction(x=0, y=0)], make_state(), gd)
    assert out == []


def test_craft_from_held_emits_craft_and_equip():
    gd = _gd_potion()
    # held ingredient allows a batch -> craft-from-held tier.
    state = make_state(level=1, inventory={_INGREDIENT: 10})
    actions = [_craft_action(),
               GatherAction(resource_code=_RESOURCE, locations=frozenset({(2, 0)})),
               MoveAction(x=0, y=0)]
    out = CraftPotionsGoal().relevant_actions(actions, state, gd)
    assert any(isinstance(a, CraftAction) for a in out)
    assert any(isinstance(a, EquipAction) and a.slot == "utility1_slot" for a in out)


def test_buy_tier_emits_npcbuy():
    gd = _gd_potion()
    gd._npc_stock = {"alchemist": {_INGREDIENT: 2}}
    gd._npc_locations = {"alchemist": (5, 0)}
    state = make_state(level=1, inventory={}, gold=1000)
    actions = [_craft_action(),
               NpcBuyAction(npc_code="alchemist", item_code=_INGREDIENT, quantity=1,
                            npc_location=(5, 0)),
               MoveAction(x=0, y=0)]
    out = CraftPotionsGoal().relevant_actions(actions, state, gd)
    assert any(isinstance(a, NpcBuyAction) for a in out)
    assert any(isinstance(a, EquipAction) and a.slot == "utility1_slot" for a in out)


def test_gather_path_bounds_to_five_potion_batch():
    gd = _gd_potion()
    # no held ingredient, no NPC sells it -> gather a POTION_GATHER_BATCH batch.
    state = make_state(level=3, inventory={})
    actions = [_craft_action(),
               GatherAction(resource_code=_RESOURCE, locations=frozenset({(2, 0)})),
               WithdrawItemAction(code=_INGREDIENT, quantity=1, bank_location=(4, 0)),
               MoveAction(x=0, y=0)]
    out = CraftPotionsGoal().relevant_actions(actions, state, gd)
    craft = next(a for a in out if isinstance(a, CraftAction))
    assert craft.quantity == 5  # POTION_GATHER_BATCH
    assert any(isinstance(a, GatherAction) for a in out)


def test_relevant_actions_includes_craftable_intermediate():
    gd = _gd_potion()
    # The potion now goes through a craftable intermediate (potion_base).
    gd._crafting_recipes = {_POTION: {"potion_base": 1}, "potion_base": {_INGREDIENT: 1}}
    gd._item_stats["potion_base"] = ItemStats(code="potion_base", level=1, type_="resource",
                                             crafting_skill="alchemy", crafting_level=1)
    state = make_state(level=1, inventory={_INGREDIENT: 10})
    actions = [_craft_action(),
               CraftAction(code="potion_base", quantity=1, workshop_location=(3, 0))]
    out = CraftPotionsGoal().relevant_actions(actions, state, gd)
    assert any(isinstance(a, CraftAction) and a.code == "potion_base" for a in out)


def test_gather_path_filters_closure_and_keeps_moves():
    gd = _gd_potion()
    state = make_state(level=3, inventory={})
    actions = [_craft_action(),
               GatherAction(resource_code=_RESOURCE, locations=frozenset({(2, 0)})),
               GatherAction(resource_code="copper_rocks", locations=frozenset({(9, 9)})),
               WithdrawItemAction(code=_INGREDIENT, quantity=1, bank_location=(4, 0)),
               WithdrawItemAction(code="gold_ore", quantity=1, bank_location=(4, 0)),
               MoveAction(x=1, y=1)]
    out = CraftPotionsGoal().relevant_actions(actions, state, gd)
    assert [g.resource_code for g in out if isinstance(a := g, GatherAction)] == [_RESOURCE]
    assert [w.code for w in out if isinstance(w, WithdrawItemAction)] == [_INGREDIENT]
    assert any(isinstance(a, MoveAction) for a in out)


def test_buy_quantity_batched_to_run_count():
    """The ingredient buy is sized to the whole batch (recipe_qty x runs - held),
    matching the co-emitted craft's run count, not left at 1."""
    gd = _gd_potion()
    gd._npc_stock = {"alchemist": {_INGREDIENT: 100}}
    gd._npc_locations = {"alchemist": (5, 0)}
    state = make_state(level=1, inventory={}, gold=100000)  # baseline 5, nothing held
    actions = [_craft_action(),
               NpcBuyAction(npc_code="alchemist", item_code=_INGREDIENT, quantity=1,
                            npc_location=(5, 0)),
               MoveAction(x=0, y=0)]
    out = CraftPotionsGoal().relevant_actions(actions, state, gd)
    craft = next(a for a in out if isinstance(a, CraftAction) and a.code == _POTION)
    buy = next(a for a in out if isinstance(a, NpcBuyAction))
    # recipe is {sunflower: 1}, nothing held -> buy == 1 * runs == craft.quantity
    assert craft.quantity > 1            # ladder chose a multi-run batch
    assert buy.quantity == craft.quantity
    assert buy.quantity > 1              # batched, not the old quantity=1


def test_buy_quantity_subtracts_held():
    """Held ingredient reduces the buy to the remaining shortfall.

    Requires a 2-ingredient recipe so the buy tier actually fires: with only
    sunflower held (herb=0), from_held = min(2//1, 0//1) = 0, which skips the
    held tier and enters the buy tier.  runs=5 (baseline at level=1, nothing
    equipped) so sunflower buy = max(1, 5-2) = 3 — a positive shortfall that is
    neither 1 (the old pass-through) nor 5 (the full batch).
    """
    gd = _gd_potion()
    gd._item_stats[_INGREDIENT2] = ItemStats(code=_INGREDIENT2, level=1, type_="resource")
    gd._crafting_recipes = {_POTION: {_INGREDIENT: 1, _INGREDIENT2: 1}}
    gd._npc_stock = {"alchemist": {_INGREDIENT: 100, _INGREDIENT2: 100}}
    gd._npc_locations = {"alchemist": (5, 0)}
    state = make_state(level=1, inventory={_INGREDIENT: 2}, gold=100000)
    actions = [
        _craft_action(),
        NpcBuyAction(npc_code="alchemist", item_code=_INGREDIENT, quantity=1,
                     npc_location=(5, 0)),
        NpcBuyAction(npc_code="alchemist", item_code=_INGREDIENT2, quantity=1,
                     npc_location=(5, 0)),
        MoveAction(x=0, y=0),
    ]
    out = CraftPotionsGoal().relevant_actions(actions, state, gd)
    craft = next(a for a in out if isinstance(a, CraftAction) and a.code == _POTION)
    buy_sun = next(a for a in out if isinstance(a, NpcBuyAction) and a.item_code == _INGREDIENT)
    buy_herb = next(a for a in out if isinstance(a, NpcBuyAction) and a.item_code == _INGREDIENT2)
    runs = craft.quantity
    # from_held=0 forces buy tier; runs must be large enough for a positive shortfall
    assert runs >= 4, f"expected runs>=4 for positive shortfall; got {runs}"
    # sunflower: 2 held -> buy = max(1, runs-2), which is runs-2 (>1 when runs>=4)
    assert buy_sun.quantity == max(1, runs - 2)
    assert buy_sun.quantity == runs - 2      # positive shortfall, not the floor
    # herb: 0 held -> buy == full batch
    assert buy_herb.quantity == runs


# ── misc surface ─────────────────────────────────────────────────────────────

def test_preemptive_flag():
    assert CraftPotionsGoal.preemptive is True


def test_desired_state_empty():
    gd = _gd_potion()
    assert CraftPotionsGoal().desired_state(make_state(), gd) == {}


def test_repr():
    assert repr(CraftPotionsGoal()) == "CraftPotionsGoal"
