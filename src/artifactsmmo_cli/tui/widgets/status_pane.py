"""Character status pane: HP/XP bars, level, gold, current goal, path projection."""

from rich.console import Group
from rich.progress_bar import ProgressBar
from rich.table import Table
from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot


class StatusPane(Static):
    snapshot: reactive[CycleSnapshot | None] = reactive(None)

    def update_snapshot(self, snap: CycleSnapshot) -> None:
        self.snapshot = snap

    def render(self):
        snap = self.snapshot
        if snap is None:
            return Text("Waiting...")
        return self._render_status(snap)

    def _render_status(self, s: CycleSnapshot) -> Group:
        # HP bar — red when critical
        hp_pct = s.hp / s.max_hp if s.max_hp else 0
        hp_color = "red" if hp_pct < 0.25 else ("yellow" if hp_pct < 0.5 else "green")
        hp_bar = ProgressBar(total=s.max_hp, completed=s.hp,
                              complete_style=hp_color, finished_style=hp_color, width=20)
        # XP bar
        xp_bar = ProgressBar(total=max(1, s.max_xp), completed=min(s.xp, s.max_xp),
                              complete_style="cyan", finished_style="cyan", width=20)

        t = Table(box=None, padding=(0, 1), show_header=False)
        t.add_column("k", style="dim")
        t.add_column("v")
        t.add_row("Char", f"[bold]{s.character}[/bold]  L{s.level}")
        t.add_row("HP", Group(hp_bar, Text(f"{s.hp}/{s.max_hp}", style=hp_color)))
        t.add_row("XP", Group(xp_bar, Text(f"{s.xp}/{s.max_xp}")))
        t.add_row("Gold", str(s.gold))
        t.add_row("Pos", f"({s.x},{s.y})")
        if s.task_code:
            t.add_row("Task", f"{s.task_code}  {s.task_progress}/{s.task_total}")
        else:
            t.add_row("Task", "[dim]none[/dim]")

        t.add_row("", "")
        t.add_row("Goal", f"[bold]{s.selected_goal}[/bold]")
        outcome_color = {"ok": "green", "no_plan": "yellow"}.get(s.outcome, "red")
        t.add_row("Action", f"{s.action}  [{outcome_color}]{s.outcome}[/{outcome_color}]")

        t.add_row("", "")
        t.add_row("Path", f"→ L{s.max_level}")
        if s.projected_cycles_to_max is not None:
            t.add_row("Cyc left", f"{s.projected_cycles_to_max:.0f}")
        else:
            t.add_row("Cyc left", "[dim]?[/dim]")
        t.add_row("Next", s.path_next_action or "[dim]?[/dim]")

        # Top 3 goal ranks
        if s.goal_rank:
            rank_lines = "\n".join(
                f"  {gr.priority:5.1f}  {gr.goal}" for gr in s.goal_rank[:3] if gr.priority > 0
            )
            if rank_lines:
                t.add_row("", "")
                t.add_row("Top", Text(rank_lines, style="dim"))

        return t
