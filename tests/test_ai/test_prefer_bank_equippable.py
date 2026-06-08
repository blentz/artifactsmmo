"""Piece B — prefer a FINISHED equippable already in the bank over crafting a new one.

This pins the behavior the macro/micro design (docs/.../2026-06-07-planning-macro-
micro-hinting-design.md, behavior #1) calls for. It is ALREADY satisfied by landed
code — no new module is needed — and this test locks that in:

* SINGLE item: when the bank holds the finished equippable, `UpgradeEquipmentGoal`
  recognizes it through `_find_inventory_upgrade` (which scans bank + inventory),
  `_find_craftable_upgrade_target` skips it (bank-held items are not re-crafted), and
  the least-cost GOAP planner picks the 2-step `Withdraw(item) -> Equip(item)` plan
  over the multi-step craft chain. (The craft chain stays in the action set for
  admissibility; it is simply more expensive, so the planner never chooses it.)

* MULTIPLES exception: a task needing N of the item must still acquire the deficit.
  The bank-aware `shopping_list` credits the held copies at the target node and
  expands the recipe for the REMAINDER (N - held), so `fully_covered_materials`
  returns nothing and the deficit's craft/gather actions survive. A finished item in
  the bank therefore never falsely satisfies a multiples requirement.

If a future change regresses either property (e.g. re-crafting a banked equippable,
or pruning the only acquisition path for a multiples deficit), this test fails.
"""

from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.equip import EquipAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.shopping_list import (
    fully_covered_materials,
    shopping_list,
)
from tests.test_ai.fixtures import make_state

_RECIPES = {"copper_dagger": {"copper_bar": 6}, "copper_bar": {"copper_ore": 10}}


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "copper_dagger": ItemStats(
            code="copper_dagger", level=1, type_="weapon",
            crafting_skill="weaponcrafting", crafting_level=1, attack={"fire": 6}),
        "copper_bar": ItemStats(
            code="copper_bar", level=1, type_="resource",
            crafting_skill="mining", crafting_level=1),
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
    }
    gd._crafting_recipes = dict(_RECIPES)
    gd._resource_drops = {"copper_rocks": "copper_ore"}
    gd._resource_skill = {"copper_rocks": ("mining", 1)}
    gd._resource_locations = {"copper_rocks": [(2, 0)]}
    gd._workshop_locations = {"weaponcrafting": (0, 0), "mining": (0, 0)}
    return gd


def _actions() -> list:
    return [
        CraftAction(code="copper_dagger", quantity=1, workshop_location=(0, 0)),
        CraftAction(code="copper_bar", quantity=1, workshop_location=(0, 0)),
        EquipAction(code="copper_dagger", slot="weapon_slot"),
        GatherAction(resource_code="copper_rocks", locations=frozenset({(2, 0)})),
        WithdrawItemAction(code="copper_dagger", quantity=1),
        WithdrawItemAction(code="copper_ore", quantity=10),
        WithdrawItemAction(code="copper_bar", quantity=6),
    ]


# ---- SINGLE: banked finished equippable preferred over crafting ----


def test_banked_finished_equippable_is_chosen_as_inventory_upgrade():
    """The finished copper_dagger in the bank is surfaced via the inventory path
    (which scans bank+inventory), and the craftable path declines to re-craft it."""
    gd = _gd()
    goal = UpgradeEquipmentGoal(initial_equipment={"weapon_slot": None})
    state = make_state(
        equipment={"weapon_slot": None}, bank_items={"copper_dagger": 1},
        inventory_max=120, skills={"mining": 1, "weaponcrafting": 1})
    assert goal.find_upgrade_target(state, gd) == ("copper_dagger", "weapon_slot")
    assert goal._find_inventory_upgrade(state, gd) == ("copper_dagger", "weapon_slot")
    # Bank-held items are NOT re-crafted: the craftable target skips them.
    assert goal._find_craftable_upgrade_target(state, gd) is None


def test_planner_prefers_withdraw_equip_over_craft_chain():
    """End-to-end: the least-cost plan is Withdraw(copper_dagger) -> Equip, NOT the
    gather/craft chain — redundant crafting is avoided."""
    gd = _gd()
    goal = UpgradeEquipmentGoal(initial_equipment={"weapon_slot": None})
    state = make_state(
        equipment={"weapon_slot": None}, bank_items={"copper_dagger": 1},
        inventory_max=120, skills={"mining": 1, "weaponcrafting": 1})
    plan = GOAPPlanner().plan(state, goal, _actions(), gd)
    reprs = [repr(a) for a in plan]
    assert reprs == ["Withdraw(copper_dagger×1)", "Equip(copper_dagger->weapon_slot)"], reprs
    assert not any(isinstance(a, GatherAction) for a in plan)
    assert not any(isinstance(a, CraftAction) for a in plan)


# ---- MULTIPLES exception: deficit still acquired ----


def test_single_qty_fully_covered_by_banked_finished_item():
    """qty=1, bank holds 1 finished item -> the whole subtree short-circuits to a
    withdraw (net deficit 0 at the target node)."""
    net = shopping_list("copper_dagger", 1, _RECIPES, {"copper_dagger": 1})
    assert net == {"copper_dagger": 0}
    assert fully_covered_materials(
        "copper_dagger", 1, _RECIPES, {"copper_dagger": 1}) == {"copper_dagger"}


def test_multiples_task_crafts_the_deficit():
    """A task needing 5, bank holds 1 finished item -> the held copy is credited but
    the deficit of 4 is expanded into its recipe; nothing is fully covered, so the
    deficit's craft/gather work survives. The single bank copy must NOT satisfy the
    whole multiples requirement."""
    net = shopping_list("copper_dagger", 5, _RECIPES, {"copper_dagger": 1})
    assert net == {"copper_dagger": 4, "copper_bar": 24, "copper_ore": 240}
    # No item is fully bank-covered, so the planner keeps every gather/craft for the
    # deficit (the multiples exception is honored — never short-circuited to a
    # single withdraw).
    assert fully_covered_materials(
        "copper_dagger", 5, _RECIPES, {"copper_dagger": 1}) == set()
