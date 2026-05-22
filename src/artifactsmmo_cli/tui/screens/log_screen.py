"""Full-screen debug-level game log modal (toggled with 'l')."""

from collections.abc import Iterable
from typing import Any

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import RichLog

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot


def build_debug_log_line(snap: CycleSnapshot) -> str:
    """Rich-markup trace record for one cycle — the same per-cycle detail the
    file tracer writes to traces.jsonl, rendered as a multi-line block:

    - decision header (ts, cycle, goal, action, outcome);
    - planner internals (nodes/depth/plan_len/timeout) + task progress, vitals,
      cooldown, position, path-next, projected cycles, path-blocked;
    - every planner attempt (goals_tried) with its own nodes/depth/plan_len;
    - the full goal-rank ranking (priority > 0);
    - suppressed goals (only when any are active).
    """
    ts = snap.timestamp[11:19] if len(snap.timestamp) >= 19 else snap.timestamp
    outcome_color = {"ok": "green", "no_plan": "yellow"}.get(snap.outcome, "red")
    task = f"{snap.task_progress}/{snap.task_total}" if snap.task_code else "-"
    proj = f"{snap.projected_cycles_to_max:.0f}" if snap.projected_cycles_to_max is not None else "?"
    timeout = "yes" if snap.planner_timed_out else "no"
    blocked = "yes" if snap.path_blocked else "no"

    lines = [
        f"[dim]{ts}[/dim] c{snap.cycle_index:>3} "
        f"[cyan]{snap.selected_goal}[/cyan] {snap.action} "
        f"[{outcome_color}]{snap.outcome}[/{outcome_color}]",
        f"  [dim]planner[/dim] nodes={snap.planner_nodes} depth={snap.planner_depth} "
        f"plan_len={snap.plan_len} timeout={timeout} "
        f"| task {task} hp {snap.hp}/{snap.max_hp} cd {snap.cooldown_remaining:.1f} "
        f"pos ({snap.x},{snap.y}) next {snap.path_next_action or '?'} proj {proj} blocked={blocked}",
    ]
    if snap.goals_tried:
        attempts = "  ".join(
            f"{g.goal}(n={g.nodes} d={g.depth} len={g.plan_len}{' TIMEOUT' if g.timed_out else ''})"
            for g in snap.goals_tried
        )
        lines.append(f"  [dim]goals[/dim] {attempts}")
    ranks = "  ".join(
        f"{gr.goal}={gr.priority:.0f}" for gr in snap.goal_rank if gr.priority > 0
    )
    lines.append(f"  [dim]rank[/dim] {ranks}")
    if snap.suppressed_goals:
        lines.append(f"  [dim]suppressed[/dim] {'  '.join(snap.suppressed_goals)}")
    return "\n".join(lines)


class LogScreen(Screen[None]):
    """Modal full-screen debug log. Dismiss with 'l' or Escape."""

    # Fill the screen. (The screen's own layout is reset from the app's grid in
    # WatchApp.CSS, where app-level rules can outrank this DEFAULT_CSS.)
    DEFAULT_CSS = """
    #log-modal #debug-log {
        width: 1fr;
        height: 1fr;
    }
    """

    BINDINGS = [("escape", "dismiss", "Back"), ("l", "dismiss", "Back")]

    def __init__(self, history: Iterable[CycleSnapshot], **kwargs: Any) -> None:
        super().__init__(id="log-modal", **kwargs)
        self._history = list(history)

    def compose(self) -> ComposeResult:
        log = RichLog(wrap=True, markup=True, auto_scroll=True, id="debug-log")
        yield log

    def on_mount(self) -> None:
        log = self.query_one("#debug-log", RichLog)
        for snap in self._history:
            log.write(build_debug_log_line(snap))

    def update_snapshot(self, snap: CycleSnapshot) -> None:
        self.query_one("#debug-log", RichLog).write(build_debug_log_line(snap))
