"""WatchApp: Textual app with four panes for live character observation."""

from collections.abc import Callable
from functools import partial

from artifactsmmo_api_client.models.log_type import LogType
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Footer, Header
from textual.worker import Worker, WorkerState

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.ai.fight_record import FightRecord
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.api_wrapper import APIWrapper
from artifactsmmo_cli.multi.child_state import ChildState
from artifactsmmo_cli.multi.supervisor_pool import SupervisorPool
from artifactsmmo_cli.tui.character_roster import CharacterRoster
from artifactsmmo_cli.tui.multi_snapshot_store import MultiSnapshotStore
from artifactsmmo_cli.tui.roster_entry import RosterEntry
from artifactsmmo_cli.tui.screens.character_screen import CharacterScreen
from artifactsmmo_cli.tui.screens.encyclopedia_screen import EncyclopediaScreen
from artifactsmmo_cli.tui.screens.fight_screen import FightScreen
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
    #character-modal, #log-modal, #plan-modal, #encyclopedia-modal, #fight-modal {
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

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("c", "toggle_character", "Character"),
        ("l", "toggle_log", "Log"),
        ("p", "toggle_plan", "Plan"),
        ("e", "toggle_encyclopedia", "Encyclopedia"),
        ("f", "toggle_fight", "Fights"),
        # The focus keys are NOT here: they are bound per instance in
        # `_bind_character_keys`, which knows the roster and can name it.
    ]

    def __init__(self, characters: list[str], game_data: GameData,
                 api: APIWrapper | None = None) -> None:
        super().__init__()
        self._roster = CharacterRoster(characters)
        self._game_data = game_data
        # Optional: only the fight modal's history backfill needs the API. When
        # absent (tests, or a host that did not supply one) the modal still shows
        # everything this session watched; only 'm' goes quiet.
        self._api = api
        self.focused_character = self._roster.names[0]
        self.title = f"artifactsmmo watch: {', '.join(self._roster.names)}"
        self._store = MultiSnapshotStore(self._roster.names)
        self._child_states: dict[str, ChildState] = {}
        self._pool: SupervisorPool | None = None
        self._bind_character_keys()
        SpriteCoverageAudit().run(game_data)

    def _bind_character_keys(self) -> None:
        """Give every character in the roster a focus key LABELLED with its name.

        Bound per instance instead of declared in `BINDINGS`, because a class
        table cannot know the roster: it could only say "Char 3", a number the
        operator just pressed and a name they could not see, and it advertised
        all five slots however many characters were actually playing. Naming
        the keys here is also what lets the status pane stop listing the roster.

        A single-character run binds nothing at all — there is nothing to switch
        to — so it keeps exactly the key legend it had before multi-character
        support.
        """
        if len(self._roster.names) < 2:
            return
        for slot, name in enumerate(self._roster.names, start=1):
            self._bindings.bind(str(slot), f"focus_character({slot})", description=name)

    def attach_pool(self, pool: SupervisorPool) -> None:
        """Run `play --all`'s child supervisors on Textual's own asyncio loop.

        Must be called before `run()`: `on_mount` only starts the worker if a
        pool is already attached, so attaching after mount would silently
        never run it.
        """
        self._pool = pool

    def on_mount(self) -> None:
        if self._pool is not None:
            self.run_worker(self._pool.run(), name="supervisors")
            self.set_interval(1.0, self._poll_child_states)

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """React when the supervisor pool's worker finishes, instead of
        idling on a dead roster with no exit or indication anything
        happened. CANCELLED is not handled here: that is the operator's own
        'q' tearing the worker down, already handled by the quit action, and
        re-exiting on top of it would be redundant at best."""
        if event.worker.name != "supervisors":
            return
        if event.state == WorkerState.SUCCESS:
            self.exit(message="All characters have stopped.")
        elif event.state == WorkerState.ERROR:
            self.exit(return_code=1, message=f"Supervisor pool failed: {event.worker.error!r}")

    def _poll_child_states(self) -> None:
        if self._pool is None:
            return
        for character in self._pool.characters():
            self.update_child_state(self._pool.state(character))

    def compose(self) -> ComposeResult:
        yield Header()
        yield StatusPane(id="status")
        with Container(id="map-cell"):        # owns the sub-tile leftover space
            yield MapPane(self._game_data, id="map")
        yield InventoryPane(id="inv")
        yield LogPane(id="log")
        yield Footer()

    def update_snapshot(self, snap: CycleSnapshot) -> None:
        """Called from the bot's worker thread via ThreadSafeBridge.
        Textual queues this onto the main thread."""
        if not self.is_running:
            # A snapshot can arrive before mount or after teardown (a child's
            # event still in flight when the app exits): querying the DOM
            # then raises ScreenStackError rather than the NoMatches that
            # `_repaint_others`/`_repaint_roster` already guard against.
            return
        self._store.record(snap)
        if snap.character == self.focused_character:
            self._repaint_focused(snap)
        self._repaint_others()
        self._repaint_roster()

    def _repaint_focused(self, snap: CycleSnapshot) -> None:
        if not self.is_running:
            return
        self.query_one("#status", StatusPane).update_snapshot(snap)
        self.query_one("#map", MapPane).update_snapshot(snap)
        self.query_one("#inv", InventoryPane).update_snapshot(snap)
        self.query_one("#log", LogPane).update_snapshot(snap)
        top = self.screen
        if isinstance(top, (CharacterScreen, LogScreen, PlanScreen, FightScreen)):
            top.update_snapshot(snap)

    def _repaint_others(self) -> None:
        """Place every character EXCEPT the focused one; the focused character
        is already drawn as the centred, animated sprite."""
        if not self.is_running:
            return
        others = {
            (snap.x, snap.y, snap.layer): self._roster.sprite(name)
            for name, snap in self._store.latest_all().items()
            if name != self.focused_character
        }
        self.query_one("#map", MapPane).set_others(others)

    def action_focus_character(self, slot: int) -> None:
        name = self._roster.at(slot)
        if name is None or name == self.focused_character:
            return
        self.focused_character = name
        self._rebind_panes(name)
        self._repaint_others()
        self._repaint_roster()

    def _rebind_panes(self, name: str) -> None:
        """Point every pane at `name`.

        A focus switch is a RE-BIND, not a snapshot push. The old code called
        `_repaint_focused` only when the target already had a snapshot, so
        switching to a character that had not yet completed a cycle repainted
        NOTHING — every pane kept the previous character's data, and because
        that character was no longer focused its later snapshots were skipped
        too, freezing the panes permanently. That is what "switching characters
        does nothing" looked like in practice.

        The panes also hold per-character state that must not leak across a
        switch: the log is append-only (it would interleave two characters'
        histories), and the status pane carries a cooldown expiry and task-ETA
        samples belonging to whoever was focused before.
        """
        if not self.is_running:
            return
        snap = self._store.last(name)
        self.query_one("#status", StatusPane).rebind(snap)
        self.query_one("#inv", InventoryPane).rebind(snap)
        self.query_one("#map", MapPane).rebind(snap)
        self.query_one("#log", LogPane).replace_history(self._store.recent(name))
        self._rebind_modal()

    def _rebind_modal(self) -> None:
        """Point the open modal at the newly focused character.

        Every defect the pane re-bind fixed also existed one level up, because
        a switch pushed the new character's snapshot into the OLD character's
        modal: `LogScreen` is append-only like `LogPane` and interleaved two
        traces; `FightScreen` accumulated both characters' fights into one list
        still labelled with the old name, and its 'm' backfill then pulled the
        focused character's server history into it; `CharacterScreen` and
        `PlanScreen` were skipped outright when the new character had no cycle
        yet, so they kept showing the previous one.

        Re-bound IN PLACE rather than popped and re-pushed: each modal mounts
        with a fixed widget id, Textual removes a screen asynchronously, and a
        same-type push therefore collides with the outgoing screen's id
        (DuplicateIds). Dismissal is the one case that pops — a character with
        no cycle yet has nothing for the character/plan modals to show, and
        showing the previous character instead is the bug being fixed.

        `EncyclopediaScreen` is game data, not character data: it is untouched
        here, so a switch leaves the operator's place in the index intact.
        """
        top = self.screen
        name = self.focused_character
        snap = self._store.last(name)
        if isinstance(top, (CharacterScreen, PlanScreen)):
            # Both rebuild their whole body from one snapshot, so pushing the
            # new character's snapshot IS a re-bind for them.
            if snap is None:
                self.pop_screen()
            else:
                top.update_snapshot(snap)
        elif isinstance(top, LogScreen):
            top.replace_history(self._store.recent(name))
        elif isinstance(top, FightScreen):
            top.rebind(self._store.fights(name), character=name,
                       fetch_older=partial(self._fetch_older_fights, name))

    def update_child_state(self, state: ChildState) -> None:
        self._child_states[state.character] = state
        self._repaint_roster()

    def roster_entries(self) -> tuple[RosterEntry, ...]:
        entries = []
        for slot, name in enumerate(self._roster.names, start=1):
            snap = self._store.last(name)
            child = self._child_states.get(name)
            entries.append(RosterEntry(
                slot=slot, character=name, color=self._roster.color(name),
                level=snap.level if snap else 0,
                x=snap.x if snap else 0, y=snap.y if snap else 0,
                alive=child.alive if child else True,
                restarts=child.restarts if child else 0,
                focused=name == self.focused_character,
                last_reason=child.last_reason if child else None,
                last_stderr_line=(
                    child.stderr_tail[-1] if child and child.stderr_tail else None
                ),
            ))
        return tuple(entries)

    def _repaint_roster(self) -> None:
        """Draw any character in trouble on the map's HUD line. It used to go to
        the status pane, which is one narrow grid cell wide and cropped a dead
        child's reason mid-sentence; the HUD line spans both wide columns."""
        if not self.is_running:
            return
        self.query_one("#map", MapPane).set_roster(self.roster_entries())

    # The five modal screens. Each mounts with a FIXED widget id
    # (character-modal / log-modal / plan-modal / encyclopedia-modal / fight-modal),
    # so two of the same kind in the screen stack collide with DuplicateIds. Toggles
    # enforce ONE modal at a time.
    _MODAL_SCREENS = (
        CharacterScreen, LogScreen, PlanScreen, EncyclopediaScreen, FightScreen)

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

    # One factory per character-scoped modal, so its toggle key and any later
    # re-bind agree on how that modal is built for the focused character.
    def _character_modal(self) -> CharacterScreen | None:
        last = self._store.last(self.focused_character)
        return CharacterScreen(last) if last is not None else None

    def _log_modal(self) -> LogScreen:
        return LogScreen(self._store.recent(self.focused_character))

    def _plan_modal(self) -> PlanScreen | None:
        last = self._store.last(self.focused_character)
        return PlanScreen(last, self._game_data) if last is not None else None

    def _fight_modal(self) -> FightScreen:
        character = self.focused_character
        # Bind the character INTO the backfill rather than reading
        # `focused_character` when 'm' fires: a switch during an in-flight fetch
        # would otherwise land one character's server history in another's list.
        return FightScreen(
            self._store.fights(character), character=character,
            fetch_older=partial(self._fetch_older_fights, character))

    def action_toggle_character(self) -> None:
        self._open_modal(CharacterScreen, self._character_modal)

    def action_toggle_log(self) -> None:
        self._open_modal(LogScreen, self._log_modal)

    def set_planning(self, active: bool) -> None:
        """Bot-thread signal (via ThreadSafeBridge): planner is deciding.

        Guarded like `update_snapshot`: a child's planning event can arrive
        before mount or after teardown, and querying the DOM then raises
        ScreenStackError instead of the NoMatches the repaints tolerate."""
        if not self.is_running:
            return
        self.query_one("#map", MapPane).set_planning(active)

    def action_toggle_plan(self) -> None:
        self._open_modal(PlanScreen, self._plan_modal)

    def action_toggle_encyclopedia(self) -> None:
        self._open_modal(
            EncyclopediaScreen,
            lambda: EncyclopediaScreen(self._game_data),
        )

    def _fetch_older_fights(self, character: str, page: int) -> list[FightRecord]:
        """One page of `character`'s server history, fights only. Runs on a
        worker thread; the character is bound by the modal that owns the fetch,
        never re-read from focus mid-flight."""
        if self._api is None:
            return []
        result = self._api.get_character_logs(character, page=page, size=100)
        return [
            FightRecord.from_log_entry(entry.content, character=character)
            for entry in result.data
            if entry.type_ == LogType.FIGHT
        ]

    def action_toggle_fight(self) -> None:
        self._open_modal(FightScreen, self._fight_modal)
