"""Tests for LearningStore loadout-profile persistence (Task 1)."""

import tempfile

from artifactsmmo_cli.ai.learning.store import LearningStore
from sqlmodel import create_engine


def _break_engine(store: LearningStore) -> None:
    """Swap in a broken engine so every query raises OperationalError."""
    bad_dir = tempfile.mkdtemp()
    store._engine = create_engine(f"sqlite:///{bad_dir}")


def test_record_and_read_loadout_profile(tmp_path):
    store = LearningStore(db_path=str(tmp_path / "t.db"), character="Robby")
    store.record_loadout_profile("combat:chicken", {"weapon_slot": "wooden_stick", "ring1_slot": "copper_ring"})
    store.record_loadout_profile("gather:woodcutting", {"weapon_slot": "iron_axe"})
    profiles = store.loadout_profiles()
    assert profiles["combat:chicken"] == {"weapon_slot": "wooden_stick", "ring1_slot": "copper_ring"}
    assert profiles["gather:woodcutting"] == {"weapon_slot": "iron_axe"}
    store.close()


def test_record_loadout_profile_upsert_last_write_wins(tmp_path):
    store = LearningStore(db_path=str(tmp_path / "t.db"), character="Robby")
    store.record_loadout_profile("combat:chicken", {"weapon_slot": "wooden_stick"})
    store.record_loadout_profile("combat:chicken", {"weapon_slot": "iron_sword"})
    assert store.loadout_profiles()["combat:chicken"] == {"weapon_slot": "iron_sword"}
    store.close()


def test_loadout_profiles_is_per_character(tmp_path):
    a = LearningStore(db_path=str(tmp_path / "t.db"), character="alice")
    b = LearningStore(db_path=str(tmp_path / "t.db"), character="bob")
    a.record_loadout_profile("combat:slime", {"weapon_slot": "wooden_stick"})
    assert "combat:slime" in a.loadout_profiles()
    assert "combat:slime" not in b.loadout_profiles()
    a.close()
    b.close()


def test_record_loadout_profile_swallows_error(tmp_path, capsys):
    store = LearningStore(db_path=str(tmp_path / "t.db"), character="hero")
    _break_engine(store)
    store.record_loadout_profile("combat:slime", {"weapon_slot": "wooden_stick"})
    assert "record_loadout_profile" in capsys.readouterr().out


def test_loadout_profiles_returns_empty_on_error(tmp_path):
    store = LearningStore(db_path=str(tmp_path / "t.db"), character="hero")
    _break_engine(store)
    assert store.loadout_profiles() == {}
