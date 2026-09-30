"""Generate docs/behavioral_completeness/GRIND_CYCLE_MATRIX.md: the grind-cycle
census (Phase 2d-L3), offline over the committed bundle.

Binds `Formal.Liveness.GrindCycles` to production: every decomposed grind
cycle must end in a leg that earns a skill's XP. `--check` exits non-zero on
any `no_earning_leg` cell (and still writes the doc).

    uv run python scripts/gen_grind_cycle.py [--check]
"""

import json
import sys
import time
from pathlib import Path

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.audit.grind_cycle_census import (
    GrindCycleGap,
    render_matrix,
    run_census,
    summary_line,
)

BUNDLE = Path("tests/test_ai/scenarios/fixtures/gamedata_bundle.json")
OUT = Path("docs/behavioral_completeness/GRIND_CYCLE_MATRIX.md")


def main() -> None:
    check = "--check" in sys.argv[1:]
    game_data = GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))
    start = time.monotonic()
    results = run_census(game_data)
    OUT.write_text(render_matrix(results))
    print(f"census done in {time.monotonic() - start:.0f}s", file=sys.stderr)
    print(summary_line(results))
    if not check:
        return
    bad = [r for r in results if r.gap is GrindCycleGap.NO_EARNING_LEG]
    if not bad:
        print("GATE CLEAN: 0 NO_EARNING_LEG cells.", file=sys.stderr)
        return
    print(f"GATE FAILED: {len(bad)} NO_EARNING_LEG cell(s):", file=sys.stderr)
    for r in bad:
        print(f"  {r.scenario} {r.skill} {r.level}: {' -> '.join(r.plan)}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
