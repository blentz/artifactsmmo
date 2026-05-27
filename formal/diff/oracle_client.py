"""Invoke the compiled Lean oracle with a batch of tagged requests, parse JSON output.

The oracle accepts a JSON array of `{"kind": ..., "args": [...]}` objects and
dispatches on `kind`, so one binary serves multiple proved components.
"""
import json
import subprocess
from pathlib import Path

ORACLE = Path(__file__).resolve().parent.parent / ".lake" / "build" / "bin" / "oracle"


def run_oracle(kind: str, inputs: list[list[int]]) -> list[dict]:
    """Run the oracle for `kind` over a batch of integer-arg lists."""
    if not ORACLE.exists():
        raise RuntimeError(f"oracle not built: {ORACLE} (run `cd formal && lake build oracle`)")
    payload = json.dumps([{"kind": kind, "args": list(args)} for args in inputs])
    proc = subprocess.run([str(ORACLE)], input=payload, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"oracle failed: {proc.stderr}")
    return json.loads(proc.stdout)
