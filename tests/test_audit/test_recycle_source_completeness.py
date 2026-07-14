"""The recycle-as-a-SOURCE behavioral census (recycle-as-acquisition epic,
Task 8).

Every cell here drives the REAL `StrategyArbiter.select` seam over the committed
bundle — the seam at which `license_destructive_actions` runs. A harness that
planned through a lower seam would see the UNLICENSED factory pool (in which the
last `copper_axe` still carries a `RecycleAction`) and the SAFETY cell would be
proving nothing.
"""

import dataclasses
import json
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.recycle import RecycleAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.wait import WaitGoal
from artifactsmmo_cli.audit.recycle_source_completeness import (
    RecycleSourceCell,
    RecycleSourceGapClass,
    RecycleSourceKind,
    RecycleSourceResult,
    _check_cell,
    census_ctx,
    census_state,
    classify_gap,
    plan_recycle_source,
    recycle_source_cell_verdict,
    recycle_source_grid,
    render_matrix,
    run_cell,
    run_census,
    scenario_for,
    summary_line,
)

BUNDLE = Path("tests/test_ai/scenarios/fixtures/gamedata_bundle.json")


def _cells(game_data: GameData) -> dict[RecycleSourceKind, RecycleSourceCell]:
    return {cell.kind: cell for cell in recycle_source_grid(game_data)}


def _actions(cell: RecycleSourceCell, game_data: GameData) -> list[object]:
    """The plan the REAL selector produces for `cell`, refusing an inconclusive
    search: every assertion below is about what the planner CHOSE, and a timed-out
    search chose nothing."""
    state = census_state(cell, game_data)
    _goal, plan, failed = plan_recycle_source(cell, state, game_data)
    assert failed is False
    return list(plan)


# ---------------------------------------------------------------------------
# THE FOUR CELLS, through the real selector.
# ---------------------------------------------------------------------------

def test_liveness_cell_plans_a_recycle(bundle_game_data: GameData) -> None:
    """The bag holds 3 water_bow (2 licensed for destruction) and the goal needs
    4 ash_plank — exactly what those 2 recycles recover. The plan must dismantle
    the bows instead of chopping 40 ash_wood."""
    cell = _cells(bundle_game_data)[RecycleSourceKind.LIVENESS]
    plan = _actions(cell, bundle_game_data)
    assert any(isinstance(a, RecycleAction) and a.code == "water_bow" for a in plan)


def test_safety_cell_never_recycles_the_working_tool(bundle_game_data: GameData) -> None:
    """ONE copper_axe owned, and it is the WORKING_KIT tool (best woodcutting).
    Its recipe is 6 copper_bar and the goal needs 6 copper_bar — the melt is
    RIGHT THERE. It must be gathered around, never dismantled."""
    cell = _cells(bundle_game_data)[RecycleSourceKind.SAFETY]
    plan = _actions(cell, bundle_game_data)
    assert plan, "a protected source must be gathered AROUND, not stalled on"
    assert not any(isinstance(a, RecycleAction) and a.code == "copper_axe"
                   for a in plan)
    assert any(isinstance(a, GatherAction) for a in plan)


def test_safety_cell_is_falsifiable(bundle_game_data: GameData) -> None:
    """THE FALSIFIABILITY WITNESS. The SAFETY cell would be worthless if the
    planner never took this route anyway. Hold TWO copper_axes — the ONE fact the
    keep authority reads (`destroyable` 0 -> 1) — and the very same census
    machinery, same source, same material, same seam, now plans
    `Recycle(copper_axe)`. So the SAFETY green is the PROTECTION talking, not a
    route the planner was blind to."""
    cell = RecycleSourceCell(
        kind=RecycleSourceKind.LIVENESS, source="copper_axe",
        material="copper_bar", needed=3, bag_copies=2, bank_copies=0)
    state = census_state(cell, bundle_game_data)
    _check_cell(cell, state, bundle_game_data, None)  # the cell IS licensed now
    _goal, plan, failed = plan_recycle_source(cell, state, bundle_game_data)
    assert failed is False
    assert any(isinstance(a, RecycleAction) and a.code == "copper_axe"
               for a in plan), (
        "the SAFETY cell is VACUOUS: with the protection lifted the planner still "
        "does not recycle, so its green proves nothing about the protection")
    assert recycle_source_cell_verdict(cell, plan, False) is True


