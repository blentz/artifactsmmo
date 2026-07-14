"""Generate docs/behavioral_completeness/RECYCLE_SOURCE_MATRIX.md by running the
recycle-as-a-SOURCE census (recycle-as-acquisition epic, Task 8) over its
four-cell grid.

Offline + deterministic (no live API): loads
tests/test_ai/scenarios/fixtures/gamedata_bundle.json — the same fixture the
craft and inventory censuses plan against.

Serial, unlike its two siblings: this grid is FOUR cells (they are ~56 and
~1900), each a single `StrategyArbiter.select` drive, so a process pool would
cost more to spin up than the census takes to run.

    uv run python scripts/gen_recycle_source_completeness.py

CI gate: pass `--check` to exit non-zero when any cell classifies
`recycle_source_bug` — the must-be-zero residual, mirroring the craft census's
`planner_bug` and the inventory census's `inventory_bug`. A planner TIMEOUT is
one of them: it is classified `recycle_source_bug` unconditionally and before
every world arm, because a gap class that can swallow a planner bug destroys the
census's entire value.

`--check` still writes the doc, so a failing pipeline also surfaces the
regenerated MATRIX:

    uv run python scripts/gen_recycle_source_completeness.py --check
"""

import json
import sys
import time
from pathlib import Path

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.audit.recycle_source_completeness import (
    RecycleSourceGapClass,
    render_matrix,
    run_census,
    summary_line,
)

BUNDLE = Path("tests/test_ai/scenarios/fixtures/gamedata_bundle.json")
OUT_DIR = Path("docs/behavioral_completeness")


def main() -> None:
    check = "--check" in sys.argv[1:]
    game_data = GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))
    start = time.monotonic()
    results = run_census(game_data)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "RECYCLE_SOURCE_MATRIX.md").write_text(render_matrix(results))
    print(f"census done in {time.monotonic() - start:.0f}s", file=sys.stderr)
    print(summary_line(results))
    if not check:
        return

    bugs = [r for r in results
            if r.gap == RecycleSourceGapClass.RECYCLE_SOURCE_BUG.value]
    if not bugs:
        print("GATE CLEAN: 0 RECYCLE_SOURCE_BUG cells.", file=sys.stderr)
        return
    print(f"GATE FAILED: {len(bugs)} RECYCLE_SOURCE_BUG cell(s):", file=sys.stderr)
    for r in bugs:
        print(f"  {r.kind} source={r.source} material={r.material} "
              f"needed={r.needed} recoverable={r.recoverable} "
              f"planner_failed={r.planner_failed} plan={list(r.plan)}",
              file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
