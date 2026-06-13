"""WatchApp tests — static properties and live-loop tests via run_test()."""

import pytest

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.tui.app import WatchApp
from artifactsmmo_cli.tui.screens.character_screen import CharacterScreen
from artifactsmmo_cli.tui.screens.log_screen import LogScreen
from artifactsmmo_cli.tui.screens.plan_screen import PlanScreen
from artifactsmmo_cli.tui.widgets.inventory_pane import InventoryPane
from artifactsmmo_cli.tui.widgets.log_pane import LogPane
from artifactsmmo_cli.tui.widgets.map_pane import TILE_H, TILE_W, MapPane
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

    def test_p_binding_present(self):
        bindings = WatchApp.BINDINGS
        keys = [b[0] if isinstance(b, tuple) else b.key for b in bindings]
        assert "p" in keys

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

    @pytest.mark.asyncio
    async def test_map_pane_fills_its_cell_height(self):
        """The map must fill its grid cell, not collapse to the 1-line legend."""
        app = _make_app()
        async with app.run_test(size=(160, 50)) as pilot:
            app.update_snapshot(_snap())
            await pilot.pause()
            m = app.query_one("#map", MapPane)
            assert m.size.height > 1            # more than just the legend line
            rows = str(m.render()).split("\n")
            tiles_h = (m.size.height - 1) // TILE_H
            tiles_w = m.size.width // TILE_W
            assert len(rows) == 1 + tiles_h * TILE_H   # HUD + sprite tile rows
            assert len(rows[1]) == tiles_w * TILE_W     # rows span the tile grid

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


class TestWatchAppBuffers:
    def test_update_stores_last_and_recent(self):
        app = _make_app()
        # exercise the pure storage method without a running app loop
        app._store_snapshot(_snap(cycle_index=1))
        app._store_snapshot(_snap(cycle_index=2))
        assert app._last_snapshot.cycle_index == 2
        assert len(app._recent_snapshots) == 2

    def test_recent_snapshots_capped(self):
        app = _make_app()
        for i in range(app.LOG_BUFFER + 50):
            app._store_snapshot(_snap(cycle_index=i))
        assert len(app._recent_snapshots) == app.LOG_BUFFER


