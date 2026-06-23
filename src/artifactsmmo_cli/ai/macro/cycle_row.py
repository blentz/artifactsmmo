"""Light projection of a learning-store Cycle for macro-research analysis,
decoupled from the SQLModel ORM so the pure analysis cores test without a DB."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CycleRow:
    character: str
    session_id: str
    cycle_index: int
    level: int | None
    selected_goal: str | None
    action_class: str | None
    planner_nodes: int | None
    planner_timed_out: bool | None
