"""WatchApp with a multi-character roster and 1-5 focus keys."""

import asyncio
from types import SimpleNamespace

import pytest
from textual.worker import WorkerState

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


def test_child_state_last_reason_and_stderr_reach_the_roster_entry():
    """Finding 3: the child's last stderr line and last_reason were captured
    and packed into ChildState but had no consumer -- RosterEntry must
    actually carry them through so a dead character's cause of death is
    reachable, not just gathered and discarded."""
    app = _app()
    app.update_child_state(
        ChildState(character="bob", alive=False, restarts=1,
                   last_reason="crash", stderr_tail=("bot log line", "Traceback: boom"))
    )
    entry = next(e for e in app.roster_entries() if e.character == "bob")
    assert entry.last_reason == "crash"
    assert entry.last_stderr_line == "Traceback: boom"  # the LAST line, not the first


def test_a_character_with_no_child_state_has_no_reason_or_stderr():
    app = _app()
    entry = next(e for e in app.roster_entries() if e.character == "alice")
    assert entry.last_reason is None
    assert entry.last_stderr_line is None


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


# --- attach_pool / on_mount / _poll_child_states: `play --all` wiring ------


class _FakePool:
    """Duck-types SupervisorPool without spawning real subprocesses: on_mount
    hands `run()` to `run_worker`, so it must be an awaitable coroutine
    function, and `_poll_child_states` reads `characters()`/`state()`."""

    def __init__(self, characters: tuple[str, ...], states: dict[str, ChildState]) -> None:
        self._characters = characters
        self._states = states
        self.run_called = False

    def characters(self) -> tuple[str, ...]:
        return self._characters

    def state(self, character: str) -> ChildState:
        return self._states[character]

    async def run(self) -> None:
        self.run_called = True


def test_attach_pool_stores_it_without_starting_it():
    """attach_pool is called BEFORE run(); on_mount is what actually starts
    the worker, so merely attaching must not run anything."""
    app = _app()
    pool = _FakePool((), {})
    app.attach_pool(pool)
    assert app._pool is pool
    assert pool.run_called is False


def test_on_mount_without_an_attached_pool_is_a_noop():
    """The single-character `play --tui` path never calls attach_pool; on_mount
    must not explode trying to run a pool that doesn't exist."""
    app = _app()
    app.on_mount()
    assert app._pool is None


def test_poll_child_states_without_an_attached_pool_is_a_noop():
    app = _app()
    app._poll_child_states()  # no pool, no characters -> nothing to update
    assert app._child_states == {}


@pytest.mark.asyncio
async def test_on_mount_starts_the_pool_worker_and_polling_updates_the_roster():
    """End-to-end through the real Textual mount lifecycle (run_test() calls
    on_mount for us): the attached pool's run() coroutine actually executes
    as a worker, and _poll_child_states pulls each character's live state
    into the roster (proving the state -> roster wiring, not just that the
    method runs without crashing)."""
    states = {
        "alice": ChildState(character="alice", alive=False, restarts=3,
                            last_reason="crash", stderr_tail=("boom",)),
    }
    pool = _FakePool(("alice",), states)
    app = _app(names=("alice",))
    app.attach_pool(pool)
    async with app.run_test():
        await asyncio.sleep(0.05)  # let the scheduled worker task actually run
        assert pool.run_called is True

        app._poll_child_states()

        entry = next(e for e in app.roster_entries() if e.character == "alice")
        assert entry.alive is False
        assert entry.restarts == 3


# --- shutdown hazard: update_snapshot / _repaint_focused before mount or
# after teardown must be a no-op, like their siblings already are -----------


def test_update_snapshot_before_mount_does_not_crash():
    """Reproduces the hazard directly: before the fix, calling
    update_snapshot on an unmounted app (is_running is False) reached
    _repaint_focused's unguarded query_one and raised ScreenStackError --
    the exact failure mode a late child event hits during app teardown."""
    app = _app(names=("alice",))
    app.update_snapshot(_snap("alice"))  # must not raise


def test_repaint_focused_before_mount_does_not_crash():
    app = _app(names=("alice",))
    app._repaint_focused(_snap("alice"))  # must not raise


# --- Finding 6: pool completion must not leave the TUI idling silently -----


def test_pool_success_ends_the_app():
    app = _app()
    calls = []
    app.exit = lambda *a, **k: calls.append((a, k))
    event = SimpleNamespace(
        worker=SimpleNamespace(name="supervisors", error=None), state=WorkerState.SUCCESS)
    app.on_worker_state_changed(event)
    assert calls, "app.exit must be called once every child has finished"


def test_pool_error_ends_the_app_with_a_nonzero_return_code():
    app = _app()
    calls = []
    app.exit = lambda *a, **k: calls.append((a, k))
    event = SimpleNamespace(
        worker=SimpleNamespace(name="supervisors", error=RuntimeError("boom")),
        state=WorkerState.ERROR)
    app.on_worker_state_changed(event)
    assert calls
    _, kwargs = calls[0]
    assert kwargs.get("return_code") == 1
    assert "boom" in str(kwargs.get("message"))


def test_an_unrelated_worker_finishing_is_ignored():
    """Only the "supervisors" worker's completion should end the app -- e.g.
    the fight-history backfill worker (fight_screen.py) finishing must not
    be mistaken for the whole pool completing."""
    app = _app()
    calls = []
    app.exit = lambda *a, **k: calls.append((a, k))
    event = SimpleNamespace(
        worker=SimpleNamespace(name="something-else", error=None), state=WorkerState.SUCCESS)
    app.on_worker_state_changed(event)
    assert calls == []


def test_the_supervisors_worker_being_cancelled_is_not_treated_as_completion():
    """CANCELLED is the operator's own 'q' tearing the worker down (already
    handled by the quit action); on_worker_state_changed must not also call
    exit() on top of that."""
    app = _app()
    calls = []
    app.exit = lambda *a, **k: calls.append((a, k))
    event = SimpleNamespace(
        worker=SimpleNamespace(name="supervisors", error=None), state=WorkerState.CANCELLED)
    app.on_worker_state_changed(event)
    assert calls == []


@pytest.mark.asyncio
async def test_the_pool_finishing_for_real_ends_the_running_app():
    """End-to-end through the real Textual worker lifecycle, not a synthetic
    event: a pool whose run() returns must actually drive the app to exit."""
    class _FinishingPool:
        def characters(self) -> tuple[str, ...]:
            return ()

        def state(self, character: str) -> ChildState:
            raise AssertionError("no characters to poll")

        async def run(self) -> None:
            return

    app = _app(names=("alice",))
    app.attach_pool(_FinishingPool())
    async with app.run_test():
        await asyncio.sleep(0.2)  # let the worker run to completion and fire exit()
        assert app.is_running is False