def test_banked_cell_withdraws_then_recycles(bundle_game_data: GameData) -> None:
    """The source lives in the BANK (where DEPOSIT_FULL puts it) and the bag is
    empty: the plan must stage the copies itself."""
    cell = _cells(bundle_game_data)[RecycleSourceKind.BANKED]
    kinds = [type(a).__name__ for a in _actions(cell, bundle_game_data)]
    assert "WithdrawItemAction" in kinds and "RecycleAction" in kinds
    assert kinds.index("WithdrawItemAction") < kinds.index("RecycleAction")


def test_partial_cell_resolves_a_mixed_plan_within_budget(
        bundle_game_data: GameData) -> None:
    """THE NODE-EXPLOSION GUARD. 4 of the 8 needed planks are recoverable; the
    rest are a from-scratch `10x ash_wood` subtree. The plan must take BOTH
    routes and it must come back within budget (A* alone burns 29,792 nodes and
    times out on this shape — the deterministic generator serves it at 0)."""
    cell = _cells(bundle_game_data)[RecycleSourceKind.PARTIAL]
    state = census_state(cell, bundle_game_data)
    _goal, plan, planner_failed = plan_recycle_source(cell, state, bundle_game_data)
    assert planner_failed is False
    assert plan
    assert any(isinstance(a, RecycleAction) and a.code == "water_bow" for a in plan)
    assert any(isinstance(a, GatherAction) for a in plan)


def test_the_whole_grid_is_clean(bundle_game_data: GameData) -> None:
    results = run_census(bundle_game_data)
    assert len(results) == len(RecycleSourceKind)
    bugs = [r for r in results
            if r.gap == RecycleSourceGapClass.RECYCLE_SOURCE_BUG.value]
    assert bugs == []
    assert all(r.passed for r in results)


# ---------------------------------------------------------------------------
# A planner timeout is a BUG, never an explained gap.
# ---------------------------------------------------------------------------

def test_planner_timeout_is_a_bug_never_an_explained_gap(
        bundle_game_data: GameData) -> None:
    """A gap class that can swallow a planner bug destroys the census's value.
    `planner_failed` outranks EVERY world arm — even in a world where the recycle
    route is genuinely impossible (no workshop), the timeout is what gets
    reported, because a timed-out search never learned anything about that
    world."""
    cell = _cells(bundle_game_data)[RecycleSourceKind.PARTIAL]
    state = census_state(cell, bundle_game_data)
    assert classify_gap(cell, state, bundle_game_data, planner_failed=True) \
        is RecycleSourceGapClass.RECYCLE_SOURCE_BUG
    assert classify_gap(cell, state, _thin_gd(), planner_failed=True) \
        is RecycleSourceGapClass.RECYCLE_SOURCE_BUG


def test_a_timed_out_search_fails_every_cell_kind(
        bundle_game_data: GameData) -> None:
    """Including SAFETY: a plan that contains no recycle BECAUSE the planner ran
    out of budget is not a protection, it is a stalled bot."""
    for cell in recycle_source_grid(bundle_game_data):
        assert recycle_source_cell_verdict(cell, [], planner_failed=True) is False


# ---------------------------------------------------------------------------
# World-limit gap classes: earned by a fact about the WORLD, never the planner.
# ---------------------------------------------------------------------------

