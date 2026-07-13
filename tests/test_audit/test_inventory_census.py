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
             cap: str, pressure: str, band: str = "in_band") -> InventoryCell:
    matches = [c for c in cells if c.reason is reason and c.kind == kind
               and c.cap == cap and c.pressure == pressure and c.band == band]
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
    assert result.band == "in_band"
    assert result.code == cell.code
    assert result.held == cell.held
    assert result.keep == cell.keep
    assert result.passed is True
    assert result.gap is None


def test_run_cell_records_gap_on_failure() -> None:
    """A FAILing cell records `passed=False` and the classified gap.

    ACTIVE_TASK's owned LIVENESS cell is a WORLD-limit failure, not a bug:
    `golden_egg` has no recipe (no RECYCLE route), its only buyer is the dormant
    event `nomadic_merchant` (no SELL route), and slot pressure deliberately does
    not open the DELETE route — so production is right to keep holding it, and the
    cell classifies VENUE_UNREACHABLE. It fails identically in BOTH bands: the
    limit is the WORLD's, and the character's level has nothing to do with it."""
    gd = _gd()
    cells = inventory_grid(gd)
    for band in ("in_band", "far"):
        cell = _cell_of(cells, KeepReason.ACTIVE_TASK, "liveness", "owned",
                        "slot_full", band)
        result = run_cell(cell, gd)
        assert result.reason == "active_task"
        assert result.band == band
        assert result.passed is False
        assert result.gap == "venue_unreachable"


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


def test_reason_coverage_is_complete() -> None:
    """EVERY non-CURRENCY KeepReason now has a PASSing LIVENESS cell (census
    Gate 2 CLEAN).

    Task 6 (deposit -> `bankable`) turned four of the five uncovered reasons
    green: HEALING_CONSUMABLE, COMBAT_WEAPON, WORKING_KIT and COMMITTED_RECIPE all
    got a PASSing liveness cell, because DepositAll sheds the surplus above each
    one's keep quantity instead of blanket-keeping the code.

    GOAL_MATERIALS was the last one, and it was NOT a deposit-selection gap:
    `select_bank_deposits` DID offer the surplus ash_wood, but CRAFT_RELIEF (which
    out-ranks DEPOSIT_FULL) fired on a craft that only freed QUANTITY while ADDING
    a stack, preempting the deposit that would actually have relieved the
    slot-limited bag. The slot gate in `craft_relief._slot_delta` closed it."""
    gd = _gd()
    results = run_census(gd, inventory_grid(gd))
    coverage = reason_coverage(results)
    uncovered = {r for r, ok in coverage.items() if not ok}
    assert uncovered == set()
    assert coverage[KeepReason.GOAL_MATERIALS] is True
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


def test_census_full_grid_reaches_zero_inventory_bug() -> None:
    """THE ACCEPTANCE: 152 cells, 144 PASS, **0 INVENTORY_BUG**.

    The grid DOUBLED (66 -> 132) when the LEVEL-DISTANCE band was added, and then
    grew to 152 because cells are DERIVED from the cap sets and COMMITTED_RECIPE /
    GOAL_MATERIALS joined `OWNED_REASONS` (an owned column each: 3 SAFETY +
    2 LIVENESS, per band).

    The band dimension landed RED at 1 INVENTORY_BUG —
    `recipe_demand owned/safety/qty_full/far` (`copper_bar`, held 40, keep 40): at
    19 levels' distance `level_distance_keep_ceiling` clamped `keep_owned` from 40
    to 5 and production DELETED 35 copies of a material the recipe demands. That
    was the shared root cause of both live defects (surplus heals destroyable at
    distance; the bank drain pulling a live task chain's own ore). The ceiling is
    now a SPACE policy only (`useful_quantity_cap(level_ceiling=False)` on the
    ownership arm), so the two bands agree cell-for-cell — which is the invariant
    the band dimension exists to enforce.

    The 8 residual FAILs are WORLD limits, not planner defects. EVERY ONE is an
    `owned/liveness/SLOT_FULL` cell, and they all fail for the same designed
    reason: an owned cell's bank is FULL by construction (banking is not an
    ownership route), and slot pressure deliberately does NOT open the DELETE route
    (`guards._fires` is quantity-only, so slot pressure never deletes what banking
    could have saved). With no recycle route either, production has nothing to fire
    and is right to keep holding. Their `owned/qty_full` twins — where the DELETE
    watermark IS reached — all PASS.

    A regression here means either a consumer got migrated (should be caught by
    the owning task, not silently here) or the census stopped seeing the bug class
    it exists to catch."""
    gd = _gd()
    results = run_census(gd, inventory_grid(gd))
    assert len(results) == 152
    passed = sum(1 for r in results if r.passed)
    assert passed == 144
    # The kit reasons' OWNED cells all pass — the ownership cap is both SAFE
    # (the last tool/weapon survives) and LIVE (the surplus above it is shed).
    kit_owned = [r for r in results if r.cap == "owned"
                 and r.reason in ("working_kit", "combat_weapon")]
    assert len(kit_owned) == 20
    assert all(r.passed for r in kit_owned)
    gap_counts: dict[str, int] = {}
    for r in results:
        if r.gap is not None:
            gap_counts[r.gap] = gap_counts.get(r.gap, 0) + 1
    assert gap_counts == {"no_route_available": 6, "venue_unreachable": 2}
    # THE residual class is EMPTY.
    assert not any(r.gap == "inventory_bug" for r in results)
    # ...and it is empty in BOTH bands, cell-for-cell: the level-distance ceiling
    # no longer moves a single protection. A FAR cell that passes only because its
    # cap shrank is impossible by construction (`keep` is the IN_BAND demand).
    by_key = {(r.reason, r.cap, r.kind, r.pressure, r.band): r for r in results}
    for (reason, cap, kind, pressure, band), r in by_key.items():
        if band != "in_band":
            continue
        twin = by_key[(reason, cap, kind, pressure, "far")]
        assert (twin.keep, twin.held) == (r.keep, r.held), (reason, cap, pressure)
        assert twin.passed == r.passed, (reason, cap, kind, pressure)
    # Every FAIL is an owned/liveness/slot_full cell — the designed dead end
    # (bank full by construction + slot pressure never opens DELETE).
    for r in results:
        if not r.passed:
            assert (r.cap, r.kind, r.pressure) == ("owned", "liveness", "slot_full"), r
    unreachable = {(r.reason, r.cap, r.pressure) for r in results
                   if r.gap == "venue_unreachable"}
    assert unreachable == {("active_task", "owned", "slot_full")}
