"""CharacterSupervisor: spawn, read, reap, and conditionally restart one bot child."""

import asyncio
from collections import deque
from collections.abc import Awaitable, Callable

from pydantic import ValidationError

from artifactsmmo_cli.multi.child_event import ChildEvent, ExitEvent, parse_child_event
from artifactsmmo_cli.multi.restart_policy import RestartPolicy

STDERR_TAIL_LINES = 20


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
    ) -> None:
        self.character = character
        self._argv = argv
        self._on_event = on_event
        self._policy = policy or RestartPolicy()
        self._sleep = sleep
        self.alive = False
        self.restarts = 0
        self.last_reason: str | None = None
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
        )
        # asyncio's stubs type these as `StreamReader | None` even though
        # PIPE guarantees both are populated; assert the narrowing honestly
        # rather than silencing mypy.
        assert process.stdout is not None
        assert process.stderr is not None
        self.alive = True
        reason_box: list[str] = []
        await asyncio.gather(
            self._read_events(process.stdout, reason_box),
            self._read_stderr(process.stderr),
        )
        await process.wait()
        self.alive = False
        # A child killed hard never emits an exit event. Treat the silence as
        # a crash rather than inventing a friendlier reason.
        return reason_box[0] if reason_box else "crash"

    async def _read_events(
        self, stream: asyncio.StreamReader, reason_box: list[str]
    ) -> None:
        while True:
            raw = await stream.readline()
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
            self._stderr.append(raw.decode().rstrip())
