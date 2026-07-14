"""disposal_route / overstock_disposal: overstock disposal-route decision.

Covers the pure core exhaustively (Bool³ = 8 configurations — mirrors the
exhaustive differential in formal/diff/test_disposal_route_diff.py) and every
adapter branch: recycle probe (full and reduced quantity), deposit on
future-value + bank room, and the true-junk / bank-closed delete fallbacks.
"""

import pytest

from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.actions.delete import DeleteItemAction
from artifactsmmo_cli.ai.actions.deposit_item import DepositItemAction
from artifactsmmo_cli.ai.actions.recycle import RecycleAction
from artifactsmmo_cli.ai.disposal_route import (
    Route,
    disposal_route,
    overstock_disposal,
)
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.discard_overstock import DiscardOverstockGoal
from artifactsmmo_cli.ai.inventory_keep import keep_owned
from artifactsmmo_cli.ai.item_catalog import ItemStats
from tests.test_ai.fixtures import make_state

BANK_LOC = (4, 1)
WORKSHOP_LOC = (1, 1)


# === Pure core: all 8 configurations (exhaustive, like the Lean `decide`) ===


@pytest.mark.parametrize("bank_ok", [True, False])
@pytest.mark.parametrize("future_value", [True, False])
def test_recycle_wins_whenever_executable(bank_ok, future_value):
    assert disposal_route(True, bank_ok, future_value) is Route.RECYCLE


def test_deposit_when_bank_open_and_future_value():
    assert disposal_route(False, True, True) is Route.DEPOSIT


@pytest.mark.parametrize(
    ("bank_ok", "future_value"),
    [(True, False), (False, True), (False, False)],
)
def test_delete_only_when_worthless(bank_ok, future_value):
    # No recycle AND (bank closed OR no future value) -> the item is true junk
    # (or nothing else is executable) and only then may it be destroyed.
    assert disposal_route(False, bank_ok, future_value) is Route.DELETE


# === Adapter: input assembly + action construction ===


def _gd(*, item_stats=None, recipes=None, workshops=None, bank_location=BANK_LOC,
        bank_capacity=50) -> GameData:
    gd = GameData()
    gd._item_stats = item_stats or {}
    gd._crafting_recipes = recipes or {}
    gd._workshop_locations = workshops or {}
    gd._bank_location = bank_location
    gd._bank_capacity = bank_capacity
    return gd


def _gear_gd(**overrides) -> GameData:
    """copper_helmet-like recyclable gear: craftable gearcrafting equipment
    with a known workshop."""
    defaults = dict(
        item_stats={"copper_helmet": ItemStats(
            code="copper_helmet", level=5, type_="helmet",
            crafting_skill="gearcrafting", crafting_level=1)},
        recipes={"copper_helmet": {"copper_bar": 6}},
        workshops={"gearcrafting": WORKSHOP_LOC},
    )
    defaults.update(overrides)
    return _gd(**defaults)


def test_recyclable_gear_routes_to_recycle():
    # The copper_helmet x33 trace bug: recyclable grind output must be recycled,
    # never deleted — even with the bank open.
    gd = _gear_gd()
    state = make_state(inventory={"copper_helmet": 8}, inventory_max=100,
                       bank_items={}, skills={"gearcrafting": 5})
    action = overstock_disposal("copper_helmet", 7, state, gd, bank_accessible=True,
                              ctx=NO_PROFILE_CONTEXT)
    assert isinstance(action, RecycleAction)
    assert action.code == "copper_helmet"
    assert action.quantity == 7
    assert action.workshop_location == WORKSHOP_LOC


def test_routed_recycle_is_stamped_with_the_owned_floor():
    """The disposal route builds its BATCH Recycle OUTSIDE `destructive_license`,
    so it stamps `owned_floor = keep_owned` itself — otherwise a plan could apply
    the same batch twice and destroy past `destroyable` (whole-branch review,
    CRITICAL 1). 8 copper_helmets, `keep_owned` 1: seven may die, and only once."""
    gd = _gear_gd()
    state = make_state(inventory={"copper_helmet": 8}, inventory_max=100,
                       bank_items={}, skills={"gearcrafting": 5})
    floor = keep_owned("copper_helmet", state, gd, NO_PROFILE_CONTEXT)
    action = overstock_disposal("copper_helmet", 7, state, gd, bank_accessible=True,
                                ctx=NO_PROFILE_CONTEXT)
    assert isinstance(action, RecycleAction)
    assert action.owned_floor == floor
    assert action.is_applicable(state, gd)
    assert not action.is_applicable(action.apply(state, gd), gd)


