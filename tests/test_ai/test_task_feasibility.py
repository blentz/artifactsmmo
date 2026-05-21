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


def test_unknown_task_type_returns_none():
    # task types other than monsters/items have no skill requirement here.
    state = make_state(task_code="some_resource", task_type="resources", task_total=10)
    assert task_requirement(state, _gd()) is None


def test_cyclic_recipe_does_not_recurse_forever():
    # A recipe that (transitively) references itself must not loop; the cycle
    # guard returns without re-walking the seen item.
    gd = GameData()
    gd._item_stats = {
        "loop_item": ItemStats(code="loop_item", level=1, type_="resource",
            crafting_skill="alchemy", crafting_level=9),
    }
    gd._crafting_recipes = {"loop_item": {"loop_item": 1}}  # self-referential
    state = make_state(task_code="loop_item", task_type="items", task_total=1,
                       skills={"alchemy": 1})
    # Resolves (no infinite loop) and returns the item's own skill gap.
    assert task_requirement(state, gd) == SkillRequirement(
        skill="alchemy", required_level=9, current_level=1)


def test_items_task_gated_by_recursive_ingredient():
    # Target item itself is feasible (crafting_level 1), but an ingredient needs
    # a higher crafting skill the character lacks -> requirement comes from the
    # ingredient (recursive walk).
    gd = GameData()
    gd._item_stats = {
        "fancy_bar": ItemStats(code="fancy_bar", level=1, type_="resource",
            crafting_skill="weaponcrafting", crafting_level=1),
        "rare_ore": ItemStats(code="rare_ore", level=1, type_="resource",
            crafting_skill="mining", crafting_level=8),
    }
    gd._crafting_recipes = {"fancy_bar": {"rare_ore": 2}}
    state = make_state(task_code="fancy_bar", task_type="items", task_total=3,
                       skills={"weaponcrafting": 5, "mining": 1})
    assert task_requirement(state, gd) == SkillRequirement(
        skill="mining", required_level=8, current_level=1)
