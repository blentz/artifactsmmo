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
    store.record_combat_outcome("combat:chicken", {"weapon_slot": "wooden_stick"}, True, True, 7)
    store.record_combat_outcome("combat:chicken", {"weapon_slot": "iron_sword"}, True, False, 7)
    rows = [r for r in store.combat_loadout_outcomes() if r.task_key == "combat:chicken"]
    assert len(rows) == 2  # APPEND (history), not last-write
    assert rows[0].loadout == {"weapon_slot": "wooden_stick"}
    assert rows[0].predicted_win is True and rows[0].actual_win is True
    assert rows[1].actual_win is False
    store.close()


def test_combat_outcomes_per_character_isolated(tmp_path):
    db = tmp_path / "t.db"
    a = LearningStore(db_path=db, character="A")
    a.record_combat_outcome("combat:chicken", {"weapon_slot": "stick"}, True, True, 7)
    a.close()
    b = LearningStore(db_path=db, character="B")
    assert b.combat_loadout_outcomes() == []
    b.close()


def test_record_combat_outcome_swallows_error(tmp_path, capsys):
    store = LearningStore(db_path=str(tmp_path / "t.db"), character="hero")
    _break_engine(store)
    store.record_combat_outcome("combat:slime", {"weapon_slot": "stick"}, True, False, 7)
    assert "record_combat_outcome" in capsys.readouterr().out


def test_combat_loadout_outcomes_returns_empty_on_error(tmp_path):
    store = LearningStore(db_path=str(tmp_path / "t.db"), character="hero")
    _break_engine(store)
    assert store.combat_loadout_outcomes() == []


def test_combat_outcome_row_fields(tmp_path):
    store = LearningStore(db_path=tmp_path / "t.db", character="Robby")
    store.record_combat_outcome(
        "combat:slime", {"weapon_slot": "iron_sword", "ring1_slot": "copper_ring"}, False, True, 7
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


def test_the_combat_record_is_scoped_to_level_and_loadout(tmp_path):
    """The learned-loss veto's evidence (2026-10-05): fights at exactly this
    level in exactly this loadout, whatever the slot order."""
    store = LearningStore(db_path=tmp_path / "t.db", character="Robby")
    sword = {"weapon_slot": "iron_sword", "ring1_slot": "copper_ring"}
    store.record_combat_outcome("combat:pig", sword, True, False, 19)
    store.record_combat_outcome("combat:pig", sword, True, True, 30)
    store.record_combat_outcome("combat:pig", sword, True, False, 30)
    store.record_combat_outcome("combat:pig", {"weapon_slot": "stick"}, True, False, 30)
    store.record_combat_outcome("combat:cow", sword, True, False, 30)
    reordered = {"ring1_slot": "copper_ring", "weapon_slot": "iron_sword"}
    assert store.combat_record("combat:pig", 30, reordered) == (2, 1)
    assert store.combat_record("combat:pig", 19, sword) == (1, 0)
    assert store.combat_record("combat:pig", 31, sword) == (0, 0)
    store.close()


def test_the_combat_record_reads_as_empty_on_error(tmp_path):
    store = LearningStore(db_path=str(tmp_path / "t.db"), character="hero")
    _break_engine(store)
    assert store.combat_record("combat:pig", 30, {}) == (0, 0)


def test_a_table_from_before_the_level_column_gains_it(tmp_path):
    """Migration (2026-10-05): an existing outcome table gains `level`; its old
    rows keep NULL and count toward no level's record."""
    path = str(tmp_path / "old.db")
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE combat_loadout_outcome (id INTEGER NOT NULL PRIMARY KEY, "
            "character VARCHAR NOT NULL, task_key VARCHAR NOT NULL, loadout VARCHAR NOT NULL, "
            "predicted_win BOOLEAN NOT NULL, actual_win BOOLEAN NOT NULL)")
        conn.exec_driver_sql(
            "INSERT INTO combat_loadout_outcome (character, task_key, loadout, predicted_win, "
            "actual_win) VALUES ('C3P0', 'combat:pig', '{}', 1, 0)")
    engine.dispose()
    store = LearningStore(db_path=path, character="C3P0")
    assert store.combat_record("combat:pig", 19, {}) == (0, 0)
    store.record_combat_outcome("combat:pig", {}, True, True, 30)
    assert store.combat_record("combat:pig", 30, {}) == (1, 1)
    store.close()


def test_the_lost_keys_are_level_scoped_in_first_loss_order(tmp_path):
    """The fights a price must carry a loss rate for (USER 2026-10-08, "Price
    the loss risk"): every key lost at exactly this level, first loss first."""
    store = LearningStore(db_path=tmp_path / "t.db", character="R2D2")
    other = LearningStore(db_path=tmp_path / "t.db", character="HAL")
    store.record_combat_outcome("combat:rat", {}, True, True, 30)
    store.record_combat_outcome("combat:king_slime", {}, True, False, 30)
    store.record_combat_outcome("combat:rat", {}, True, False, 30)
    store.record_combat_outcome("combat:king_slime", {}, True, False, 30)
    store.record_combat_outcome("combat:pig", {}, True, False, 29)
    other.record_combat_outcome("combat:ogre", {}, True, False, 30)
    assert store.lost_task_keys(30) == ["combat:king_slime", "combat:rat"]
    assert store.lost_task_keys(29) == ["combat:pig"]
    assert store.lost_task_keys(31) == []
    store.close()
    other.close()


def test_the_lost_keys_read_as_empty_on_error(tmp_path):
    store = LearningStore(db_path=str(tmp_path / "t.db"), character="hero")
    _break_engine(store)
    assert store.lost_task_keys(30) == []
