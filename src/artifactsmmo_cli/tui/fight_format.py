"""Rich-markup renderers for a captured fight.

The transcript is server-rendered English and is emitted VERBATIM. The only
styling applied to it is a plain substring search for a couple of notable
phrases, which silently does nothing if the server rewords them. Nothing here
parses the prose — every number in the summary comes from a structured field on
`FightRecord`.
"""

from rich.markup import escape

from artifactsmmo_cli.ai.fight_record import FightRecord

_RESULT_COLOR = {"win": "green", "loss": "red"}

_EMPHASISED = ("Critical strike", "Blocked")
"""Phrases wrapped in [bold] when present. A plain substring search: if the
server rewords them the line renders unemphasised, which is the intended
degradation. Never grows into a parser."""


def _result_markup(rec: FightRecord) -> str:
    color = _RESULT_COLOR[rec.result]
    return f"[{color}]{rec.result}[/{color}]"


def _hp_span(rec: FightRecord) -> str:
    """`485->275`, or `?->275` when the source had no starting HP (backfill)."""
    before = "?" if rec.hp_before is None else str(rec.hp_before)
    return f"{before}->{rec.hp_after}"


def _drops_clause(rec: FightRecord) -> str:
    if not rec.drops:
        return ""
    drops = " ".join(f"{d.code} x{d.quantity}" for d in rec.drops)
    return f"  drops {drops}"


def fight_summary_line(rec: FightRecord) -> str:
    """The one dim line the live log pane appends under a fight cycle."""
    return (
        f"[dim]   fight:[/dim] {_result_markup(rec)} {rec.turns}t  "
        f"hp {_hp_span(rec)}  xp {rec.xp}  gold {rec.gold}{_drops_clause(rec)}"
    )


def fight_row_label(rec: FightRecord) -> str:
    """One row in the fight modal's list."""
    clock = rec.started_at[11:19]
    return (
        f"{_result_markup(rec)}  [dim]{clock}[/dim]  "
        f"{rec.opponent}  {rec.turns}t  hp {_hp_span(rec)}"
    )


def _emphasise(line: str) -> str:
    """Escape the line for Rich, then bold any notable phrase present."""
    rendered = escape(line)
    for phrase in _EMPHASISED:
        if phrase in rendered:
            rendered = rendered.replace(phrase, f"[bold]{phrase}[/bold]")
    return rendered


def fight_detail_lines(rec: FightRecord) -> list[str]:
    """Header plus the verbatim transcript, ready for a RichLog."""
    header = (
        f"{rec.opponent}  {_result_markup(rec)}  {rec.turns} turns  "
        f"hp {_hp_span(rec)}  xp {rec.xp}  gold {rec.gold}{_drops_clause(rec)}"
    )
    return [header, ""] + [_emphasise(line) for line in rec.logs]
