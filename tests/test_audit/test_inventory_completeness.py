"""Inventory keep/disposal census cores (item-protection-authority epic, Task 4).

The census is the ACCEPTANCE MECHANISM for the keep-authority migration, so these
tests hold it to the two properties that make it worth anything:

  * it is COMPLETE — the grid is DERIVED from the `KeepReason` registry, so every
    reason gets a SAFETY and a LIVENESS cell and `CURRENCY` is the ONE declared
    exemption; and
  * it is NOT BLIND — driven against the REAL `StrategyArbiter`, the WORKING_KIT
    liveness cell FAILS, because `bank_selection._keep_codes` still blanket-keeps
    the working-kit tools and banks NONE of a copper_axe hoard. A census that
    cannot see the bug it exists to catch is worse than no census.
"""

import pytest

from artifactsmmo_cli.ai.actions.delete import DeleteItemAction
from artifactsmmo_cli.ai.actions.deposit_all import DepositAllAction
from artifactsmmo_cli.ai.actions.deposit_item import DepositItemAction
from artifactsmmo_cli.ai.actions.ge_fill import GeFillBuyOrderAction
from artifactsmmo_cli.ai.actions.npc_sell import NpcSellAction
from artifactsmmo_cli.ai.actions.recycle import RecycleAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.bank_selection import select_bank_deposits
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.inventory_caps import LEVEL_BAND_FAR, LEVEL_BAND_NEAR
from artifactsmmo_cli.ai.inventory_keep import (
    IN_BAG_REASONS,
    KEEP_ALL,
    OWNED_REASONS,
    KeepReason,
    bankable,
    destroyable,
    keep_owned,
    reason_quantity,
)
from artifactsmmo_cli.ai.tiers.guards import GuardKind, active_guards
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE
from artifactsmmo_cli.audit.inventory_completeness import (
    BANDS,
    CENSUS_LEVEL,
    CENSUS_LEVEL_FAR,
    FILLER_STACKS,
    SENTINEL_HELD,
    SURPLUS,
    InventoryCell,
    InventoryGapClass,
    _action_disposal,
    _bank,
    _cap_value,
    _capacities,
    _delete_pressure,
    _held_for,
    _recyclable,
    _sellable,
    band_level,
    caps_for,
    census_ctx,
    census_decision,
    census_state,
    check_binding,
    classify_gap,
    disposed_quantity,
    filler_codes,
    inventory_cell_verdict,
    inventory_grid,
    plan_inventory,
    scenario_for,
)
from tests.test_ai.fixtures import make_state

# ---------------------------------------------------------------------------
# The brief's completeness tests: the grid is DERIVED from the registry.
# ---------------------------------------------------------------------------

def test_grid_covers_every_reason_with_safety_and_liveness(bundle_game_data: GameData) -> None:
    """Behavioral completeness: the grid is DERIVED from the registry, so every
    KeepReason gets a SAFETY and a LIVENESS cell. CURRENCY is the one declared
    exemption (KEEP_ALL means nothing is ever disposable)."""
    cells = inventory_grid(bundle_game_data)
    for reason in KeepReason:
        kinds = {c.kind for c in cells if c.reason is reason}
        assert "safety" in kinds, f"{reason} has no SAFETY cell"
        if reason is not KeepReason.CURRENCY:
            assert "liveness" in kinds, f"{reason} has no LIVENESS cell"


def test_currency_is_the_only_liveness_exemption(bundle_game_data: GameData) -> None:
    cells = inventory_grid(bundle_game_data)
    exempt = {r for r in KeepReason
              if "liveness" not in {c.kind for c in cells if c.reason is r}}
    assert exempt == {KeepReason.CURRENCY}


def test_gap_classes_have_no_expected_bug_class() -> None:
    """INVENTORY_BUG means UNEXPLAINED, never EXPECTED — the craft-census rule."""
    assert InventoryGapClass.INVENTORY_BUG.value == "inventory_bug"


# ---------------------------------------------------------------------------
# THE SELF-CHECK: the census can SEE the live hoard bug.
# ---------------------------------------------------------------------------

def _cell_of(cells: list[InventoryCell], reason: KeepReason, kind: str,
             cap: str, pressure: str, band: str = "in_band") -> InventoryCell:
    matches = [c for c in cells if c.reason is reason and c.kind == kind
               and c.cap == cap and c.pressure == pressure and c.band == band]
    assert len(matches) == 1, matches
    return matches[0]


