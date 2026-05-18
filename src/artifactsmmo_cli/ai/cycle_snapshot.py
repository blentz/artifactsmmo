"""CycleSnapshot: frozen per-cycle state + decision context for TUI consumers."""

from pydantic import BaseModel, Field


class GoalRankEntry(BaseModel):
    """One row in the per-cycle goal-priority ladder."""

    goal: str
    priority: float


class CycleSnapshot(BaseModel):
    """Everything a watcher needs about one bot cycle. Frozen at end-of-cycle."""

    cycle_index: int
    timestamp: str  # ISO-8601 UTC
    character: str

    # State
    x: int
    y: int
    level: int
    xp: int
    max_xp: int
    hp: int
    max_hp: int
    gold: int
    inventory: dict[str, int] = Field(default_factory=dict)
    inventory_max: int = 0
    equipment: dict[str, str | None] = Field(default_factory=dict)
    skills: dict[str, int] = Field(default_factory=dict)
    skill_xp: dict[str, int] = Field(default_factory=dict)
    task_code: str | None = None
    task_type: str | None = None
    task_progress: int = 0
    task_total: int = 0

    # Decision
    selected_goal: str
    action: str
    outcome: str
    goal_rank: list[GoalRankEntry] = Field(default_factory=list)
    path_next_action: str | None = None
    projected_cycles_to_max: float | None = None
    max_level: int = 0
    remaining_levels: int = 0
