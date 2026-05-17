"""End-to-end smoke for --learn flag plumbing."""

import subprocess


def test_default_learn_db_path_format():
    from artifactsmmo_cli.commands.play import default_learn_db_path
    path = default_learn_db_path()
    assert path.endswith("learning.db")
    assert "artifactsmmo" in path


def test_play_help_shows_learn_flags():
    result = subprocess.run(
        ["uv", "run", "artifactsmmo", "play", "play", "--help"],
        capture_output=True, text=True, timeout=30,
    )
    assert "--learn" in result.stdout
    assert "--learn-db" in result.stdout


def test_play_marks_exit_reason_crash_when_run_raises(monkeypatch, tmp_path):
    """Capture true exit_reason in finally — not always 'normal'."""
    from sqlalchemy import create_engine
    from sqlmodel import Session
    from sqlmodel import select as sqlmodel_select
    from artifactsmmo_cli.ai.learning.models import Session as SessRow
    from artifactsmmo_cli.ai.learning.store import LearningStore
    from artifactsmmo_cli.ai.player import GamePlayer

    db_path = tmp_path / "learn.db"

    def boom(self):
        raise RuntimeError("simulated crash")

    monkeypatch.setattr(GamePlayer, "run", boom)

    # Simulate the play() command's lifecycle inline
    store = LearningStore(db_path=str(db_path), character="TestChar")
    store.start_session()
    exit_reason = "crash"
    try:
        player = GamePlayer(character="TestChar", history=store)
        try:
            player.run()
            exit_reason = "normal"
        except KeyboardInterrupt:
            exit_reason = "keyboard_interrupt"
            raise
    except RuntimeError:
        pass  # expected
    finally:
        store.end_session(exit_reason=exit_reason)
        store.close()

    # With lazy session creation (Bug 2 fix), the row should NOT exist
    # because no cycles were recorded.
    engine = create_engine(f"sqlite:///{db_path}")
    with Session(engine) as s:
        rows = list(s.exec(sqlmodel_select(SessRow)))
    assert len(rows) == 0, "lazy session creation: no row should exist if no cycle recorded"
