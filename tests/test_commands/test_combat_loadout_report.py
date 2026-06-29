"""Tests for the combat-loadout-report CLI command."""

import pytest
import typer
from typer.testing import CliRunner

from artifactsmmo_cli.ai.learning.models import CombatLoadoutOutcome
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.commands.combat_loadout_report import (
    _default_db_path,
    combat_loadout_report_command,
)


def test_default_db_path_points_at_learning_db() -> None:
    p = _default_db_path()
    assert p.endswith("artifactsmmo/learning.db")


def test_bad_parameter_on_missing_db(tmp_path: pytest.TempdirFactory) -> None:
    missing = tmp_path / "nope.db"
    with pytest.raises(typer.BadParameter):
        combat_loadout_report_command(db=str(missing), out=None)
    assert not missing.exists()


def _seed_outcomes(db: str) -> None:
    """Seed CombatLoadoutOutcome rows into the db for both hero and ally."""
    store_hero = LearningStore(db_path=db, character="hero")
    store_hero.record_combat_outcome(
        task_key="combat:chicken",
        loadout={"weapon_slot": "stick"},
        predicted_win=True,
        actual_win=True,
    )
    store_hero.record_combat_outcome(
        task_key="combat:chicken",
        loadout={"weapon_slot": "stick"},
        predicted_win=True,
        actual_win=False,  # over-estimate
    )
    store_ally = LearningStore(db_path=db, character="ally")
    store_ally.record_combat_outcome(
        task_key="combat:wolf",
        loadout={"weapon_slot": "sword"},
        predicted_win=False,
        actual_win=True,  # under-estimate
    )


def test_command_prints_report(tmp_path: pytest.TempdirFactory, capsys: pytest.CaptureFixture) -> None:
    db = str(tmp_path / "l.db")
    _seed_outcomes(db)
    combat_loadout_report_command(db=db, out=None)
    captured = capsys.readouterr()
    assert "combat:chicken" in captured.out
    assert "combat:wolf" in captured.out
    assert "# Combat-loadout calibration" in captured.out


def test_command_writes_to_out_file(tmp_path: pytest.TempdirFactory) -> None:
    db = str(tmp_path / "l.db")
    _seed_outcomes(db)
    out = tmp_path / "report.md"
    combat_loadout_report_command(db=db, out=str(out))
    text = out.read_text()
    assert "# Combat-loadout calibration" in text
    assert "combat:chicken" in text
    assert "combat:wolf" in text


def test_command_cross_character_all_rows(
    tmp_path: pytest.TempdirFactory, capsys: pytest.CaptureFixture
) -> None:
    """Report spans ALL characters; no per-character filter."""
    db = str(tmp_path / "l.db")
    _seed_outcomes(db)
    combat_loadout_report_command(db=db, out=None)
    captured = capsys.readouterr()
    # Both hero's chicken and ally's wolf should appear
    assert "combat:chicken" in captured.out
    assert "combat:wolf" in captured.out


def test_command_empty_db_gives_empty_state_message(
    tmp_path: pytest.TempdirFactory, capsys: pytest.CaptureFixture
) -> None:
    """Empty db produces an empty-state message, not a crash."""
    db = str(tmp_path / "l.db")
    # Create the db by initializing a store (so the file exists but is empty)
    LearningStore(db_path=db, character="hero")
    combat_loadout_report_command(db=db, out=None)
    captured = capsys.readouterr()
    assert "No fight outcome data recorded yet" in captured.out