def test_recycle_quantity_reduced_to_fit_minted_materials():
    # Recycling mints ~half the materials into the bag (HTTP 497 otherwise);
    # the probe descends until RecycleAction.is_applicable accepts.
    gd = _gear_gd()
    # 6-bar recipe -> recycling qty recovers >= 3*qty bars; free = 2 slots.
    state = make_state(inventory={"copper_helmet": 8, "filler": 90},
                       inventory_max=100, bank_items={},
                       skills={"gearcrafting": 5})
    action = overstock_disposal("copper_helmet", 7, state, gd, bank_accessible=True,
                              ctx=NO_PROFILE_CONTEXT)
    assert isinstance(action, RecycleAction)
    assert action.quantity < 7


def test_recycle_impossible_falls_to_deposit():
    # Bag completely full: no recycle quantity fits the minted materials, but
    # the gear is bankable (equippable = future value) -> deposit, not delete.
    gd = _gear_gd()
    state = make_state(inventory={"copper_helmet": 8, "filler": 92},
                       inventory_max=100, bank_items={},
                       skills={"gearcrafting": 5})
    action = overstock_disposal("copper_helmet", 7, state, gd, bank_accessible=True,
                              ctx=NO_PROFILE_CONTEXT)
    assert isinstance(action, DepositItemAction)
    assert action.code == "copper_helmet"
    assert action.quantity == 7
    assert action.bank_location == BANK_LOC


def test_skill_gated_gear_deposits_instead_of_recycling():
    # Recycling is gated on the crafting skill (HTTP 493): below the recipe
    # level the RecycleAction is inapplicable, so the gear banks.
    gd = _gear_gd(item_stats={"copper_helmet": ItemStats(
        code="copper_helmet", level=5, type_="helmet",
        crafting_skill="gearcrafting", crafting_level=5)})
    state = make_state(inventory={"copper_helmet": 8}, inventory_max=100,
                       bank_items={}, skills={"gearcrafting": 1})
    action = overstock_disposal("copper_helmet", 7, state, gd, bank_accessible=True,
                              ctx=NO_PROFILE_CONTEXT)
    assert isinstance(action, DepositItemAction)


def test_alchemy_craftable_is_not_recycled():
    # Server rule: recycling exists only for weapon/gear/jewelry crafts.
    # recall_potion (alchemy, utility type) must never enter the recycle probe —
    # it deposits (equippable utility = future value).
    gd = _gd(
        item_stats={"recall_potion": ItemStats(
            code="recall_potion", level=1, type_="utility",
            crafting_skill="alchemy", crafting_level=1)},
        recipes={"recall_potion": {"sunflower": 1}},
        workshops={"alchemy": WORKSHOP_LOC},
    )
    state = make_state(inventory={"recall_potion": 60}, inventory_max=100,
                       bank_items={}, skills={"alchemy": 10})
    action = overstock_disposal("recall_potion", 58, state, gd, bank_accessible=True,
                              ctx=NO_PROFILE_CONTEXT)
    assert isinstance(action, DepositItemAction)


def test_recipe_demanded_material_deposits():
    # The emerald_stone x16 trace bug: a gem consumed by (even far-future)
    # jewelry recipes is bankable value, not junk.
    gd = _gd(
        item_stats={
            "emerald_stone": ItemStats(code="emerald_stone", level=20, type_="resource"),
            "emerald_ring": ItemStats(
                code="emerald_ring", level=20, type_="ring",
                crafting_skill="jewelrycrafting", crafting_level=20),
        },
        recipes={"emerald_ring": {"emerald_stone": 2}},
    )
    state = make_state(inventory={"emerald_stone": 16}, inventory_max=100,
                       bank_items={})
    action = overstock_disposal("emerald_stone", 16, state, gd, bank_accessible=True,
                              ctx=NO_PROFILE_CONTEXT)
    assert isinstance(action, DepositItemAction)
    assert action.quantity == 16


