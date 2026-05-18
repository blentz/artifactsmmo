"""Tests for persistent blocker memory + ReachUnlockLevelGoal."""

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.consumable import UseConsumableAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.reach_unlock_level import (
    PRIORITY_WHEN_BLOCKER_ACTIVE,
    ReachUnlockLevelGoal,
)
from artifactsmmo_cli.ai.learning.store import LearningStore
from tests.test_ai.fixtures import make_state


class TestBlockerPersistence:
    def test_set_and_get_roundtrip(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        store.set_blocker("bank", "sea_marauder", required_level=6)
        b = store.get_blocker("bank")
        store.close()
        assert b is not None
        assert b.unlock_monster == "sea_marauder"
        assert b.required_level == 6

    def test_unknown_blocker_returns_none(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        assert store.get_blocker("nonexistent") is None
        store.close()

    def test_upsert_updates_existing(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        store.set_blocker("bank", "low_monster", required_level=3)
        store.set_blocker("bank", "sea_marauder", required_level=6)
        b = store.get_blocker("bank")
        store.close()
        assert b is not None
        assert b.unlock_monster == "sea_marauder"
        assert b.required_level == 6

    def test_persistence_survives_reopen(self, tmp_path):
        db = str(tmp_path / "p.db")
        store1 = LearningStore(db_path=db, character="hero")
        store1.set_blocker("bank", "sea_marauder", required_level=6)
        store1.close()
        store2 = LearningStore(db_path=db, character="hero")
        b = store2.get_blocker("bank")
        store2.close()
        assert b is not None
        assert b.required_level == 6

    def test_blocker_is_per_character(self, tmp_path):
        db = str(tmp_path / "p.db")
        s1 = LearningStore(db_path=db, character="hero")
        s1.set_blocker("bank", "monsterA", required_level=5)
        s1.close()
        s2 = LearningStore(db_path=db, character="other_char")
        # blockers table uses blocker_code as primary key, so the second
        # character's get returns None unless they wrote their own entry.
        assert s2.get_blocker("bank") is None
        s2.close()


class TestReachUnlockLevelGoal:
    def test_zero_when_already_at_level(self):
        goal = ReachUnlockLevelGoal(target_level=6)
        assert goal.priority(make_state(level=6), GameData()) == 0.0
        assert goal.is_satisfied(make_state(level=6)) is True

    def test_zero_when_target_level_unknown(self):
        goal = ReachUnlockLevelGoal(target_level=0)
        assert goal.priority(make_state(level=2), GameData()) == 0.0

    def test_fires_high_when_under_level(self):
        goal = ReachUnlockLevelGoal(target_level=6)
        assert goal.priority(make_state(level=2), GameData()) == PRIORITY_WHEN_BLOCKER_ACTIVE
        assert goal.is_satisfied(make_state(level=2)) is False

    def test_relevant_actions_filters_beatable_monsters_only(self):
        gd = GameData()
        gd._monster_level = {"chicken": 1, "yellow_slime": 3, "sea_marauder": 7}
        goal = ReachUnlockLevelGoal(target_level=6)
        actions = [
            FightAction(monster_code="chicken"),       # level 1, char L2 can beat
            FightAction(monster_code="yellow_slime"),  # level 3, char L2 borderline (>= 2)
            FightAction(monster_code="sea_marauder"),  # level 7, char L2 cannot beat
            RestAction(),
            UseConsumableAction(_item_stats={}),
            GatherAction(resource_code="ash_tree"),    # excluded
        ]
        relevant = goal.relevant_actions(actions, make_state(level=2), gd)
        codes = [a.monster_code for a in relevant if isinstance(a, FightAction)]
        assert "chicken" in codes
        assert "yellow_slime" in codes
        assert "sea_marauder" not in codes
        assert any(isinstance(a, RestAction) for a in relevant)
        assert not any(isinstance(a, GatherAction) for a in relevant)

    def test_repr_includes_target(self):
        assert repr(ReachUnlockLevelGoal(target_level=6)) == "ReachUnlockLevel(6)"
