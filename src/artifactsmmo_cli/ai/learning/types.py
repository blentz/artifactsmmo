"""Pydantic models for data returned by LearningStore queries (not persisted)."""

from pydantic import BaseModel, ConfigDict


class ActionStats(BaseModel):
    """Aggregated statistics for one action_repr."""

    model_config = ConfigDict(frozen=True)

    action_repr: str
    sample_count: int
    median_cost_seconds: float | None
    success_rate: float
    median_delta_xp: float | None
    median_delta_gold: float | None


class GoalStats(BaseModel):
    """Aggregated statistics for one goal_repr."""

    model_config = ConfigDict(frozen=True)

    goal_repr: str
    sample_count: int
    avg_cycles_to_satisfy: float | None
    satisfaction_rate: float
