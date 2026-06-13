"""Full-screen plan-tree modal (toggled with 'p')."""

from rich.console import RenderableType
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Static

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.tui.plan_summary import build_plan_summary


def build_plan_detail(snap: CycleSnapshot, game_data: GameData) -> RenderableType:
    """Adapter: pull the plan-relevant fields off the snapshot and render."""
    return build_plan_summary(
        snap.chosen_root, snap.strategy_ranking, snap.inventory, snap.bank_items,
        game_data, snap.projected_cycles_to_max,
        xp=snap.xp, max_xp=snap.max_xp, skill_xp=snap.skill_xp,
        task_code=snap.task_code, task_progress=snap.task_progress,
        task_total=snap.task_total, path_next_action=snap.path_next_action,
    )


class PlanScreen(Screen[None]):
    """Modal full-screen plan tree. Dismiss with 'p' or Escape."""

    # Fill the screen. (The screen's own layout is reset from the app's grid in
    # WatchApp.CSS, where app-level rules can outrank this DEFAULT_CSS.)
    DEFAULT_CSS = """
    #plan-modal #plan-scroll {
        width: 1fr;
        height: 1fr;
        padding: 1 2;
    }
    """

    BINDINGS = [("escape", "dismiss", "Back"), ("p", "dismiss", "Back")]

    def __init__(self, snapshot: CycleSnapshot, game_data: GameData) -> None:
        super().__init__(id="plan-modal")
        self._snapshot = snapshot
        self._game_data = game_data

    def compose(self) -> ComposeResult:
        # Scroll container so a tall plan tree scrolls instead of clipping.
        with VerticalScroll(id="plan-scroll"):
            yield Static(build_plan_detail(self._snapshot, self._game_data), id="plan-detail")

    def update_snapshot(self, snap: CycleSnapshot) -> None:
        self._snapshot = snap
        self.query_one("#plan-detail", Static).update(build_plan_detail(snap, self._game_data))
