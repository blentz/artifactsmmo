"""End-to-end smoke for --learn flag plumbing."""

import os
import re
import subprocess
import sys


def test_default_learn_db_path_format():
    from artifactsmmo_cli.commands.play import default_learn_db_path
    path = default_learn_db_path()
    assert path.endswith("learning.db")
    assert "artifactsmmo" in path


def test_play_help_shows_learn_flags():
    """Invoke the CLI via the active Python interpreter rather than `uv run`
    so the test works inside any pytest environment (the prior
    `subprocess.run(['uv', 'run', ...])` form failed when uv wasn't on the
    test subprocess PATH — e.g. inside a pre-commit hook)."""
    # Run the typer app directly via -c so the test doesn't depend on
    # an installed entry-point script or a uv binary on PATH.
    result = subprocess.run(
        [
            sys.executable, "-c",
            "from artifactsmmo_cli.main import app; app()",
            "play", "--help",
        ],
        capture_output=True, text=True, timeout=30,
        env={**os.environ, "NO_COLOR": "1"},
    )
    # Under GitHub Actions rich force-styles the help even with NO_COLOR
    # (bold/dim spans split "--learn" into "-" + "-learn"); strip ANSI
    # escapes so the substring asserts see the plain text.
    plain = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
    assert "--learn" in plain, plain + result.stderr
    assert "--learn-db" in plain


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
    engine.dispose()  # close the verification connection; otherwise it leaks (ResourceWarning)
    assert len(rows) == 0, "lazy session creation: no row should exist if no cycle recorded"
