"""WatchApp tests — static properties and live-loop tests via run_test()."""

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.tui.app import WatchApp
from artifactsmmo_cli.tui.widgets.inventory_pane import InventoryPane
from artifactsmmo_cli.tui.widgets.log_pane import LogPane
from artifactsmmo_cli.tui.widgets.map_pane import MapPane
from artifactsmmo_cli.tui.widgets.status_pane import StatusPane


def _make_app(character: str = "hero") -> WatchApp:
    return WatchApp(character=character, game_data=GameData())


def _snap(**overrides) -> CycleSnapshot:
    base = dict(
        cycle_index=1,
        timestamp="2026-05-21T12:00:00Z",
        character="hero",
        x=0,
        y=0,
        level=1,
        xp=0,
        max_xp=100,
        hp=100,
        max_hp=100,
        gold=0,
        selected_goal="test_goal",
        action="wait",
        outcome="ok",
    )
    base.update(overrides)
    return CycleSnapshot(**base)


class TestWatchAppStaticProperties:
    def test_title_includes_character(self):
        app = _make_app("my_char")
        assert "my_char" in app.title

    def test_css_is_string(self):
        assert isinstance(WatchApp.CSS, str)

    def test_css_contains_grid(self):
        assert "grid" in WatchApp.CSS

    def test_bindings_includes_quit(self):
        bindings = WatchApp.BINDINGS
        keys = [b[0] if isinstance(b, tuple) else b.key for b in bindings]
        assert "q" in keys

    def test_stores_character(self):
        app = _make_app("warrior")
        assert app._character == "warrior"

    def test_stores_game_data(self):
        gd = GameData()
        app = WatchApp(character="hero", game_data=gd)
        assert app._game_data is gd


class TestWatchAppCompose:
    async def test_compose_yields_status_pane(self):
        app = _make_app()
        async with app.run_test(size=(120, 50)):
            assert app.query_one("#status", StatusPane) is not None

    async def test_compose_yields_map_pane(self):
        app = _make_app()
        async with app.run_test(size=(120, 50)):
            assert app.query_one("#map", MapPane) is not None

    async def test_compose_yields_inventory_pane(self):
        app = _make_app()
        async with app.run_test(size=(120, 50)):
            assert app.query_one("#inv", InventoryPane) is not None

    async def test_compose_yields_log_pane(self):
        app = _make_app()
        async with app.run_test(size=(120, 50)):
            assert app.query_one("#log", LogPane) is not None


class TestWatchAppUpdateSnapshot:
    async def test_update_snapshot_dispatches_to_status(self):
        app = _make_app()
        async with app.run_test(size=(120, 50)):
            snap = _snap()
            app.update_snapshot(snap)
            assert app.query_one("#status", StatusPane).snapshot == snap

    async def test_update_snapshot_dispatches_to_inventory(self):
        app = _make_app()
        async with app.run_test(size=(120, 50)):
            snap = _snap()
            app.update_snapshot(snap)
            assert app.query_one("#inv", InventoryPane).snapshot == snap

    async def test_update_snapshot_dispatches_to_map(self):
        app = _make_app()
        async with app.run_test(size=(120, 50)):
            snap = _snap()
            app.update_snapshot(snap)
            assert app.query_one("#map", MapPane).snapshot == snap

    async def test_update_snapshot_calls_log_write(self):
        app = _make_app()
        async with app.run_test(size=(120, 50)):
            snap = _snap()
            app.update_snapshot(snap)
            # LogPane.update_snapshot writes a line; verify no exception


class TestWatchAppQuitBinding:
    async def test_quit_key_exits_app(self):
        app = _make_app()
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.press("q")
