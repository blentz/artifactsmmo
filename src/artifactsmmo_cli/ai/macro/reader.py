"""Read-only loader: stream all-character Cycle rows and project to CycleRow."""

from artifactsmmo_cli.ai.macro.cycle_row import CycleRow
from artifactsmmo_cli.ai.trace_stats import load_cycles_from_db


def load_cycle_rows(db_path: str) -> list[CycleRow]:
    """All cycles across every character, ts-asc, projected to CycleRow."""
    return [
        CycleRow(
            character=c.character,
            session_id=c.session_id,
            cycle_index=c.cycle_index,
            level=c.level,
            selected_goal=c.selected_goal,
            action_class=c.action_class,
            planner_nodes=c.planner_nodes,
            planner_timed_out=c.planner_timed_out,
        )
        for c in load_cycles_from_db(db_path, character=None)
    ]
