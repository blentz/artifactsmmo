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
    """The live hoard bug: WORKING_KIT's in_bag LIVENESS cell fails because
    `bank_selection` still blanket-keeps the best gathering tool, so the
    CellResult records passed=False with an INVENTORY_BUG gap."""
    gd = _gd()
    cells = inventory_grid(gd)
    cell = _cell_of(cells, KeepReason.WORKING_KIT, "liveness", "in_bag", "slot_full")
    result = run_cell(cell, gd)
    assert result.reason == "working_kit"
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


def test_reason_coverage_reports_the_known_red_baseline() -> None:
    """The RED baseline this task must faithfully report: the five in-bag-only
    reasons whose deposit route is still blanket-keep have NO passing
    liveness cell; the owned-cap reasons (and ACTIVE_TASK's owned side) do."""
    gd = _gd()
    results = run_census(gd, inventory_grid(gd))
    coverage = reason_coverage(results)
    uncovered = {r for r, ok in coverage.items() if not ok}
    assert uncovered == {
        KeepReason.HEALING_CONSUMABLE,
        KeepReason.COMBAT_WEAPON,
        KeepReason.WORKING_KIT,
        KeepReason.COMMITTED_RECIPE,
        KeepReason.GOAL_MATERIALS,
    }
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


def test_census_full_grid_matches_expected_red_baseline() -> None:
    """The documented Task-5 RED baseline: 56 cells, 42 PASS, 13
    INVENTORY_BUG, 1 NO_ROUTE_AVAILABLE. A regression here means either a
    consumer got migrated (should be caught by Tasks 6-9, not silently here)
    or the census stopped seeing the bug class it exists to catch."""
    gd = _gd()
    results = run_census(gd, inventory_grid(gd))
    assert len(results) == 56
    passed = sum(1 for r in results if r.passed)
    assert passed == 42
    gap_counts: dict[str, int] = {}
    for r in results:
        if r.gap is not None:
            gap_counts[r.gap] = gap_counts.get(r.gap, 0) + 1
    assert gap_counts == {"inventory_bug": 13, "no_route_available": 1}
