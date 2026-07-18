"""Cut the realized cycle trajectory into progression bands: runs at one
character level, or runs grinding one skill target. Bands never span a
session or character boundary."""

from dataclasses import dataclass
from itertools import groupby

from artifactsmmo_cli.ai.macro.cost import parse_goal_type
from artifactsmmo_cli.ai.macro.cycle_row import CycleRow


@dataclass(frozen=True)
class Band:
    character: str
    session_id: str
    kind: str
    key: str
    rows: tuple[CycleRow, ...]


def _segment_key(row: CycleRow, kind: str) -> str | None:
    """The band key for a row, or None if the row is excluded from this kind.

    `kind` is validated by `segment_bands` before this is called, so only
    "level" and "skill" ever reach here — no redundant kind guard."""
    if kind == "level":
        return f"level={row.level}"
    if parse_goal_type(row.selected_goal) != "LevelSkill":
        return None
    return row.selected_goal


def segment_bands(rows: list[CycleRow], kind: str) -> list[Band]:
    if kind not in ("level", "skill"):
        raise ValueError(f"unknown band kind: {kind}")
    bands: list[Band] = []
    by_owner = sorted(rows, key=lambda r: (r.character, r.session_id, r.cycle_index))

    def flush(char: str, sess: str, current_key: str | None,
              run: list[CycleRow]) -> None:
        if current_key is not None and run:
            bands.append(Band(char, sess, kind, current_key, tuple(run)))

    for (char, sess), session_rows in groupby(
        by_owner, key=lambda r: (r.character, r.session_id)
    ):
        current_key: str | None = None
        run: list[CycleRow] = []
        for r in session_rows:
            k = _segment_key(r, kind)
            if k != current_key:
                flush(char, sess, current_key, run)
                run = []
                current_key = k
            if k is not None:
                run.append(r)
        flush(char, sess, current_key, run)
    return bands
