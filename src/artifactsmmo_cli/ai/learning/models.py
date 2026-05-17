"""SQLModel definitions for the GOAP learning store.

Each model is simultaneously a Pydantic model (validation at construction)
and a SQLAlchemy ORM row (persistence).
"""

from typing import Any

from pydantic import TypeAdapter
from sqlmodel import Field, SQLModel
from sqlmodel._compat import finish_init

_FLOAT_FIELDS: frozenset[str] = frozenset(
    {"predicted_cost", "actual_cooldown_seconds"}
)
_validate_float: TypeAdapter[float | None] = TypeAdapter(float | None)


class Cycle(SQLModel, table=True):
    """One row per player-loop cycle."""

    __tablename__ = "cycles"

    id: int | None = Field(default=None, primary_key=True)

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

    # Goal completion tracking
    cycles_to_satisfy: int | None = None

    def __init__(self, **data: Any) -> None:
        if finish_init.get():
            for field in _FLOAT_FIELDS:
                if field in data:
                    _validate_float.validate_python(data[field])
        super().__init__(**data)