def test_working_kit_liveness_cell_PASSES_against_the_real_arbiter(
        bundle_game_data: GameData) -> None:
    """THE census self-check, now GREEN (Task 6). This cell is the live 18-axe
    hoard in miniature: a slot-pressured bag holding SEVEN copper_axe, the best
    woodcutting tool.

    It used to FAIL. `bank_selection._keep_codes` returned a CODE-set, which can
    only say "keep ALL copies", so DepositAll banked the 18 junk stacks and NONE
    of the axes while the keep authority said 6 were `bankable`. Deposit now asks
    that authority (`bankable(code)`) instead of a code-set, so the working tool
    stays and its 6 spares bank.

    Everything the disposal path needs is present and asserted below: the bank is
    reachable and has room, DEPOSIT_FULL fires (slot pressure 19/20 = 0.95, above
    the 0.90 watermark), the plan really is a DepositAll, and the axes really do
    leave the bag."""
    gd = bundle_game_data
    cell = _cell_of(inventory_grid(gd), KeepReason.WORKING_KIT,
                    "liveness", "in_bag", "slot_full")
    assert cell.code == "copper_axe"
    assert (cell.held, cell.keep) == (1 + SURPLUS, 1)

    state = census_state(cell.reason, cell.cap, cell.pressure, cell.held, gd,
                         cell.band)
    ctx = census_ctx(cell.reason, state, gd)

    # The authority licenses shedding the surplus...
    assert bankable("copper_axe", state, gd, ctx) == SURPLUS
    # ...the bag really is slot-pressured (19/20), not quantity-pressured...
    assert state.inventory_slots_used == FILLER_STACKS + 1
    assert state.inventory_slots_free == 1
    assert state.inventory_used < state.inventory_max * 0.85
    # ...and the deposit relief really does fire.
    assert GuardKind.DEPOSIT_FULL in active_guards(state, gd, None, ctx, ctx.step_profile)

    # And the production deposit selector now sheds EXACTLY the surplus: the
    # working axe stays, its spares go to the bank (recoverable).
    deposits = dict(select_bank_deposits(state, gd, ctx))
    assert deposits["copper_axe"] == SURPLUS
    assert state.inventory["copper_axe"] - deposits["copper_axe"] == 1

    plan = plan_inventory(cell, state, gd)
    assert plan and any(isinstance(a, DepositAllAction) for a in plan), \
        [repr(a) for a in plan]
    assert disposed_quantity(cell, plan, state, gd) == SURPLUS
    assert inventory_cell_verdict(cell, plan, state, gd) is True


def test_currency_safety_cell_passes_against_the_real_arbiter(
        bundle_game_data: GameData) -> None:
    """The other half of the self-check: the census is not just a FAIL machine.
    tasks_coin is KEEP_ALL, the bag is slot-pressured, DepositAll fires — and the
    coins survive, so the SAFETY cell PASSES."""
    gd = bundle_game_data
    cell = _cell_of(inventory_grid(gd), KeepReason.CURRENCY,
                    "safety", "in_bag", "slot_full")
    assert (cell.code, cell.held, cell.keep) == (TASKS_COIN_CODE, SENTINEL_HELD, KEEP_ALL)
    state = census_state(cell.reason, cell.cap, cell.pressure, cell.held, gd,
                         cell.band)
    plan = plan_inventory(cell, state, gd)
    assert disposed_quantity(cell, plan, state, gd) == 0
    assert inventory_cell_verdict(cell, plan, state, gd) is True


def test_owned_liveness_cell_drives_the_real_arbiter_under_a_full_bank(
        bundle_game_data: GameData) -> None:
    """An OWNED-cap cell's bank is FULL by construction — destroying is only the
    right route when banking cannot absorb the surplus (the bank-full cascade).
    Here the quantity-pressured EQUIPPED cell sheds its 6 spare daggers, which is
    what `destroyable` licenses."""
    gd = bundle_game_data
    cell = _cell_of(inventory_grid(gd), KeepReason.EQUIPPED,
                    "liveness", "owned", "qty_full")
    state = census_state(cell.reason, cell.cap, cell.pressure, cell.held, gd,
                         cell.band)
    ctx = census_ctx(cell.reason, state, gd)
    assert state.bank_items is not None and len(state.bank_items) == gd.bank_capacity
    assert destroyable(cell.code, state, gd, ctx) == SURPLUS
    plan = plan_inventory(cell, state, gd)
    assert inventory_cell_verdict(cell, plan, state, gd) is True
    assert disposed_quantity(cell, plan, state, gd) > 0


# ---------------------------------------------------------------------------
# Grid derivation details.
# ---------------------------------------------------------------------------

def test_grid_crosses_every_reason_with_every_cap_and_pressure(
        bundle_game_data: GameData) -> None:
    """The grid is a full cross-product, not a sample: SAFETY in all three
    pressure states, LIVENESS in the two PRESSURED ones (a roomy bag is not
    supposed to shed anything, so a liveness demand there would be vacuous)."""
    cells = inventory_grid(bundle_game_data)
    for reason in KeepReason:
        for cap in caps_for(reason):
            safety = {c.pressure for c in cells
                      if c.reason is reason and c.cap == cap and c.kind == "safety"}
            liveness = {c.pressure for c in cells
                        if c.reason is reason and c.cap == cap and c.kind == "liveness"}
            assert safety == {"slot_full", "qty_full", "below_threshold"}
            expected = set() if reason is KeepReason.CURRENCY else {"slot_full", "qty_full"}
            assert liveness == expected


