"""Integration tests: TaskCancelGoal.value and _build_goals both driven by task_decision."""

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.task_cancel import TaskCancelGoal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.player import GamePlayer
from tests.test_ai.fixtures import make_state


def _make_gd() -> GameData:
    gd = GameData()
    gd._monster_locations = {"chicken": [(1, 0)]}
    gd._monster_level = {"chicken": 1}
    gd._resource_locations = {}
    gd._workshop_locations = {}
    gd._bank_location = (4, 0)
    gd._taskmaster_location = (1, 2)
    gd._item_stats = {
        "small_health_potion": ItemStats(
            code="small_health_potion", level=1, type_="utility",
            crafting_skill="alchemy", crafting_level=5,
        )
    }
    gd._crafting_recipes = {"small_health_potion": {"sunflower": 3}}
    gd._resource_skill = {}
    return gd


def _make_player(gd: GameData, state, history: LearningStore) -> GamePlayer:
    player = GamePlayer(character="hero", history=history)
    player.game_data = gd
    player.state = state
    return player


class TestTaskDecisionIntegration:
    def test_pivot_case_cancel_fires_and_no_level_skill_goal(self, tmp_path):
        """PIVOT (alchemy 1, no observations): cancel value > 0 and no LevelSkill goal."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        gd = _make_gd()
        state = make_state(
            task_code="small_health_potion",
            task_type="items",
            task_total=29,
            task_progress=0,
            skills={"alchemy": 1},
        )
        try:
            assert TaskCancelGoal().value(state, gd, store) > 0
            player = _make_player(gd, state, store)
            goals = player._build_goals()
            assert not any(repr(g) == "LevelSkill(alchemy->5)" for g in goals)
        finally:
            store.close()

    def test_pursue_case_cancel_zero_and_level_skill_goal_present(self, tmp_path):
        """PURSUE (alchemy 4 with gap-of-1 observed, high reward): cancel == 0 and LevelSkill goal present."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        # Seed observations: alchemy levels 1-4 with max_xp=10 each (cheap grind)
        for lvl in (1, 2, 3, 4):
            store.record_skill_max_xp("alchemy", lvl, 10)
        # Seed high reward value so skill_up_vpc >= DEFAULT_COIN_VALUE_GOLD
        store.record_task_reward_value(100000.0)
        gd = _make_gd()
        # State: alchemy 4, task needs crafting_level 5 — gap of 1, fully observed
        state = make_state(
            task_code="small_health_potion",
            task_type="items",
            task_total=1,
            task_progress=0,
            skills={"alchemy": 4},
        )
        try:
            assert TaskCancelGoal().value(state, gd, store) == 0
            player = _make_player(gd, state, store)
            goals = player._build_goals()
            assert any(repr(g) == "LevelSkill(alchemy->5)" for g in goals)
        finally:
            store.close()
