"""The trouble line lives on the map's HUD line, not in the status pane.

It used to render above the status table in the left-hand column, which is one
narrow grid cell wide — a dead child's line ("[2]✗bob L7 (5,-1) [crash: ...]")
was cropped after a dozen characters, so the diagnostic it exists to carry was
the part that got cut. The map's HUD line spans the two wide grid columns and
already carries the coordinates, with room to spare after them.

What renders is unchanged: only characters IN TROUBLE — dead, or alive after a
restart — because the key legend names the healthy ones.
"""

from rich.text import Text

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.tui.palette import BLOOD, TUNIC
from artifactsmmo_cli.tui.roster_entry import RosterEntry
from artifactsmmo_cli.tui.widgets.map_pane import MapPane


def _snap(**overrides: object) -> CycleSnapshot:
    base = dict(
        cycle_index=1, timestamp="2026-07-31T12:00:00Z", character="alice",
        x=0, y=0, level=7, xp=0, max_xp=150, hp=120, max_hp=120, gold=0,
        selected_goal="ReachLevel(50)", action="Rest()", outcome="ok",
    )
    base.update(overrides)
    return CycleSnapshot(**base)  # type: ignore[arg-type]


def _pane() -> MapPane:
    return MapPane(GameData())


def _entries(*, bob_alive: bool = False, bob_restarts: int = 2) -> tuple[RosterEntry, ...]:
    return (
        RosterEntry(slot=1, character="alice", color=TUNIC, level=19,
                    x=0, y=2, alive=True, restarts=0, focused=True),
        RosterEntry(slot=2, character="bob", color=BLOOD, level=7,
                    x=5, y=-1, alive=bob_alive, restarts=bob_restarts, focused=False),
    )


def _hud(pane: MapPane) -> str:
    return pane.hud_text(0, 0).plain


def test_the_hud_line_still_leads_with_the_coordinates():
    pane = _pane()
    pane.set_roster(_entries())

    assert _hud(pane).startswith("(0,0)")


def test_a_dead_character_is_named_on_the_hud_line():
    pane = _pane()
    pane.set_roster(_entries())
    hud = _hud(pane)

    assert "bob" in hud and "✗" in hud


def test_a_dead_characters_reason_and_stderr_reach_the_hud_line():
    """The whole point of the move: this is the only place a dead child's cause
    of death is reachable, and it is what the narrow column was cropping."""
    pane = _pane()
    pane.set_roster((
        RosterEntry(slot=2, character="bob", color=BLOOD, level=7, x=5, y=-1,
                    alive=False, restarts=0, focused=False,
                    last_reason="crash", last_stderr_line="Traceback: boom"),
        RosterEntry(slot=1, character="alice", color=TUNIC, level=19, x=0, y=2,
                    alive=True, restarts=0, focused=True),
    ))
    hud = _hud(pane)

    assert "crash" in hud and "Traceback: boom" in hud


def test_a_healthy_character_is_not_named_on_the_hud_line():
    pane = _pane()
    pane.set_roster(_entries())

    assert "alice" not in _hud(pane)


def test_an_alive_character_that_has_restarted_is_still_reported():
    pane = _pane()
    pane.set_roster(_entries(bob_alive=True, bob_restarts=3))

    assert "bob" in _hud(pane) and "↻3" in _hud(pane)


def test_a_roster_with_nothing_wrong_leaves_the_coordinates_alone():
    pane = _pane()
    bare = _hud(pane)
    pane.set_roster(_entries(bob_alive=True, bob_restarts=0))

    assert _hud(pane) == bare


def test_a_single_character_roster_never_renders():
    """Single-character play must look exactly as it did before
    multi-character support."""
    pane = _pane()
    bare = _hud(pane)
    pane.set_roster(_entries()[:1])

    assert _hud(pane) == bare


def test_the_hud_line_repaints_when_the_roster_changes():
    """The HUD Strip is cached on a content signature. A child dying while the
    map sits still changes no coordinate, so without the roster in that
    signature the line would keep its stale cached Strip and the death would
    never appear."""
    pane = _pane()
    pane.snapshot = _snap()
    pane.set_roster(_entries(bob_alive=True, bob_restarts=0))
    before = pane.render_line(0).text

    pane.set_roster(_entries())

    assert pane.render_line(0).text != before
    assert "bob" in pane.render_line(0).text


def test_a_death_before_the_first_cycle_is_still_reported():
    """With no snapshot the pane shows a waiting message. A child can die
    before ever completing a cycle, and that is exactly when the operator needs
    the reason, so the waiting line carries the roster too."""
    pane = _pane()
    pane.set_roster(_entries())

    assert "bob" in pane.render_line(0).text


def test_the_dead_characters_colour_survives_the_hud_style():
    """The HUD strip is painted with an opaque background style; per-character
    colours must not be flattened by it."""
    pane = _pane()
    pane.set_roster(_entries())
    text: Text = pane.hud_text(0, 0)

    assert any(span.style == BLOOD for span in text.spans)