def test_grid_separates_slot_pressure_from_quantity_pressure(
        bundle_game_data: GameData) -> None:
    """Slot-full and quantity-full are DIFFERENT worlds — the HTTP 497 livelock
    lived in that gap (20/20 slots at 68/124 quantity). The slot-full cell is
    slot-pressured and quantity-relaxed; the qty-full cell is the mirror."""
    gd = bundle_game_data
    cells = inventory_grid(gd)
    slot = _cell_of(cells, KeepReason.WORKING_KIT, "liveness", "in_bag", "slot_full")
    qty = _cell_of(cells, KeepReason.WORKING_KIT, "liveness", "in_bag", "qty_full")
    roomy = _cell_of(cells, KeepReason.WORKING_KIT, "safety", "in_bag", "below_threshold")

    slot_state = census_state(slot.reason, slot.cap, slot.pressure, slot.held, gd,
                              slot.band)
    qty_state = census_state(qty.reason, qty.cap, qty.pressure, qty.held, gd,
                             qty.band)
    roomy_state = census_state(roomy.reason, roomy.cap, roomy.pressure, roomy.held, gd,
                               roomy.band)

    assert slot_state.inventory_slots_free == 1
    assert slot_state.inventory_free > 1  # quantity is NOT the binding limit
    assert qty_state.inventory_free >= 1
    assert qty_state.inventory_slots_free > 1  # slots are NOT the binding limit
    assert _delete_pressure(qty_state) and not _delete_pressure(slot_state)
    # ...and the roomy bag crosses no watermark at all.
    assert not _delete_pressure(roomy_state)
    assert GuardKind.DEPOSIT_FULL not in active_guards(
        roomy_state, gd, None, census_ctx(roomy.reason, roomy_state, gd), None)


def test_in_bag_cells_get_a_roomy_bank_and_owned_cells_a_full_one(
        bundle_game_data: GameData) -> None:
    """The cap decides the bank: banking IS the in-bag route (so the bank must
    have room), and banking is NOT an ownership route (so an owned cell's bank is
    full — otherwise production would rightly bank instead of destroy and the
    liveness obligation would be unsatisfiable by design, not by bug)."""
    gd = bundle_game_data
    in_bag = census_state(KeepReason.WORKING_KIT, "in_bag", "slot_full", 7, gd,
                          "in_band")
    owned = census_state(KeepReason.EQUIPPED, "owned", "slot_full", 7, gd,
                         "in_band")
    assert in_bag.bank_items == {}
    assert owned.bank_items is not None and len(owned.bank_items) == gd.bank_capacity
    # No bank stock of the cell's own code: it would credit `destroyable`.
    assert "copper_dagger" not in owned.bank_items


def test_filler_never_contests_the_reason_under_test(bundle_game_data: GameData) -> None:
    """The junk that creates pressure must not carry any property a keep reason
    keys on — a filler heal would take a share of HEALING_CONSUMABLE's aggregate
    target, a filler tool would contest WORKING_KIT's best-tool pick."""
    gd = bundle_game_data
    for reason in KeepReason:
        scenario = scenario_for(reason, gd)
        fillers = filler_codes(scenario, gd)
        assert len(fillers) == FILLER_STACKS
        assert scenario.code not in fillers
        for code in fillers:
            stats = gd.item_stats(code)
            assert stats is not None
            assert stats.type_ == "resource"
            assert stats.hp_restore == 0
            assert not stats.skill_effects


def test_census_ctx_binds_the_goal_step_profile_from_production(
        bundle_game_data: GameData) -> None:
    """GOAL_MATERIALS is only live when `ctx.step_profile` is populated, and the
    census must populate it the way the arbiter does — from the production
    `_step_protection_profile` of the production step goal, not by hand.

    The step (6 `cooked_beef` <- 6 `raw_beef`) is chosen so GOAL_MATERIALS BINDS on
    the OWNED cap: `raw_beef`'s owned-side sibling RECIPE_DEMAND is only 5
    (`BATCH_BUFFER x max_recipe_demand(raw_beef)`, and exactly one recipe consumes
    it, 1-per), so a 6-unit step out-asks it by 1. `check_binding` would refuse the
    cell otherwise — see GOAL_STEP_CODE."""
    gd = bundle_game_data
    state = census_state(KeepReason.GOAL_MATERIALS, "in_bag", "slot_full", 12, gd,
                         "in_band")
    ctx = census_ctx(KeepReason.GOAL_MATERIALS, state, gd)
    assert ctx.step_profile == {"cooked_beef": 6, "raw_beef": 6}
    # ...and the decision handed to the arbiter carries the SAME step, so the
    # arbiter re-derives that map itself.
    decision = census_decision(KeepReason.GOAL_MATERIALS, gd)
    assert decision.chosen_step is not None
    assert decision.chosen_step.code == "cooked_beef"
    # Every other reason is exercised with no step: the disposal ladder answers.
    assert census_decision(KeepReason.WORKING_KIT, gd).chosen_step is None
    assert census_ctx(KeepReason.WORKING_KIT, state, gd).step_profile == {}


