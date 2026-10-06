"""Whether the held items task should be worked now — shared by the root walk's
offer (through `decisions.route`) and the task objective's step (Phase
5-2c-iii-c-2 #4; this was the PURSUE_TASK discretionary rung's predicate)."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.task_decision import PURSUE, task_decision
from artifactsmmo_cli.ai.world_state import WorldState


def pursue_due(state: WorldState, game_data: GameData, history: LearningStore | None) -> bool:
    """A held, unmet items task the projection says to PURSUE
    (`task_decision`; PIVOT is the TASK_CANCEL rung's)."""
    return (state.task_type == "items"
            and bool(state.task_code) and state.task_total > 0
            and state.task_progress < state.task_total
            and history is not None
            and task_decision(state, game_data, history) == PURSUE)