def test_true_junk_still_deletes():
    # The sap case (2026-06-24 livelock): no recipe consumes it, not equippable
    # -> Delete keeps clearing the bag; banking it would just hoard junk.
    gd = _gd(item_stats={"sap": ItemStats(code="sap", level=1, type_="resource")})
    state = make_state(inventory={"sap": 33}, inventory_max=100, bank_items={})
    action = overstock_disposal("sap", 33, state, gd, bank_accessible=True,
                              ctx=NO_PROFILE_CONTEXT)
    assert isinstance(action, DeleteItemAction)
    assert action.quantity == 33


def test_bank_inaccessible_deletes_even_valuable():
    # Liveness over hoarding: with no executable recycle and no bank, Delete is
    # the only action that clears the overstock.
    gd = _gd(
        item_stats={"emerald_stone": ItemStats(code="emerald_stone", level=20, type_="resource")},
        recipes={"emerald_ring": {"emerald_stone": 2}},
    )
    state = make_state(inventory={"emerald_stone": 16}, inventory_max=100,
                       bank_items={})
    action = overstock_disposal("emerald_stone", 16, state, gd, bank_accessible=False,
                              ctx=NO_PROFILE_CONTEXT)
    assert isinstance(action, DeleteItemAction)


def test_bank_full_deletes():
    gd = _gd(
        item_stats={"emerald_stone": ItemStats(code="emerald_stone", level=20, type_="resource")},
        recipes={"emerald_ring": {"emerald_stone": 2}},
        bank_capacity=2,
    )
    state = make_state(inventory={"emerald_stone": 16}, inventory_max=100,
                       bank_items={"a": 1, "b": 1})
    action = overstock_disposal("emerald_stone", 16, state, gd, bank_accessible=True,
                              ctx=NO_PROFILE_CONTEXT)
    assert isinstance(action, DeleteItemAction)


def test_unknown_bank_location_deletes():
    gd = _gd(
        item_stats={"emerald_stone": ItemStats(code="emerald_stone", level=20, type_="resource")},
        recipes={"emerald_ring": {"emerald_stone": 2}},
        bank_location=None,
    )
    state = make_state(inventory={"emerald_stone": 16}, inventory_max=100,
                       bank_items={})
    action = overstock_disposal("emerald_stone", 16, state, gd, bank_accessible=True,
                              ctx=NO_PROFILE_CONTEXT)
    assert isinstance(action, DeleteItemAction)


def test_unvisited_bank_deletes():
    # bank_items None (never visited) -> bank_has_room is False -> no deposit.
    gd = _gd(
        item_stats={"emerald_stone": ItemStats(code="emerald_stone", level=20, type_="resource")},
        recipes={"emerald_ring": {"emerald_stone": 2}},
    )
    state = make_state(inventory={"emerald_stone": 16}, inventory_max=100,
                       bank_items=None)
    action = overstock_disposal("emerald_stone", 16, state, gd, bank_accessible=True,
                              ctx=NO_PROFILE_CONTEXT)
    assert isinstance(action, DeleteItemAction)


def test_craftable_non_equippable_is_not_recycled():
    # A gearcrafting-crafted NON-equippable (intermediate) never enters the
    # recycle probe; with recipe demand it deposits.
    gd = _gd(
        item_stats={
            "iron_bar": ItemStats(code="iron_bar", level=10, type_="resource",
                                  crafting_skill="gearcrafting", crafting_level=10),
            "iron_sword": ItemStats(code="iron_sword", level=10, type_="weapon",
                                    crafting_skill="weaponcrafting", crafting_level=10),
        },
        recipes={"iron_sword": {"iron_bar": 6}},
        workshops={"gearcrafting": WORKSHOP_LOC},
    )
    state = make_state(inventory={"iron_bar": 20}, inventory_max=100,
                       bank_items={}, skills={"gearcrafting": 10})
    action = overstock_disposal("iron_bar", 14, state, gd, bank_accessible=True,
                              ctx=NO_PROFILE_CONTEXT)
    assert isinstance(action, DepositItemAction)