def test_gear_demand_scenario_binds_gear_keep(bundle_game_data: GameData) -> None:
    gd = bundle_game_data
    state = census_state(KeepReason.GEAR_DEMAND, "owned", "slot_full", 8, gd,
                         "in_band")
    ctx = census_ctx(KeepReason.GEAR_DEMAND, state, gd)
    assert ctx.gear_keep == {"copper_boots": 2}


def test_committed_recipe_scenario_runs_two_disjoint_committed_roots(
        bundle_game_data: GameData) -> None:
    """The scenario carries an in-flight craft AND an items-task, because
    COMMITTED_RECIPE only BINDS on the OWNED cap when it out-asks RECIPE_DEMAND —
    and it can only do that by SUMMING two disjoint roots (its own semantics: 44
    ore, not 36). With the craft alone the sibling's `5 x max_recipe_demand`
    heuristic (40 copper_bar) wins; with the task alone the two TIE, because
    RECIPE_DEMAND's `task_cap` term is the very same chain walk."""
    gd = bundle_game_data
    state = census_state(KeepReason.COMMITTED_RECIPE, "in_bag", "slot_full", 54, gd,
                         "in_band")
    assert state.crafting_target == "copper_axe"
    assert (state.task_code, state.task_type, state.task_total) == (
        "copper_dagger", "items", 7)
    assert state.inventory["copper_bar"] == 54
    ctx = census_ctx(KeepReason.COMMITTED_RECIPE, state, gd)
    # 1 axe (6 bars) + 7 daggers (42 bars) = 48 — strictly above RECIPE_DEMAND's 42.
    assert reason_quantity(KeepReason.COMMITTED_RECIPE, "copper_bar",
                           state, gd, ctx) == 48
    assert reason_quantity(KeepReason.RECIPE_DEMAND, "copper_bar",
                           state, gd, ctx) == 42
    assert keep_owned("copper_bar", state, gd, ctx) == 48


def test_every_cell_keep_is_the_authority_answer(bundle_game_data: GameData) -> None:
    """The oracle is CONFORMANCE: each cell's `keep` is what `keep_in_bag` /
    `keep_owned` return at that cell's own state — no hand-written expectations."""
    gd = bundle_game_data
    for cell in inventory_grid(gd):
        state = census_state(cell.reason, cell.cap, cell.pressure, cell.held,
                             gd, cell.band)
        ctx = census_ctx(cell.reason, state, gd)
        assert _cap_value(cell.cap, cell.code, state, gd, ctx) == cell.keep
        assert state.inventory[cell.code] == cell.held
        if cell.kind == "liveness":
            shed = (bankable if cell.cap == "in_bag" else destroyable)
            assert shed(cell.code, state, gd, ctx) == SURPLUS


def test_caps_for_matches_the_registry() -> None:
    for reason in KeepReason:
        caps = caps_for(reason)
        assert ("in_bag" in caps) is (reason in IN_BAG_REASONS)
        assert ("owned" in caps) is (reason in OWNED_REASONS)


def test_caps_for_rejects_a_reason_that_protects_nothing() -> None:
    """A reason in neither ladder would silently generate NO cells — the exact
    completeness hole the census exists to prevent."""
    with pytest.raises(ValueError, match="NEITHER keep cap"):
        caps_for("not_a_reason")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Cell construction: the anti-lying checks.
# ---------------------------------------------------------------------------

def test_check_binding_accepts_a_tie() -> None:
    """Two reasons wanting the SAME quantity is fine — the cap is the same either
    way, so the cell still tests what it names."""
    check_binding(KeepReason.ACTIVE_TASK, "owned", "slot_full", "in_band",
                  "golden_egg", 5, 5, 5)


def test_check_binding_rejects_a_moving_cap() -> None:
    with pytest.raises(ValueError, match="cap moved"):
        check_binding(KeepReason.ACTIVE_TASK, "owned", "slot_full", "in_band",
                      "golden_egg", 5, 7, 7)


def test_check_binding_rejects_a_shadowed_reason() -> None:
    """A sibling reason out-asking this one would make the "surplus" protected by
    the SIBLING — the liveness FAIL would be a census artifact, not a bug."""
    with pytest.raises(ValueError, match="out-asks"):
        check_binding(KeepReason.ACTIVE_TASK, "owned", "slot_full", "in_band",
                      "copper_ore", 400, 400, 5)


def test_held_for_safety_liveness_and_the_keep_all_sentinel() -> None:
    assert _held_for(6, "safety", KeepReason.COMMITTED_RECIPE) == 6
    assert _held_for(6, "liveness", KeepReason.COMMITTED_RECIPE) == 6 + SURPLUS
    # KEEP_ALL is not holdable: the sentinel cell holds a plausible stock.
    assert _held_for(KEEP_ALL, "safety", KeepReason.CURRENCY) == SENTINEL_HELD
    with pytest.raises(ValueError, match="unknown cell kind"):
        _held_for(6, "sideways", KeepReason.COMMITTED_RECIPE)


