"""CharacterSupervisor: spawn, read, reap, and conditionally restart one bot child."""

import asyncio
from collections import deque
from collections.abc import Awaitable, Callable

from pydantic import ValidationError

from artifactsmmo_cli.multi.child_event import ChildEvent, ExitEvent, parse_child_event
from artifactsmmo_cli.multi.restart_policy import RestartPolicy

STDERR_TAIL_LINES = 20

DEFAULT_STREAM_LIMIT = 8 * 1024 * 1024
"""Passed as `limit=` to `create_subprocess_exec`. asyncio's own default
(2**16 = 65536 bytes) is too tight: a real `SnapshotEvent(...).model_dump_json()`
for a 300-node plan_tree + grind_expansion with 200 bank_items measured
51,725 bytes -- 79% of the default -- at plausible late-game values. Past the
configured limit, `StreamReader.readline()` raises `ValueError` rather than
returning the line; 8 MiB leaves generous headroom for growth."""

TERMINATE_TIMEOUT_SECONDS = 5.0
"""How long to wait for a graceful SIGTERM before escalating to SIGKILL."""


class CharacterSupervisor:
    """One character's subprocess, from spawn to final death.

    The child's stdout is the event protocol and its stderr is the human log;
    both are drained concurrently so neither can fill its pipe buffer and
    deadlock the child.
    """

    def __init__(
        self,
        character: str,
        argv: list[str],
        on_event: Callable[[ChildEvent], None],
        policy: RestartPolicy | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        on_stderr: Callable[[str], None] | None = None,
        stream_limit: int = DEFAULT_STREAM_LIMIT,
        terminate_timeout: float = TERMINATE_TIMEOUT_SECONDS,
    ) -> None:
        self.character = character
        self._argv = argv
        self._on_event = on_event
        self._policy = policy or RestartPolicy()
        self._sleep = sleep
        self._on_stderr = on_stderr
        self._stream_limit = stream_limit
        self._terminate_timeout = terminate_timeout
        self.alive = False
        self.restarts = 0
        self.last_reason: str | None = None
        # Set only while a child is actually running. Diagnostics / tests use
        # this to prove the OS process is really gone after termination, not
        # merely that this supervisor stopped watching it.
        self.pid: int | None = None
        self._stderr: deque[str] = deque(maxlen=STDERR_TAIL_LINES)

    @property
    def stderr_tail(self) -> tuple[str, ...]:
        return tuple(self._stderr)

    async def run(self) -> None:
        """Run the child, restarting while the policy allows it."""
        while True:
            reason = await self._run_once()
            self.last_reason = reason
            decision = self._policy.decide(reason, self.restarts)
            if not decision.restart:
                return
            self.restarts += 1
            await self._sleep(decision.delay_seconds)

    async def _run_once(self) -> str:
        """One child lifetime. Returns the exit reason to judge."""
        process = await asyncio.create_subprocess_exec(
            *self._argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=self._stream_limit,
        )
        # asyncio's stubs type these as `StreamReader | None` even though
        # PIPE guarantees both are populated; assert the narrowing honestly
        # rather than silencing mypy.
        assert process.stdout is not None
        assert process.stderr is not None
        self.pid = process.pid
        self.alive = True
        reason_box: list[str] = []
        try:
            await asyncio.gather(
                self._read_events(process.stdout, reason_box),
                self._read_stderr(process.stderr),
            )
        finally:
            # Whatever happened above -- clean EOF, an exception out of a
            # reader, or this coroutine's own task being cancelled (e.g.
            # Textual cancelling the "supervisors" worker on 'q') -- the
            # child must never outlive this method. Without this, a
            # cancellation left the subprocess alive with nobody draining
            # its pipes: up to 5 bot subprocesses still hitting the live
            # game account, each taking one more real action before dying
            # accidentally on SIGPIPE.
            await self._terminate(process)
            self.alive = False
            self.pid = None
        # A child killed hard never emits an exit event. Treat the silence as
        # a crash rather than inventing a friendlier reason.
        return reason_box[0] if reason_box else "crash"

    async def _terminate(self, process: "asyncio.subprocess.Process") -> None:
        """Ensure the child is dead and reaped, whatever happened above.

        Graceful SIGTERM first, escalating to SIGKILL if the child ignores
        it; always awaits `wait()` so no zombie is left behind, even when the
        child had already exited on its own (the common case).
        """
        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(
                    process.wait(), timeout=self._terminate_timeout
                )
            except TimeoutError:
                process.kill()
        await process.wait()

    async def _read_events(
        self, stream: asyncio.StreamReader, reason_box: list[str]
    ) -> None:
        while True:
            try:
                raw = await stream.readline()
            except ValueError as exc:
                # The line exceeded `self._stream_limit`. readline() has
                # already discarded the oversized data and resumed searching
                # for the next newline internally, so the stream is still
                # readable -- this is a protocol error to surface, exactly
                # like an unparseable-but-complete line, never a reason to
                # stop draining the pipe.
                self._stderr.append(f"protocol error: line exceeded the stream limit ({exc})")
                continue
            if not raw:
                return  # EOF; a partial trailing line is a normal mid-write death
            line = raw.decode().strip()
            if not line:
                continue
            try:
                event = parse_child_event(line)
            except ValidationError as exc:
                self._stderr.append(f"protocol error: {line[:120]} ({exc.error_count()} errors)")
                continue
            if isinstance(event, ExitEvent):
                reason_box.append(event.reason)
            self._on_event(event)

    async def _read_stderr(self, stream: asyncio.StreamReader) -> None:
        while True:
            raw = await stream.readline()
            if not raw:
                return
            line = raw.decode().rstrip()
            self._stderr.append(line)
            if self._on_stderr is not None:
                self._on_stderr(line)
