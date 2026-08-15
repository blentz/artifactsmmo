"""One reader for every verification harness: the learning store, not traces.

Each of the six verification harnesses (`craft_xp_replay`, `gather_xp_replay`,
`level_cost_replay`, `kill_rate_audit`, `server_axiom_replay`, and the fit that
follows) used to hand-roll its own loader over `play-trace-*.jsonl` files,
producing dicts shaped `{"cycle": n, "state": {...}, "action": ...}` and then
recovering per-cycle deltas by DIFFERENCING CONSECUTIVE STATE SNAPSHOTS. Those
files are a debugging artifact the user deletes; they were never the durable
record. The learning store (`artifactsmmo_cli.ai.learning.store.LearningStore`)
is, and every harness reads it through this module from now on.

THE DIFFERENCE IS THE POINT, NOT AN IMPLEMENTATION DETAIL. Differencing
consecutive snapshots is exactly what produced the off-by-one that made a craft
replay credit every craft with the FOLLOWING cycle's XP: state[i+1] - state[i]
is the delta caused by the action recorded at cycle i+1, not at cycle i, and a
loader that reads a "cycle" dict built from state differences has to get that
shift right by hand, silently, on every call site. It survived three review
rounds before anyone checked it against `fight.xp` in the same record.

The store already attributes each delta to its own row: `Cycle.delta_xp`,
`Cycle.delta_hp`, and `Cycle.delta_skill_xp_json` are written by the SAME
`record_cycle` call that wrote the action that caused them (see
`LearningStore.record_cycle`). So `CycleRecord` exposes those deltas directly
and a consumer reads `record.delta_xp`, never a difference of two `record.xp`
values it computed itself. This does not merely avoid the bug that already
happened; it makes that class of bug unrepresentable, because there is no
second row's state left in a `CycleRecord` to subtract by mistake.

`CycleRecord.skill_levels` is `None`, never `{}`, when the row carries no
level information — `Cycle.skill_levels_json` is NULLABLE, NOT BACK-FILLED
(see `models.CycleBase.skill_levels_json`), and every row recorded before
2026-08-15 is in that state. `None` means "this row cannot answer a level
question"; `{}` would claim the character held no skills at all, which is
never true. A consumer must be able to tell the two apart to exclude the row
rather than silently treat it as level 0.
"""

import json
from dataclasses import dataclass

from sqlmodel import Session as SqlSession
from sqlmodel import col, select

from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore


class EmptyCorpusError(RuntimeError):
    """Raised by `load_cycles` when the query returns no rows.

    A harness that silently finds nothing to check is indistinguishable from
    one that checked and found nothing wrong — this project has a standing
    rule against that shape of vacuity. `load_cycles` never returns `[]`;
    an empty result is always an error a caller must see."""


@dataclass(frozen=True)
class CycleRecord:
    """One `cycles` row, decoded into the shape a verification harness reads.

    `delta_xp` / `delta_hp` / `delta_skill_xp` are the row's OWN deltas, as
    recorded by the same `record_cycle` call that wrote `action_repr` — never
    a difference a caller computed against a neighboring row. See the module
    docstring for why that distinction is load-bearing."""

    character: str
    cycle_index: int
    action_repr: str | None
    action_class: str | None
    outcome: str | None
    level: int | None
    xp: int | None
    hp: int | None
    delta_xp: int | None
    delta_hp: int | None
    delta_skill_xp: dict[str, int]
    skill_levels: dict[str, int] | None


def _parse_skill_xp(raw: str | None) -> dict[str, int]:
    """Parse `delta_skill_xp_json`. Malformed JSON yields `{}` rather than
    raising. Mirrors `learning.projections._parse_skill_xp`."""
    if raw is None:
        return {}
    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return {}
        return {str(k): int(v) for k, v in parsed.items()}
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}


def _parse_skill_levels(raw: str | None) -> dict[str, int] | None:
    """Parse `skill_levels_json` to `None` when the row cannot answer a level
    question — either the column is absent (row predates 2026-08-15) or the
    stored value is malformed. `{}` is never returned: it would claim the
    character held no skills, which the absence of data cannot support."""
    if raw is None:
        return None
    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return None
        return {str(k): int(v) for k, v in parsed.items()}
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def _to_record(row: Cycle) -> CycleRecord:
    return CycleRecord(
        character=row.character,
        cycle_index=row.cycle_index,
        action_repr=row.action_repr,
        action_class=row.action_class,
        outcome=row.outcome,
        level=row.level,
        xp=row.xp,
        hp=row.hp,
        delta_xp=row.delta_xp,
        delta_hp=row.delta_hp,
        delta_skill_xp=_parse_skill_xp(row.delta_skill_xp_json),
        skill_levels=_parse_skill_levels(row.skill_levels_json),
    )


def load_cycles(db_path: str, character: str | None = None) -> list[CycleRecord]:
    """Read every `cycles` row from the learning store at `db_path`, ordered
    by `(character, cycle_index)`, optionally restricted to one `character`.

    Raises `EmptyCorpusError` when the query returns no rows — never returns
    `[]`. Opens its own `LearningStore` (which runs the store's schema
    migrations) and disposes it before returning."""
    store = LearningStore(db_path=db_path, character=character or "")
    try:
        stmt = select(Cycle)
        if character is not None:
            stmt = stmt.where(col(Cycle.character) == character)
        stmt = stmt.order_by(col(Cycle.character), col(Cycle.cycle_index))
        with SqlSession(store._engine) as s:
            rows = list(s.exec(stmt))
    finally:
        store.close()
    if not rows:
        raise EmptyCorpusError(
            f"load_cycles found no rows in {db_path!r} (character={character!r})"
        )
    return [_to_record(row) for row in rows]
