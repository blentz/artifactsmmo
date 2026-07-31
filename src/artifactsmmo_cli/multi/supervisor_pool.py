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
        await asyncio.gather(*(s.run() for s in self._supervisors))
