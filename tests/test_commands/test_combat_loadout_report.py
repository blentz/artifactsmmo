"""Tests for the combat-loadout-report CLI command."""

from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

from typer.testing import CliRunner

from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.commands.combat_loadout_report import _default_db_path
from artifactsmmo_cli.main import app


def test_default_db_path_points_at_learning_db() -> None:
    p = _default_db_path()
    assert p.endswith("artifactsmmo/learning.db")


def test_bad_parameter_on_missing_db(tmp_path: Path, runner: CliRunner) -> None:
    missing = tmp_path / "nope.db"
    result = runner.invoke(app, ["combat-loadout-report", "--db", str(missing)])
    assert result.exit_code != 0
    assert not missing.exists()


def _seed_outcomes(db: str) -> None:
    """Seed CombatLoadoutOutcome rows into the db for both hero and ally."""
    store_hero = LearningStore(db_path=db, character="hero")
    store_hero.record_combat_outcome(
        task_key="combat:chicken",
        loadout={"weapon_slot": "stick"},
        predicted_win=True,
        actual_win=True,
        level=5,
    )
    store_hero.record_combat_outcome(
        task_key="combat:chicken",
        loadout={"weapon_slot": "stick"},
        predicted_win=True,
        actual_win=False,  # over-estimate
        level=5,
    )
    store_ally = LearningStore(db_path=db, character="ally")
    store_ally.record_combat_outcome(
        task_key="combat:wolf",
        loadout={"weapon_slot": "sword"},
        predicted_win=False,
        actual_win=True,  # under-estimate
        level=5,
    )


def test_command_prints_report(tmp_path: Path, runner: CliRunner) -> None:
    db = str(tmp_path / "l.db")
    _seed_outcomes(db)
    result = runner.invoke(app, ["combat-loadout-report", "--db", db])
    assert result.exit_code == 0
    assert "combat:chicken" in result.output
    assert "combat:wolf" in result.output
    assert "# Combat-loadout calibration" in result.output


def test_command_writes_to_out_file(tmp_path: Path, runner: CliRunner) -> None:
    db = str(tmp_path / "l.db")
    _seed_outcomes(db)
    out = tmp_path / "report.md"
    result = runner.invoke(app, ["combat-loadout-report", "--db", db, "--out", str(out)])
    assert result.exit_code == 0
    text = out.read_text()
    assert "# Combat-loadout calibration" in text
    assert "combat:chicken" in text
    assert "combat:wolf" in text


def test_command_cross_character_all_rows(tmp_path: Path, runner: CliRunner) -> None:
    """Report spans ALL characters; no per-character filter."""
    db = str(tmp_path / "l.db")
    _seed_outcomes(db)
    result = runner.invoke(app, ["combat-loadout-report", "--db", db])
    assert result.exit_code == 0
    # Both hero's chicken and ally's wolf should appear
    assert "combat:chicken" in result.output
    assert "combat:wolf" in result.output


def test_command_empty_db_gives_empty_state_message(
    tmp_path: Path, runner: CliRunner
) -> None:
    """Empty db produces an empty-state message, not a crash."""
    db = str(tmp_path / "l.db")
    # Create the db by initializing a store (so the file exists but is empty)
    LearningStore(db_path=db, character="hero")
    result = runner.invoke(app, ["combat-loadout-report", "--db", db])
    assert result.exit_code == 0
    assert "No fight outcome data recorded yet" in result.output


def test_command_fills_p_win_from_the_db(tmp_path: Path, runner: CliRunner) -> None:
    db = str(tmp_path / "l.db")
    store = LearningStore(db_path=db, character="hero")
    store.record_combat_outcome("combat:owl", {}, True, True, 5, p_win=Fraction(97, 100))
    store.close()
    result = runner.invoke(app, ["combat-loadout-report", "--db", db])
    assert result.exit_code == 0
    assert "| 0.9-1.0 | 1 | 97% | 100% |" in result.output


def test_command_names_a_threshold_beyond_the_liveness_bound(tmp_path: Path, runner: CliRunner) -> None:
    """hero's imp losses each cost 9030 s against 60 s a win: θ 0.993, above
    the 99/100 the liveness proof covers."""
    db = str(tmp_path / "l.db")
    store = LearningStore(db_path=db, character="hero")
    store.start_session()
    store.record_combat_outcome("combat:imp", {}, True, True, 5, p_win=Fraction(1))
    now = datetime.now(tz=timezone.utc).isoformat()
    cycles: list[tuple[str, str, str, float]] = []
    for won in [True] * 5 + [False] * 5:
        cycles.append(("FightAction", "Fight(imp)", "ok" if won else "error:fight_lost", 10.0))
        cycles.append(("RestAction", "Rest", "ok", 50.0 if won else 9000.0))
        if not won:
            cycles.append(("MoveAction", "Move(0,0)", "ok", 20.0))
    cycles.append(("FightAction", "Fight(imp)", "ok", 10.0))
    for i, (cls, rep, outcome, secs) in enumerate(cycles):
        store.record_cycle(Cycle(ts=now, session_id="x", cycle_index=i, character="hero",
                                 action_class=cls, action_repr=rep, outcome=outcome,
                                 actual_cooldown_seconds=secs))
    store.close()
    result = runner.invoke(app, ["combat-loadout-report", "--db", db])
    assert result.exit_code == 0
    assert "| hero | imp | 0.993 |" in result.output
