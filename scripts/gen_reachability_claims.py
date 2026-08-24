"""Run the reachability-claim census over production Python and print the
register: every comment that asserts a named thing has no caller, the subject
it resolves to, and whether the import/reference graph agrees.

    uv run python scripts/gen_reachability_claims.py

CI gate: pass `--check` to exit non-zero when any claim is FALSE — a comment
saying live code is dead, which is what the wave-3b deletion pass found three
of, one of them on a module with eleven production importers — or when the
sweep is smaller than `MIN_CLAIMS`, because a census that silently stops
finding anything must fail rather than report a clean residual over nothing.

    uv run python scripts/gen_reachability_claims.py --check

The register goes to stdout rather than a doc: it is derived from src/ in
under a second, so a committed copy would only ever be a second thing to keep
in sync. `formal/gate.sh` prints it as part of the census phase.

Offline, no API, no fixtures — `ast` over src/ and nothing else.
"""

import sys
import time
from pathlib import Path

from artifactsmmo_cli.audit.reachability_claims import (
    MIN_CLAIMS,
    render_register,
    run_census,
    summary_line,
)

SRC = Path("src")


def main() -> None:
    check = "--check" in sys.argv[1:]
    sources = {
        str(path).replace("\\", "/"): path.read_text()
        for path in sorted(SRC.rglob("*.py"))
    }
    start = time.monotonic()
    verdicts = run_census(sources)
    print(f"census done in {time.monotonic() - start:.1f}s", file=sys.stderr)
    register = render_register(verdicts)
    if register:
        print(register)
    print(summary_line(verdicts))
    if not check:
        return
    false_claims = [v for v in verdicts if v.is_false]
    if false_claims:
        print(
            f"FALSE REACHABILITY CLAIM x{len(false_claims)} — these say live code "
            "has no caller:",
            file=sys.stderr,
        )
        for verdict in false_claims:
            print(
                f"  {verdict.claim.module}:{verdict.claim.lineno}: "
                f'`{verdict.claim.subject}` — "{verdict.claim.phrase}" — but it is '
                f"reached by {', '.join(verdict.reached_by[:5])}",
                file=sys.stderr,
            )
        sys.exit(1)
    if len(verdicts) < MIN_CLAIMS:
        print(
            f"BLIND SWEEP — {len(verdicts)} claims found, expected at least "
            f"{MIN_CLAIMS}. The matcher has stopped seeing this repo's phrasing; "
            "a census that finds nothing cannot report a clean residual.",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
