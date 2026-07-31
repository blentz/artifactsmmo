"""Focus switching must RE-BIND every pane to the new character.

The original implementation treated a switch as "push one snapshot": it called
`_repaint_focused` only `if snap is not None`, and pushed a single snapshot into
an append-only log. Three defects followed, all reproduced here:

1. Switching to a character with no snapshot yet repainted NOTHING, so every
   pane kept showing the PREVIOUS character's data — and since the previous
   character was no longer focused, its later snapshots were skipped too, so the
   panes froze permanently. To an operator this reads as "switching does not
   work; no pane changes".
2. The log pane accumulated across characters, so after a switch it showed a
   mixture of both characters' history rather than the new character's.
3. The status pane carried the previous character's cooldown countdown and task
   ETA samples across the switch.
"""

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.tui.app import WatchApp
from artifactsmmo_cli.tui.widgets.inventory_pane import InventoryPane
from artifactsmmo_cli.tui.widgets.log_pane import LogPane
from artifactsmmo_cli.tui.widgets.status_pane import StatusPane


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


async def test_focusing_a_character_with_no_snapshot_clears_the_panes():
    """The reported bug. Focusing bob while only alice has data must NOT leave
    alice's numbers on screen labelled as bob."""
    app = _app()
    async with app.run_test(size=(120, 50)) as pilot:
        app.update_snapshot(_snap("alice", level=7))
        await pilot.press("2")
        await pilot.pause()

        assert app.focused_character == "bob"
        assert app.query_one("#status", StatusPane).snapshot is None
        assert app.query_one("#inv", InventoryPane).snapshot is None


async def test_switching_back_restores_that_characters_snapshot():
    app = _app()
    async with app.run_test(size=(120, 50)) as pilot:
        app.update_snapshot(_snap("alice", level=7))
        app.update_snapshot(_snap("bob", level=42))

        await pilot.press("2")
        await pilot.pause()
        assert app.query_one("#status", StatusPane).snapshot.level == 42

        await pilot.press("1")
        await pilot.pause()
        assert app.query_one("#status", StatusPane).snapshot.level == 7


async def test_the_log_pane_shows_only_the_focused_characters_history():
    """Append-only writes mixed both characters together. After a switch the
    log must hold the new character's lines and none of the old one's."""
    app = _app()
    async with app.run_test(size=(120, 50)) as pilot:
        app.update_snapshot(_snap("alice", selected_goal="AliceGoal"))
        app.update_snapshot(_snap("bob", selected_goal="BobGoal"))

        await pilot.press("2")
        await pilot.pause()

        text = "\n".join(str(line) for line in app.query_one("#log", LogPane).lines)
        assert "BobGoal" in text
        assert "AliceGoal" not in text


async def test_switching_resets_the_previous_characters_cooldown():
    """A 300s cooldown belonging to alice must not keep counting down while the
    operator is watching bob."""
    app = _app()
    async with app.run_test(size=(120, 50)) as pilot:
        app.update_snapshot(_snap("alice", cooldown_remaining=300.0))
        status = app.query_one("#status", StatusPane)
        assert status._cooldown_expiry is not None

        await pilot.press("2")
        await pilot.pause()
        assert status._cooldown_expiry is None


async def test_switching_resets_the_previous_characters_task_eta():
    app = _app()
    async with app.run_test(size=(120, 50)) as pilot:
        app.update_snapshot(_snap("alice", task_code="cow", task_progress=5))
        status = app.query_one("#status", StatusPane)
        assert status._eta_samples

        await pilot.press("2")
        await pilot.pause()
        assert status._eta_samples == []


async def test_a_non_focused_characters_snapshot_never_touches_the_panes():
    """Regression guard for the routing that already worked."""
    app = _app()
    async with app.run_test(size=(120, 50)) as pilot:
        app.update_snapshot(_snap("alice", level=7))
        app.update_snapshot(_snap("bob", level=42))
        await pilot.pause()
        assert app.query_one("#status", StatusPane).snapshot.level == 7


async def test_switching_while_a_modal_is_open_updates_the_modal_too():
    """An operator can switch characters with the character modal up; the modal
    must follow the switch rather than keep showing the old character."""
    app = _app()
    async with app.run_test(size=(120, 50)) as pilot:
        app.update_snapshot(_snap("alice", level=7))
        app.update_snapshot(_snap("bob", level=42))
        await pilot.press("c")               # open the character modal
        await pilot.pause()

        await pilot.press("2")               # switch to bob underneath it
        await pilot.pause()

        assert app.screen._snapshot.level == 42
        assert app.screen._snapshot.character == "bob"
