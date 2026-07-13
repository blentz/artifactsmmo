"""Generate docs/behavioral_completeness/INVENTORY_MATRIX.md from the
committed bundle by running the inventory keep/disposal census (item-
protection-authority epic, Task 5) over the full `KeepReason`-derived grid.

Offline + deterministic (no live API): loads
tests/test_ai/scenarios/fixtures/gamedata_bundle.json — the same fixture the
craft census and the scenario suite plan against.

Parallel: like the craft census, every cell is an independent planner drive.
We fan the (few, ~56) cells across a process pool (each worker loads GameData
ONCE via the initializer). Run:

    uv run python scripts/gen_inventory_completeness.py [max_workers]

CI gate: pass `--check` to exit non-zero when EITHER of two obligations trips:

  * Gate 1 — any cell classifies `INVENTORY_BUG` (the must-be-zero
    residual, mirroring the craft census's `planner_bug`).
  * Gate 2 — reason coverage (the anti-rot mechanism): every `KeepReason`
    except `CURRENCY` must have at least one PASSing LIVENESS cell, or a
    future protection reason could be added without ever proving its
    surplus is still disposable.

`--check` still writes the doc, so a failing pipeline also surfaces the
regenerated MATRIX:

    uv run python scripts/gen_inventory_completeness.py --check [max_workers]

Task 5 lands this RED on purpose: the disposal consumers (`bank_selection`,
`recycle_surplus`, `guards`) have not been migrated off the old `frozenset`
code-set blankets yet (item-protection-authority epic Tasks 6-9), so several
in-bag LIVENESS cells fail today. That RED state is the census working, not a
bug in the census.
"""

import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.inventory_keep import KeepReason
from artifactsmmo_cli.audit.inventory_census import (
    CellResult,
    census_cells,
    reason_coverage,
    run_cell,
)
from artifactsmmo_cli.audit.inventory_completeness import InventoryCell
from artifactsmmo_cli.audit.inventory_report import render_matrix, summary_line

BUNDLE = Path("tests/test_ai/scenarios/fixtures/gamedata_bundle.json")
OUT_DIR = Path("docs/behavioral_completeness")

# Per-worker GameData, built once by the pool initializer from the bundle dict.
_GD: GameData | None = None


def _init_worker(bundle_dict: dict) -> None:
    global _GD
    _GD = GameData.from_cache_bundle(bundle_dict)


def _run_one(cell: InventoryCell) -> CellResult:
    assert _GD is not None  # set by _init_worker in every pool worker
    return run_cell(cell, _GD)


def main() -> None:
    argv = sys.argv[1:]
    check = "--check" in argv
    positional = [a for a in argv if not a.startswith("--")]
    max_workers = int(positional[0]) if positional else (os.cpu_count() or 4)
    bundle_dict = json.loads(BUNDLE.read_text())
    gd = GameData.from_cache_bundle(bundle_dict)
    cells = census_cells(gd)
    start = time.monotonic()
    print(f"census: {len(cells)} cells on {max_workers} workers", file=sys.stderr)
    results: list[CellResult] = []
    with ProcessPoolExecutor(
        max_workers=max_workers, initializer=_init_worker, initargs=(bundle_dict,)
    ) as ex:
        for i, res in enumerate(ex.map(_run_one, cells, chunksize=1), start=1):
            results.append(res)
    coverage = reason_coverage(results)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "INVENTORY_MATRIX.md").write_text(render_matrix(results, coverage))
    print(f"census done in {time.monotonic() - start:.0f}s", file=sys.stderr)
    print(summary_line(results))
    if not check:
        return

    bugs = [r for r in results if r.gap == "inventory_bug"]
    missing_coverage = [
        reason for reason in KeepReason
        if reason is not KeepReason.CURRENCY and not coverage[reason]
    ]

    if bugs:
        print(f"GATE 1 FAILED: {len(bugs)} INVENTORY_BUG cell(s):", file=sys.stderr)
        for r in bugs:
            print(f"  {r.reason} {r.cap}/{r.kind}/{r.pressure} ({r.code})",
                  file=sys.stderr)
    else:
        print("GATE 1 CLEAN: 0 INVENTORY_BUG cells.", file=sys.stderr)

    if missing_coverage:
        names = ", ".join(reason.value for reason in missing_coverage)
        print(f"GATE 2 FAILED: {len(missing_coverage)} KeepReason(s) with no "
              f"PASSing LIVENESS cell: {names}", file=sys.stderr)
    else:
        print("GATE 2 CLEAN: every non-CURRENCY KeepReason has a PASSing "
              "LIVENESS cell.", file=sys.stderr)

    if bugs or missing_coverage:
        sys.exit(1)


if __name__ == "__main__":
    main()
