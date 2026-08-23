"""Generate docs/behavioral_completeness/OPEN_RUNG_MATRIX.md by running the O1
open-rung census (wave-3 resolution design, §3.5 obligation O1 — the ACCEPTANCE
gate for "the bot cannot raise this skill and cannot say why").

Offline + deterministic (no live API): loads
tests/test_ai/scenarios/fixtures/gamedata_bundle.json — the same fixture the
craft, inventory, recycle-source, obtain-parity, shed and requirement censuses
plan against.

Serial, like its small siblings: the grid is `len(SCENARIOS) x len(SKILL_NAMES)`
cells, each one catalogue arithmetic plus one short-circuiting obtainability
walk, with a single `resolve_root` drive amortised across each scenario's eight
skills. Measured at ~1.3s on the committed bundle, so a process pool would cost
more to spin up than the census takes to run.

    uv run python scripts/gen_open_rung.py

CI gate: pass `--check` to exit non-zero when any cell classifies
`o1_silent_stall` or `o1_unexplained` — the two must-be-zero residuals,
mirroring the craft census's `planner_bug`, the shed census's
`shed_starvation_bug` and the obtain census's `obtain_parity_bug`. The four
`WALL_*` classes are EXPLAINED closures (the catalogue, not the graph, stopped
the climb) and do not fail the gate.

`--check` still writes the doc, so a failing pipeline also surfaces the
regenerated MATRIX:

    uv run python scripts/gen_open_rung.py --check
"""

import json
import sys
import time
from pathlib import Path

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.audit.open_rung_completeness import (
    RESIDUALS,
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
    (OUT_DIR / "OPEN_RUNG_MATRIX.md").write_text(render_matrix(results))
    print(f"census done in {time.monotonic() - start:.1f}s", file=sys.stderr)
    print(summary_line(results))
    if not check:
        return

    bugs = [r for r in results if r.gap in RESIDUALS]
    if not bugs:
        print("GATE CLEAN: 0 O1_SILENT_STALL / O1_UNEXPLAINED cells.",
              file=sys.stderr)
        return
    print(f"GATE FAILED: {len(bugs)} residual cell(s):", file=sys.stderr)
    for r in bugs:
        inv = r.inventory
        print(f"  {r.scenario} ReachSkillLevel({r.skill}, {r.target}) "
              f"gap={r.gap} routed={r.routed} in_level={inv.in_level} "
              f"xp_positive={inv.xp_positive} obtainable={inv.obtainable} "
              f"above={inv.above} gather_in_level={inv.gather_in_level} "
              f"gather_xp_positive={inv.gather_xp_positive} "
              f"gather_rung={inv.gather_rung}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