def test_cap_value_rejects_an_unknown_cap(bundle_game_data: GameData) -> None:
    gd = bundle_game_data
    state = census_state(KeepReason.WORKING_KIT, "in_bag", "slot_full", 7, gd,
                         "in_band")
    ctx = census_ctx(KeepReason.WORKING_KIT, state, gd)
    with pytest.raises(ValueError, match="unknown cap"):
        _cap_value("sideways", "copper_axe", state, gd, ctx)


def test_band_level_maps_each_band_and_rejects_an_unknown_one() -> None:
    """The band IS the character level — the only input that differs between a
    cell and its far twin. IN_BAND sits inside `LEVEL_BAND_NEAR` of the level-1
    census items (distance 4, no ceiling); FAR sits at or beyond
    `LEVEL_BAND_FAR` (distance 19, the tightest ceiling). An unknown band raises
    rather than silently defaulting to a level whose distance nobody chose."""
    assert band_level("in_band") == CENSUS_LEVEL
    assert band_level("far") == CENSUS_LEVEL_FAR
    assert abs(1 - CENSUS_LEVEL) < LEVEL_BAND_NEAR
    assert abs(1 - CENSUS_LEVEL_FAR) >= LEVEL_BAND_FAR
    with pytest.raises(ValueError, match="unknown level band"):
        band_level("sideways")


def test_bands_are_the_grid_dimension(bundle_game_data: GameData) -> None:
    """Every cell exists in BOTH bands, and the two halves are identical except
    for the character's level: same code, same `keep` (the reason's DEMAND is
    band-invariant — no reason reads the character's level), same `held`. That
    equality is the obligation; a FAR cap that disagrees is the bug."""
    cells = inventory_grid(bundle_game_data)
    assert {c.band for c in cells} == set(BANDS)
    by_key = {(c.reason, c.cap, c.kind, c.pressure, c.band): c for c in cells}
    for (reason, cap, kind, pressure, band), cell in by_key.items():
        if band != "in_band":
            continue
        twin = by_key[(reason, cap, kind, pressure, "far")]
        assert (twin.code, twin.keep, twin.held) == (cell.code, cell.keep, cell.held)


def test_capacities_rejects_an_unknown_pressure() -> None:
    assert _capacities("slot_full", 25, 19) == (100, 20)
    assert _capacities("below_threshold", 25, 19)[1] == 100
    with pytest.raises(ValueError, match="unknown pressure"):
        _capacities("exploding", 25, 19)


def test_scenario_for_rejects_an_unregistered_reason(bundle_game_data: GameData) -> None:
    with pytest.raises(ValueError, match="no census scenario"):
        scenario_for("not_a_reason", bundle_game_data)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# A deliberately impoverished catalog: the census FAILS LOUD rather than
# quietly shrinking its grid (API-data rule).
# ---------------------------------------------------------------------------

def _thin_gd() -> GameData:
    """A catalog with the census items but almost no junk — real GameData,
    hand-stocked, so the data-starvation paths are exercised without mocking the
    unit under test."""
    gd = GameData()
    gd._item_stats = {
        "copper_axe": ItemStats(code="copper_axe", level=1, type_="weapon",
                                subtype="tool", skill_effects={"woodcutting": -10},
                                crafting_skill="weaponcrafting", crafting_level=1),
        "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource",
                                crafting_skill="mining", crafting_level=1),
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
    }
    gd._crafting_recipes = {"copper_axe": {"copper_bar": 6},
                            "copper_bar": {"copper_ore": 6}}
    return gd


def test_missing_catalog_item_fails_loud_instead_of_shrinking_the_grid() -> None:
    """Use only game data or FAIL — never default. A census that silently skipped
    a reason whose item vanished from the catalog would report a completeness it
    does not have."""
    gd = _thin_gd()
    with pytest.raises(ValueError, match="not in the game catalog"):
        scenario_for(KeepReason.CURRENCY, gd)


def test_too_little_junk_to_build_pressure_fails_loud() -> None:
    gd = _thin_gd()
    scenario = scenario_for(KeepReason.WORKING_KIT, gd)
    with pytest.raises(ValueError, match="filler resources"):
        filler_codes(scenario, gd)


# ---------------------------------------------------------------------------
# Disposal accounting + verdicts.
# ---------------------------------------------------------------------------

def _disposal_gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "copper_axe": ItemStats(code="copper_axe", level=1, type_="weapon",
                                subtype="tool", skill_effects={"woodcutting": -10},
                                crafting_skill="weaponcrafting", crafting_level=1),
        "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource",
                                crafting_skill="mining", crafting_level=1),
    }
    gd._crafting_recipes = {"copper_axe": {"copper_bar": 6},
                            "copper_bar": {"copper_ore": 6}}
    gd._workshop_locations = {"weaponcrafting": (2, 1), "mining": (1, 5)}
    gd._bank_location = (7, 13)
    gd.world.bank_capacity = 50
    return gd


