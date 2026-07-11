"""Generate docs/craft_completeness/{MATRIX,BACKLOG}.md from the committed
bundle by running the Phase-1 census over every craftable recipe.

Offline + deterministic (no live API): loads
tests/test_ai/scenarios/fixtures/gamedata_bundle.json.

Parallel: the census is embarrassingly parallel — every (recipe, cell) is an
independent planner drive. We fan the cells across a process pool (each worker
loads GameData ONCE via the initializer, so the large bundle is parsed per
worker, never per cell). Wall time is roughly serial/(cores). Determinism is
unchanged: each cell's planner run is independent with its own per-process
memo; only the budget-bound cells (deep chains that hit the 10 s wall) vary
between regens, exactly as in the serial run. Run:

    uv run python scripts/gen_craft_completeness.py [max_workers]
"""

import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.audit.craft_census import CellResult, craftable_recipes, run_cell
from artifactsmmo_cli.audit.craft_completeness import CraftCell, craft_grid
from artifactsmmo_cli.audit.craft_report import (
    render_backlog,
    render_matrix,
    summary_line,
)

BUNDLE = Path("tests/test_ai/scenarios/fixtures/gamedata_bundle.json")
OUT_DIR = Path("docs/craft_completeness")

# Per-worker GameData, built once by the pool initializer from the bundle dict.
_GD: GameData | None = None


def _init_worker(bundle_dict: dict) -> None:
    global _GD
    _GD = GameData.from_cache_bundle(bundle_dict)


def _run_one(work: tuple[str, CraftCell]) -> CellResult:
    recipe, cell = work
    assert _GD is not None  # set by _init_worker in every pool worker
    return run_cell(recipe, cell, _GD)


def main() -> None:
    max_workers = int(sys.argv[1]) if len(sys.argv) > 1 else (os.cpu_count() or 4)
    bundle_dict = json.loads(BUNDLE.read_text())
    gd = GameData.from_cache_bundle(bundle_dict)
    recipes = craftable_recipes(gd)
    work: list[tuple[str, CraftCell]] = [
        (recipe, cell) for recipe in recipes for cell in craft_grid(recipe, gd)
    ]
    start = time.monotonic()
    print(f"census: {len(recipes)} recipes / {len(work)} cells on {max_workers} workers",
          file=sys.stderr)
    results: list[CellResult] = []
    with ProcessPoolExecutor(
        max_workers=max_workers, initializer=_init_worker, initargs=(bundle_dict,)
    ) as ex:
        # chunksize=1: cells are wildly uneven (instant vs 10 s budget wall), so
        # per-cell dispatch keeps every worker busy instead of a slow chunk
        # stranding a core.
        for i, res in enumerate(ex.map(_run_one, work, chunksize=1), start=1):
            results.append(res)
            if i % 100 == 0:
                print(f"[{i}/{len(work)}] {time.monotonic() - start:6.0f}s", file=sys.stderr)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "MATRIX.md").write_text(render_matrix(results))
    (OUT_DIR / "BACKLOG.md").write_text(render_backlog(results))
    print(f"census done in {time.monotonic() - start:.0f}s", file=sys.stderr)
    print(summary_line(results))


if __name__ == "__main__":
    main()
