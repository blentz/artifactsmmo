"""A character switch must re-bind the OPEN MODAL, not push a snapshot into it.

`_rebind_panes` fixed the four background panes but still treated whatever modal
was on top as a snapshot sink: it called `top.update_snapshot(snap)`, and only
when the new character already had a snapshot. Every defect that motivated the
pane re-bind survives one level up, in the modals:

1. `LogScreen` is append-only (a `RichLog`), exactly like `LogPane`. Pushing the
   new character's cycle into it left the operator reading a MIXTURE of two
   characters' traces with nothing marking the boundary.
2. `FightScreen` merges snapshots into a per-character record list and carries
   the character name it was built with. After a switch it accumulated the new
   character's fights into the old character's list under the old character's
   name, and `m` (load older) backfilled the NEW character's server history into
   it, because the app's fetch callback reads `focused_character` at call time.
3. `CharacterScreen` / `PlanScreen` were skipped entirely when the new character
   had no snapshot yet, so they went on showing the previous character — the
   original "switching does nothing" symptom, still reachable through a modal.

A modal is bound to one character, so a switch rebuilds it through the SAME
factory the toggle key uses. `EncyclopediaScreen` is game-data, not character
data, and must survive a switch untouched.
"""

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.ai.fight_record import FightRecord
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.tui.app import WatchApp
from artifactsmmo_cli.tui.screens.character_screen import CharacterScreen
from artifactsmmo_cli.tui.screens.encyclopedia_screen import EncyclopediaScreen
from artifactsmmo_cli.tui.screens.fight_screen import FightScreen
from artifactsmmo_cli.tui.screens.log_screen import LogScreen
from artifactsmmo_cli.tui.screens.plan_screen import PlanScreen


def _record(started_at: str, opponent: str) -> FightRecord:
    return FightRecord(
        started_at=started_at, result="win", turns=3, opponent=opponent,
        logs=(f"Fight start: vs {opponent}",),
        hp_before=100, hp_after=90, xp=10, gold=1, drops=(),
    )


def _snap(character: str, **overrides: object) -> CycleSnapshot:
    base = dict(
        cycle_index=1, timestamp="2026-07-31T12:00:00Z", character=character,
        x=0, y=0, level=7, xp=0, max_xp=150, hp=120, max_hp=120, gold=0,
        selected_goal="ReachLevel(50)", action="Rest()", outcome="ok",
    )
    base.update(overrides)
    return CycleSnapshot(**base)  # type: ignore[arg-type]


def _app() -> WatchApp:
    return WatchApp(characters=["alice", "bob"], game_data=GameData())


async def test_the_log_modal_shows_only_the_new_characters_history():
    app = _app()
    async with app.run_test(size=(120, 50)) as pilot:
        app.update_snapshot(_snap("alice", selected_goal="AliceGoal"))
        app.update_snapshot(_snap("bob", selected_goal="BobGoal"))
        await pilot.press("l")
        await pilot.pause()

        await pilot.press("2")
        await pilot.pause()

        assert isinstance(app.screen, LogScreen)
        text = "\n".join(str(line) for line in app.screen.query_one("#debug-log").lines)
        assert "BobGoal" in text
        assert "AliceGoal" not in text


async def test_the_fight_modal_never_mixes_two_characters_fights():
    app = _app()
    async with app.run_test(size=(120, 50)) as pilot:
        app.update_snapshot(_snap(
            "alice", fight=_record("2026-07-31T12:00:00.000000", "chicken")))
        app.update_snapshot(_snap(
            "bob", fight=_record("2026-07-31T12:00:01.000000", "cow")))
        await pilot.press("f")
        await pilot.pause()

        await pilot.press("2")
        await pilot.pause()

        assert isinstance(app.screen, FightScreen)
        assert [r.opponent for r in app.screen.records] == ["cow"]


async def test_the_fight_modal_carries_the_new_characters_name():
    """`_character` labels the modal and scopes its backfill; a stale one meant
    'm' pulled the focused character's server history into a list titled with
    somebody else's name."""
    app = _app()
    async with app.run_test(size=(120, 50)) as pilot:
        app.update_snapshot(_snap("alice"))
        app.update_snapshot(_snap("bob"))
        await pilot.press("f")
        await pilot.pause()

        await pilot.press("2")
        await pilot.pause()

        assert app.screen._character == "bob"


async def test_the_character_modal_closes_when_the_new_character_has_no_cycle():
    """The reported freeze, one level up: with no snapshot to show, the modal
    must not go on displaying the previous character."""
    app = _app()
    async with app.run_test(size=(120, 50)) as pilot:
        app.update_snapshot(_snap("alice", level=7))
        await pilot.press("c")
        await pilot.pause()
        assert isinstance(app.screen, CharacterScreen)

        await pilot.press("2")
        await pilot.pause()

        assert not isinstance(app.screen, CharacterScreen)


async def test_the_fight_modal_empties_for_a_character_with_no_fights():
    """A character who has fought nothing must show an empty list, not the
    previous character's fights, and must not leave a highlighted row pointing
    into a list that no longer has one."""
    app = _app()
    async with app.run_test(size=(120, 50)) as pilot:
        app.update_snapshot(_snap(
            "alice", fight=_record("2026-07-31T12:00:00.000000", "chicken")))
        app.update_snapshot(_snap("bob"))
        await pilot.press("f")
        await pilot.pause()

        await pilot.press("2")
        await pilot.pause()

        assert app.screen.records == []
        assert app.screen.query_one("#fight-list").index is None


async def test_the_plan_modal_closes_when_the_new_character_has_no_cycle():
    app = _app()
    async with app.run_test(size=(120, 50)) as pilot:
        app.update_snapshot(_snap("alice"))
        await pilot.press("p")
        await pilot.pause()
        assert isinstance(app.screen, PlanScreen)

        await pilot.press("2")
        await pilot.pause()

        assert not isinstance(app.screen, PlanScreen)


async def test_the_encyclopedia_modal_survives_a_character_switch():
    """Game data is not character data: rebuilding it would throw away the
    operator's place in the index for no reason."""
    app = _app()
    async with app.run_test(size=(120, 50)) as pilot:
        app.update_snapshot(_snap("alice"))
        app.update_snapshot(_snap("bob"))
        await pilot.press("e")
        await pilot.pause()
        opened = app.screen
        assert isinstance(opened, EncyclopediaScreen)

        await pilot.press("2")
        await pilot.pause()

        assert app.screen is opened


async def test_set_planning_before_mount_does_not_raise():
    """`update_snapshot` already guards this: a child's event can arrive before
    mount or after teardown, and querying the DOM then raises ScreenStackError.
    The planning signal reaches the app by the same bridge and needs the same
    guard."""
    app = _app()

    app.set_planning(True)          # never mounted — must be a no-op, not a crash
