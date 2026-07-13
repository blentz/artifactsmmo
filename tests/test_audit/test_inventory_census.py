"""Inventory-completeness census engine (item-protection-authority epic,
Task 5): drives the Task-4 pure cores over the KeepReason-derived grid and
records a flat CellResult, plus the reason-coverage table Gate 2 reads."""

import json
from pathlib import Path

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.inventory_keep import KeepReason
from artifactsmmo_cli.audit.inventory_census import (
    CellResult,
    census_cells,
    reason_coverage,
    run_cell,
    run_census,
)
from artifactsmmo_cli.audit.inventory_completeness import InventoryCell, inventory_grid

BUNDLE = Path("tests/test_ai/scenarios/fixtures/gamedata_bundle.json")


def _gd() -> GameData:
    return GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))


def _cell_of(cells: list[InventoryCell], reason: KeepReason, kind: str,
             cap: str, pressure: str) -> InventoryCell:
    matches = [c for c in cells if c.reason is reason and c.kind == kind
               and c.cap == cap and c.pressure == pressure]
    assert len(matches) == 1
    return matches[0]


def test_run_cell_records_a_passing_safety_cell() -> None:
    """A SAFETY cell that holds exactly `keep` copies passes with no gap —
    e.g. CURRENCY safety, which nothing may ever dispose."""
    gd = _gd()
    cells = inventory_grid(gd)
    cell = _cell_of(cells, KeepReason.CURRENCY, "safety", "in_bag", "slot_full")
    result = run_cell(cell, gd)
    assert result.reason == "currency"
    assert result.cap == "in_bag"
    assert result.kind == "safety"
    assert result.pressure == "slot_full"
    assert result.code == cell.code
    assert result.held == cell.held
    assert result.keep == cell.keep
    assert result.passed is True
    assert result.gap is None


def test_run_cell_records_gap_on_failure() -> None:
    """A FAILing cell records `passed=False` and the classified gap.

    GOAL_MATERIALS' in_bag LIVENESS cell is the residual failure after the Task-6
    deposit migration: `select_bank_deposits` DOES offer the surplus ash_wood, but
    the arbiter takes the objective-step Craft instead of the deposit guard, so no
    disposal happens in the plan — an INVENTORY_BUG the census keeps flagging until
    the ladder-ordering residual is closed. (WORKING_KIT, the cell this test used
    to pin RED, now PASSes: see
    `test_working_kit_liveness_cell_PASSES_against_the_real_arbiter`.)"""
    gd = _gd()
    cells = inventory_grid(gd)
    cell = _cell_of(cells, KeepReason.GOAL_MATERIALS, "liveness", "in_bag", "slot_full")
    result = run_cell(cell, gd)
    assert result.reason == "goal_materials"
    assert result.passed is False
    assert result.gap == "inventory_bug"


def test_census_cells_is_the_grid() -> None:
    """census_cells is the single source the generator and tests share — it
    IS inventory_grid, not a re-derivation of it."""
    gd = _gd()
    assert census_cells(gd) == inventory_grid(gd)


def test_run_census_full_grid_with_progress() -> None:
    """run_census over the full grid yields one CellResult per cell and fires
    the progress callback once per cell, in order."""
    gd = _gd()
    cells = inventory_grid(gd)
    seen: list[tuple[int, int]] = []

    def progress(done: int, total: int) -> None:
        seen.append((done, total))

    results = run_census(gd, cells, progress=progress)
    assert len(results) == len(cells)
    assert all(isinstance(r, CellResult) for r in results)
    assert seen == [(i, len(cells)) for i in range(1, len(cells) + 1)]


def test_run_census_no_progress() -> None:
    """run_census with no progress callback (covers the progress-None branch)
    still reaches every cell."""
    gd = _gd()
    cells = inventory_grid(gd)[:3]
    results = run_census(gd, cells)
    assert len(results) == 3


def test_reason_coverage_currency_exempt_even_with_no_liveness_cell() -> None:
    """CURRENCY has no LIVENESS cell at all (the declared exemption), yet
    reason_coverage reports it True unconditionally — never penalized for the
    one reason that structurally cannot earn a passing liveness cell."""
    gd = _gd()
    results = run_census(gd, inventory_grid(gd))
    coverage = reason_coverage(results)
    assert coverage[KeepReason.CURRENCY] is True
    assert not any(r.kind == "liveness" and r.reason == "currency" for r in results)