def test_bank_for_an_owned_cell_never_stocks_the_scenario_closure(
        bundle_game_data: GameData) -> None:
    """The owned-cap bank is filled to capacity to shut the DEPOSIT route, but
    never with the cell's own item or its recipe closure — bank copies count
    toward `keep_owned`, so stocking them would silently shrink `destroyable`."""
    gd = bundle_game_data
    stock = _bank("owned", scenario_for(KeepReason.EQUIPPED, gd), gd)
    assert len(stock) == gd.bank_capacity
    assert "copper_dagger" not in stock

    thin = _thin_gd()
    thin.world.bank_capacity = 50
    # Every item in this catalog IS the axe's closure, so nothing may be stocked.
    assert _bank("owned", scenario_for(KeepReason.WORKING_KIT, thin), thin) == {}
    assert _bank("in_bag", scenario_for(KeepReason.WORKING_KIT, thin), thin) == {}


def test_action_disposal_counts_each_route_against_the_right_cap() -> None:
    """Deposit empties the BAG but retains OWNERSHIP; recycle/sell/delete remove
    the copies from the world. A `keep_owned` obligation can therefore never be
    satisfied — nor violated — by banking."""
    gd = _disposal_gd()
    state = make_state(inventory={"copper_axe": 8})
    assert _action_disposal(DepositItemAction(code="copper_axe", quantity=3),
                            "copper_axe", state, gd) == (3, 0)
    assert _action_disposal(RecycleAction(code="copper_axe", quantity=2),
                            "copper_axe", state, gd) == (2, 2)
    assert _action_disposal(DeleteItemAction(code="copper_axe", quantity=4),
                            "copper_axe", state, gd) == (4, 4)
    assert _action_disposal(NpcSellAction(npc_code="n", item_code="copper_axe",
                                          quantity=5), "copper_axe", state, gd) == (5, 5)
    assert _action_disposal(GeFillBuyOrderAction(order_id="o", item_code="copper_axe",
                                                 price=1, quantity=6),
                            "copper_axe", state, gd) == (6, 6)
    # A different code, and a non-disposal action, dispose nothing.
    assert _action_disposal(DeleteItemAction(code="copper_bar", quantity=4),
                            "copper_axe", state, gd) == (0, 0)
    assert _action_disposal(RecycleAction(code="copper_bar", quantity=1),
                            "copper_axe", state, gd) == (0, 0)
    assert _action_disposal(DepositItemAction(code="copper_bar", quantity=1),
                            "copper_axe", state, gd) == (0, 0)
    assert _action_disposal(NpcSellAction(npc_code="n", item_code="copper_bar",
                                          quantity=1), "copper_axe", state, gd) == (0, 0)
    assert _action_disposal(RestAction(), "copper_axe", state, gd) == (0, 0)


def test_action_disposal_reads_deposit_all_through_the_production_selector() -> None:
    """`DepositAll` names no code — it banks whatever `select_bank_deposits` picks,
    which is the very function the hoard bug lived in. The census must therefore
    ASK that selector, not assume "DepositAll banks everything" (nor, as the bug
    did, that it banks nothing of a protected code)."""
    gd = _disposal_gd()
    state = make_state(inventory={"copper_axe": 8, "copper_bar": 3}, bank_items={})
    action = DepositAllAction(bank_location=(7, 13), game_data=gd)
    # The axe is the best woodcutting tool -> WORKING_KIT keeps ONE -> 7 of 8 bank
    # (from the BAG only: a deposit never touches ownership).
    assert _action_disposal(action, "copper_axe", state, gd) == (7, 0)
    # The bar has no demand at all (no crafting target) -> the whole stack banks.
    assert _action_disposal(action, "copper_bar", state, gd) == (3, 0)


def test_disposed_quantity_walks_the_plan_through_production_apply() -> None:
    """Each action is judged at the state it would really run in: the second
    DepositAll sees the bag the first one left behind."""
    gd = _disposal_gd()
    state = make_state(inventory={"copper_bar": 9}, bank_items={})
    cell = InventoryCell(reason=KeepReason.RECIPE_DEMAND, kind="liveness",
                         cap="in_bag", band="in_band", code="copper_bar",
                         held=9, keep=3, pressure="slot_full")
    plan = [DepositItemAction(code="copper_bar", quantity=4),
            DepositAllAction(bank_location=(7, 13), game_data=gd)]
    # 4 banked explicitly, then DepositAll banks the 5 that remain.
    assert disposed_quantity(cell, plan, state, gd) == 9


def test_disposed_quantity_ignores_consumption_that_is_not_disposal() -> None:
    """A craft consuming its inputs is USE, not disposal — a bag count that went
    down is not evidence the surplus was shed. (Deleting the same copies IS.)"""
    gd = _disposal_gd()
    state = make_state(inventory={"copper_bar": 9}, bank_items={})
    cell = InventoryCell(reason=KeepReason.RECIPE_DEMAND, kind="liveness",
                         cap="owned", band="in_band", code="copper_bar",
                         held=9, keep=3, pressure="qty_full")
    # Deposits never satisfy an OWNED obligation.
    assert disposed_quantity(
        cell, [DepositItemAction(code="copper_bar", quantity=6)], state, gd) == 0
    assert disposed_quantity(
        cell, [DeleteItemAction(code="copper_bar", quantity=6)], state, gd) == 6


