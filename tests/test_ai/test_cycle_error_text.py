"""A failed cycle must carry WHY it failed into the learning store.

`outcome` collapses distinct dead-ends onto one label. `error:other` alone
covers four separate `_execute_level_skill` raises — a cyclic skill dependency,
"no grind rung at execution", a sub-plan that EXHAUSTED the planning budget, and
a sub-plan that hit a genuine dead end — and the message that tells them apart
rode only the JSONL trace. Traces are deleted periodically and are not a durable
record, so `learning.db` is where a durable claim has to come from, and it could
not answer "which one".

The cost of that gap, measured over the live store: 246 `error:other` cycles on
`LevelSkill`, which `planner_nodes` splits three ways (98 at 1-23 nodes, 29 at
619-12,214, 119 timed out at 7,464-61,669) — three populations that need three
different fixes, and no way to attribute a single row to one of them.
"""

import sqlite3
from contextlib import closing

from sqlmodel import Session, select

from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.player import GamePlayer
from tests.test_ai.fixtures import make_state

GRIND_FAILURE = ("LevelSkill(jewelrycrafting) grind sub-plan EXHAUSTED the 15.0s "
                 "planning budget — goal=GatherMaterials(topaz, {topaz:1}) "
                 "nodes=19552 depth=13.")


def _record(store: LearningStore, outcome: str, last_error: str | None) -> list[Cycle]:
    player = GamePlayer(character="hero", dry_run=False, history=store)
    player._last_error = last_error
    prev = make_state(level=5)
    player._record_learning_cycle(
        prev_state=prev, new_state=make_state(level=5, xp=prev.xp + 10),
        action_repr="LevelSkill(jewelrycrafting->20)", action_class="LevelSkill",
        outcome=outcome, selected_goal="ReachSkill(jewelrycrafting->18)",
        predicted_cost=0.0, actual_cooldown_seconds=0.0,
        planner_nodes=19552, planner_depth=13, planner_timed_out=True,
        plan_len=1,
    )
    with Session(store._engine) as s:
        return list(s.exec(select(Cycle).where(
            Cycle.action_repr == "LevelSkill(jewelrycrafting->20)")))


def test_a_failed_cycle_records_the_error_message(tmp_path):
    store = LearningStore(db_path=str(tmp_path / "err.db"), character="hero")
    try:
        store.start_session()
        rows = _record(store, "error:other", GRIND_FAILURE)
        assert len(rows) == 1
        assert rows[0].error_text == GRIND_FAILURE
    finally:
        store.close()


def test_a_successful_cycle_records_no_error_even_with_a_stale_message(tmp_path):
    """Gated on the OUTCOME, not on the field being set.

    `_execute` never runs on a no-plan cycle, so `_last_error` is not cleared
    there and a PRIOR failure's message is still in the field. Writing it
    against an `ok` row would attribute a failure to a cycle that succeeded —
    the same reasoning the trace's own `error` key is gated by.
    """
    store = LearningStore(db_path=str(tmp_path / "ok.db"), character="hero")
    try:
        store.start_session()
        rows = _record(store, "ok", GRIND_FAILURE)
        assert len(rows) == 1
        assert rows[0].error_text is None
    finally:
        store.close()


def test_a_failed_cycle_with_no_message_records_none(tmp_path):
    store = LearningStore(db_path=str(tmp_path / "none.db"), character="hero")
    try:
        store.start_session()
        rows = _record(store, "error:network", None)
        assert len(rows) == 1
        assert rows[0].error_text is None
    finally:
        store.close()


def test_a_store_predating_the_column_gains_it_on_open(tmp_path):
    """The caches in the wild were written before this column existed.

    Without the one-shot ALTER, every `record_cycle` INSERT on an old cache
    fails with "table cycles has no column named error_text" and learning goes
    silently dead — exactly what the `consumables_expended_json` column did on
    2026-07-05 when it shipped in the model with no matching migration.

    The legacy schema is built by OPENING a current store and dropping the one
    column, rather than by hand-rolling a CREATE TABLE. A hand-rolled copy goes
    stale the moment any other column is added, and then tests the migration
    against a table that never existed.
    """
    db = tmp_path / "old.db"
    store = LearningStore(db_path=str(db), character="hero")
    store.close()
    with closing(sqlite3.connect(db)) as conn:
        conn.execute("ALTER TABLE cycles DROP COLUMN error_text")
        conn.commit()
        cols = {row[1] for row in conn.execute("PRAGMA table_info(cycles)")}
    assert "error_text" not in cols, "legacy fixture must predate the column"

    store = LearningStore(db_path=str(db), character="hero")
    try:
        store.start_session()
        with closing(sqlite3.connect(db)) as conn:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(cycles)")}
        assert "error_text" in cols
        rows = _record(store, "error:other", GRIND_FAILURE)
        assert [r.error_text for r in rows] == [GRIND_FAILURE]
    finally:
        store.close()
