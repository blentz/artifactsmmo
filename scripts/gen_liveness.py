"""Generate docs/behavioral_completeness/LIVENESS_MATRIX.md — the liveness census.

Six censuses gate on whether the planner CAN do a thing. This one asks whether it
ever DID. See `artifactsmmo_cli/audit/liveness_completeness` for why that gap
mattered: 18 of 34 goals and 17 of 36 actions had never fired, no character had
ever held a task, and the unified objective `J` had never executed — all of it
green the whole time.

    uv run python scripts/gen_liveness.py

CI gate: pass `--check` to exit non-zero on the must-be-zero residuals —

  * UNDECLARED: a Goal or Action that has never run and carries no reason in
    `DORMANT`. Adding a class without either turns the gate red, which is the
    point: the question is asked when the code is written, not weeks later.
  * STALE: a class declared dormant that the store shows running. A reason nobody
    rechecks is a green light with an out-of-date argument behind it.
  * ORPHAN: a `DORMANT` entry naming a class that no longer exists, which would
    silently excuse the wrong thing if the name were reused.

RUNS WITHOUT A LEARNING DB, and that is deliberate. The class roster comes from
the SOURCE, so the completeness of the declaration is checkable in CI or a fresh
clone with no observations at all; only the STALE arm needs a store. A census that
could run only where the bot had already played is one that never runs.

`--learn-db PATH` overrides the default (`~/.cache/artifactsmmo/learning.db`).
`--check` still writes the doc, so a failing pipeline also surfaces the matrix.
"""

import sys
from pathlib import Path

from artifactsmmo_cli.audit.liveness_completeness import (
    orphan_declarations,
    render_matrix,
    run_census,
    stale,
    summary_line,
    undeclared,
)
from artifactsmmo_cli.learning_db_path import default_learn_db_path

OUT_DIR = Path("docs/behavioral_completeness")


def _db_path(argv: list[str]) -> str:
    if "--learn-db" in argv:
        return argv[argv.index("--learn-db") + 1]
    return default_learn_db_path()


def main() -> None:
    argv = sys.argv[1:]
    check = "--check" in argv
    rows = run_census(_db_path(argv))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "LIVENESS_MATRIX.md").write_text(render_matrix(rows))
    print(summary_line(rows))
    if not check:
        return

    bad_undeclared = undeclared(rows)
    bad_stale = stale(rows)
    bad_orphans = orphan_declarations(rows)
    if not (bad_undeclared or bad_stale or bad_orphans):
        print("GATE CLEAN: 0 undeclared, 0 stale, 0 orphan declarations.",
              file=sys.stderr)
        return

    for row in bad_undeclared:
        print(f"GATE FAILED (UNDECLARED): {row.kind} {row.name} has never run and "
              f"carries no reason. Add one to "
              f"`audit/liveness_completeness.DORMANT`, or make it reachable.",
              file=sys.stderr)
    for row in bad_stale:
        print(f"GATE FAILED (STALE): {row.kind} {row.name} is declared dormant "
              f"({row.declared!r}) but the store shows {row.observed} cycles. "
              f"Remove the declaration.", file=sys.stderr)
    for name in bad_orphans:
        print(f"GATE FAILED (ORPHAN): DORMANT names {name!r}, which no longer "
              f"exists in ai/. Remove the entry.", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
