"""The one-line report of any character in trouble, drawn on the map's HUD line.

Healthy characters are deliberately absent: the key legend at the bottom of the
screen labels each focus key with its character, so listing them again is
duplication the operator can already read. What is duplicated nowhere is a child
in trouble — a dead one's exit reason and last stderr line are reachable here
and nowhere else, and the restart count is reported nowhere else either — so
those entries, and only those, get a line.
"""

from collections.abc import Sequence

from rich.text import Text

from artifactsmmo_cli.tui.roster_entry import RosterEntry

STDERR_TAIL_CHARS = 60
"""How much of a dead child's last stderr line to show."""


def build_roster_line(entries: Sequence[RosterEntry]) -> Text:
    """One segment per character that is dead, or alive only after a restart.

    Empty for a single-character run, which must look exactly as it did before
    multi-character support, and empty when every child is healthy.
    """
    line = Text(no_wrap=True, overflow="crop")
    if len(entries) < 2:
        return line
    for entry in entries:
        if entry.alive and not entry.restarts:
            continue
        marker = "●" if entry.alive else "✗"
        label = f"[{entry.slot}]{marker}{entry.character} L{entry.level} ({entry.x},{entry.y})"
        if entry.restarts:
            label += f" ↻{entry.restarts}"
        if not entry.alive:
            detail = entry.last_reason or ""
            if entry.last_stderr_line:
                tail = entry.last_stderr_line[:STDERR_TAIL_CHARS]
                detail = f"{detail}: {tail}" if detail else tail
            if detail:
                label += f" [{detail}]"
        style = f"bold {entry.color}" if entry.focused else entry.color
        line.append(label + "  ", style=style)
    return line
