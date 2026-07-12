"""build_actions emits one LevelSkill per distinct in-skill craft level so A*
and the directed generator can satisfy any gated CraftAction's skill gate."""

from artifactsmmo_cli.ai.actions.factory import build_actions
from artifactsmmo_cli.ai.actions.level_skill import LevelSkill
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.scenario import ScenarioCharacter, scenario_state
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "widget": ItemStats(code="widget", level=5, type_="resource",
                            subtype="craft", crafting_skill="gearcrafting",
                            crafting_level=5),
        "trinket": ItemStats(code="trinket", level=1, type_="resource",
                             subtype="craft", crafting_skill="gearcrafting",
                             crafting_level=1),
        "bar": ItemStats(code="bar", level=5, type_="resource",
                         subtype="craft", crafting_skill="mining",
                         crafting_level=5),
        "gear_ore": ItemStats(code="gear_ore", level=1, type_="resource",
                              subtype="mob"),
    }
    gd._crafting_recipes = {"widget": {"gear_ore": 2}, "trinket": {"gear_ore": 1},
                            "bar": {"gear_ore": 1}}
    gd._workshop_locations = {"gearcrafting": (2, 2), "mining": (3, 3)}
    gd._bank_location = (1, 1)
    gd._taskmaster_location = (0, 0)
    return gd


def test_build_actions_emits_one_level_skill_per_distinct_level() -> None:
    gd = _gd()
    state = scenario_state(ScenarioCharacter(name="t", level=5), gd)
    objective = CharacterObjective.from_game_data(gd)
    actions = build_actions(gd, state, objective, bank_accessible=True,
                            task_exchange_min_coins=0)
    level_skills = {(a.skill, a.target_level) for a in actions
                    if isinstance(a, LevelSkill)}
    assert level_skills == {("gearcrafting", 5), ("gearcrafting", 1),
                            ("mining", 5)}
