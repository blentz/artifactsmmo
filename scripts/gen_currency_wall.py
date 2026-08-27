"""Generate docs/behavioral_completeness/CURRENCY_WALL_MATRIX.md by running the
O7 currency-wall census (wave-6 routes design, §7 obligation O7 — the ACCEPTANCE
gate for "the root costs a million actions and nothing says which currency
stopped it").

Offline + deterministic (no live API): loads
tests/test_ai/scenarios/fixtures/gamedata_bundle.json — the same fixture the
craft, inventory, recycle-source, obtain-parity, shed, open-rung and requirement
censuses plan against.

UNLIKE ITS SIBLINGS IT TAKES THE BUNDLE PATH, NOT A `GameData`. The world is a
per-scenario fact here: `ScenarioCharacter` declares `ge_market` and
`unlocked_achievements`, and pricing every cell in one world is what voided this
census's first run — the only `tasks_coin` vendor is behind an achievement gate,
so a single default world makes the funded arm unreachable and the sweep
vacuous. `run_census` builds each declared world itself.

Serial, like its small siblings: the grid is `len(SCENARIOS) x currencies`
cells, each one a pair of `route_price` calls plus catalogue arithmetic, with a
single `resolve_root` drive amortised across each scenario's six currencies.
Measured at ~1.2s on the committed bundle, so a process pool would cost more to
spin up than the census takes to run.

    uv run python scripts/gen_currency_wall.py

CI gate: pass `--check` to exit non-zero when

  * the sweep is smaller than `MIN_CELLS` (a blind sweep cannot report a clean
    residual);
  * the FUNDED arm was exercised zero times (`reference_set_residual`) — O7's
    own ship condition, and the failure its first run shipped undetected;
  * any cell classifies `o7_silent_currency_stall`, `o7_unexplained` or
    `currency_catalogue_empty`.

The three `WALL_*` classes are EXPLAINED closures (the catalogue, not the graph,
is why the currency has no route) and do not fail the gate. Their count is
printed either way: a wall count of zero is a finding about the fixture set, not
a success.

`--check` still writes the doc, so a failing pipeline also surfaces the
regenerated MATRIX:

    uv run python scripts/gen_currency_wall.py --check
"""

import sys
import time
from pathlib import Path

from artifactsmmo_cli.audit.currency_wall_census import (
    MIN_CELLS,
    RESIDUALS,
    reference_set_residual,
    render_matrix,
    run_census,
    summary_line,
)

BUNDLE = Path("tests/test_ai/scenarios/fixtures/gamedata_bundle.json")
OUT_DIR = Path("docs/behavioral_completeness")


def main() -> None:
    check = "--check" in sys.argv[1:]
    start = time.monotonic()
    results = run_census(BUNDLE)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "CURRENCY_WALL_MATRIX.md").write_text(render_matrix(results))
    print(f"census done in {time.monotonic() - start:.1f}s", file=sys.stderr)
    print(summary_line(results))
    if not check:
        return

    # BLINDNESS FLOOR, BEFORE the residual test. `[r for r in results if r.gap
    # in RESIDUALS]` is satisfied by an EMPTY census, so a `run_census` that
    # discovered nothing would print "0 cells ... GATE CLEAN" and exit 0 — the
    # flattering-gate failure this repo has shipped once already. The suite's
    # floors cannot cover this path: `scripts/*` is coverage-omitted and
    # census-gate.yml runs the scripts without pytest. `MIN_CELLS` is the SAME
    # constant the suite asserts, so the two cannot drift.
    if len(results) < MIN_CELLS:
        print(f"GATE FAILED: census swept {len(results)} cells, floor is "
              f"{MIN_CELLS} — the sweep went blind, so a clean residual count "
              f"would mean nothing.", file=sys.stderr)
        sys.exit(1)

    # REFERENCE-SET FLOOR, also before the residual test and for the same
    # reason at one remove: a full-sized grid in which the funded arm never
    # fires has every residual trivially zero. This is the exact state the
    # census's first run was in — 44 cells priced in a world whose only
    # tasks_coin vendor had no tile — and nothing then in place would have said
    # so. O7's text makes it a ship condition, so it is a gate failure and not
    # a warning.
    empty = reference_set_residual(results)
    if empty:
        print(f"GATE FAILED: {empty}", file=sys.stderr)
        sys.exit(1)

    bugs = [r for r in results if r.gap in RESIDUALS]
    if not bugs:
        print(f"GATE CLEAN: {len(results)} cells swept, 0 residual "
              f"(O7_SILENT_CURRENCY_STALL / O7_MULTI_CURRENCY_WALL / "
              f"O7_UNEXPLAINED / CURRENCY_CATALOGUE_EMPTY).", file=sys.stderr)
        return
    print(f"GATE FAILED: {len(bugs)} residual cell(s):", file=sys.stderr)
    for r in bugs:
        evidence = r.evidence
        detail = "no evidence (catalogue empty)" if evidence is None else (
            f"earnable={evidence.task_earnable} "
            f"droppers={list(evidence.droppers)} "
            f"live_tiles={list(evidence.on_live_tiles)} "
            f"winnable={list(evidence.winnable)} "
            f"event_gated={list(evidence.event_gated)}")
        print(f"  {r.scenario} currency={r.currency} root={r.root} "
              f"gap={r.gap} charged={r.charged} "
              f"price={r.base_price}->{r.granted_price} {detail}",
              file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