class TestWatchAppModals:
    @pytest.mark.asyncio
    async def test_c_toggles_character_screen(self):
        app = _make_app()
        async with app.run_test() as pilot:
            app.update_snapshot(_snap())
            await pilot.press("c")
            assert isinstance(app.screen, CharacterScreen)
            await pilot.press("c")
            assert not isinstance(app.screen, CharacterScreen)

    @pytest.mark.asyncio
    async def test_l_toggles_log_screen(self):
        app = _make_app()
        async with app.run_test() as pilot:
            app.update_snapshot(_snap())
            await pilot.press("l")
            assert isinstance(app.screen, LogScreen)
            await pilot.press("escape")
            assert not isinstance(app.screen, LogScreen)

    @pytest.mark.asyncio
    async def test_log_screen_fills_terminal(self):
        """The log widget fills the whole modal screen, not a small content box."""
        app = _make_app()
        async with app.run_test(size=(120, 50)) as pilot:
            app.update_snapshot(_snap())
            await pilot.press("l")
            log = app.screen.query_one("#debug-log")
            assert log.size.width == 120
            assert log.size.height == 50

    @pytest.mark.asyncio
    async def test_character_screen_fills_terminal(self):
        """The character detail scroll container fills the whole modal screen."""
        app = _make_app()
        async with app.run_test(size=(120, 50)) as pilot:
            app.update_snapshot(_snap())
            await pilot.press("c")
            scroll = app.screen.query_one("#char-scroll")
            assert scroll.size.width == 120
            assert scroll.size.height == 50

    @pytest.mark.asyncio
    async def test_character_screen_update_snapshot_while_open(self):
        """app.update_snapshot while CharacterScreen is on top dispatches to it (line 92)."""
        app = _make_app()
        async with app.run_test() as pilot:
            app.update_snapshot(_snap(level=1))
            await pilot.press("c")
            assert isinstance(app.screen, CharacterScreen)
            app.update_snapshot(_snap(level=9))
            assert app.screen._snapshot.level == 9

    @pytest.mark.asyncio
    async def test_log_screen_update_snapshot_while_open(self):
        """app.update_snapshot while LogScreen is on top writes to it (line 92)."""
        app = _make_app()
        async with app.run_test() as pilot:
            app.update_snapshot(_snap(cycle_index=1))
            await pilot.press("l")
            assert isinstance(app.screen, LogScreen)
            log_widget = app.screen.query_one("#debug-log")
            lines_before = len(log_widget.lines)
            app.update_snapshot(_snap(cycle_index=99))
            assert len(log_widget.lines) > lines_before

    @pytest.mark.asyncio
    async def test_action_toggle_character_pops_when_screen_is_character(self):
        """action_toggle_character() pops CharacterScreen directly (app line 96)."""
        app = _make_app()
        async with app.run_test():
            app.update_snapshot(_snap())
            await app.push_screen(CharacterScreen(app._last_snapshot))
            assert isinstance(app.screen, CharacterScreen)
            app.action_toggle_character()
            assert not isinstance(app.screen, CharacterScreen)

    @pytest.mark.asyncio
    async def test_action_toggle_log_pops_when_screen_is_log(self):
        """action_toggle_log() pops LogScreen directly (app line 102)."""
        app = _make_app()
        async with app.run_test():
            app.update_snapshot(_snap())
            await app.push_screen(LogScreen(app._recent_snapshots))
            assert isinstance(app.screen, LogScreen)
            app.action_toggle_log()
            assert not isinstance(app.screen, LogScreen)

    @pytest.mark.asyncio
    async def test_c_no_op_without_snapshot(self):
        """Pressing 'c' with no snapshot does not push a CharacterScreen (elif guard)."""
        app = _make_app()
        async with app.run_test() as pilot:
            # Do NOT call update_snapshot — _last_snapshot is None
            await pilot.press("c")
            assert not isinstance(app.screen, CharacterScreen)

    @pytest.mark.asyncio
    async def test_p_toggles_plan_screen(self):
        app = _make_app()
        async with app.run_test() as pilot:
            app.update_snapshot(_snap())
            await pilot.press("p")
            assert isinstance(app.screen, PlanScreen)
            await pilot.press("p")
            assert not isinstance(app.screen, PlanScreen)

    @pytest.mark.asyncio
    async def test_plan_screen_update_snapshot_while_open(self):
        """app.update_snapshot while PlanScreen is on top dispatches to it."""
        app = _make_app()
        async with app.run_test() as pilot:
            app.update_snapshot(_snap(level=1))
            await pilot.press("p")
            assert isinstance(app.screen, PlanScreen)
            app.update_snapshot(_snap(level=9))
            assert app.screen._snapshot.level == 9

    @pytest.mark.asyncio
    async def test_action_toggle_plan_pops_when_screen_is_plan(self):
        """action_toggle_plan() pops PlanScreen directly."""
        app = _make_app()
        async with app.run_test():
            app.update_snapshot(_snap())
            await app.push_screen(PlanScreen(app._last_snapshot, app._game_data))
            assert isinstance(app.screen, PlanScreen)
            app.action_toggle_plan()
            assert not isinstance(app.screen, PlanScreen)

    @pytest.mark.asyncio
    async def test_p_no_op_without_snapshot(self):
        """Pressing 'p' with no snapshot does not push a PlanScreen (elif guard)."""
        app = _make_app()
        async with app.run_test() as pilot:
            # Do NOT call update_snapshot — _last_snapshot is None
            await pilot.press("p")
            assert not isinstance(app.screen, PlanScreen)


class TestThreeByThreeLayout:
    async def test_map_spans_wide_right_block_and_log_is_full_width(self):
        app = WatchApp("hero", GameData())
        async with app.run_test(size=(120, 45)) as pilot:
            map_pane = app.query_one("#map", MapPane)
            inv_pane = app.query_one("#inv")
            log_pane = app.query_one("#log")
            status_pane = app.query_one("#status")
            # --- size-based checks (kept) ---
            # Map occupies the wide right block: wider than the left column inv.
            assert map_pane.size.width > inv_pane.size.width
            # Map spans both top rows: taller than the single-row inventory.
            assert map_pane.size.height > inv_pane.size.height
            # Log is the full-width bottom strip, ~5 lines.
            assert log_pane.size.width > map_pane.size.width
            assert log_pane.size.height <= 7
            # --- absolute cell-position checks ---
            # These pin the auto-flow yield order in compose(): Textual 6.1.0
            # has no column:/row: placement props, so panes land in cells purely
            # by DOM order. A reorder of status/map/inv/log would move regions and
            # fail these, whereas the size checks above would still pass.
            #
            # status: top-left (col1, row1).
            assert status_pane.region.x == 0
            # map: wide RIGHT block spanning both top rows.
            assert map_pane.region.x >= status_pane.region.right  # right of left col
            assert map_pane.region.y == status_pane.region.y       # top aligns row1
            assert map_pane.region.bottom > inv_pane.region.y      # spans past row1
            # inv: left column, row 2 (directly under status).
            assert inv_pane.region.x == status_pane.region.x
            assert inv_pane.region.y > status_pane.region.y
            # log: full-width bottom row, under both columns.
            assert log_pane.region.x == status_pane.region.x
            assert log_pane.region.right >= map_pane.region.right
            assert log_pane.region.y > map_pane.region.y
            assert log_pane.region.height <= 7
            await pilot.pause()
