"""A long-lived Lean oracle process, spoken to over a pipe.

Spawning the compiled oracle costs ~107ms and that cost is almost entirely
process startup: a batch of 400 requests costs 111ms, i.e. 0.28ms per request.
The differential suite calls the oracle once per Hypothesis example and declares
~48,000 examples, so it was paying the 107ms startup roughly 48,000 times —
40m47s of user CPU to produce a 2:09 wall-clock run.

This keeps ONE oracle alive per process (so, under `pytest -n auto`, one per
xdist worker) and exchanges framed JSON lines with it.

SAFETY: requests and responses are matched positionally over a pipe, so a single
desynchronised line would leave every later test comparing Python against the
answer to a DIFFERENT question — and still passing. Every request carries a
monotonic id which the oracle echoes, and `request` asserts it. A desync is a
loud failure, never a vacuous pass.

Set `ARTIFACTSMMO_ORACLE_MODE=spawn` to bypass this entirely and use the
original spawn-per-call path, which remains the parity oracle.
"""

from __future__ import annotations

import contextlib
import json
import os
import select
import subprocess
import threading
from pathlib import Path

ORACLE = Path(__file__).resolve().parent.parent / ".lake" / "build" / "bin" / "oracle"

#: A single request is answered in well under a second; this bound exists only so
#: that a wedged oracle surfaces as an error instead of hanging the suite forever.
#: The persistent process is the one new failure mode this design introduces, and
#: this is what keeps it diagnosable.
READ_TIMEOUT_SECONDS = 120.0


def oracle_missing_error() -> RuntimeError:
    """The shared 'you did not build it' error, so both call paths agree."""
    return RuntimeError(f"oracle not built: {ORACLE} (run `cd formal && lake build oracle`)")


def align_results(expected: int, tagged: list[dict], context: str) -> list[dict]:
    """Reassemble a batch's results BY `rid`, never by position.

    Position is the dangerous part of a pipe protocol: a scrambled, truncated or
    duplicated batch still yields well-formed answers, so a differential test
    would compare Python against the wrong question and PASS. Matching by key
    turns every one of those into an exception.

    Pure, so each failure mode is tested directly rather than by trying to
    provoke a real oracle into misbehaving.
    """
    if len(tagged) != expected:
        raise RuntimeError(
            f"oracle returned {len(tagged)} results for {expected} requests ({context})")
    by_rid: dict[int, dict] = {}
    for item in tagged:
        if "rid" not in item or "value" not in item:
            raise RuntimeError(f"oracle result missing rid/value: {item!r} ({context})")
        rid = item["rid"]
        if rid in by_rid:
            raise RuntimeError(f"oracle returned duplicate rid {rid} ({context})")
        by_rid[rid] = item["value"]
    missing = set(range(expected)) - by_rid.keys()
    unknown = by_rid.keys() - set(range(expected))
    if missing or unknown:
        raise RuntimeError(
            f"oracle rid mismatch ({context}): missing {sorted(missing)}, "
            f"unexpected {sorted(unknown)}")
    return [by_rid[i] for i in range(expected)]


class OracleServer:
    """Owns one `oracle --serve` subprocess and the framed exchange with it."""

    def __init__(self) -> None:
        self._proc: subprocess.Popen[str] | None = None
        self._next_id = 0
        # Tests within one pytest process are sequential, but a lock costs
        # nothing and keeps a desync impossible if that ever stops being true.
        self._lock = threading.Lock()

    def _start(self) -> subprocess.Popen[str]:
        if not ORACLE.exists():
            raise oracle_missing_error()
        return subprocess.Popen(
            [str(ORACLE), "--serve"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1,
        )

    def request(self, kind: str, args_batches: list[list]) -> list[dict]:
        """Send one batch, return its results. Raises rather than returning
        anything questionable — a differential gate that guesses is worthless."""
        with self._lock:
            if self._proc is not None and self._proc.poll() is not None:
                # It died (crash, or a test killed it). Reap its pipes before
                # replacing it, or they leak as a ResourceWarning later.
                self._close_pipes(self._proc)
                self._proc = None
            if self._proc is None:
                self._proc = self._start()
            proc = self._proc
            assert proc.stdin is not None and proc.stdout is not None

            self._next_id += 1
            req_id = self._next_id
            payload = json.dumps({
                "id": req_id,
                "reqs": [{"rid": i, "kind": kind, "args": list(a)}
                         for i, a in enumerate(args_batches)],
            })
            try:
                proc.stdin.write(payload + "\n")
                proc.stdin.flush()
            except BrokenPipeError as exc:
                raise RuntimeError(
                    f"oracle died before request {req_id} ({kind}): {self._drain_stderr()}"
                ) from exc

            # select() rather than a bare readline so a wedged oracle raises
            # instead of blocking the suite indefinitely.
            ready, _, _ = select.select([proc.stdout], [], [], READ_TIMEOUT_SECONDS)
            if not ready:
                self._kill()
                raise RuntimeError(
                    f"oracle timed out after {READ_TIMEOUT_SECONDS}s on request "
                    f"{req_id} ({kind}, {len(args_batches)} args)"
                )
            line = proc.stdout.readline()
            if not line:
                raise RuntimeError(
                    f"oracle closed its output on request {req_id} ({kind}): "
                    f"{self._drain_stderr()}"
                )

            reply = json.loads(line)
            if "error" in reply:
                raise RuntimeError(f"oracle error on request {req_id} ({kind}): {reply['error']}")
            if reply.get("id") != req_id:
                # Response/request desync: every later comparison would be
                # against the wrong question. Fail hard rather than silently pass.
                self._kill()
                raise RuntimeError(
                    f"oracle response desync: sent id {req_id} ({kind}), got id "
                    f"{reply.get('id')!r}. The oracle process has been killed."
                )
            return align_results(
                len(args_batches), reply["results"], f"id {req_id}, kind {kind}")

    def _drain_stderr(self) -> str:
        proc = self._proc
        if proc is None or proc.stderr is None:
            return "<no stderr>"
        proc.poll()
        try:
            return proc.stderr.read() or "<empty stderr>"
        except ValueError:
            return "<stderr closed>"

    @staticmethod
    def _close_pipes(proc: subprocess.Popen[str]) -> None:
        """Close all three streams. Popen does not do this for us on kill(), and
        a leaked pipe surfaces later as a ResourceWarning — fatal under this
        suite's `-W error`, and attributed to whatever test happens to be running
        when the collector notices."""
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            if stream is not None and not stream.closed:
                with contextlib.suppress(BrokenPipeError):
                    stream.close()

    def _kill(self) -> None:
        proc, self._proc = self._proc, None
        if proc is None:
            return
        proc.kill()
        proc.wait()
        self._close_pipes(proc)

    def close(self) -> None:
        """Shut the oracle down by closing its stdin, which ends its read loop."""
        proc, self._proc = self._proc, None
        if proc is None:
            return
        try:
            if proc.stdin is not None and not proc.stdin.closed:
                proc.stdin.close()
            proc.wait(timeout=5)
        except (subprocess.TimeoutExpired, BrokenPipeError, ValueError):
            proc.kill()
            proc.wait()
        finally:
            self._close_pipes(proc)


def persistent_enabled() -> bool:
    """False when the caller pinned the original spawn-per-call parity path."""
    return os.environ.get("ARTIFACTSMMO_ORACLE_MODE", "serve") != "spawn"
