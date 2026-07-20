"""ParticipateRaidGoal: contribute damage to an open raid boss (epic P4c).

The last link in the raid chain. `raid_participation` decides WHETHER to engage
and `factory` emits the FightAction at the raid tile, but goals filter
`relevant_actions` and nothing targeted the boss -- so the action existed and was
never selectable.

Participation is throughput, not victory: upstream states a raid fight is won by
"surviving all 100 turns or finishing the boss", the boss carries a shared HP pool
across every participating account, and rewards are damage-thresholded (1 event
ticket per 20,000 damage, changelog 8.2.0). So this goal deliberately does NOT
consult `is_winnable` -- see `raid_participation` for the two gates that replace
it.

Rides the DISCRETIONARY band as a plain candidate with NO new `MeansKind`: a new
kind ripples through the ladder, `DecideKey.lean` and the E-tower rows (the
EquipOwnedGoal lesson). Discretionary already yields to every guard and objective
step, which is the right priority for a timed bonus -- a raid must never preempt
survival or a committed gear step.
"""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

RAID_PARTICIPATION_VALUE = 20.0
"""Below the survival floor and below GATHER_MATERIALS (50): a raid is a timed
bonus, never a reason to skip healing or a committed step. Vestigial for routing
(the arbiter selects by band position, not value) but kept consistent with its
neighbours so it does not read as a priority claim it cannot make."""


class ParticipateRaidGoal(Goal):
    """Fight an open raid's boss at its tile, for damage-thresholded rewards."""

    def __init__(self, raid_code: str, monster_code: str, xp_floor: int) -> None:
        self._raid_code = raid_code
        self._monster_code = monster_code
        self._xp_floor = xp_floor

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        return RAID_PARTICIPATION_VALUE

    def is_satisfied(self, state: WorldState) -> bool:
        """Satisfied by ONE engagement, measured as XP above the floor captured
        when the goal was built this cycle.

        There is no "done" for a raid itself -- the boss has a shared pool nobody
        finishes alone, and every fight adds damage toward the next reward
        threshold. But a goal that is NEVER satisfied gives A* no goal test, so
        the search runs to max_depth and returns no plan at all; the candidate is
        then rejected and the raid is never selected (observed exactly that before
        this floor existed).

        So the unit of work is one engagement. The goal re-arms next cycle from a
        fresh floor while the window stays open, which is also what keeps the bot
        re-deciding between engagements instead of committing to a long raid plan
        it cannot re-evaluate.
        """
        return state.xp > self._xp_floor

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {}

    def relevant_actions(self, actions: list[Action], state: WorldState,
                         game_data: GameData) -> list[Action]:
        """Only the boss's own fight. The factory emits it from the raid tile
        (gated on the window being open), so no location logic is repeated here."""
        return [a for a in actions
                if isinstance(a, FightAction) and a.monster_code == self._monster_code]

    def __repr__(self) -> str:
        return f"ParticipateRaid({self._raid_code})"
