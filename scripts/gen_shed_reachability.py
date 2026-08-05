"""Generate docs/behavioral_completeness/SHED_REACHABILITY_MATRIX.md by running
the shed-reachability census (disposal-unification epic, part 2 — the ACCEPTANCE
gate for defect A, starvation, and defect B, the drain/route contradiction).

Offline + deterministic (no live API): loads
tests/test_ai/scenarios/fixtures/gamedata_bundle.json — the same fixture the
craft, inventory, recycle-source and obtain-parity censuses plan against.

Serial, like its small siblings: this grid is FIVE cells (the craft grid is
~1900), four of them a single `StrategyArbiter.select` drive and the fifth a
pure catalog sweep, so a process pool would cost more to spin up than the
census takes to run.

    uv run python scripts/gen_shed_reachability.py

CI gate: pass `--check` to exit non-zero when any cell classifies
`shed_starvation_bug` or `disposal_contradiction_bug` — the two must-be-zero
residuals, mirroring the craft census's `planner_bug`, the inventory census's
`inventory_bug`, the recycle census's `recycle_source_bug` and the obtain
census's `obtain_parity_bug`. A planner TIMEOUT is one of them: it is classified
`shed_starvation_bug` unconditionally and before every world arm, because a gap
class that can swallow a planner bug destroys the census's entire value.

`--check` still writes the doc, so a failing pipeline also surfaces the
regenerated MATRIX:

    uv run python scripts/gen_shed_reachability.py --check
"""

import json
import sys
import time
from pathlib import Path

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.audit.shed_reachability_completeness import (
    ShedGapClass,
    render_matrix,
    run_census,
    summary_line,
)

BUNDLE = Path("tests/test_ai/scenarios/fixtures/gamedata_bundle.json")
OUT_DIR = Path("docs/behavioral_completeness")

RESIDUALS = frozenset({ShedGapClass.SHED_STARVATION_BUG.value,
                       ShedGapClass.DISPOSAL_CONTRADICTION_BUG.value})
"""The two gap classes that must reach 0. The world-limit classes
(`bank_unreachable`, `no_reachable_buyer`) are EXPLAINED failures and do not fail
the gate — they say the bundle's map, not the ladder, is what stopped the shed."""


def main() -> None:
    check = "--check" in sys.argv[1:]
    game_data = GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))
    start = time.monotonic()
    results = run_census(game_data)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "SHED_REACHABILITY_MATRIX.md").write_text(render_matrix(results))
    print(f"census done in {time.monotonic() - start:.0f}s", file=sys.stderr)
    print(summary_line(results))
    if not check:
        return

    bugs = [r for r in results if r.gap in RESIDUALS]
    if not bugs:
        print("GATE CLEAN: 0 SHED_STARVATION_BUG / DISPOSAL_CONTRADICTION_BUG "
              "cells.", file=sys.stderr)
        return
    print(f"GATE FAILED: {len(bugs)} residual cell(s):", file=sys.stderr)
    for r in bugs:
        print(f"  {r.kind} gap={r.gap} rung={r.rung} licensed={r.licensed} "
              f"swept={r.swept} contradictions={r.contradictions} "
              f"goal={r.goal} planner_failed={r.planner_failed} "
              f"plan={list(r.plan)}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
