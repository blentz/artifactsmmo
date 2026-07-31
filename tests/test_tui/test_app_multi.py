"""WatchApp with a multi-character roster and 1-5 focus keys."""

import pytest

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.multi.child_state import ChildState
from artifactsmmo_cli.tui.app import WatchApp
from artifactsmmo_cli.tui.widgets.map_pane import MapPane
from artifactsmmo_cli.tui.widgets.status_pane import StatusPane


def _snap(character: str, **overrides) -> CycleSnapshot:
    base = dict(
        cycle_index=1, timestamp="2026-07-30T12:00:00Z", character=character,
        x=0, y=0, level=1, xp=0, max_xp=150, hp=120, max_hp=120, gold=0,
        selected_goal="ReachLevel(50)", action="Rest()", outcome="ok",
    )
    base.update(overrides)
    return CycleSnapshot(**base)


def _app(names=("alice", "bob", "carol")) -> WatchApp:
    return WatchApp(characters=list(names), game_data=GameData())


def test_the_first_roster_character_is_focused_initially():
    assert _app().focused_character == "alice"


def test_keys_one_to_five_are_bound():
    keys = {binding[0] for binding in WatchApp.BINDINGS}
    assert {"1", "2", "3", "4", "5"} <= keys


def test_focusing_an_occupied_slot_switches_character():
    app = _app()
    app.action_focus_character(2)
    assert app.focused_character == "bob"


def test_focusing_an_empty_slot_is_a_no_op():
    app = _app(names=("alice",))
    app.action_focus_character(4)
    assert app.focused_character == "alice"


@pytest.mark.asyncio
async def test_only_the_focused_characters_snapshot_drives_the_status_pane():
    app = _app()
    async with app.run_test():
        app.update_snapshot(_snap("bob", level=42))
        assert app.query_one("#status", StatusPane).snapshot is None
        app.update_snapshot(_snap("alice", level=7))
        assert app.query_one("#status", StatusPane).snapshot.level == 7


@pytest.mark.asyncio
async def test_a_foreign_snapshot_still_places_that_character_on_the_map():
    app = _app()
    async with app.run_test():
        app.update_snapshot(_snap("bob", x=3, y=4))
        assert (3, 4) in app.query_one("#map", MapPane)._others


@pytest.mark.asyncio
async def test_switching_focus_repaints_the_panes_from_the_store():
    app = _app()
    async with app.run_test():
        app.update_snapshot(_snap("bob", level=42))
        app.action_focus_character(2)
        assert app.query_one("#status", StatusPane).snapshot.level == 42


@pytest.mark.asyncio
async def test_the_focused_character_is_not_drawn_twice():
    """The focused character renders as the centred animated sprite, so they
    must be absent from the static others map."""
    app = _app()
    async with app.run_test():
        app.update_snapshot(_snap("alice", x=1, y=1))
        assert (1, 1) not in app.query_one("#map", MapPane)._others


def test_child_state_reaches_the_roster():
    app = _app()
    app.update_child_state(
        ChildState(character="bob", alive=False, restarts=2,
                   last_reason="stuck_exit", stderr_tail=("boom",))
    )
    entry = next(e for e in app.roster_entries() if e.character == "bob")
    assert entry.alive is False
    assert entry.restarts == 2


def test_roster_entries_report_the_focused_character():
    """A verifiable-failure check on top of the brief's suite: an
    implementation that never sets `focused=True` on any entry (or always sets
    it on slot 1 regardless of app.focused_character) would slip past the tests above."""
    app = _app()
    app.action_focus_character(2)
    entries = {e.character: e for e in app.roster_entries()}
    assert entries["bob"].focused is True
    assert entries["alice"].focused is False
    assert entries["carol"].focused is False


def test_action_focus_on_the_already_focused_slot_is_a_no_op_not_a_crash():
    """Guards the `name == self.focused_character` early return: calling it on the slot
    already focused must not explode by trying to repaint an unmounted app."""
    app = _app()
    app.action_focus_character(1)
    assert app.focused_character == "alice"
