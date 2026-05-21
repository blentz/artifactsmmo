from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.task_decision import PIVOT, PURSUE, task_decision
from tests.test_ai.fixtures import make_state


def _gd():
    gd = GameData()
    gd._item_stats = {"small_health_potion": ItemStats(code="small_health_potion",
        level=1, type_="utility", crafting_skill="alchemy", crafting_level=5)}
    gd._crafting_recipes = {"small_health_potion": {"sunflower": 3}}
    return gd


def test_feasible_task_pursues(tmp_path):
    store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
    state = make_state(task_code="small_health_potion", task_type="items",
                       task_total=29, skills={"alchemy": 9})  # >= 5, feasible
    assert task_decision(state, _gd(), store) == PURSUE
    store.close()


def test_huge_skill_gap_low_confidence_pivots(tmp_path):
    store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
    state = make_state(task_code="small_health_potion", task_type="items",
                       task_total=29, skills={"alchemy": 1})  # no observations
    assert task_decision(state, _gd(), store) == PIVOT
    store.close()


def test_confident_cheap_high_reward_pursues(tmp_path):
    store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
    for lvl in (1, 2, 3, 4):
        store.record_skill_max_xp("alchemy", lvl, 10)  # cheap + observed
    store.record_task_reward_value(100000.0)           # high reward
    state = make_state(task_code="small_health_potion", task_type="items",
                       task_total=1, skills={"alchemy": 4})  # gap of 1, observed
    assert task_decision(state, _gd(), store) == PURSUE
    store.close()
