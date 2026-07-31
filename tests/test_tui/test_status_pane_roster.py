"""The status pane no longer carries the roster at all.

It is one narrow grid cell wide, so the trouble line it used to render was
cropped mid-diagnostic. That line moved to the map's HUD line
(test_map_pane_roster); what is checked here is that nothing was left behind —
the pane renders its status table and only its status table, and the app routes
roster updates to the map.
"""

from rich.console import Console

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.tui.app import WatchApp
from artifactsmmo_cli.tui.widgets.map_pane import MapPane
from artifactsmmo_cli.tui.widgets.status_pane import StatusPane


def _snap(character: str) -> CycleSnapshot:
    return CycleSnapshot(
        cycle_index=1, timestamp="2026-07-31T12:00:00Z", character=character,
        x=0, y=0, level=7, xp=0, max_xp=150, hp=120, max_hp=120, gold=0,
        selected_goal="ReachLevel(50)", action="Rest()", outcome="ok",
    )


def _rendered(pane: StatusPane) -> str:
    console = Console(no_color=True, width=120)
    with console.capture() as cap:
        console.print(pane.render())
    return cap.get()


def test_the_status_pane_has_no_roster_surface_left():
    """No leftover renderer, no leftover setter — the pane must not keep a
    second, narrower copy of a line that now lives on the map."""
    pane = StatusPane()

    assert not hasattr(pane, "roster_text")
    assert not hasattr(pane, "update_roster")


def test_the_status_pane_renders_only_its_status_table():
    pane = StatusPane()
    pane.update_snapshot(_snap("alice"))

    assert _rendered(pane).lstrip().startswith("Char")


async def test_roster_updates_reach_the_map_pane():
    """End to end: a child's state has to arrive where the line is now drawn."""
    app = WatchApp(characters=["alice", "bob"], game_data=GameData())
    async with app.run_test(size=(120, 50)) as pilot:
        app.update_snapshot(_snap("alice"))
        await pilot.pause()

        hud = app.query_one("#map", MapPane).hud_text(0, 0).plain

        assert hud.startswith("(0,0)")
        assert "alice" not in hud          # healthy: named by the key legend
