"""End-to-end test for the `artifactsmmo stats` command group.

Writes a small synthetic DB, then invokes the typer apps directly via
the CliRunner so the test exercises arg parsing, DB plumbing, and
section rendering in one pass."""

from datetime import datetime, timezone

from sqlmodel import Session as SqlSession
from sqlmodel import SQLModel, create_engine
from typer.testing import CliRunner

from artifactsmmo_cli.ai.learning.models import Cycle, Session
from artifactsmmo_cli.commands.stats import app as stats_app


def _seed_db(db_path: str) -> str:
    """Create a store rich enough to render every summary section.

    Includes a fight loss (errors + fights + fight-losses tables), crafts /
    deletes / withdraws (breakdown tables), a completed task (task-completions
    table), planner load, and an 8+ cycle stuck window. Returns session_id."""
    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)
    sid = "session-test-1"
    started = datetime(2026, 6, 5, 12, 0, 0, tzinfo=timezone.utc).isoformat()
    ended = datetime(2026, 6, 5, 12, 30, 0, tzinfo=timezone.utc).isoformat()
    rows: list[Cycle] = []
    idx = 0

    def add(action: str, **kw) -> None:
        nonlocal idx
        ts = f"2026-06-05T12:{idx:02d}:00+00:00"
        rows.append(Cycle(ts=ts, session_id=sid, cycle_index=idx,
                          character="Robby", action_repr=action, **kw))
        idx += 1

    # Task starts, progresses, completes (task-completions section).
    add("Gather(copper_rocks)", outcome="ok",
        selected_goal="PursueTask(copper_ore)", task_code="copper_ore",
        task_progress=0, task_total=2, planner_nodes=120, plan_len=4)
    add("Craft(copper_bar×1)", outcome="ok",
        selected_goal="PursueTask(copper_ore)", task_code="copper_ore",
        task_progress=1, task_total=2, planner_nodes=200, plan_len=6,
        planner_timed_out=True)
    add("TaskTrade(copper_ore×2)", outcome="ok",
        selected_goal="PursueTask(copper_ore)", task_code="copper_ore",
        task_progress=2, task_total=2)
    # A fight loss (errors + fights + fight-losses sections).
    add("Fight(chicken)", outcome="error:fight_lost", hp=2, max_hp=130,
        selected_goal="HuntMonsters")
    # Equip + deposit + withdraw + delete (inventory-events + breakdowns).
    add("Equip(copper_pickaxe->weapon_slot)", outcome="ok",
        selected_goal="UpgradeEquipment")
    add("Withdraw(ash_wood×5)", outcome="ok", selected_goal="UpgradeEquipment")
    add("Delete(apple×5)", outcome="ok", selected_goal="UpgradeEquipment")
    add("DepositAll", outcome="ok", selected_goal="UpgradeEquipment")
    # 8 identical cycles → a stuck window.
    for _ in range(9):
        add("Wait", outcome="ok", selected_goal="Idle",
            task_code="stuck_task", task_progress=0, inventory_used=99)

    with SqlSession(engine) as s:
        s.add(Session(
            session_id=sid, character="Robby", started_at=started, ended_at=ended,
            cycle_count=len(rows), exit_reason="normal",
        ))
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
    assert "cycles" in res.output
    # Outcomes table.
    assert "Outcomes" in res.output
    # Selected goals table.
    assert "PursueTask(copper_ore)" in res.output
    # Inventory events: at least the equip and the (zero) crafts.
    assert "Inventory events" in res.output
    assert "equip / loadout" in res.output


def test_summary_renders_every_optional_section(tmp_path):
    """The rich seed triggers all conditionally-rendered tables."""
    db = str(tmp_path / "learning.db")
    _seed_db(db)
    runner = CliRunner()
    res = runner.invoke(stats_app, [
        "summary", "--db", db, "--character", "Robby", "--session", "last",
    ])
    assert res.exit_code == 0, res.output
    out = res.output
    # Errors-by-action (fight_lost outcome).
    assert "Errors by action" in out
    # Planner load row.
    assert "Planner load" in out
    # Fights summary + recent fight-losses.
    assert "Fights" in out
    assert "Fight losses" in out
    assert "chicken" in out
    # Item breakdown tables.
    assert "Crafts" in out
    assert "Deletes" in out
    assert "Withdraws" in out
    # Task completion timing.
    assert "Task completions" in out
    assert "copper_ore" in out
    # Stuck-window detection.
    assert "Stuck windows" in out
    assert "stuck_task" in out


def test_summary_goals_only_filter(tmp_path):
    db = str(tmp_path / "learning.db")
    _seed_db(db)
    runner = CliRunner()
    res = runner.invoke(stats_app, [
        "summary", "--db", db, "--character", "Robby", "--goals-only",
    ])
    assert res.exit_code == 0, res.output
    assert "selected goals" in res.output
    # Other sections must NOT render in goals-only mode.
    assert "Outcomes" not in res.output
    assert "Planner load" not in res.output


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


def _seed_minimal_db(db_path: str) -> None:
    """One session whose single cycle has no errors / fights / crafts / task /
    stuck-window — so every optional section short-circuits to None."""
    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)
    sid = "min-1"
    started = datetime(2026, 6, 5, 12, 0, 0, tzinfo=timezone.utc).isoformat()
    with SqlSession(engine) as s:
        s.add(Session(session_id=sid, character="Robby", started_at=started,
                      ended_at=None, cycle_count=1, exit_reason=None))
        s.add(Cycle(ts="2026-06-05T12:00:00+00:00", session_id=sid,
                    cycle_index=0, character="Robby", outcome="ok",
                    action_repr="Move(0,0)", selected_goal="Idle"))
        s.commit()
    engine.dispose()


def test_summary_omits_empty_optional_sections(tmp_path):
    """With no errors/fights/crafts/tasks/stuck data, those sections are
    skipped entirely (their `return None` branches)."""
    db = str(tmp_path / "learning.db")
    _seed_minimal_db(db)
    runner = CliRunner()
    res = runner.invoke(stats_app, [
        "summary", "--db", db, "--character", "Robby", "--session", "last",
    ])
    assert res.exit_code == 0, res.output
    out = res.output
    # Core sections still render.
    assert "Overview" in out
    assert "Inventory events" in out
    # Optional sections are absent because their data is empty.
    assert "Errors by action" not in out
    assert "Fights" not in out
    assert "Fight losses" not in out
    assert "Crafts" not in out
    assert "Deletes" not in out
    assert "Withdraws" not in out
    assert "Task completions" not in out
    assert "Stuck windows" not in out


def test_sessions_missing_db_exits_nonzero(tmp_path):
    runner = CliRunner()
    res = runner.invoke(stats_app, ["sessions", "--db", str(tmp_path / "nope.db")])
    assert res.exit_code != 0
    assert "not found" in res.output


def test_sessions_empty_db_says_none_found(tmp_path):
    db = str(tmp_path / "learning.db")
    engine = create_engine(f"sqlite:///{db}")
    SQLModel.metadata.create_all(engine)
    engine.dispose()
    runner = CliRunner()
    res = runner.invoke(stats_app, ["sessions", "--db", db])
    assert res.exit_code == 0
    assert "no sessions found" in res.output
