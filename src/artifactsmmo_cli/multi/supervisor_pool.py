"""SupervisorPool: owns every character's supervisor and runs them together."""

import asyncio
from collections.abc import Awaitable, Callable, Sequence

from artifactsmmo_cli.multi.character_supervisor import CharacterSupervisor
from artifactsmmo_cli.multi.child_state import ChildState


class SupervisorPool:
    """Runs one CharacterSupervisor per character, concurrently.

    Roster order is preserved: it comes from the account and is the tiebreak
    for sprite draw order, so it must never be re-sorted.

    Children are STAGGERED into life rather than launched together. Every bot
    process opens with an unmetered game-data load -- `GameData.load` predates
    the RateGovernor and calls no `_acquire_*` -- whose `_load_ge_orders` leg
    is live-only (the order book changes constantly, so a warm disk cache does
    not spare it) and pages the ACCOUNT bucket, the tightest one the API
    declares. Launched simultaneously, N children present N such bursts to
    that shared bucket inside the same second and the losers take an HTTP 429;
    `GameData.load`'s bounded retry then makes them collide again, one backoff
    later, until a child exhausts its budget and dies at boot. Spacing the
    launches by `stagger_seconds` means only one child is ever mid-boot, so
    the bursts queue instead of collide.
    """

    def __init__(
        self,
        supervisors: Sequence[CharacterSupervisor],
        stagger_seconds: float = 0.0,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        on_stagger: Callable[[str, float], None] | None = None,
    ) -> None:
        self._supervisors = tuple(supervisors)
        self._by_name = {s.character: s for s in self._supervisors}
        self._stagger_seconds = stagger_seconds
        self._sleep = sleep
        self._on_stagger = on_stagger

    def characters(self) -> tuple[str, ...]:
        return tuple(s.character for s in self._supervisors)

    def state(self, character: str) -> ChildState:
        supervisor = self._by_name[character]
        return ChildState(
            character=supervisor.character,
            alive=supervisor.alive,
            restarts=supervisor.restarts,
            last_reason=supervisor.last_reason,
            stderr_tail=supervisor.stderr_tail,
        )

    async def run(self) -> None:
        """Run every supervisor concurrently, tracking each one until it
        actually finishes.

        The default ``asyncio.gather(...)`` (``return_exceptions=False``)
        propagates the moment ANY supervisor's ``run()`` raises -- e.g.
        ``create_subprocess_exec`` failing with an OSError for a bad argv.
        The other supervisors are then neither cancelled nor awaited: they
        become orphaned asyncio Tasks with live game-bot subprocesses that
        nothing is tracking, still hitting the API, for as long as the
        parent process happens to keep running.

        ``return_exceptions=True`` keeps every supervisor tracked to its own
        natural completion -- none is ever silently abandoned -- and any
        failures are collected and re-raised once the whole pool is done,
        instead of on the very first one.
        """
        results = await asyncio.gather(
            *(
                self._run_after_stagger(index, supervisor)
                for index, supervisor in enumerate(self._supervisors)
            ),
            return_exceptions=True,
        )
        errors = [result for result in results if isinstance(result, BaseException)]
        if not errors:
            return
        if len(errors) == 1:
            raise errors[0]
        # BaseExceptionGroup accepts any BaseException (e.g. a CancelledError
        # slipping through alongside a real crash); Python auto-downgrades it
        # to a plain ExceptionGroup when every member is an Exception, which
        # is the common case here.
        raise BaseExceptionGroup("supervisor pool: multiple children failed", errors)

    async def _run_after_stagger(
        self, index: int, supervisor: CharacterSupervisor
    ) -> None:
        """Hold this child back `index * stagger_seconds` before spawning it.

        The delay is UNCONDITIONAL -- `sleep(0.0)` for the first child, and for
        every child of a single-character pool or a pool built with no stagger
        -- so there is no branch here to get the boundary wrong on: the roster's
        first character is never delayed, and a `--rate-budget`-less or
        one-child pool behaves exactly as it did before.

        It also applies once per child LIFETIME, not per restart: `run()` owns
        the restart loop internally, and a lone child restarting has nothing to
        collide with. Restart pacing stays `RestartPolicy`'s job.

        A genuinely-delayed child (`wait_seconds > 0`) is announced through
        `on_stagger` BEFORE the sleep, so the hold is visible the moment the
        pool starts rather than staying silent until the child eventually
        spawns -- that silence is exactly what read as "the program doesn't
        start up now" with several characters appearing dead at once. A child
        with nothing to wait for (index 0, or any pool built with no stagger)
        is never announced: `holding 0s` would misreport a delay that never
        happens.
        """
        wait_seconds = index * self._stagger_seconds
        if wait_seconds > 0 and self._on_stagger is not None:
            self._on_stagger(supervisor.character, wait_seconds)
        await self._sleep(wait_seconds)
        await supervisor.run()
