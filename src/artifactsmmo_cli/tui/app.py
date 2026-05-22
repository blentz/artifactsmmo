"""WatchApp: Textual app with four panes for live character observation."""

from collections import deque

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.tui.screens.character_screen import CharacterScreen
from artifactsmmo_cli.tui.screens.log_screen import LogScreen
from artifactsmmo_cli.tui.widgets.inventory_pane import InventoryPane
from artifactsmmo_cli.tui.widgets.log_pane import LogPane
from artifactsmmo_cli.tui.widgets.map_pane import MapPane
from artifactsmmo_cli.tui.widgets.status_pane import StatusPane


class WatchApp(App):
    """Live watch-mode TUI. Subscribes to GamePlayer's cycle_observer."""

    CSS = """
    Screen {
        layout: grid;
        grid-size: 2 2;
        grid-columns: 1fr 2fr;
        grid-rows: 1fr 1fr;
    }
    /* The bare `Screen` grid above also matches the pushed modals; reset them
       to a full-screen vertical layout. This rule must live in the app
       stylesheet (not the modals' DEFAULT_CSS) because app CSS outranks a
       screen's DEFAULT_CSS regardless of selector specificity. */
    #character-modal, #log-modal {
        layout: vertical;
    }
    #status {
        column-span: 1;
        row-span: 1;
        border: solid white;
        padding: 0 1;
    }
    #map {
        column-span: 1;
        row-span: 1;
        border: solid white;
        padding: 0 1;
    }
    #inv {
        column-span: 1;
        row-span: 1;
        border: solid white;
        padding: 0 1;
    }
    #log {
        column-span: 1;
        row-span: 1;
        border: solid white;
        padding: 0 1;
    }
    """

    LOG_BUFFER = 500

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("c", "toggle_character", "Character"),
        ("l", "toggle_log", "Log"),
    ]

    def __init__(self, character: str, game_data: GameData, **kwargs) -> None:
        super().__init__(**kwargs)
        self._character = character
        self._game_data = game_data
        self.title = f"artifactsmmo watch: {character}"
        self._last_snapshot: CycleSnapshot | None = None
        self._recent_snapshots: deque[CycleSnapshot] = deque(maxlen=self.LOG_BUFFER)

    def compose(self) -> ComposeResult:
        yield Header()
        yield StatusPane(id="status")
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
        if isinstance(top, (CharacterScreen, LogScreen)):
            top.update_snapshot(snap)

    def action_toggle_character(self) -> None:
        if isinstance(self.screen, CharacterScreen):
            self.pop_screen()
        elif self._last_snapshot is not None:
            self.push_screen(CharacterScreen(self._last_snapshot))

    def action_toggle_log(self) -> None:
        if isinstance(self.screen, LogScreen):
            self.pop_screen()
        else:
            self.push_screen(LogScreen(self._recent_snapshots))
