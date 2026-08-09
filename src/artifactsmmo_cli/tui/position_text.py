"""One rendering of a character's position, shared by every surface that shows it."""

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot

OVERWORLD = "overworld"


def position_text(snap: CycleSnapshot) -> str:
    """`(x,y)` on the overworld, `(x,y) layer` anywhere else.

    A tile is identified by (layer, x, y) — the same coordinates exist on the
    overworld, underground and interior layers — so coordinates alone name a
    different tile than the character is standing on once it has taken a
    transition. The layer is omitted on the overworld because a run that never
    leaves it would otherwise repeat the word on every line.
    """
    if snap.layer == OVERWORLD:
        return f"({snap.x},{snap.y})"
    return f"({snap.x},{snap.y}) {snap.layer}"
