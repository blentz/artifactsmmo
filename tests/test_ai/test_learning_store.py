"""Tests for LearningStore."""

import os
import tempfile

import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session as SqlSession

from artifactsmmo_cli.ai.learning.models import Cycle, Session
from artifactsmmo_cli.ai.learning.store import LearningStore


@pytest.fixture
def tmp_db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    if os.path.exists(path):
        os.unlink(path)


class TestLearningStoreInit:
    def test_creates_db_file(self, tmp_db_path):
        os.unlink(tmp_db_path)
        assert not os.path.exists(tmp_db_path)
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        assert os.path.exists(tmp_db_path)
        store.close()

    def test_creates_tables(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        with SqlSession(store._engine) as s:
            result = s.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )).all()
        store.close()
        names = {row[0] for row in result}
        assert "cycles" in names
        assert "sessions" in names

    def test_wal_journal_mode_enabled(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        with store._engine.connect() as conn:
            mode = conn.execute(text("PRAGMA journal_mode")).scalar()
        store.close()
        assert mode == "wal"

    def test_idempotent_init(self, tmp_db_path):
        store1 = LearningStore(db_path=tmp_db_path, character="testchar")
        store1.close()
        store2 = LearningStore(db_path=tmp_db_path, character="testchar")
        store2.close()


class TestSessionLifecycle:
    def test_start_session_returns_id_and_inserts_row(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        session_id = store.start_session()
        assert session_id.startswith("session-")

        with SqlSession(store._engine) as s:
            rows = s.execute(text("SELECT session_id, character, exit_reason FROM sessions")).all()
        store.close()
        assert len(rows) == 1
        assert rows[0][0] == session_id
        assert rows[0][1] == "testchar"
        assert rows[0][2] is None

    def test_end_session_records_exit_reason(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        session_id = store.start_session()
        store.end_session(exit_reason="keyboard_interrupt")
        with SqlSession(store._engine) as s:
            rows = s.execute(text(
                "SELECT exit_reason, ended_at FROM sessions WHERE session_id=:sid"
            ), {"sid": session_id}).all()
        store.close()
        assert rows[0][0] == "keyboard_interrupt"
        assert rows[0][1] is not None

    def test_end_session_without_start_is_noop(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.end_session()
        store.close()


class TestRecordCycle:
    def test_round_trip(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        cycle = Cycle(
            ts="2026-05-17T00:00:00+00:00",
            session_id="overridden",
            cycle_index=0,
            character="overridden",
            outcome="ok",
            action_repr="Fight(yellow_slime)",
            actual_cooldown_seconds=12.5,
        )
        store.record_cycle(cycle)

        with SqlSession(store._engine) as s:
            rows = s.execute(text(
                "SELECT action_repr, actual_cooldown_seconds, session_id, character FROM cycles"
            )).all()
        store.close()
        assert len(rows) == 1
        assert rows[0][0] == "Fight(yellow_slime)"
        assert rows[0][1] == 12.5

    def test_record_cycle_overrides_session_id_and_character(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="actual_char")
        session_id = store.start_session()
        cycle = Cycle(
            ts="2026-05-17T00:00:00+00:00",
            session_id="wrong",
            cycle_index=0,
            character="wrong",
            outcome="ok",
        )
        store.record_cycle(cycle)
        with SqlSession(store._engine) as s:
            rows = s.execute(text("SELECT session_id, character FROM cycles")).all()
        store.close()
        assert rows[0][0] == session_id
        assert rows[0][1] == "actual_char"

    def test_record_cycle_swallows_sqlalchemy_error(self, tmp_db_path, monkeypatch):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()

        def boom(self, instance):
            raise SQLAlchemyError("simulated DB failure")

        monkeypatch.setattr(SqlSession, "add", boom)
        cycle = Cycle(
            ts="2026-05-17T00:00:00+00:00",
            session_id="x", cycle_index=0, character="testchar", outcome="ok",
        )
        store.record_cycle(cycle)
        store.close()


def test_package_reexport():
    from artifactsmmo_cli.ai.learning import LearningStore as RootImport
    from artifactsmmo_cli.ai.learning.store import LearningStore as ModuleImport
    assert RootImport is ModuleImport


def _insert_cycles(store, action_repr, cooldowns, outcomes=None):
    """Helper: insert N cycles with given cooldowns and outcomes."""
    outcomes = outcomes or ["ok"] * len(cooldowns)
    for i, (cd, oc) in enumerate(zip(cooldowns, outcomes)):
        store.record_cycle(Cycle(
            ts=f"2026-05-17T00:00:{i:02d}+00:00",
            session_id="x", cycle_index=i, character="x", outcome=oc,
            action_repr=action_repr,
            actual_cooldown_seconds=cd,
        ))


class TestActionCost:
    def test_returns_default_when_fewer_than_5_samples(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        _insert_cycles(store, "Fight(x)", [10.0, 11.0, 12.0])
        assert store.action_cost("Fight(x)", default=99.0) == 99.0
        store.close()

    def test_returns_median_when_at_least_5_samples(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        _insert_cycles(store, "Fight(x)", [10.0, 11.0, 12.0, 13.0, 14.0])
        assert store.action_cost("Fight(x)", default=99.0) == 12.0
        store.close()

    def test_filters_by_action_repr(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        _insert_cycles(store, "Fight(x)", [10.0] * 5)
        _insert_cycles(store, "Fight(y)", [20.0] * 5)
        assert store.action_cost("Fight(x)", default=99.0) == 10.0
        assert store.action_cost("Fight(y)", default=99.0) == 20.0
        store.close()

    def test_ignores_failed_actions(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        _insert_cycles(store, "Fight(x)",
                       cooldowns=[10.0, 10.0, 10.0, 99.0, 99.0],
                       outcomes=["ok", "ok", "ok", "error:HTTP_497", "error:HTTP_497"])
        assert store.action_cost("Fight(x)", default=42.0) == 42.0
        store.close()
