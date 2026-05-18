"""WatchApp: Textual app with four panes for live character observation."""

from textual.app import App, ComposeResult
from textual.containers import Grid
from textual.widgets import Footer, Header

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.ai.game_data import GameData
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

    BINDINGS = [("q", "quit", "Quit")]

    def __init__(self, character: str, game_data: GameData, **kwargs) -> None:
        super().__init__(**kwargs)
        self._character = character
        self._game_data = game_data
        self.title = f"artifactsmmo watch: {character}"

    def compose(self) -> ComposeResult:
        yield Header()
        yield StatusPane(id="status")
        yield MapPane(self._game_data, id="map")
        yield InventoryPane(id="inv")
        yield LogPane(id="log")
        yield Footer()

    def update_snapshot(self, snap: CycleSnapshot) -> None:
        """Called from the bot's worker thread via ThreadSafeBridge.
        Textual queues this onto the main thread."""
        self.query_one("#status", StatusPane).update_snapshot(snap)
        self.query_one("#map", MapPane).update_snapshot(snap)
        self.query_one("#inv", InventoryPane).update_snapshot(snap)
        self.query_one("#log", LogPane).update_snapshot(snap)