def _thin_gd() -> GameData:
    """A real GameData with the census items but NO map at all — so no workshop
    and no bank tile. Hand-stocked rather than mocked: the classifier must be
    exercised against genuine catalog objects."""
    gd = GameData()
    gd._item_stats = {
        "water_bow": ItemStats(code="water_bow", level=5, type_="weapon",
                               crafting_skill="weaponcrafting", crafting_level=5),
        "ash_plank": ItemStats(code="ash_plank", level=1, type_="resource",
                               crafting_skill="woodcutting", crafting_level=1),
    }
    gd._crafting_recipes = {"water_bow": {"ash_plank": 5},
                            "ash_plank": {"ash_wood": 10}}
    return gd


def _no_bank_gd() -> GameData:
    """The real bundle with every BANK tile removed from the map — the workshop
    (and so the recycle) is still there, but the bank copy can never be staged."""
    bundle = json.loads(BUNDLE.read_text())
    bundle["maps"] = [
        tile for tile in bundle["maps"]
        if (((tile.get("interactions") or {}).get("content") or {}).get("type")
            != "bank")]
    return GameData.from_cache_bundle(bundle)


def test_no_workshop_is_a_world_limit_not_a_planner_bug(
        bundle_game_data: GameData) -> None:
    cell = _cells(bundle_game_data)[RecycleSourceKind.LIVENESS]
    state = census_state(cell, bundle_game_data)
    assert classify_gap(cell, state, _thin_gd(), planner_failed=False) \
        is RecycleSourceGapClass.WORKSHOP_UNREACHABLE


def test_a_source_with_no_recipe_has_no_workshop(bundle_game_data: GameData) -> None:
    """`_workshop_reachable` reads the SOURCE's crafting skill; an item the
    catalog does not craft has none, so no workshop can recycle it."""
    cell = RecycleSourceCell(kind=RecycleSourceKind.LIVENESS, source="ash_wood",
                             material="ash_plank", needed=1, bag_copies=1,
                             bank_copies=0)
    state = census_state(_cells(bundle_game_data)[RecycleSourceKind.LIVENESS],
                         bundle_game_data)
    assert classify_gap(cell, state, bundle_game_data, planner_failed=False) \
        is RecycleSourceGapClass.WORKSHOP_UNREACHABLE


def test_no_bank_explains_a_banked_cell_only(bundle_game_data: GameData) -> None:
    no_bank = _no_bank_gd()
    banked = _cells(bundle_game_data)[RecycleSourceKind.BANKED]
    liveness = _cells(bundle_game_data)[RecycleSourceKind.LIVENESS]
    assert classify_gap(banked, census_state(banked, no_bank), no_bank,
                        planner_failed=False) \
        is RecycleSourceGapClass.BANK_UNREACHABLE
    # The bag-side cell's fuel is already in hand: a missing bank explains
    # nothing there, so it falls through to the residual.
    assert classify_gap(liveness, census_state(liveness, no_bank), no_bank,
                        planner_failed=False) \
        is RecycleSourceGapClass.RECYCLE_SOURCE_BUG


def test_every_route_open_falls_through_to_the_residual(
        bundle_game_data: GameData) -> None:
    """The fall-through, never a positive match: workshop on the map, bank on the
    map, planner conclusive — a FAIL here is the planner's."""
    cell = _cells(bundle_game_data)[RecycleSourceKind.LIVENESS]
    state = census_state(cell, bundle_game_data)
    assert classify_gap(cell, state, bundle_game_data, planner_failed=False) \
        is RecycleSourceGapClass.RECYCLE_SOURCE_BUG


# ---------------------------------------------------------------------------
# Cell construction: a cell that does not test what it names RAISES.
# ---------------------------------------------------------------------------

def test_grid_is_total_over_the_kind_registry(bundle_game_data: GameData) -> None:
    kinds = {cell.kind for cell in recycle_source_grid(bundle_game_data)}
    assert kinds == set(RecycleSourceKind)


def test_scenario_for_rejects_an_unregistered_kind(
        bundle_game_data: GameData) -> None:
    with pytest.raises(ValueError, match="no census scenario"):
        scenario_for("not_a_kind", bundle_game_data)  # type: ignore[arg-type]