def test_verdicts_are_conformance_to_the_authority() -> None:
    gd = _disposal_gd()
    state = make_state(inventory={"copper_bar": 3}, bank_items={})
    safety = InventoryCell(reason=KeepReason.RECIPE_DEMAND, kind="safety",
                           cap="in_bag", band="in_band", code="copper_bar",
                           held=3, keep=3, pressure="slot_full")
    assert inventory_cell_verdict(safety, [], state, gd) is True
    assert inventory_cell_verdict(
        safety, [DepositItemAction(code="copper_bar", quantity=1)], state, gd) is False

    live_state = make_state(inventory={"copper_bar": 9}, bank_items={})
    liveness = InventoryCell(reason=KeepReason.RECIPE_DEMAND, kind="liveness",
                             cap="in_bag", band="in_band", code="copper_bar",
                             held=9, keep=3, pressure="slot_full")
    assert inventory_cell_verdict(liveness, [], live_state, gd) is False
    assert inventory_cell_verdict(
        liveness, [DepositItemAction(code="copper_bar", quantity=1)],
        live_state, gd) is True

    with pytest.raises(ValueError, match="unknown cell kind"):
        inventory_cell_verdict(
            InventoryCell(reason=KeepReason.RECIPE_DEMAND, kind="sideways",  # type: ignore[arg-type]
                          cap="in_bag", band="in_band", code="copper_bar",
                          held=9, keep=3, pressure="slot_full"), [], live_state, gd)


def test_keep_all_safety_verdict_clamps_the_sentinel() -> None:
    """KEEP_ALL (1_000_000) exceeds any holdable stock, so the SAFETY verdict
    clamps `keep` to `held` — "every copy is protected", which is what the
    sentinel means. Without the clamp the CURRENCY cell would fail vacuously."""
    gd = _disposal_gd()
    state = make_state(inventory={TASKS_COIN_CODE: SENTINEL_HELD})
    cell = InventoryCell(reason=KeepReason.CURRENCY, kind="safety", cap="in_bag",
                         band="in_band", code=TASKS_COIN_CODE,
                         held=SENTINEL_HELD, keep=KEEP_ALL, pressure="slot_full")
    assert inventory_cell_verdict(cell, [], state, gd) is True
    assert inventory_cell_verdict(
        cell, [DeleteItemAction(code=TASKS_COIN_CODE, quantity=1)], state, gd) is False


# ---------------------------------------------------------------------------
# Gap classes: honest explanations only; INVENTORY_BUG is the residual.
# ---------------------------------------------------------------------------

def _gap_cell(reason: KeepReason, cap: str, code: str,
              kind: str = "liveness") -> InventoryCell:
    return InventoryCell(reason=reason, kind=kind, cap=cap,  # type: ignore[arg-type]
                         band="in_band", code=code, held=9, keep=3,
                         pressure="slot_full")  # type: ignore[arg-type]


def test_keep_all_sentinel_classifies_only_the_declared_liveness_exemption() -> None:
    """The exemption is DECLARED, not discovered: a CURRENCY *liveness*
    obligation is excused by design. A CURRENCY *safety* FAIL means a plan
    DISPOSED currency — a bug like any other, so it falls through to the
    cascade."""
    gd = _disposal_gd()
    state = make_state(inventory={TASKS_COIN_CODE: 9}, bank_items={})
    live = _gap_cell(KeepReason.CURRENCY, "in_bag", TASKS_COIN_CODE)
    assert classify_gap(live, state, gd) is InventoryGapClass.KEEP_ALL_SENTINEL
    safety = _gap_cell(KeepReason.CURRENCY, "in_bag", TASKS_COIN_CODE, kind="safety")
    assert classify_gap(safety, state, gd) is InventoryGapClass.INVENTORY_BUG


def test_in_bag_gap_classes() -> None:
    gd = _disposal_gd()
    cell = _gap_cell(KeepReason.WORKING_KIT, "in_bag", "copper_axe")
    # Bank located + room -> nothing excuses the FAIL.
    assert classify_gap(cell, make_state(inventory={"copper_axe": 9}, bank_items={}),
                        gd) is InventoryGapClass.INVENTORY_BUG
    # Bank at capacity -> DEPOSIT genuinely cannot take it.
    full = make_state(inventory={"copper_axe": 9},
                      bank_items={f"junk_{i}": 1 for i in range(gd.bank_capacity)})
    assert classify_gap(cell, full, gd) is InventoryGapClass.BANK_FULL
    # No bank on the map at all -> the route's venue is unreachable.
    gd._bank_location = None
    assert classify_gap(cell, make_state(inventory={"copper_axe": 9}, bank_items={}),
                        gd) is InventoryGapClass.VENUE_UNREACHABLE


