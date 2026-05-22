"""Full-screen debug-level game log modal (toggled with 'l')."""

from collections.abc import Iterable
from typing import Any

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import RichLog

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot


def build_debug_log_line(snap: CycleSnapshot) -> str:
    """Rich-markup debug record for one cycle: the compact decision line plus
    task progress, vitals, cooldown, position, path-next, projected cycles, and
    the full goal-rank ranking (priority > 0)."""
    ts = snap.timestamp[11:19] if len(snap.timestamp) >= 19 else snap.timestamp
    outcome_color = {"ok": "green", "no_plan": "yellow"}.get(snap.outcome, "red")
    ranks = "  ".join(
        f"{gr.goal}={gr.priority:.0f}" for gr in snap.goal_rank if gr.priority > 0
    )
    task = f"{snap.task_progress}/{snap.task_total}" if snap.task_code else "-"
    proj = f"{snap.projected_cycles_to_max:.0f}" if snap.projected_cycles_to_max is not None else "?"
    return (
        f"[dim]{ts}[/dim] c{snap.cycle_index:>3} "
        f"[cyan]{snap.selected_goal}[/cyan] {snap.action} "
        f"[{outcome_color}]{snap.outcome}[/{outcome_color}] "
        f"| task {task} hp {snap.hp}/{snap.max_hp} cd {snap.cooldown_remaining:.1f} "
        f"pos ({snap.x},{snap.y}) next {snap.path_next_action or '?'} proj {proj} "
        f"| {ranks}"
    )


class LogScreen(Screen[None]):
    """Modal full-screen debug log. Dismiss with 'l' or Escape."""

    BINDINGS = [("escape", "dismiss", "Back"), ("l", "dismiss", "Back")]

    def __init__(self, history: Iterable[CycleSnapshot], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._history = list(history)

    def compose(self) -> ComposeResult:
        log = RichLog(wrap=False, markup=True, auto_scroll=True, id="debug-log")
        yield log

    def on_mount(self) -> None:
        log = self.query_one("#debug-log", RichLog)
        for snap in self._history:
            log.write(build_debug_log_line(snap))

    def update_snapshot(self, snap: CycleSnapshot) -> None:
        self.query_one("#debug-log", RichLog).write(build_debug_log_line(snap))
