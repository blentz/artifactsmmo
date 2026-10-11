"""JoinPartyGoal: go to a live party lease's tile and hold there
(docs/PLAN_group_fights.md increment 4; the `PARTY_JOIN` guard's goal).

USER 2026-10-10 ruling 2, "always": a lease naming this character as a
member pulls it off its own objective — so the goal is a GUARD's (an
interrupt that leaves the commitment to resume), not a root alternative
served on its rotation turn, which would walk the member off the tile after
one hold."""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.hold_for_party import HoldForPartyAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.party_lease_core import PartyLease
from artifactsmmo_cli.ai.world_state import WorldState

JOIN_PARTY_VALUE = 40.0
"""Guard-tier value: guards run on the fixed ladder, not by value; positive
while unsatisfied is all that is read."""


class JoinPartyGoal(Goal):
    """Hold on `lease`'s tile (one `HoldForPartyAction`, movement folded in)."""

    def __init__(self, lease: PartyLease, game_data: GameData) -> None:
        self._lease = lease
        self._region = game_data.region_of(lease.x, lease.y, lease.layer)

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        return 0.0 if self.is_satisfied(state) else JOIN_PARTY_VALUE

    def is_satisfied(self, state: WorldState) -> bool:
        return state.party_held == self._lease.boss

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"party_held": self._lease.boss}

    def relevant_actions(self, actions: list[Action], state: WorldState,
                         game_data: GameData) -> list[Action]:
        return [HoldForPartyAction(lease=self._lease, travel_region=self._region)]

    def __repr__(self) -> str:
        return f"JoinParty({self._lease.boss})"
