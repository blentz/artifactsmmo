from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.task_feasibility import SkillRequirement, task_requirement
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "small_health_potion": ItemStats(code="small_health_potion", level=1,
            type_="utility", crafting_skill="alchemy", crafting_level=5),
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
            crafting_skill="weaponcrafting", crafting_level=1),
    }
    gd._monster_level = {"dragon": 40, "chicken": 1}
    return gd


def test_items_task_returns_skill_gap():
    state = make_state(task_code="small_health_potion", task_type="items",
                       task_total=29, skills={"alchemy": 1})
    assert task_requirement(state, _gd()) == SkillRequirement(
        skill="alchemy", required_level=5, current_level=1)


def test_items_task_feasible_returns_none():
    state = make_state(task_code="copper_dagger", task_type="items",
                       task_total=5, skills={"weaponcrafting": 6})
    assert task_requirement(state, _gd()) is None


def test_monster_task_too_hard_returns_requirement():
    state = make_state(task_code="dragon", task_type="monsters", task_total=1, level=3)
    req = task_requirement(state, _gd())
    assert req is not None and req.skill == "combat"


def test_monster_task_beatable_returns_none():
    state = make_state(task_code="chicken", task_type="monsters", task_total=1, level=3)
    assert task_requirement(state, _gd()) is None


def test_no_task_returns_none():
    assert task_requirement(make_state(task_code=None), _gd()) is None