def test_no_workshop_known_deposits_gear():
    gd = _gear_gd(workshops={})
    state = make_state(inventory={"copper_helmet": 8}, inventory_max=100,
                       bank_items={}, skills={"gearcrafting": 5})
    action = overstock_disposal("copper_helmet", 7, state, gd, bank_accessible=True,
                              ctx=NO_PROFILE_CONTEXT)
    assert isinstance(action, DepositItemAction)


def test_unknown_item_stats_treated_as_junk():
    gd = _gd()
    state = make_state(inventory={"mystery": 5}, inventory_max=100, bank_items={})
    action = overstock_disposal("mystery", 5, state, gd, bank_accessible=True,
                              ctx=NO_PROFILE_CONTEXT)
    assert isinstance(action, DeleteItemAction)


# === Goal integration: DiscardOverstockGoal routes its fallback ===


class TestDiscardOverstockRouting:
    def test_fallback_recycles_recyclable_gear(self):
        # The trace bug end-to-end: overstocked copper_helmet under bag
        # pressure, no NPC buyer -> the goal emits a Recycle, not a Delete.
        gd = _gear_gd()
        goal = DiscardOverstockGoal(game_data=gd, ctx=NO_PROFILE_CONTEXT, bank_accessible=True)
        state = make_state(inventory={"copper_helmet": 18}, inventory_max=20,
                           bank_items={}, skills={"gearcrafting": 5})
        relevant = goal.relevant_actions([], state, gd)
        assert len(relevant) == 1
        assert isinstance(relevant[0], RecycleAction)
        assert relevant[0].code == "copper_helmet"

    def test_fallback_deposits_recipe_demanded_material(self):
        gd = _gd(
            item_stats={
                "emerald_stone": ItemStats(code="emerald_stone", level=5, type_="resource"),
                "emerald_ring": ItemStats(
                    code="emerald_ring", level=20, type_="ring",
                    crafting_skill="jewelrycrafting", crafting_level=20),
            },
            recipes={"emerald_ring": {"emerald_stone": 2}},
        )
        goal = DiscardOverstockGoal(game_data=gd, ctx=NO_PROFILE_CONTEXT, bank_accessible=True)
        state = make_state(inventory={"emerald_stone": 18}, inventory_max=20,
                           bank_items={})
        relevant = goal.relevant_actions([], state, gd)
        assert len(relevant) == 1
        assert isinstance(relevant[0], DepositItemAction)
        assert relevant[0].code == "emerald_stone"

    def test_fallback_still_deletes_junk_with_bank_open(self):
        # sap-livelock regression guard: junk keeps deleting even at the bank.
        gd = _gd(item_stats={"sap": ItemStats(code="sap", level=1, type_="resource")})
        goal = DiscardOverstockGoal(game_data=gd, ctx=NO_PROFILE_CONTEXT, bank_accessible=True)
        state = make_state(inventory={"sap": 18}, inventory_max=20, bank_items={})
        relevant = goal.relevant_actions([], state, gd)
        assert len(relevant) == 1
        assert isinstance(relevant[0], DeleteItemAction)

    def test_default_bank_inaccessible_preserves_delete(self):
        # Ctor default (bank_accessible=False) keeps the legacy delete
        # behavior for call sites that don't thread the context flag.
        gd = _gd(
            item_stats={"emerald_stone": ItemStats(code="emerald_stone", level=5, type_="resource")},
            recipes={"emerald_ring": {"emerald_stone": 2}},
        )
        goal = DiscardOverstockGoal(game_data=gd, ctx=NO_PROFILE_CONTEXT)
        state = make_state(inventory={"emerald_stone": 18}, inventory_max=20,
                           bank_items={})
        relevant = goal.relevant_actions([], state, gd)
        assert len(relevant) == 1
        assert isinstance(relevant[0], DeleteItemAction)
