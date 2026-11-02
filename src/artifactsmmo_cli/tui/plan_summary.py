"""Pure builder for the plan screen's header block: the objective line. The
plan body itself is rendered by the PlanTree widget from the snapshot's
plan_tree."""

from rich.console import Group, RenderableType
from rich.text import Text

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot


def build_plan_header(snap: CycleSnapshot) -> RenderableType:
    """Objective header for the plan screen."""
    parts: list[RenderableType] = [
        Text(f"OBJECTIVE  reach level {snap.max_level}", style="bold")
    ]
    if snap.chosen_root is None:
        parts.append(Text("No committed objective this cycle."))
    return Group(*parts)
