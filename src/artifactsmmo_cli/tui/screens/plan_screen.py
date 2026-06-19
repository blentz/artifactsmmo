"""Full-screen plan-tree modal (toggled with 'p')."""

from rich.console import RenderableType
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Static

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.tui.plan_summary import ALT_PAGE_SIZE, build_plan_summary


def build_plan_detail(snap: CycleSnapshot, game_data: GameData, alt_page: int = 0) -> RenderableType:
    """Adapter: pull the plan-relevant fields off the snapshot and render."""
    return build_plan_summary(
        snap.chosen_root, snap.strategy_ranking, snap.inventory, snap.bank_items,
        game_data, snap.projected_cycles_to_max,
        xp=snap.xp, max_xp=snap.max_xp, skill_xp=snap.skill_xp,
        task_code=snap.task_code, task_progress=snap.task_progress,
        task_total=snap.task_total, path_next_action=snap.path_next_action,
        plan_len=snap.plan_len, suppressed_goals=snap.suppressed_goals,
        alt_page=alt_page,
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

    BINDINGS = [
        ("escape", "dismiss", "Back"),
        ("p", "dismiss", "Back"),
        ("[", "alt_prev", "Prev alts"),
        ("]", "alt_next", "Next alts"),
    ]

    def __init__(self, snapshot: CycleSnapshot, game_data: GameData) -> None:
        super().__init__(id="plan-modal")
        self._snapshot = snapshot
        self._game_data = game_data
        self._alt_page = 0

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="plan-scroll"):
            yield Static(build_plan_detail(self._snapshot, self._game_data, self._alt_page),
                         id="plan-detail")

    def _rerender(self) -> None:
        if self.is_mounted:
            self.query_one("#plan-detail", Static).update(
                build_plan_detail(self._snapshot, self._game_data, self._alt_page))

    def update_snapshot(self, snap: CycleSnapshot) -> None:
        self._snapshot = snap
        self._rerender()

    def _alt_pages(self) -> int:
        stubs = [r for r in self._snapshot.strategy_ranking
                 if r.root_repr != self._snapshot.chosen_root]
        return max(1, (len(stubs) + ALT_PAGE_SIZE - 1) // ALT_PAGE_SIZE)

    def action_alt_prev(self) -> None:
        self._alt_page = max(0, self._alt_page - 1)
        self._rerender()

    def action_alt_next(self) -> None:
        self._alt_page = min(self._alt_pages() - 1, self._alt_page + 1)
        self._rerender()
