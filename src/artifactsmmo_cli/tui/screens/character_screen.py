"""Full-screen character detail modal (toggled with 'c')."""

from rich.console import RenderableType
from rich.table import Table
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Static

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot


def build_character_detail(snap: CycleSnapshot) -> RenderableType:
    """Full character detail from a snapshot: vitals, all skills (level + xp),
    every equipment slot, and the current task. Combat stats are not in the
    snapshot and are intentionally omitted."""
    t = Table(box=None, padding=(0, 2), show_header=False, title=f"{snap.character}  L{snap.level}")
    t.add_column("k", style="dim")
    t.add_column("v")
    t.add_row("HP", f"{snap.hp}/{snap.max_hp}")
    t.add_row("XP", f"{snap.xp}/{snap.max_xp}")
    t.add_row("Gold", str(snap.gold))
    t.add_row("Pos", f"({snap.x},{snap.y})")
    if snap.task_code:
        t.add_row("Task", f"{snap.task_code}  {snap.task_progress}/{snap.task_total}")
    else:
        t.add_row("Task", "none")
    t.add_row("", "")
    for skill in sorted(snap.skills):
        xp = snap.skill_xp.get(skill, 0)
        t.add_row(skill, f"L{snap.skills[skill]}   xp {xp}")
    t.add_row("", "")
    for slot in sorted(snap.equipment):
        t.add_row(slot, snap.equipment[slot] or "—")
    return t


class CharacterScreen(Screen[None]):
    """Modal full-screen character detail. Dismiss with 'c' or Escape."""

    BINDINGS = [("escape", "dismiss", "Back"), ("c", "dismiss", "Back")]

    def __init__(self, snapshot: CycleSnapshot) -> None:
        super().__init__()
        self._snapshot = snapshot

    def compose(self) -> ComposeResult:
        # Scroll container so a tall character sheet scrolls instead of clipping.
        with VerticalScroll():
            yield Static(build_character_detail(self._snapshot), id="char-detail")

    def update_snapshot(self, snap: CycleSnapshot) -> None:
        self._snapshot = snap
        self.query_one("#char-detail", Static).update(build_character_detail(snap))
