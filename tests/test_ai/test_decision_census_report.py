"""The read-only `decision-census` CLI over a real (tmp_path) learning DB."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.commands import decision_census_report as cmd


@pytest.fixture
def db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """Point the command at an isolated database, never the fleet's real one."""
    path = str(tmp_path / "learning.db")
    monkeypatch.setattr(cmd, "default_learn_db_path", lambda: path)
    return path


def _seed(db: str, character: str, stamps: list[str], exit_reason: str) -> None:
    store = LearningStore(db, character=character)
    store.start_session()
    for i, ts in enumerate(stamps):
        store.record_cycle(Cycle(
            ts=ts, session_id="placeholder", cycle_index=i, character=character,
            outcome="error:HTTP_404" if i == 0 else "ok", action_repr="GeCancel(o1)",
            action_class="GeCancelOrderAction", selected_goal="CancelOrders", delta_xp=10,
            delta_skill_xp_json="{}", actual_cooldown_seconds=3.0))
    store.end_session(exit_reason=exit_reason)
    store.close()


def test_the_window_bounds_every_character_by_wall_clock(
        db_path: str, capsys: pytest.CaptureFixture[str]) -> None:
    _seed(db_path, "Robby", ["2026-09-24T01:00:00+00:00", "2026-09-24T02:00:00+00:00",
                             "2026-09-23T00:00:00+00:00"], "crash")
    _seed(db_path, "HAL", [], "normal")

    cmd.decision_census_command(["Robby", "HAL", "Nobody"], hours=24.0,
                                until="2026-09-25T00:00:00+00:00")
    out = capsys.readouterr().out

    assert "window 2026-09-24T00:00:00+00:00 .. 2026-09-25T00:00:00+00:00 (24 h)" in out
    robby = out.split("== Robby ==")[1].split("== HAL ==")[0]
    assert "cycles 2 (0.1/h)  ok 50.0%" in robby  # the 09-23 row is outside the window
    assert "errors: http_404=1" in robby
    hal = out.split("== HAL ==")[1].split("== Nobody ==")[0]
    assert "cycles 0 (0.0/h)  ok n/a" in hal
    assert "nodes p50/p95/max n/a/n/a/n/a" in hal
    assert "errors: none" in out.split("== Nobody ==")[1]
    assert "sessions ended: none" in out.split("== Nobody ==")[1]


def test_sessions_that_ended_in_the_window_are_counted(
        db_path: str, capsys: pytest.CaptureFixture[str]) -> None:
    # A session row exists only once a cycle is recorded, so seed one.
    _seed(db_path, "Robby", [datetime.now(tz=UTC).isoformat()], "crash")
    cmd.decision_census_command(["Robby"], hours=1.0, until=None)
    assert "sessions ended: crash=1" in capsys.readouterr().out
