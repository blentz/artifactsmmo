"""LowYieldCancelGoal: cancel a task whose projected reward is worse than
alternatives, based on Phase G projections and scalarization.

Companion to (not replacement for) `TaskCancelGoal`, which only handles the
"target monster is too strong" case. This goal is strictly data-driven:
fires only when the learning store has enough samples to make a confident
projection AND a clear alternative beats the current task.
"""

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, col, select

from artifactsmmo_cli.ai import priorities
from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.task import TaskCancelAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.projections import (
    expected_yield_per_cycle,
    project_task_completion,
)
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

CONFIDENCE_THRESHOLD = 0.5
"""Don't cancel until projection confidence ≥ this. Below the threshold we
defer to existing hardcoded priorities and let the task run."""

ALTERNATIVE_MARGIN = 1.5
"""Cancel only when the alternative's scalar rate is at least this multiple
of the current task's rate. Higher = more conservative cancels."""


class LowYieldCancelGoal(Goal):
    """Cancel an in-flight task when projection says alternatives pay more."""

    def __init__(self, taskmaster_location: tuple[int, int] | None = None) -> None:
        self._taskmaster_location = taskmaster_location

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        return self.priority(state, game_data, history)

    def priority(self, state: WorldState, game_data: GameData,
                 history: LearningStore | None = None) -> float:
        if self.is_satisfied(state):
            return 0.0
        if history is None or not state.task_code:
            return 0.0

        # G-H: char_xp/cycle is the primary metric under the max-level
        # root objective. Other reward shapes (gold, skill_xp, coins) are
        # means to that end; they don't justify keeping a zero-char-XP
        # task running when alternatives pay actual char-XP per cycle.
        farm_items_yield = expected_yield_per_cycle("FarmItems", history)
        if farm_items_yield.sample_count == 0:
            return 0.0
        current_char_xp_per_cycle = farm_items_yield.char_xp

        # Alternative: best FarmMonster repr the bot has data on.
        alt_repr = self._best_alternative_repr(history)
        if alt_repr is None:
            return 0.0
        alt_yield = expected_yield_per_cycle(alt_repr, history)
        if alt_yield.sample_count == 0:
            return 0.0
        alternative_char_xp_per_cycle = alt_yield.char_xp

        # Zero-char-XP task case: any positive alternative beats it
        # immediately (no margin needed). Catches gudgeon-style tasks
        # that pay only at CompleteTask — when we see N cycles of pure
        # zero, fire ASAP instead of waiting for confidence to compound.
        if current_char_xp_per_cycle == 0 and alternative_char_xp_per_cycle > 0:
            return priorities.LOW_YIELD_CANCEL

        # Positive-but-low task case: require ALTERNATIVE_MARGIN to
        # avoid noise-driven flapping. Confidence threshold still
        # applies — don't act on tiny samples.
        projection = project_task_completion(state, history)
        if projection is None or projection.confidence < CONFIDENCE_THRESHOLD:
            return 0.0

        if alternative_char_xp_per_cycle < current_char_xp_per_cycle * ALTERNATIVE_MARGIN:
            return 0.0

        return priorities.LOW_YIELD_CANCEL

    def is_satisfied(self, state: WorldState) -> bool:
        return not state.task_code or state.task_total == 0

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"task_code": None, "task_total": 0}

    def relevant_actions(self, actions: list[Action], state: WorldState, game_data: GameData) -> list[Action]:
        return [a for a in actions if isinstance(a, TaskCancelAction)]

    @staticmethod
    def _best_alternative_repr(history: LearningStore) -> str | None:
        """Find the FarmMonster repr with the most observed cycles.

        FarmMonster reprs are per-monster, e.g. "FarmMonster(chicken)". The
        canonical alternative for this comparison is whichever monster the
        bot has actually been farming.
        """
        try:
            with Session(history._engine) as s:
                stmt = (
                    select(Cycle.selected_goal)
                    .where(
                        col(Cycle.character) == history._character,
                        col(Cycle.selected_goal).like("FarmMonster(%"),
                    )
                    .order_by(col(Cycle.id).desc())
                    .limit(50)
                )
                rows = list(s.exec(stmt))
        except SQLAlchemyError:
            return None
        if not rows:
            return None
        counts: dict[str, int] = {}
        for r in rows:
            counts[r] = counts.get(r, 0) + 1
        return max(counts, key=lambda k: counts[k])

    def __repr__(self) -> str:
        return "LowYieldCancel"
