"""Regenerate the requirement-walk parity characterization matrix.

Wave 0 of the requirement-model unification epic
(`docs/superpowers/specs/2026-07-19-requirement-model-unification-epic.md`).

`--check` IS A DRIFT GATE, NOT A BUG COUNT — and that difference is the point.

The other four censuses assert a residual is ZERO (`planner_bug`,
`obtain_parity_bug`, ...). This one cannot: it is CHARACTERIZATION-first, and
today's answer includes four defects (D1-D4) it deliberately pins. A bug count
would either be permanently red or would have to launder the defects into
"expected", which is exactly the flattering-gate failure this epic exists to
undo.

So `--check` fails when the committed matrix and a fresh run DISAGREE. During
the migration waves that is the signal you want: any change to what the six
walks answer shows up here as a diff, and the reviewer decides whether it is an
intentional D-fix or a regression. Wave 0 is the only wave that may commit a
matrix change without also citing the D-number it closes.
"""
import json
import sys
import time
from pathlib import Path

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.audit.requirement_parity import (
    render_matrix,
    run_census,
    summary_line,
)

BUNDLE = Path("tests/test_ai/scenarios/fixtures/gamedata_bundle.json")
OUT = Path("docs/behavioral_completeness/REQUIREMENT_PARITY_MATRIX.md")


def main() -> None:
    check = "--check" in sys.argv[1:]
    game_data = GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))

    start = time.monotonic()
    rows = run_census(game_data)
    fresh = render_matrix(rows)
    print(f"census done in {time.monotonic() - start:.1f}s", file=sys.stderr)
    print(summary_line(rows))

    if not check:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(fresh)
        return

    if not OUT.exists():
        print(f"GATE FAILED: {OUT} missing — run without --check first.",
              file=sys.stderr)
        sys.exit(1)

    committed = OUT.read_text()
    if committed == fresh:
        print("GATE CLEAN: requirement-walk answers unchanged.", file=sys.stderr)
        return

    # Report the first differing line — the whole matrix is ~320 rows and a
    # full dump buries the signal.
    # strict=False on purpose: a length change is a legitimate drift (a target
    # appeared or vanished) and is reported by the `else` branch below, so
    # truncating to the common prefix here is what surfaces the FIRST differing
    # line rather than raising before we can name it.
    for n, (a, b) in enumerate(
        zip(committed.splitlines(), fresh.splitlines(), strict=False), 1
    ):
        if a != b:
            print(f"GATE FAILED: requirement-walk answers DRIFTED at line {n}.",
                  file=sys.stderr)
            print(f"  committed: {a}", file=sys.stderr)
            print(f"  fresh    : {b}", file=sys.stderr)
            break
    else:
        print("GATE FAILED: matrix length changed "
              f"({len(committed.splitlines())} -> {len(fresh.splitlines())} lines).",
              file=sys.stderr)
    print("If this is an intentional D1-D4 fix, regenerate and cite the "
          "D-number in the commit.", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
