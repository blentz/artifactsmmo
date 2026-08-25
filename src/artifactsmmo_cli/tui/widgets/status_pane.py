"""Character status pane: HP/XP bars, level, gold, current goal, path projection."""

import math
import time
from datetime import datetime
from typing import Any

from rich.console import Group, RenderableType
from rich.progress_bar import ProgressBar
from rich.table import Table
from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot

ETA_WINDOW = 20
"""Number of recent (time, progress) samples used to estimate task ETA."""


def _epoch(timestamp: str) -> float:
    """ISO-8601 (UTC, possibly trailing 'Z') -> epoch seconds."""
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).timestamp()


def cooldown_expiry_epoch(timestamp: str, cooldown_remaining: float, now: float) -> float | None:
    """Wall-clock epoch at which a snapshot's cooldown ends; None once it is over.

    `cooldown_remaining` is the value AS OF `timestamp` — a `CycleSnapshot` is
    frozen at end-of-cycle — NOT as of display time. Anchoring the countdown at
    display time (`monotonic() + cooldown_remaining`) restarted it from full
    every time the pane was re-bound, so a snapshot captured two minutes ago
    counted down its whole cooldown again on a character switch.

    Both ends of this subtraction are WALL CLOCK: the anchor is a UTC timestamp
    produced by the bot process, so `now` must come from `time.time()`. Mixing
    in `time.monotonic()` — whose epoch is an arbitrary process-local zero —
    would be the very bug being fixed here.

    Elapsed is floored at zero so that a TUI clock running BEHIND the bot's
    cannot print a countdown longer than the cooldown the server published: the
    worst skew shows the full cooldown, never more. A snapshot old enough that
    its cooldown has expired yields None, i.e. "ready", which is the truth.
    """
    elapsed = max(0.0, now - _epoch(timestamp))
    remaining = cooldown_remaining - elapsed
    return now + remaining if remaining > 0 else None


def task_eta_seconds(samples: list[tuple[float, int]], remaining: int) -> float | None:
    """Estimate seconds to finish `remaining` task units from (time, progress)
    samples. None when there is too little data or no positive progress rate."""
    if len(samples) < 2:
        return None
    t0, p0 = samples[0]
    t1, p1 = samples[-1]
    span = t1 - t0
    gained = p1 - p0
    if span <= 0 or gained <= 0:
        return None
    rate = gained / span
    return remaining / rate


def format_eta(seconds: float) -> str:
    """Human ETA: '~45s' under a minute, else '~Xm Ys'."""
    total = int(seconds)
    if total < 60:
        return f"~{total}s"
    return f"~{total // 60}m {total % 60}s"


class StatusPane(Static):
    snapshot: reactive[CycleSnapshot | None] = reactive(None)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._eta_task: str | None = None
        self._eta_samples: list[tuple[float, int]] = []
        self._cooldown_expiry: float | None = None

    def update_snapshot(self, snap: CycleSnapshot) -> None:
        self._track_eta(snap)
        self._cooldown_expiry = cooldown_expiry_epoch(
            snap.timestamp, snap.cooldown_remaining, time.time()
        )
        self.snapshot = snap

    def rebind(self, snap: CycleSnapshot | None) -> None:
        """Point this pane at a different character.

        The ETA samples and the cooldown expiry are per-character transient
        state. Without clearing them a focus switch left the previous
        character's cooldown counting down and its task-ETA history feeding a
        projection for someone else. `None` means the new character has
        produced no cycle yet, so the pane goes blank rather than keep showing
        the previous character's numbers.

        Clearing stays load-bearing after the countdown was re-based on the
        snapshot's own timestamp: a `None` snapshot never reaches
        `update_snapshot`, so without the clear the OLD character's expiry
        would survive the switch and keep ticking under the new name.
        """
        self._eta_task = None
        self._eta_samples = []
        self._cooldown_expiry = None
        if snap is None:
            self.snapshot = None
            return
        self.update_snapshot(snap)

    def on_mount(self) -> None:
        """Tick once a second so the cooldown counts down between AI cycles."""
        self.set_interval(1.0, self._tick)

    def _tick(self) -> None:
        if self._cooldown_expiry is not None:
            self.refresh()
            if self._cooldown_remaining() <= 0.0:
                self._cooldown_expiry = None

    def _cooldown_remaining(self) -> float:
        """Seconds left on the focused character's cooldown, right now.

        `_cooldown_expiry` is a wall-clock epoch (see `cooldown_expiry_epoch`),
        so the clock read here must be `time.time()` to match it.
        """
        if self._cooldown_expiry is None:
            return 0.0
        return max(0.0, self._cooldown_expiry - time.time())

    def _track_eta(self, snap: CycleSnapshot) -> None:
        if not snap.task_code:
            self._eta_task = None
            self._eta_samples = []
            return
        if snap.task_code != self._eta_task:
            self._eta_task = snap.task_code
            self._eta_samples = []
        self._eta_samples.append((_epoch(snap.timestamp), snap.task_progress))
        if len(self._eta_samples) > ETA_WINDOW:
            self._eta_samples = self._eta_samples[-ETA_WINDOW:]

    def render(self) -> RenderableType:
        snap = self.snapshot
        return Text("Waiting...") if snap is None else self._render_status(snap)

    def _render_status(self, s: CycleSnapshot) -> Table:
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
        t.add_row("HP", Group(Text(f"{s.hp}/{s.max_hp}", style=hp_color), hp_bar))
        t.add_row("XP", Group(Text(f"{s.xp}/{s.max_xp}", style="cyan"), xp_bar))
        t.add_row("Gold", str(s.gold))
        t.add_row("Pos", f"({s.x},{s.y})")
        cd_remaining = self._cooldown_remaining()
        if cd_remaining > 0:
            cd_color = "yellow" if cd_remaining < 10 else "red"
            t.add_row("Cooldown", f"[{cd_color}]{math.ceil(cd_remaining)}s[/{cd_color}]")
        else:
            t.add_row("Cooldown", "[green]ready[/green]")
        if s.task_code:
            t.add_row("Task", f"{s.task_code}  {s.task_progress}/{s.task_total}")
            remaining = max(0, s.task_total - s.task_progress)
            eta = task_eta_seconds(self._eta_samples, remaining)
            t.add_row("ETA", format_eta(eta) if eta is not None else "[dim]—[/dim]")
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
