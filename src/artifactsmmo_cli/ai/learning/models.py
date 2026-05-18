"""SQLModel definitions for the GOAP learning store.

The two-model pattern: `CycleBase` is a non-table SQLModel (full Pydantic
validation at construction). `Cycle(CycleBase, table=True)` adds persistence.

Construct as `Cycle.model_validate(data)` or `Cycle(**CycleBase(...).model_dump())`
to get validation; construct as `Cycle(...)` directly to skip validation (SQLModel's
default for table models, optimised for ORM round-trips).
"""

from sqlmodel import Field, SQLModel


class CycleBase(SQLModel):
    """Non-table base: Pydantic validates all fields at construction."""

    ts: str = Field(index=True)
    session_id: str = Field(index=True)
    cycle_index: int
    character: str = Field(index=True)

    # State snapshot
    x: int | None = None
    y: int | None = None
    hp: int | None = None
    max_hp: int | None = None
    gold: int | None = None
    level: int | None = None
    xp: int | None = None
    inventory_used: int | None = None
    inventory_max: int | None = None
    bank_accessible: bool = True
    task_code: str | None = None
    task_type: str | None = None
    task_progress: int | None = None
    task_total: int | None = None

    # Goal + action
    selected_goal: str | None = Field(default=None, index=True)
    action_repr: str | None = Field(default=None, index=True)
    action_class: str | None = None
    outcome: str

    # Cost & planner
    predicted_cost: float | None = None
    actual_cooldown_seconds: float | None = None
    planner_nodes: int | None = None
    planner_depth: int | None = None
    planner_timed_out: bool | None = None
    plan_len: int | None = None

    # Effects (state delta from previous cycle)
    delta_gold: int | None = None
    delta_xp: int | None = None
    delta_hp: int | None = None
    delta_inv_used: int | None = None
    drops_json: str | None = None
    # Per-skill XP delta as JSON {skill_name: int}. Sparse — only skills
    # whose XP actually changed appear. Default "{}" so old rows are valid.
    # Read by Phase G-B projections to attribute skill-XP yield per cycle.
    delta_skill_xp_json: str = Field(default="{}")

    # Goal completion tracking
    cycles_to_satisfy: int | None = None


class Cycle(CycleBase, table=True):
    """ORM-persisted Cycle. Inherits all fields from CycleBase."""

    __tablename__ = "cycles"

    id: int | None = Field(default=None, primary_key=True)


class SessionBase(SQLModel):
    """Non-table base: Pydantic validates all fields at construction."""

    started_at: str
    character: str = Field(index=True)
    ended_at: str | None = None
    cycle_count: int = 0
    exit_reason: str | None = None


class Session(SessionBase, table=True):
    """ORM-persisted Session row, one per GamePlayer.run() invocation."""

    __tablename__ = "sessions"

    session_id: str = Field(primary_key=True)
