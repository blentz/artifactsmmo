"""One reader for the harnesses that replay `cycles` rows: the learning store,
not traces.

FIVE harnesses import this module — `gather_xp_replay`, `level_cost_replay`,
`trace_characterize`, `trace_lockstep`, `xp_formula_replay` — and each of the
five used to hand-roll its own loader over `play-trace-*.jsonl` files,
producing dicts shaped `{"cycle": n, "state": {...}, "action": ...}` and then
recovering per-cycle deltas by DIFFERENCING CONSECUTIVE STATE SNAPSHOTS. Those
files are a debugging artifact the user deletes; they were never the durable
record. The learning store (`artifactsmmo_cli.ai.learning.store.LearningStore`)
is.

It is NOT the reader for every harness in `formal/diff`, and three that sit
next to it deliberately do not import it:

  * `craft_xp_replay` reads the store's `craft_yield` table directly. That
    table, not `cycles`, is where a craft's xp and quantity are recorded, so
    this module has nothing it needs.
  * `kill_rate_audit` never read a trace at all — it statically parses
    `formal/diff/mutate.py` to enumerate mutation `run_group` calls.
  * `server_axiom_replay` still reads `REPO_ROOT / "traces.jsonl"` — a
    different file from the deleted `play-trace-*.jsonl` corpus, and a
    migration nobody has done.

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
values it computed itself. This does not make the mistake impossible —
`CycleRecord` still carries the row's absolute `xp`/`hp`, and a future harness
could difference two records exactly as before and reproduce the bug — but it
makes the correct path the convenient one and removes any NEED to difference,
which is what the three review rounds that missed the original bug did not
have.

`CycleRecord.skill_levels` is `None` — never `{}` — whenever the row cannot
answer a level question: `Cycle.skill_levels_json` is NULLABLE, NOT
BACK-FILLED (see `models.CycleBase.skill_levels_json`), and every row
recorded before 2026-08-15 is in that state; a row whose stored value parses
to an empty object is treated the same way, since a level lookup against zero
observed skills is exactly as unanswerable as a level lookup against a NULL
column. `{}` would claim the character held no skills at all, which is never
true. A consumer must be able to tell "no answer" apart from "level 0" and
exclude the row rather than silently defaulting it.
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

    `delta_xp` / `delta_hp` / `delta_inv_used` / `delta_skill_xp` are the row's
    OWN deltas, as recorded by the same `record_cycle` call that wrote
    `action_repr` — never a difference a caller computed against a neighboring
    row. See the module docstring for why that distinction is load-bearing.

    THE SCALARS ARE POST-ACTION. `hp`, `max_hp`, `xp`, `level`,
    `inventory_used` and `inventory_max` are copied from `new_state` — the
    state AFTER this row's action ran (`player.py`'s `_record_learning_cycle`,
    which is the `Cycle(...)` write site; NOT `_make_cycle_record`, an
    unrelated method that builds the identically-named `recovery.CycleRecord`
    for the stuck rules and carries no hp at all) —
    while `skill_levels` is copied from `prev_state` and is PRE-action. A check
    of the form "REST leaves hp at max_hp" therefore reads `hp == max_hp` on
    the Rest row itself and needs no neighbor.

    WHAT THIS RECORD STILL CANNOT ANSWER: `session_id`. `cycles` carries it;
    this record does not, so a consumer can order rows by `ts` but cannot tell
    whether two chronologically adjacent rows belong to the same run. Any
    measurement of "what happened NEXT within one session" — chore-run lengths,
    bursts between fights — is therefore still out of reach, not because the
    store lacks the data but because this field list does. Add `session_id`
    here if such a measurement is ever wanted."""

    character: str
    cycle_index: int
    ts: str
    action_repr: str | None
    action_class: str | None
    outcome: str | None
    level: int | None
    xp: int | None
    hp: int | None
    max_hp: int | None
    inventory_used: int | None
    inventory_max: int | None
    delta_xp: int | None
    delta_hp: int | None
    delta_inv_used: int | None
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
    question: the column is absent (row predates 2026-08-15), the stored
    value is malformed or not a JSON object, OR the object is empty. `{}` is
    never returned — an empty object is exactly as unable to answer "what
    level was skill X held at" as a NULL column is, so both collapse to the
    same `None`, and a consumer never has to special-case which reason it
    was."""
    if raw is None:
        return None
    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict) or not parsed:
            return None
        return {str(k): int(v) for k, v in parsed.items()}
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def _to_record(row: Cycle) -> CycleRecord:
    return CycleRecord(
        character=row.character,
        cycle_index=row.cycle_index,
        ts=row.ts,
        action_repr=row.action_repr,
        action_class=row.action_class,
        outcome=row.outcome,
        level=row.level,
        xp=row.xp,
        hp=row.hp,
        max_hp=row.max_hp,
        inventory_used=row.inventory_used,
        inventory_max=row.inventory_max,
        delta_xp=row.delta_xp,
        delta_hp=row.delta_hp,
        delta_inv_used=row.delta_inv_used,
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
