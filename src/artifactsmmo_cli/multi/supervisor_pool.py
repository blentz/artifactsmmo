"""SupervisorPool: owns every character's supervisor and runs them together."""

import asyncio
from collections.abc import Sequence

from artifactsmmo_cli.multi.character_supervisor import CharacterSupervisor
from artifactsmmo_cli.multi.child_state import ChildState


class SupervisorPool:
    """Runs one CharacterSupervisor per character, concurrently.

    Roster order is preserved: it comes from the account and is the tiebreak
    for sprite draw order, so it must never be re-sorted.
    """

    def __init__(self, supervisors: Sequence[CharacterSupervisor]) -> None:
        self._supervisors = tuple(supervisors)
        self._by_name = {s.character: s for s in self._supervisors}

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
            *(s.run() for s in self._supervisors), return_exceptions=True
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
