"""Tests for LearningStore combat loadout outcome append table (Task 1)."""

import tempfile

from sqlmodel import create_engine

from artifactsmmo_cli.ai.learning.store import LearningStore


def _break_engine(store: LearningStore) -> None:
    """Swap in a broken engine so every query raises OperationalError."""
    bad_dir = tempfile.mkdtemp()
    store._engine = create_engine(f"sqlite:///{bad_dir}")


def test_record_and_read_combat_outcomes(tmp_path):
    store = LearningStore(db_path=tmp_path / "t.db", character="Robby")
    store.record_combat_outcome("combat:chicken", {"weapon_slot": "wooden_stick"}, True, True)
    store.record_combat_outcome("combat:chicken", {"weapon_slot": "iron_sword"}, True, False)
    rows = [r for r in store.combat_loadout_outcomes() if r.task_key == "combat:chicken"]
    assert len(rows) == 2  # APPEND (history), not last-write
    assert rows[0].loadout == {"weapon_slot": "wooden_stick"}
    assert rows[0].predicted_win is True and rows[0].actual_win is True
    assert rows[1].actual_win is False
    store.close()


def test_combat_outcomes_per_character_isolated(tmp_path):
    db = tmp_path / "t.db"
    a = LearningStore(db_path=db, character="A")
    a.record_combat_outcome("combat:chicken", {"weapon_slot": "stick"}, True, True)
    a.close()
    b = LearningStore(db_path=db, character="B")
    assert b.combat_loadout_outcomes() == []
    b.close()


def test_record_combat_outcome_swallows_error(tmp_path, capsys):
    store = LearningStore(db_path=str(tmp_path / "t.db"), character="hero")
    _break_engine(store)
    store.record_combat_outcome("combat:slime", {"weapon_slot": "stick"}, True, False)
    assert "record_combat_outcome" in capsys.readouterr().out


def test_combat_loadout_outcomes_returns_empty_on_error(tmp_path):
    store = LearningStore(db_path=str(tmp_path / "t.db"), character="hero")
    _break_engine(store)
    assert store.combat_loadout_outcomes() == []


def test_combat_outcome_row_fields(tmp_path):
    store = LearningStore(db_path=tmp_path / "t.db", character="Robby")
    store.record_combat_outcome(
        "combat:slime", {"weapon_slot": "iron_sword", "ring1_slot": "copper_ring"}, False, True
    )
    rows = store.combat_loadout_outcomes()
    assert len(rows) == 1
    row = rows[0]
    assert row.character == "Robby"
    assert row.task_key == "combat:slime"
    assert row.loadout == {"weapon_slot": "iron_sword", "ring1_slot": "copper_ring"}
    assert row.predicted_win is False
    assert row.actual_win is True
    store.close()
