"""Inventory keep/disposal census engine (item-protection-authority epic,
Task 5). Drives the Task-4 pure cores (`inventory_grid` -> `census_state` ->
`plan_inventory` -> `inventory_cell_verdict` -> `classify_gap`) over the full
census grid and records a flat, render-ready `CellResult` per cell, plus the
reason-coverage table the `--check` anti-rot gate reads. No decision logic
lives here — it is the orchestration layer between the proven cores and the
doc renderer / generator script, mirroring `audit/craft_census.py`."""

from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.inventory_keep import KeepReason
from artifactsmmo_cli.audit.inventory_completeness import (
    InventoryCell,
    census_state,
    classify_gap,
    inventory_cell_verdict,
    inventory_grid,
    plan_inventory,
)


@dataclass(frozen=True)
class CellResult:
    """One census outcome: a `KeepReason` exercised at one (cap, kind, pressure,
    band) cell. `passed` mirrors `inventory_cell_verdict`; `gap` is the
    `InventoryGapClass` value string on failure (None on pass)."""

    reason: str
    cap: str
    kind: str
    pressure: str
    band: str
    code: str
    held: int
    keep: int
    passed: bool
    gap: str | None


def run_cell(cell: InventoryCell, game_data: GameData) -> CellResult:
    """Drive the Task-4 cores for one grid cell and record the outcome.

    `planner_failed` (an inconclusive search — budget timeout or node cap) rides from
    `plan_inventory` into `classify_gap`, which turns it into the UNEXPLAINED residual:
    a gap class may only be earned by a fact about the WORLD, never by the planner
    running out of budget (see `classify_gap`)."""
    state = census_state(cell.reason, cell.cap, cell.pressure, cell.held,
                         game_data, cell.band)
    plan, planner_failed = plan_inventory(cell, state, game_data)
    passed = inventory_cell_verdict(cell, plan, state, game_data)
    gap = (None if passed
           else classify_gap(cell, state, game_data, planner_failed).value)
    return CellResult(
        reason=cell.reason.value,
        cap=cell.cap,
        kind=cell.kind,
        pressure=cell.pressure,
        band=cell.band,
        code=cell.code,
        held=cell.held,
        keep=cell.keep,
        passed=passed,
        gap=gap,
    )


# Process-local handle set once per worker by `_init_census_worker`, so the
# (large) GameData is pickled once at pool startup rather than once per cell.
_WORKER_GAME_DATA: GameData | None = None


def _init_census_worker(game_data: GameData) -> None:
    global _WORKER_GAME_DATA
    _WORKER_GAME_DATA = game_data


def _run_cell_in_worker(cell: InventoryCell) -> CellResult:
    assert _WORKER_GAME_DATA is not None
    return run_cell(cell, _WORKER_GAME_DATA)


def run_census(
    game_data: GameData,
    cells: list[InventoryCell],
    progress: Callable[[int, int], None] | None = None,
    *,
    max_workers: int | None = None,
) -> list[CellResult]:
    """Run the census over `cells` (the caller supplies the grid — the
    generator passes `inventory_grid(gd)`; tests pass a tiny explicit list).
    `progress(done, total)` is called after each cell if supplied.

    Each cell is an INDEPENDENT, deterministic, pure-CPU planner search
    (`plan_inventory` runs `history=None`), so cells are fanned out across a
    process pool — a GOAP search is GIL-bound, so processes (not threads) are
    what give the speedup. `ProcessPoolExecutor.map` yields results in `cells`
    order, so both the returned list and the `progress` sequence keep the exact
    order the serial loop produced."""
    if not cells:
        return []
    results: list[CellResult] = []
    total = len(cells)
    with ProcessPoolExecutor(
        max_workers=max_workers,
        initializer=_init_census_worker,
        initargs=(game_data,),
    ) as executor:
        for done, result in enumerate(
            executor.map(_run_cell_in_worker, cells), start=1
        ):
            results.append(result)
            if progress is not None:
                progress(done, total)
    return results


def reason_coverage(results: list[CellResult]) -> dict[KeepReason, bool]:
    """Every `KeepReason` -> whether it has earned at least one PASSing
    LIVENESS cell — the anti-rot mechanism (Task 5 Gate 2). `CURRENCY` is the
    single declared exemption (`KEEP_ALL` means nothing is ever disposable, so
    it can never earn a passing liveness cell and is reported True
    unconditionally); every other reason must prove its surplus is sheddable
    or this reports False, which the `--check` gate treats as a failure.

    Total over `KeepReason` (not merely over what appears in `results`): a
    reason `inventory_grid` silently dropped would be UNCOVERED here too,
    rather than absent from the dict — a future reason cannot go unproven by
    quietly not showing up."""
    passing = {
        KeepReason(r.reason) for r in results if r.kind == "liveness" and r.passed
    }
    return {
        reason: reason is KeepReason.CURRENCY or reason in passing
        for reason in KeepReason
    }


def census_cells(game_data: GameData) -> list[InventoryCell]:
    """The full census grid, derived from the `KeepReason` registry
    (`inventory_grid`) — the single source the generator and tests both use so
    neither can drift from the other."""
    return inventory_grid(game_data)
