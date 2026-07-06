"""RestoreHPGoal: restore HP to full, with urgency that spikes when HP is low."""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.thresholds import CRITICAL_HP_FRACTION
from artifactsmmo_cli.ai.world_state import WorldState

# Value returned when HP is critically low (< CRITICAL_HP_FRACTION).
# Beats every other goal's normal ceiling (UnlockBank=90, LowYieldCancel=70)
# so the bot heals/consumes before continuing combat.
_HP_CRITICAL = 110.0


class RestoreHPGoal(Goal):
    """Restore HP to full. Urgency spikes when HP is low.

    Below CRITICAL_HP_FRACTION the goal returns a value above any other goal's
    normal ceiling (UnlockBank=90, LowYieldCancel=70) so it preempts combat and
    drives Rest/UseConsumable immediately. Without that, combat-driving goals
    keep running until HP bottoms out (seen post-restart on real Robby: HP=13
    while UnlockBank kept fighting chickens).
    """

    preemptive = True  # HP-critical may interrupt a committed goal when it outranks it

    CRITICAL_HP_FRACTION = CRITICAL_HP_FRACTION  # from thresholds (module global)
    CRITICAL_HP_VALUE = _HP_CRITICAL

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if state.hp_percent < self.CRITICAL_HP_FRACTION:
            return self.CRITICAL_HP_VALUE
        return (1.0 - state.hp_percent) * 100.0

    def is_satisfied(self, state: WorldState) -> bool:
        return state.hp >= state.max_hp

    def relevant_actions(self, actions: list[Action], state: WorldState,
                         game_data: GameData) -> list[Action]:
        """Recovery, craft (cook-then-eat) and movement (reach the workshop)
        only. HP restoration can never require fighting, gathering or banking,
        but with the FULL action set the h=0 planner must exhaust every state
        cheaper than Rest's cost-10 before popping [Rest] — live probe
        2026-07-06: 1822 actions, 79s to find the 1-step plan, so the 10s
        cheap pass timed out every cycle and the HP guard never planned."""
        return [a for a in actions if a.tags & {"recovery", "craft", "movement"}]

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"hp": state.max_hp}

    def __repr__(self) -> str:
        return "RestoreHP"
