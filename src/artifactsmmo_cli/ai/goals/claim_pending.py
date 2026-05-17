"""ClaimPendingGoal: claim any pending items available on the account."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState


class ClaimPendingGoal(Goal):
    """Claim pending items (achievements, GE order completions, etc.) when available."""

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if not state.pending_items:
            return 0.0
        return 25.0

    def is_satisfied(self, state: WorldState) -> bool:
        return not state.pending_items

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"pending_items": None}

    def __repr__(self) -> str:
        return "ClaimPending"
