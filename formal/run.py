"""Run each TLA+ spec under PlusPy and report PASS/FAIL.

PlusPy is an interpreter: each spec enumerates its bounded input domain in
Next and asserts the correctness property per input via TLC!Assert. A clean
run exits 0 with no assertion failure; a violated property halts PlusPy with
the asserted message. This runner invokes PlusPy per module and aggregates.
"""

import subprocess
import sys
from pathlib import Path

FORMAL = Path(__file__).resolve().parent
PLUSPY = FORMAL / "vendor" / "PlusPy" / "pluspy.py"
SPECS = FORMAL / "specs"
LIB = FORMAL / "vendor" / "PlusPy" / "modules" / "lib"

# (module, iteration count = input-domain size). Counts filled in per task.
MODULES: list[tuple[str, int]] = [
    ("Smoke", 3),
]

# Substrings PlusPy emits when an assertion fails.
# On success PlusPy prints "MAIN DONE" and nothing else distinguishing.
# On failure PlusPy prints "Evaluating Assert ... failed" followed by a
# Python traceback with "AssertionError". Neither substring appears in a
# clean run, so there are no false positives.
FAILURE_MARKERS = ("Evaluating Assert", "AssertionError")


def run_module(module: str, count: int) -> tuple[bool, str]:
    if not PLUSPY.exists():
        return False, "PlusPy not found — run ./formal/setup.sh first"
    proc = subprocess.run(
        [
            sys.executable,
            str(PLUSPY),
            f"-c{count}",
            "-P",
            f"{SPECS}:{LIB}",
            module,
        ],
        capture_output=True,
        text=True,
    )
    output = proc.stdout + proc.stderr
    failed = proc.returncode != 0 or any(m in output for m in FAILURE_MARKERS)
    return (not failed), output


def main() -> int:
    results: list[tuple[str, bool]] = []
    for module, count in MODULES:
        ok, output = run_module(module, count)
        results.append((module, ok))
        if not ok:
            print(f"--- {module} output ---\n{output}\n")
    width = max(len(m) for m, _ in results)
    print("\nFormal verification results:")
    for module, ok in results:
        print(f"  {module:<{width}}  {'PASS' if ok else 'FAIL'}")
    return 0 if all(ok for _, ok in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
