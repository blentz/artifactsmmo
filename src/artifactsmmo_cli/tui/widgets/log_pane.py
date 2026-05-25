"""Scrolling log of per-cycle decisions. Wraps Textual's RichLog."""

from typing import Any

from textual.widgets import RichLog

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot


class LogPane(RichLog):
    """Append-only decision log. Auto-scrolls to bottom."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(wrap=False, markup=True, auto_scroll=True, **kwargs)

    def update_snapshot(self, snap: CycleSnapshot) -> None:
        outcome_color = {"ok": "green", "no_plan": "yellow"}.get(snap.outcome, "red")
        # Compact, scan-friendly format: time, cycle, goal, action, outcome.
        # Use only the HH:MM:SS portion of the timestamp.
        ts = snap.timestamp[11:19] if len(snap.timestamp) >= 19 else snap.timestamp
        line = (
            f"[dim]{ts}[/dim] "
            f"c{snap.cycle_index:>3} "
            f"[cyan]{snap.selected_goal:<25}[/cyan] "
            f"{snap.action:<35} "
            f"[{outcome_color}]{snap.outcome}[/{outcome_color}]"
        )
        self.write(line)
