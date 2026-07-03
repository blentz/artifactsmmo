"""Full-screen plan-tree modal (toggled with 'p'): an objective header above an
interactive collapsible prerequisite tree."""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.tui.plan_summary import build_plan_header
from artifactsmmo_cli.tui.widgets.plan_tree import PlanTree


class PlanScreen(Screen[None]):
    """Modal full-screen plan tree. Dismiss with 'p' or Escape."""

    DEFAULT_CSS = """
    #plan-modal #plan-header {
        padding: 1 2 0 2;
    }
    #plan-modal #plan-tree {
        width: 1fr;
        height: 1fr;
        padding: 0 2 1 2;
    }
    """

    BINDINGS = [
        ("escape", "dismiss", "Back"),
        ("p", "dismiss", "Back"),
    ]

    def __init__(self, snapshot: CycleSnapshot, game_data: GameData) -> None:
        super().__init__(id="plan-modal")
        self._snapshot = snapshot
        self._game_data = game_data

    def compose(self) -> ComposeResult:
        yield Static(build_plan_header(self._snapshot), id="plan-header")
        yield PlanTree(id="plan-tree")

    def on_mount(self) -> None:
        self.query_one("#plan-tree", PlanTree).set_nodes(self._snapshot.plan_tree)

    def update_snapshot(self, snap: CycleSnapshot) -> None:
        self._snapshot = snap
        if self.is_mounted:
            self.query_one("#plan-header", Static).update(build_plan_header(snap))
            self.query_one("#plan-tree", PlanTree).set_nodes(snap.plan_tree)
