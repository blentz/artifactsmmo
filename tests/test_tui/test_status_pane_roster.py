"""StatusPane renders the multi-character roster line.

The line used to name every character on every cycle. That duplicated the key
legend, which now carries the names (see test_app_character_keybinds), so a
healthy roster renders NOTHING here. What is not duplicated anywhere is a
child in trouble — a dead one's exit reason and last stderr line are reachable
nowhere else, and a restart count is reported nowhere else — so those entries,
and only those, still get a line.
"""

from rich.console import Console

from artifactsmmo_cli.tui.palette import BLOOD, TUNIC
from artifactsmmo_cli.tui.roster_entry import RosterEntry
from artifactsmmo_cli.tui.widgets.status_pane import StatusPane


def _entries():
    return (
        RosterEntry(slot=1, character="alice", color=TUNIC, level=19,
                    x=0, y=2, alive=True, restarts=0, focused=True),
        RosterEntry(slot=2, character="bob", color=BLOOD, level=7,
                    x=5, y=-1, alive=False, restarts=2, focused=False),
    )


def test_a_healthy_character_is_not_listed():
    """alice is alive and has never restarted: the key legend already names
    her, so repeating it here is the redundancy this line was carrying."""
    pane = StatusPane()
    pane.update_roster(_entries())

    assert "alice" not in pane.roster_text().plain


def test_a_character_in_trouble_is_named_with_its_slot_and_level():
    """bob is dead: he is named here because nothing else reports it."""
    pane = StatusPane()
    pane.update_roster(_entries())
    text = pane.roster_text().plain

    assert "2" in text and "bob" in text and "7" in text


def test_an_alive_character_that_has_restarted_is_still_shown():
    """A child that died and came back looks healthy right now, but the restart
    count is reported nowhere else, so it keeps its line."""
    entries = (
        RosterEntry(slot=1, character="alice", color=TUNIC, level=19,
                    x=0, y=2, alive=True, restarts=3, focused=True),
        RosterEntry(slot=2, character="bob", color=BLOOD, level=7,
                    x=5, y=-1, alive=True, restarts=0, focused=False),
    )
    pane = StatusPane()
    pane.update_roster(entries)
    text = pane.roster_text().plain

    assert "alice" in text and "↻3" in text
    assert "bob" not in text


def test_a_roster_with_nothing_wrong_renders_nothing():
    entries = (
        RosterEntry(slot=1, character="alice", color=TUNIC, level=19,
                    x=0, y=2, alive=True, restarts=0, focused=True),
        RosterEntry(slot=2, character="bob", color=BLOOD, level=7,
                    x=5, y=-1, alive=True, restarts=0, focused=False),
    )
    pane = StatusPane()
    pane.update_roster(entries)

    assert pane.roster_text().plain == ""


def test_a_dead_character_is_visibly_marked():
    pane = StatusPane()
    pane.update_roster(_entries())
    assert "✗" in pane.roster_text().plain


def test_a_restart_count_is_shown_when_nonzero():
    """Checking that a bare '2' appears anywhere is vacuous here: bob's own
    slot number is 2, so that substring is present regardless of whether
    restarts render at all. Anchor on the restart glyph the implementation
    uses (↻) directly adjacent to the count instead."""
    pane = StatusPane()
    pane.update_roster(_entries())
    assert "↻2" in pane.roster_text().plain


def test_a_zero_restart_count_is_not_shown():
    """The alive, never-restarted entry must NOT get a ↻0 marker — otherwise
    the restart glyph would be unconditional and this whole feature vacuous."""
    pane = StatusPane()
    pane.update_roster(_entries())
    assert "↻0" not in pane.roster_text().plain


def test_a_single_character_roster_renders_nothing():
    """Single-character play must look exactly as it did before."""
    pane = StatusPane()
    pane.update_roster(_entries()[:1])
    assert pane.roster_text().plain == ""


def _rendered(pane: StatusPane) -> str:
    console = Console(no_color=True, width=120)
    with console.capture() as cap:
        console.print(pane.render())
    return cap.get()


def test_render_prepends_the_roster_line_to_the_status_body():
    """render() (not just roster_text()) must actually surface the strip above
    the usual status table when a character is in trouble."""
    pane = StatusPane()
    pane.update_roster(_entries())
    out = _rendered(pane)
    assert "bob" in out
    assert "Waiting..." in out  # the usual no-snapshot body is still present


def test_render_omits_the_roster_line_for_a_single_character():
    """A single-character roster must render IDENTICALLY to no roster at
    all — the render() wrapping must not leak an empty Group."""
    pane = StatusPane()
    pane.update_roster(_entries()[:1])
    with_roster = _rendered(pane)
    bare = StatusPane()
    without_roster = _rendered(bare)
    assert with_roster == without_roster


# --- Finding 3: a dead character's last stderr line / exit reason must be
# reachable where it is shown, not merely captured and discarded ------------


def test_a_dead_characters_last_reason_is_shown():
    entries = (
        RosterEntry(slot=1, character="alice", color=TUNIC, level=19,
                    x=0, y=2, alive=True, restarts=0, focused=True),
        RosterEntry(slot=2, character="bob", color=BLOOD, level=7,
                    x=5, y=-1, alive=False, restarts=2, focused=False,
                    last_reason="crash", last_stderr_line="Traceback: boom"),
    )
    pane = StatusPane()
    pane.update_roster(entries)
    text = pane.roster_text().plain
    assert "crash" in text
    assert "Traceback: boom" in text


def test_an_alive_characters_reason_and_stderr_are_not_shown():
    """last_reason/last_stderr_line are set only once a child has actually
    died; showing them for a live character would be misleading noise."""
    entries = (
        RosterEntry(slot=1, character="alice", color=TUNIC, level=19,
                    x=0, y=2, alive=True, restarts=0, focused=True,
                    last_reason="crash", last_stderr_line="stale from a prior life"),
    )
    pane = StatusPane()
    pane.update_roster(entries * 2)  # keep it multi-character so the line renders
    text = pane.roster_text().plain
    assert "crash" not in text
    assert "stale from a prior life" not in text


def test_a_dead_character_with_no_reason_or_stderr_renders_as_before():
    """Backward-compatible default: a dead entry that never got a reason or
    stderr line (e.g. never actually observed) must not sprout an empty
    bracket."""
    pane = StatusPane()
    pane.update_roster(_entries())
    text = pane.roster_text().plain
    assert "[]" not in text
