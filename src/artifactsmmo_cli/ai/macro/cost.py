"""Per-goal-type A* search-cost aggregation over realized cycles."""

from collections import defaultdict
from dataclasses import dataclass

from artifactsmmo_cli.ai.macro.cycle_row import CycleRow


def parse_goal_type(selected_goal: str | None) -> str:
    if not selected_goal:
        return "<none>"
    return selected_goal.split("(", 1)[0]


@dataclass(frozen=True)
class CostStat:
    goal_type: str
    n_cycles: int
    total_nodes: int
    mean_nodes: float
    timeouts: int


def cost_by_goal_type(rows: list[CycleRow]) -> list[CostStat]:
    nodes: dict[str, int] = defaultdict(int)
    counts: dict[str, int] = defaultdict(int)
    timeouts: dict[str, int] = defaultdict(int)
    for r in rows:
        gt = parse_goal_type(r.selected_goal)
        nodes[gt] += r.planner_nodes or 0
        counts[gt] += 1
        if r.planner_timed_out:
            timeouts[gt] += 1
    stats = [
        CostStat(gt, counts[gt], nodes[gt],
                 nodes[gt] / counts[gt] if counts[gt] else 0.0, timeouts[gt])
        for gt in counts
    ]
    return sorted(stats, key=lambda s: s.total_nodes, reverse=True)
