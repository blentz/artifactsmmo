"""GrindCharacterXPGoal: kill monsters for character XP when no task is held
and the projection says monster grinding is the highest-yield use of cycles.

This is the strategic counterpart to taskmaster-driven grinding: when Robby
has no task assigned, he should pursue the most XP-rewarding monster he can
beat reliably, rather than falling back to a low-tier default.
"""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.equipment.scoring import pick_loadout
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.projections import expected_yield_per_cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.priority_band import clamp_into_band
from artifactsmmo_cli.ai.world_state import WorldState

# Lower bound when active — matches FarmMonster cold-start default (from retired priorities.py).
PRIORITY_FLOOR = 30.0
"""Minimum priority when active. Matches existing FarmMonster default so the
goal doesn't regress behavior in the cold-start case."""

# Upper bound — stays under LowYieldCancelGoal(70) and LevelSkillGoal(55).
PRIORITY_CEILING = 45.0
"""Cap on the projected-scalar contribution. Stays under LowYieldCancelGoal(70),
LevelSkillGoal(55), and ensures survival/bank goals always dominate."""

SCALAR_TO_PRIORITY_GAIN = 5.0
"""Per scalar-yield unit, how much extra priority. Tuned so a goal pulling
~3 char-XP/cycle (scalar ≈ 6 at level 1) clears the ceiling."""


class GrindCharacterXPGoal(Goal):
    """Farm a specific monster for character XP. Only active when no task held."""

    def __init__(self, target_monster: str, initial_xp: int = 0,
                 game_data: GameData | None = None) -> None:
        self._target_monster = target_monster
        self._initial_xp = initial_xp
        self._game_data = game_data

    def _loadout_optimal(self, state: WorldState) -> bool:
        if self._game_data is None:
            return True
        optimal = pick_loadout(self._target_monster, state, self._game_data)
        return all(state.equipment.get(slot) == code for slot, code in optimal.items())

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if self.is_satisfied(state):
            return 0.0
        if history is None:
            return PRIORITY_FLOOR

        fight_yield = expected_yield_per_cycle(f"FarmMonster({self._target_monster})", history)
        if fight_yield.sample_count == 0:
            return PRIORITY_FLOOR
        # G-H: under max-level root objective, char_xp/cycle is the metric.
        # Scalar (used previously) mixed in gold/skill_xp which dilute the
        # signal — we explicitly want to rank by character progression rate.
        bonus = fight_yield.char_xp * SCALAR_TO_PRIORITY_GAIN
        # Floor-clamp so an unlucky run of observed-negative char_xp can't
        # push priority below PRIORITY_FLOOR and permanently suppress the only
        # combat goal (leaving the bot with no plan when no task is held).
        return clamp_into_band(PRIORITY_FLOOR, PRIORITY_CEILING, bonus)

    def is_satisfied(self, state: WorldState) -> bool:
        return state.xp > self._initial_xp and self._loadout_optimal(state)

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"xp": self._initial_xp + 10}

    def relevant_actions(
        self, actions: list[Action], state: WorldState, game_data: GameData
    ) -> list[Action]:
        """Fight the target monster + HP recovery only — no diversions."""
        result: list[Action] = []
        for action in actions:
            if isinstance(action, FightAction) and action.monster_code == self._target_monster:
                result.append(action)
            elif "recovery" in action.tags:
                result.append(action)
            # OptimizeLoadoutAction for this target (bare Equip/Unequip lack target_monster_code)
            elif "equip" in action.tags and getattr(action, "target_monster_code", None) == self._target_monster:
                result.append(action)
        return result

    def __repr__(self) -> str:
        return f"GrindCharacterXP({self._target_monster})"
