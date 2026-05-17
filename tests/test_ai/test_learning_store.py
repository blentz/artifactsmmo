"""Tests for LearningStore."""

import os
import tempfile

import pytest
from sqlalchemy import text
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
