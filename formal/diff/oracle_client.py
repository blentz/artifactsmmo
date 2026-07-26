"""Invoke the compiled Lean oracle with a batch of tagged requests, parse JSON output.

The oracle accepts a JSON array of `{"kind": ..., "args": [...]}` objects and
dispatches on `kind`, so one binary serves multiple proved components.

Two transports, same answers:

* DEFAULT — one long-lived `oracle --serve` process per Python process (so one
  per xdist worker), spoken to over a pipe. Spawning the binary costs ~107ms
  regardless of batch size, and the differential suite calls the oracle once per
  Hypothesis example, so spawn-per-call paid that startup ~48,000 times.
* `ARTIFACTSMMO_ORACLE_MODE=spawn` — the original spawn-per-call path, kept as
  the parity oracle. If the two transports ever disagree, that is a bug in the
  serving layer, and this is how you find out.

Both public functions keep their exact signatures, so no differential test changed.
"""
import atexit
import json
import subprocess

from formal.diff.oracle_server import (
    ORACLE,
    OracleServer,
    oracle_missing_error,
    persistent_enabled,
)

_SERVER = OracleServer()
atexit.register(_SERVER.close)


def _spawn_once(kind: str, args_batches: list[list]) -> list[dict]:
    """The original transport: one process per call, read to EOF, exit."""
    if not ORACLE.exists():
        raise oracle_missing_error()
    payload = json.dumps([{"kind": kind, "args": list(args)} for args in args_batches])
    proc = subprocess.run([str(ORACLE)], input=payload, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"oracle failed: {proc.stderr}")
    return json.loads(proc.stdout)


def _dispatch(kind: str, args_batches: list[list]) -> list[dict]:
    if persistent_enabled():
        return _SERVER.request(kind, args_batches)
    return _spawn_once(kind, args_batches)


def run_oracle(kind: str, inputs: list[list[int]]) -> list[dict]:
    """Run the oracle for `kind` over a batch of integer-arg lists."""
    return _dispatch(kind, list(inputs))


def run_oracle_structured(kind: str, args_batches: list[list]) -> list[dict]:
    """Like run_oracle but each args entry may contain arbitrary JSON values
    (objects/strings), not just ints. For string-keyed structured inputs."""
    return _dispatch(kind, args_batches)
