"""Generate docs/behavioral_completeness/OBTAIN_PARITY_MATRIX.md by running the
obtain-model PARITY census (one-obtain-model epic, Task 7 — the ACCEPTANCE gate)
over its six-cell grid.

THE gate that makes the seven-inert-commits divergence bug unshippable: it fails
CI if the bot's two plan producers (the O(closure) descent and the A* search)
ever disagree again about what is obtainable.

Offline + deterministic (no live API): loads
tests/test_ai/scenarios/fixtures/gamedata_bundle.json — the same fixture the
craft, inventory, and recycle-source censuses plan against.

Serial, like the recycle-source census: this grid is SIX cells (the craft grid is
~1900), each a single `StrategyArbiter.select` drive plus one A* plan, so a
process pool would cost more to spin up than the census takes to run.

    uv run python scripts/gen_obtain_parity.py

CI gate: pass `--check` to exit non-zero when any cell classifies
`obtain_parity_bug` — the must-be-zero residual, mirroring the craft census's
`planner_bug`, the inventory census's `inventory_bug`, and the recycle census's
`recycle_source_bug`. A planner TIMEOUT is one of them: it is classified
`obtain_parity_bug` unconditionally and before every other arm, because a gap
class that can swallow a planner bug destroys the census's entire value.

`--check` still writes the doc, so a failing pipeline also surfaces the
regenerated MATRIX:

    uv run python scripts/gen_obtain_parity.py --check
"""

import json
import sys
import time
from pathlib import Path

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.audit.obtain_parity_completeness import (
    ParityGapClass,
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
    (OUT_DIR / "OBTAIN_PARITY_MATRIX.md").write_text(render_matrix(results))
    print(f"census done in {time.monotonic() - start:.0f}s", file=sys.stderr)
    print(summary_line(results))
    if not check:
        return

    bugs = [r for r in results
            if r.gap == ParityGapClass.OBTAIN_PARITY_BUG.value]
    if not bugs:
        print("GATE CLEAN: 0 OBTAIN_PARITY_BUG cells.", file=sys.stderr)
        return
    print(f"GATE FAILED: {len(bugs)} OBTAIN_PARITY_BUG cell(s):", file=sys.stderr)
    for r in bugs:
        print(f"  {r.kind} material={r.material} needed={r.needed} "
              f"model={list(r.model_kinds)} pool_applicable={list(r.pool_applicable_kinds)} "
              f"descent={list(r.descent_kinds)} astar={list(r.astar_kinds)} "
              f"POOL<=MODEL={r.pool_subset_model} MODEL<=POOL={r.model_subset_pool} "
              f"parity={r.plan_parity} planner_failed={r.planner_failed}",
              file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
