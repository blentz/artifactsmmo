"""LearningStore must tolerate concurrent writers (5 children share one DB)."""

from sqlalchemy import text

from artifactsmmo_cli.ai.learning.store import LearningStore


def test_busy_timeout_is_set(tmp_path):
    store = LearningStore(db_path=str(tmp_path / "learning.db"), character="hero")
    with store._engine.connect() as conn:
        timeout_ms = conn.exec_driver_sql("PRAGMA busy_timeout").fetchone()[0]
    store.close()
    assert timeout_ms >= 5000, (
        f"busy_timeout is {timeout_ms}ms; concurrent children need a real wait"
    )


def test_second_writer_waits_instead_of_failing(tmp_path):
    db = str(tmp_path / "learning.db")
    first = LearningStore(db_path=db, character="alice")
    second = LearningStore(db_path=db, character="bob")
    first.start_session()
    second.start_session()
    first._ensure_session_row()
    second._ensure_session_row()
    first.end_session(exit_reason="normal")
    second.end_session(exit_reason="normal")
    with second._engine.connect() as conn:
        rows = conn.execute(text("SELECT DISTINCT character FROM sessions")).fetchall()
    first.close()
    second.close()
    assert {r[0] for r in rows} == {"alice", "bob"}
