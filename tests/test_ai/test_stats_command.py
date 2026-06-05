"""End-to-end test for the `artifactsmmo stats` command group.

Writes a small synthetic DB, then invokes the typer apps directly via
the CliRunner so the test exercises arg parsing, DB plumbing, and
section rendering in one pass."""

from datetime import datetime, timezone

from sqlmodel import Session as SqlSession, SQLModel, create_engine
from typer.testing import CliRunner

from artifactsmmo_cli.ai.learning.models import Cycle, Session
from artifactsmmo_cli.commands.stats import app as stats_app


def _seed_db(db_path: str) -> str:
    """Create a minimal store with one session + a few cycles. Returns session_id."""
    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)
    sid = "session-test-1"
    started = datetime(2026, 6, 5, 12, 0, 0, tzinfo=timezone.utc).isoformat()
    ended = datetime(2026, 6, 5, 12, 30, 0, tzinfo=timezone.utc).isoformat()
    with SqlSession(engine) as s:
        s.add(Session(
            session_id=sid, character="Robby", started_at=started, ended_at=ended,
            cycle_count=3, exit_reason="normal",
        ))
        rows = [
            Cycle(ts="2026-06-05T12:00:00+00:00", session_id=sid, cycle_index=0,
                  character="Robby", outcome="ok",
                  action_repr="Gather(copper_rocks)", selected_goal="PursueTask(copper_ore)",
                  task_code="copper_ore", task_progress=0, task_total=2),
            Cycle(ts="2026-06-05T12:10:00+00:00", session_id=sid, cycle_index=1,
                  character="Robby", outcome="ok",
                  action_repr="TaskTrade(copper_ore×2)", selected_goal="PursueTask(copper_ore)",
                  task_code="copper_ore", task_progress=2, task_total=2),
            Cycle(ts="2026-06-05T12:20:00+00:00", session_id=sid, cycle_index=2,
                  character="Robby", outcome="ok",
                  action_repr="Equip(copper_pickaxe->weapon_slot)",
                  selected_goal="UpgradeEquipment",
                  task_code=None, task_progress=0, task_total=0),
        ]
        for r in rows:
            s.add(r)
        s.commit()
    engine.dispose()
    return sid


def test_sessions_lists_recent_sessions(tmp_path):
    db = str(tmp_path / "learning.db")
    _seed_db(db)
    runner = CliRunner()
    res = runner.invoke(stats_app, ["sessions", "--db", db, "--limit", "5"])
    assert res.exit_code == 0, res.output
    assert "Robby" in res.output
    assert "normal" in res.output


def test_summary_shows_core_sections(tmp_path):
    db = str(tmp_path / "learning.db")
    _seed_db(db)
    runner = CliRunner()
    res = runner.invoke(stats_app, [
        "summary", "--db", db, "--character", "Robby",
        "--session", "last",
    ])
    assert res.exit_code == 0, res.output
    # Overview present.
    assert "cycles" in res.output and "3" in res.output
    # Outcomes table.
    assert "Outcomes" in res.output
    # Selected goals table.
    assert "PursueTask(copper_ore)" in res.output
    # Inventory events: at least the equip and the (zero) crafts.
    assert "Inventory events" in res.output
    assert "equip / loadout" in res.output


def test_summary_planner_only_filter(tmp_path):
    db = str(tmp_path / "learning.db")
    _seed_db(db)
    runner = CliRunner()
    res = runner.invoke(stats_app, [
        "summary", "--db", db, "--character", "Robby", "--planner-only",
    ])
    assert res.exit_code == 0, res.output
    assert "Planner load" in res.output
    # Other section titles must NOT appear in planner-only mode.
    assert "Outcomes" not in res.output


def test_summary_missing_db_exits_nonzero(tmp_path):
    runner = CliRunner()
    res = runner.invoke(stats_app, ["summary", "--db", str(tmp_path / "nope.db")])
    assert res.exit_code != 0
    assert "not found" in res.output


def test_summary_session_all_filter(tmp_path):
    db = str(tmp_path / "learning.db")
    _seed_db(db)
    runner = CliRunner()
    res = runner.invoke(stats_app, [
        "summary", "--db", db, "--session", "all",
    ])
    assert res.exit_code == 0, res.output
    assert "cycles" in res.output


def test_summary_no_match_says_so(tmp_path):
    db = str(tmp_path / "learning.db")
    _seed_db(db)
    runner = CliRunner()
    res = runner.invoke(stats_app, [
        "summary", "--db", db, "--character", "NoSuchChar",
    ])
    assert res.exit_code == 0
    assert "no cycles matched" in res.output
