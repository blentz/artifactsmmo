"""Run the vocabulary gate over src/ and print its verdict: every identifier
that names tier, rung, band, ladder or milestone outside its allowance, and
every allowance the tree no longer uses (spec 2026-10-18 §5 item 4).

    uv run python scripts/gen_vocabulary_gate.py

CI gate: pass `--check` to exit non-zero on any violation or orphan.

    uv run python scripts/gen_vocabulary_gate.py --check

Offline, no API, no fixtures: `tokenize` over src/ and nothing else.
"""

import sys
from pathlib import Path

from artifactsmmo_cli.audit.vocabulary_gate import render, run_gate

SRC = Path("src")


def main() -> None:
    check = "--check" in sys.argv[1:]
    sources = {str(path): path.read_text() for path in sorted(SRC.rglob("*.py"))}
    result = run_gate(sources)
    print(render(result))
    if check and not result.passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
