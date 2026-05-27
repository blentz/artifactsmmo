"""Invoke the compiled Lean oracle with a batch of inputs, parse its JSON output."""
import json
import subprocess
from pathlib import Path

ORACLE = Path(__file__).resolve().parent.parent / ".lake" / "build" / "bin" / "oracle"


def run_oracle(inputs: list[tuple[int, int, int, int]]) -> list[dict]:
    if not ORACLE.exists():
        raise RuntimeError(f"oracle not built: {ORACLE} (run `cd formal && lake build oracle`)")
    payload = json.dumps([list(t) for t in inputs])
    proc = subprocess.run([str(ORACLE)], input=payload, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"oracle failed: {proc.stderr}")
    return json.loads(proc.stdout)