def test_missing_catalog_item_fails_loud(bundle_game_data: GameData) -> None:
    """Use only game data or FAIL — never default."""
    gd = _thin_gd()
    with pytest.raises(ValueError, match="not in the game catalog"):
        scenario_for(RecycleSourceKind.SAFETY, gd)


def test_a_cell_that_already_holds_the_material_is_vacuous(
        bundle_game_data: GameData) -> None:
    cell = RecycleSourceCell(kind=RecycleSourceKind.LIVENESS, source="water_bow",
                             material="water_bow", needed=1, bag_copies=3,
                             bank_copies=0)
    state = census_state(cell, bundle_game_data)
    with pytest.raises(ValueError, match="the goal is satisfied"):
        _check_cell(cell, state, bundle_game_data, None)


def test_a_safety_cell_whose_source_is_licensed_raises(
        bundle_game_data: GameData) -> None:
    """Two axes: the authority licenses one. That is a LIVENESS cell wearing the
    SAFETY name — it must not ship."""
    cell = RecycleSourceCell(kind=RecycleSourceKind.SAFETY, source="copper_axe",
                             material="copper_bar", needed=6, bag_copies=2,
                             bank_copies=0)
    state = census_state(cell, bundle_game_data)
    with pytest.raises(ValueError, match="the authority licenses"):
        _check_cell(cell, state, bundle_game_data, None)


def test_a_safety_cell_with_another_recycle_route_raises(
        bundle_game_data: GameData) -> None:
    """The axe is protected, but a spare water_bow (whose recipe also yields the
    material? no — a spare copper_dagger, whose recipe IS copper_bar) offers the
    planner a DIFFERENT licensed recycle for the same material. The cell would
    then be safe for the wrong reason."""
    cell = RecycleSourceCell(kind=RecycleSourceKind.SAFETY, source="copper_axe",
                             material="copper_bar", needed=6, bag_copies=1,
                             bank_copies=0)
    state = census_state(cell, bundle_game_data)
    state = dataclasses.replace(
        state, inventory={**state.inventory, "copper_dagger": 3})
    with pytest.raises(ValueError, match="is recoverable"):
        _check_cell(cell, state, bundle_game_data, None)


def test_a_partial_cell_that_is_fully_recoverable_raises(
        bundle_game_data: GameData) -> None:
    cell = RecycleSourceCell(kind=RecycleSourceKind.PARTIAL, source="water_bow",
                             material="ash_plank", needed=4, bag_copies=3,
                             bank_copies=0)
    state = census_state(cell, bundle_game_data)
    with pytest.raises(ValueError, match="is not a PARTIAL cover"):
        _check_cell(cell, state, bundle_game_data, None)


def test_a_liveness_cell_the_recycle_cannot_serve_raises(
        bundle_game_data: GameData) -> None:
    cell = RecycleSourceCell(kind=RecycleSourceKind.LIVENESS, source="water_bow",
                             material="ash_plank", needed=9, bag_copies=3,
                             bank_copies=0)
    state = census_state(cell, bundle_game_data)
    with pytest.raises(ValueError, match="recoverable 4 < needed 9"):
        _check_cell(cell, state, bundle_game_data, None)


def test_a_banked_cell_holding_a_bag_copy_raises(
        bundle_game_data: GameData) -> None:
    cell = RecycleSourceCell(kind=RecycleSourceKind.BANKED, source="water_bow",
                             material="ash_plank", needed=4, bag_copies=3,
                             bank_copies=3)
    state = census_state(cell, bundle_game_data)
    with pytest.raises(ValueError, match="BANK ONLY"):
        _check_cell(cell, state, bundle_game_data, None)


