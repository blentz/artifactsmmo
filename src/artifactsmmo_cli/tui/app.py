"""WatchApp: Textual app with four panes for live character observation."""

from collections import deque
from collections.abc import Callable

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Footer, Header

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.tui.screens.character_screen import CharacterScreen
from artifactsmmo_cli.tui.screens.log_screen import LogScreen
from artifactsmmo_cli.tui.screens.plan_screen import PlanScreen
from artifactsmmo_cli.tui.sprite_coverage_audit import SpriteCoverageAudit
from artifactsmmo_cli.tui.widgets.inventory_pane import InventoryPane
from artifactsmmo_cli.tui.widgets.log_pane import LogPane
from artifactsmmo_cli.tui.widgets.map_pane import MapPane
from artifactsmmo_cli.tui.widgets.status_pane import StatusPane


class WatchApp(App[None]):
    """Live watch-mode TUI. Subscribes to GamePlayer's cycle_observer."""

    CSS = """
    Screen {
        layout: grid;
        grid-size: 3 3;
        grid-columns: 1fr 2fr 2fr;
        grid-rows: 1fr 1fr 7;
    }
    /* The bare `Screen` grid above also matches pushed modals; reset them to a
       full-screen vertical layout. App CSS outranks a screen's DEFAULT_CSS. */
    #character-modal, #log-modal, #plan-modal {
        layout: vertical;
    }
    /* Textual has no explicit cell-placement (`column`/`row`) props: cells are
       auto-flowed in DOM order, so compose() yields status, map, inv, log to
       land them in the intended cells. status -> (col1,row1); map spans
       cols2-3 x rows1-2; inv -> (col1,row2); log spans all of row3. */
    #status {
        border: solid white;
        padding: 0 1;
    }
    /* The map cell fills the grid slot and OWNS the sub-tile leftover space, so a
       closed modal's text there is repainted away like any other pane (unowned
       screen space is NOT re-emitted on screen resume, which stranded remnants). */
    #map-cell {
        column-span: 2;
        row-span: 2;
        /* Opaque background so the leftover strip (right/below the tile-exact map)
           is repainted on modal close instead of stranding the old pane's text. */
        background: $background;
    }
    #map {
        border: solid white;
        /* Auto-size to an exact whole-tile grid (MapPane.get_content_width/height):
           no padding, no sub-tile filler, border hugs the tiles. The leftover
           (< 1 tile) is owned by #map-cell, not stranded as unowned screen space. */
        width: auto;
        height: auto;
    }
    #inv {
        border: solid white;
        padding: 0 1;
    }
    #log {
        column-span: 3;
        border: solid white;
        padding: 0 1;
    }
    """

    LOG_BUFFER = 500

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("c", "toggle_character", "Character"),
        ("l", "toggle_log", "Log"),
        ("p", "toggle_plan", "Plan"),
    ]

    def __init__(self, character: str, game_data: GameData) -> None:
        super().__init__()
        self._character = character
        self._game_data = game_data
        self.title = f"artifactsmmo watch: {character}"
        self._last_snapshot: CycleSnapshot | None = None
        self._recent_snapshots: deque[CycleSnapshot] = deque(maxlen=self.LOG_BUFFER)
        SpriteCoverageAudit().run(game_data)

    def compose(self) -> ComposeResult:
        yield Header()
        yield StatusPane(id="status")
        with Container(id="map-cell"):        # owns the sub-tile leftover space
            yield MapPane(self._game_data, id="map")
        yield InventoryPane(id="inv")
        yield LogPane(id="log")
        yield Footer()

    def _store_snapshot(self, snap: CycleSnapshot) -> None:
        self._last_snapshot = snap
        self._recent_snapshots.append(snap)

    def update_snapshot(self, snap: CycleSnapshot) -> None:
        """Called from the bot's worker thread via ThreadSafeBridge.
        Textual queues this onto the main thread."""
        self._store_snapshot(snap)
        self.query_one("#status", StatusPane).update_snapshot(snap)
        self.query_one("#map", MapPane).update_snapshot(snap)
        self.query_one("#inv", InventoryPane).update_snapshot(snap)
        self.query_one("#log", LogPane).update_snapshot(snap)
        top = self.screen
        if isinstance(top, (CharacterScreen, LogScreen, PlanScreen)):
            top.update_snapshot(snap)

    # The three modal screens. Each mounts with a FIXED widget id
    # (character-modal / log-modal / plan-modal), so two of the same kind in the
    # screen stack collide with DuplicateIds. Toggles enforce ONE modal at a time.
    _MODAL_SCREENS = (CharacterScreen, LogScreen, PlanScreen)

    def _open_modal(self, screen_type: type[Screen[None]],
                    factory: Callable[[], Screen[None] | None]) -> None:
        """Single-modal toggle. Close whatever modal is currently on top, then open
        `screen_type` only when a DIFFERENT modal (or none) was showing. This is the
        fix for the DuplicateIds crash from chaining modals (e.g. log -> character ->
        log): the old per-toggle code only checked the TOP screen, so pressing a
        second modal pushed it ABOVE the first and a third press re-pushed a screen
        whose fixed id was still mounted underneath."""
        top = self.screen
        was_same = isinstance(top, screen_type)
        if isinstance(top, self._MODAL_SCREENS):
            self.pop_screen()
        if was_same:
            return                       # toggled THIS modal off — done
        new = factory()
        if new is not None:
            self.push_screen(new)

    def action_toggle_character(self) -> None:
        self._open_modal(
            CharacterScreen,
            lambda: CharacterScreen(self._last_snapshot)
            if self._last_snapshot is not None else None)

    def action_toggle_log(self) -> None:
        self._open_modal(LogScreen, lambda: LogScreen(self._recent_snapshots))

    def set_planning(self, active: bool) -> None:
        """Bot-thread signal (via ThreadSafeBridge): planner is deciding."""
        self.query_one("#map", MapPane).set_planning(active)

    def action_toggle_plan(self) -> None:
        self._open_modal(
            PlanScreen,
            lambda: PlanScreen(self._last_snapshot, self._game_data)
            if self._last_snapshot is not None else None)