def test_reason_coverage_after_the_deposit_migration() -> None:
    """Task 6 (deposit -> `bankable`) turned FOUR of the five uncovered reasons
    green: HEALING_CONSUMABLE, COMBAT_WEAPON, WORKING_KIT and COMMITTED_RECIPE all
    now have a PASSing liveness cell, because DepositAll sheds the surplus above
    each one's keep quantity instead of blanket-keeping the code.

    GOAL_MATERIALS remains uncovered: its surplus IS offered by
    `select_bank_deposits`, but the arbiter takes the objective-step Craft over the
    deposit guard, so nothing is shed in the plan (a ladder-ordering residual, not
    a keep-authority one)."""
    gd = _gd()
    results = run_census(gd, inventory_grid(gd))
    coverage = reason_coverage(results)
    uncovered = {r for r, ok in coverage.items() if not ok}
    assert uncovered == {KeepReason.GOAL_MATERIALS}
    assert coverage[KeepReason.HEALING_CONSUMABLE] is True
    assert coverage[KeepReason.COMBAT_WEAPON] is True
    assert coverage[KeepReason.WORKING_KIT] is True
    assert coverage[KeepReason.COMMITTED_RECIPE] is True
    assert coverage[KeepReason.ACTIVE_TASK] is True
    assert coverage[KeepReason.EQUIPPED] is True
    assert coverage[KeepReason.GEAR_DEMAND] is True
    assert coverage[KeepReason.RECIPE_DEMAND] is True


def test_reason_coverage_total_over_keepreason() -> None:
    """reason_coverage is total over the enum, not merely over what appears in
    the results list — every KeepReason member has a key."""
    gd = _gd()
    results = run_census(gd, inventory_grid(gd))
    coverage = reason_coverage(results)
    assert set(coverage) == set(KeepReason)


def test_census_full_grid_matches_the_post_deposit_migration_baseline() -> None:
    """The baseline after Task 7b (WORKING_KIT / COMBAT_WEAPON filed under the
    OWNED cap as well): 66 cells, 62 PASS, 3 INVENTORY_BUG, 1 NO_ROUTE_AVAILABLE
    — down from the Task-5 RED baseline of 42 PASS / 13 INVENTORY_BUG.

    The grid GREW by 10 because cells are DERIVED from the cap sets: the two kit
    reasons now feed `keep_owned` too, so each gained an owned column (3 SAFETY +
    2 LIVENESS cells). All 10 PASS — a banked kit surplus is genuinely destroyed
    by the production recycle route, and the last copy survives.

    The 3 residual INVENTORY_BUG cells are UNCHANGED by this task and are NOT
    deposit-selection bugs:
      * goal_materials in_bag/liveness (x2 pressure states) — the surplus IS
        offered by `select_bank_deposits`; the arbiter takes the objective-step
        Craft instead of the deposit guard, so the plan sheds nothing;
      * active_task owned/liveness/slot_full — a DESTRUCTIVE-route cell
        (recycle/sell/delete), owned by the `destroyable` migration (Tasks 8-9).

    A regression here means either a consumer got migrated (should be caught by
    the owning task, not silently here) or the census stopped seeing the bug class
    it exists to catch."""
    gd = _gd()
    results = run_census(gd, inventory_grid(gd))
    assert len(results) == 66
    passed = sum(1 for r in results if r.passed)
    assert passed == 62
    # The kit reasons' new OWNED cells all pass — the ownership cap is both SAFE
    # (the last tool/weapon survives) and LIVE (the surplus above it is shed).
    kit_owned = [r for r in results if r.cap == "owned"
                 and r.reason in ("working_kit", "combat_weapon")]
    assert len(kit_owned) == 10
    assert all(r.passed for r in kit_owned)
    gap_counts: dict[str, int] = {}
    for r in results:
        if r.gap is not None:
            gap_counts[r.gap] = gap_counts.get(r.gap, 0) + 1
    assert gap_counts == {"inventory_bug": 2, "no_route_available": 1,
                          "venue_unreachable": 1}
    bugs = {(r.reason, r.cap, r.pressure) for r in results if r.gap == "inventory_bug"}
    assert bugs == {
        ("goal_materials", "in_bag", "slot_full"),
        ("goal_materials", "in_bag", "qty_full"),
    }
    # `active_task owned/slot_full` (golden_egg) left INVENTORY_BUG when the SELL
    # migration (Task 8) taught the classifier what a sale actually costs: its only
    # buyer is the `nomadic_merchant` EVENT NPC, dormant in this bundle, so there is
    # NO executable sale — and with no recipe there is no recycle, and slot pressure
    # deliberately does not open DELETE. Production is right to keep holding it.
    unreachable = {(r.reason, r.cap, r.pressure) for r in results
                   if r.gap == "venue_unreachable"}
    assert unreachable == {("active_task", "owned", "slot_full")}
