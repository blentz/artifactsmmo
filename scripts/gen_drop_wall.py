"""Generate docs/behavioral_completeness/DROP_WALL_MATRIX.md by running the
drop-wall census — `is_winnable` on DROP, the biggest unfixed wall of the
2026-08-09 exclusion audit, measured where it actually binds.

Offline + deterministic (no live API): loads
tests/test_ai/scenarios/fixtures/gamedata_bundle.json — the same fixture the
craft, inventory, recycle-source, obtain-parity, shed, open-rung, requirement
and currency-wall censuses plan against.

LIKE THE CURRENCY CENSUS IT TAKES THE BUNDLE PATH, NOT A `GameData`: the world
is a per-scenario fact (`ge_market`, `unlocked_achievements`), and pricing every
cell in one world is what voided that census's first run. `run_census` builds
each declared world itself.

AND UNLIKE EVERY CENSUS IN THIS REPO IT PRICES THE ALTERNATIVES, not only the
resolved root. That is the whole finding: an infinite price is a VETO, so a
drop-walled candidate never becomes the argmax. Priced on the argmax alone this
census reports 0 walls; priced over root + alternatives it reports 9.

Serial: 438 cells, each a `route_price` call, with the per-item attribution
probe run only on a candidate that already crossed the collective one. Measured
at ~3s on the committed bundle.

    uv run python scripts/gen_drop_wall.py

CI gate: pass `--check` to exit non-zero when

  * the sweep is smaller than `MIN_CELLS` (a blind sweep cannot report a clean
    residual);
  * neither wall arm was exercised (`witness_residual`) — a full-sized grid in
    which the subject never appears has every residual trivially zero;
  * any cell classifies `drop_wall_unattributed`.

The two `WALL_*` classes are EXPLAINED closures (the catalogue, not the graph,
is why the route is absent) and do not fail the gate. Their count is printed
either way: a wall count of zero is a finding about the fixture set, not a
success.

`--check` still writes the doc, so a failing pipeline also surfaces the
regenerated MATRIX:

    uv run python scripts/gen_drop_wall.py --check
"""

import sys
import time
from pathlib import Path

from artifactsmmo_cli.audit.drop_wall_census import (
    MIN_CELLS,
    RESIDUALS,
    argmax_blindness,
    render_matrix,
    run_census,
    summary_line,
    witness_residual,
)

BUNDLE = Path("tests/test_ai/scenarios/fixtures/gamedata_bundle.json")
OUT_DIR = Path("docs/behavioral_completeness")


def main() -> None:
    check = "--check" in sys.argv[1:]
    start = time.monotonic()
    results = run_census(BUNDLE)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "DROP_WALL_MATRIX.md").write_text(render_matrix(results))
    print(f"census done in {time.monotonic() - start:.1f}s", file=sys.stderr)
    print(summary_line(results))
    print(argmax_blindness(results))
    if not check:
        return

    # BLINDNESS FLOOR, BEFORE the residual test. `[r for r in results if r.gap
    # in RESIDUALS]` is satisfied by an EMPTY census, so a `run_census` that
    # discovered nothing would print "0 cells ... GATE CLEAN" and exit 0 — the
    # flattering-gate failure this repo has shipped once already. The suite's
    # floors cannot cover this path: `scripts/*` is coverage-omitted and the
    # census gate runs the scripts without pytest. `MIN_CELLS` is the SAME
    # constant the suite asserts, so the two cannot drift.
    if len(results) < MIN_CELLS:
        print(f"GATE FAILED: census swept {len(results)} cells, floor is "
              f"{MIN_CELLS} — the sweep went blind, so a clean residual count "
              f"would mean nothing.", file=sys.stderr)
        sys.exit(1)

    # WITNESS FLOOR, for the same reason at one remove: a full-sized grid in
    # which neither wall arm ever fires has every residual trivially zero. The
    # committed bundle exercises the CLOSES arm 9 times, so a zero here means
    # the fixtures, the pricer or the detector moved — each of which is worth
    # failing a pipeline over.
    unwitnessed = witness_residual(results)
    if unwitnessed:
        print(f"GATE FAILED: {unwitnessed}", file=sys.stderr)
        sys.exit(1)

    bugs = [r for r in results if r.gap in RESIDUALS]
    if not bugs:
        print(f"GATE CLEAN: {len(results)} cells swept, 0 residual "
              f"(DROP_WALL_UNATTRIBUTED).", file=sys.stderr)
        return
    print(f"GATE FAILED: {len(bugs)} residual cell(s):", file=sys.stderr)
    for r in bugs:
        print(f"  {r.scenario} candidate={r.candidate} "
              f"{'argmax' if r.is_resolved_root else 'alt'} gap={r.gap} "
              f"price={r.base_price}->{r.granted_price}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