def test_owned_gap_classes() -> None:
    gd = _disposal_gd()
    full_bank = {f"junk_{i}": 1 for i in range(gd.bank_capacity)}
    axe = _gap_cell(KeepReason.EQUIPPED, "owned", "copper_axe")
    roomy_state = make_state(inventory={"copper_axe": 9}, bank_items=full_bank,
                             inventory_max=100)
    # copper_axe is weaponcrafting-crafted at a PLACED workshop -> recyclable,
    # so a FAIL has no excuse.
    assert classify_gap(axe, roomy_state, gd) is InventoryGapClass.INVENTORY_BUG

    # Same item, workshop off the map: the route exists but its venue does not.
    gd._workshop_locations = {}
    assert classify_gap(axe, roomy_state, gd) is InventoryGapClass.VENUE_UNREACHABLE

    # A material with no recycle route, no buyer, and a roomy bag: production has
    # no destructive route to fire — the DELETE watermark is deliberately
    # quantity-gated, so slot pressure alone never deletes.
    bar = _gap_cell(KeepReason.RECIPE_DEMAND, "owned", "copper_bar")
    assert classify_gap(bar, make_state(inventory={"copper_bar": 9},
                                        bank_items=full_bank, inventory_max=100),
                        gd) is InventoryGapClass.NO_ROUTE_AVAILABLE
    # ...but at the discard watermark, DELETE is a route -> no excuse left.
    assert classify_gap(bar, make_state(inventory={"copper_bar": 9},
                                        bank_items=full_bank, inventory_max=10),
                        gd) is InventoryGapClass.INVENTORY_BUG


def test_owned_gap_venue_unreachable_for_an_unplaced_buyer() -> None:
    """A vendor in the catalog that sits on no tile is a VENUE limit, not an
    absent route."""
    gd = _disposal_gd()
    gd.world.npc_sell_prices = {"floating_merchant": {"copper_bar": 4}}
    cell = _gap_cell(KeepReason.RECIPE_DEMAND, "owned", "copper_bar")
    state = make_state(inventory={"copper_bar": 9},
                       bank_items={f"junk_{i}": 1 for i in range(gd.bank_capacity)},
                       inventory_max=100)
    assert classify_gap(cell, state, gd) is InventoryGapClass.VENUE_UNREACHABLE
    # Place the vendor and the route is real again -> the FAIL is unexplained.
    gd.world.npc_tiles = {"floating_merchant": (4, 4)}
    assert _sellable("copper_bar", state, gd)
    assert classify_gap(cell, state, gd) is InventoryGapClass.INVENTORY_BUG


def test_owned_gap_venue_unreachable_for_a_dormant_event_merchant() -> None:
    """A PLACED buyer is not a route when its event window is SHUT: every gold
    merchant in this game is an event NPC, and `NpcSellAction` refuses the sale.
    A location-only probe would blame the planner for not taking a sale the
    server would reject (`active_task owned/slot_full`, golden_egg)."""
    gd = _disposal_gd()
    gd.world.npc_sell_prices = {"nomadic_merchant": {"copper_bar": 4}}
    gd.world.npc_tiles = {"nomadic_merchant": (4, 4)}
    gd._npc_event_code["nomadic_merchant"] = "nomadic_merchant"
    gd._event_npc_spawns["nomadic_merchant"] = (4, 4)
    cell = _gap_cell(KeepReason.RECIPE_DEMAND, "owned", "copper_bar")
    state = make_state(inventory={"copper_bar": 9},
                       bank_items={f"junk_{i}": 1 for i in range(gd.bank_capacity)},
                       inventory_max=100)
    assert _sellable("copper_bar", state, gd) is False
    assert classify_gap(cell, state, gd) is InventoryGapClass.VENUE_UNREACHABLE


def test_recyclable_is_intrinsic_to_the_item_and_the_world() -> None:
    """Deliberately protection-FREE: reading the keep logic here would let a
    blanket-protected hoard classify itself as "no route" and the census would
    excuse the very bug it hunts."""
    gd = _disposal_gd()
    assert _recyclable("copper_axe", gd) is True
    # No recipe -> nothing to recycle into.
    assert _recyclable("copper_ore", gd) is False
    # Recipe, but a skill the /recycling endpoint refuses (mining).
    assert _recyclable("copper_bar", gd) is False
    # Unknown item.
    assert _recyclable("nonexistent", gd) is False
    # Recipe + accepted skill, but no workshop on the map.
    gd._workshop_locations = {}
    assert _recyclable("copper_axe", gd) is False


def test_delete_pressure_reads_the_quantity_watermark_only() -> None:
    """The discard guards are quantity-gated on purpose (slot pressure must never
    DELETE what banking could have saved), so the census's delete-route probe is
    too."""
    assert _delete_pressure(make_state(inventory={"copper_bar": 19},
                                       inventory_max=20)) is True
    assert _delete_pressure(make_state(inventory={"copper_bar": 5},
                                       inventory_max=20)) is False
    assert _delete_pressure(make_state(inventory={}, inventory_max=0)) is False