def test_a_cell_a_higher_band_preempted_raises(bundle_game_data: GameData) -> None:
    """If a guard or a collect-band candidate won, the plan is not this cell's
    answer — the cell never reached the planner it names."""
    cell = _cells(bundle_game_data)[RecycleSourceKind.LIVENESS]
    state = census_state(cell, bundle_game_data)
    with pytest.raises(ValueError, match="preempted the objective step"):
        _check_cell(cell, state, bundle_game_data, WaitGoal())


# ---------------------------------------------------------------------------
# Verdict + reporting.
# ---------------------------------------------------------------------------

def test_verdict_rejects_an_unknown_kind(bundle_game_data: GameData) -> None:
    cell = RecycleSourceCell(kind="exploding", source="water_bow",  # type: ignore[arg-type]
                             material="ash_plank", needed=4, bag_copies=3,
                             bank_copies=0)
    with pytest.raises(ValueError, match="unknown cell kind"):
        recycle_source_cell_verdict(cell, [], planner_failed=False)


def test_banked_verdict_needs_the_withdraw_BEFORE_the_recycle(
        bundle_game_data: GameData) -> None:
    cell = _cells(bundle_game_data)[RecycleSourceKind.BANKED]
    recycle = RecycleAction(code="water_bow", quantity=1,
                            workshop_location=(1, 1))
    withdraw = WithdrawItemAction(code="water_bow", quantity=1,
                                  bank_location=(2, 2), accessible=True)
    assert recycle_source_cell_verdict(cell, [withdraw, recycle], False) is True
    assert recycle_source_cell_verdict(cell, [recycle, withdraw], False) is False
    assert recycle_source_cell_verdict(cell, [recycle], False) is False
    assert recycle_source_cell_verdict(cell, [withdraw], False) is False


def test_partial_verdict_needs_BOTH_routes(bundle_game_data: GameData) -> None:
    cell = _cells(bundle_game_data)[RecycleSourceKind.PARTIAL]
    recycle = RecycleAction(code="water_bow", quantity=1,
                            workshop_location=(1, 1))
    gather = GatherAction(resource_code="ash_tree", locations=frozenset({(1, 1)}))
    assert recycle_source_cell_verdict(cell, [recycle, gather], False) is True
    assert recycle_source_cell_verdict(cell, [recycle], False) is False
    assert recycle_source_cell_verdict(cell, [gather], False) is False


def test_run_cell_records_the_authority_and_the_plan(
        bundle_game_data: GameData) -> None:
    cell = _cells(bundle_game_data)[RecycleSourceKind.LIVENESS]
    result = run_cell(cell, bundle_game_data)
    assert result.passed is True
    assert result.gap is None
    assert result.recoverable == 4
    assert result.destroyable == 2
    assert result.goal == "GatherMaterials(ash_plank, {ash_plank:4})"
    assert any("Recycle(water_bow" in leg for leg in result.plan)


def test_summary_and_matrix_report_the_residual() -> None:
    passing = RecycleSourceResult(
        kind="liveness", source="water_bow", material="ash_plank", needed=4,
        recoverable=4, destroyable=2, goal="GatherMaterials(ash_plank)",
        plan=("Recycle(water_bow×1)",), planner_failed=False, passed=True, gap=None)
    failing = RecycleSourceResult(
        kind="partial", source="water_bow", material="ash_plank", needed=8,
        recoverable=4, destroyable=2, goal="GatherMaterials(ash_plank)",
        plan=(), planner_failed=True, passed=False,
        gap=RecycleSourceGapClass.RECYCLE_SOURCE_BUG.value)
    assert summary_line([passing, failing]) == (
        "2 cells; PASS 1; recycle_source_bug 1")
    doc = render_matrix([passing, failing])
    assert "| liveness | water_bow | ash_plank | 4 | 4 | 2 | PASS |" in doc
    assert "**recycle_source_bug**" in doc
    assert "(empty)" in doc


def test_census_ctx_leaves_the_step_profile_to_the_arbiter() -> None:
    ctx = census_ctx()
    assert ctx.step_profile == {}
    assert ctx.bank_accessible is True
    assert ctx.combat_monster is None
