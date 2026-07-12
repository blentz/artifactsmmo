"""next_grind_goal picks the grind rung for a LevelSkill and builds the
skill_grind GatherMaterials goal the player executes one leg of per cycle —
mirroring strategy_driver.py:866-871."""

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.level_skill_expand import next_grind_goal
from artifactsmmo_cli.ai.scenario import ScenarioCharacter, scenario_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "trinket": ItemStats(code="trinket", level=1, type_="resource",
                             subtype="craft", crafting_skill="gearcrafting",
                             crafting_level=1),
        "gear_ore": ItemStats(code="gear_ore", level=1, type_="resource",
                              subtype="mob"),
    }
    gd._crafting_recipes = {"trinket": {"gear_ore": 1}}
    gd._resource_drops = {"gear_rocks": "gear_ore"}
    gd._resource_skill = {"gear_rocks": ("mining", 1)}
    gd._resource_locations = {"gear_rocks": [(3, 3)]}
    gd._workshop_locations = {"gearcrafting": (2, 2)}
    return gd


def test_next_grind_goal_targets_the_rung_skill_grind() -> None:
    gd = _gd()
    state = scenario_state(
        ScenarioCharacter(name="t", level=5, skills={"gearcrafting": 1}), gd)
    goal = next_grind_goal("gearcrafting", state, gd)
    assert isinstance(goal, GatherMaterialsGoal)
    assert goal.skill_grind is True
    # targets the selected rung, held+1 (mirrors strategy_driver:866-871)
    assert goal.needed == {"trinket": 1}


def test_next_grind_goal_none_when_no_rung() -> None:
    gd = GameData()
    gd._item_stats = {
        "lonely": ItemStats(code="lonely", level=10, type_="resource",
                            subtype="craft", crafting_skill="gearcrafting",
                            crafting_level=10),
    }
    gd._crafting_recipes = {"lonely": {"gear_ore": 2}}
    state = scenario_state(
        ScenarioCharacter(name="t", level=5, skills={"gearcrafting": 5}), gd)
    assert next_grind_goal("gearcrafting", state, gd) is None


def test_next_grind_goal_gather_arm_when_no_craft_rung() -> None:
    """A gather skill (alchemy) with no craftable rung at the current level
    grinds by GATHERING an in-skill resource: next_grind_goal targets the
    gatherable drop, not a craft (LevelSkill epic P4 gather arm)."""
    gd = GameData()
    gd._item_stats = {
        "small_potion": ItemStats(code="small_potion", level=5, type_="consumable",
                                  subtype="potion", crafting_skill="alchemy",
                                  crafting_level=5),
        "sunflower": ItemStats(code="sunflower", level=1, type_="resource",
                               subtype="alchemy"),
    }
    gd._crafting_recipes = {"small_potion": {"sunflower": 3}}
    gd._resource_drops = {"sunflower_field": "sunflower"}
    gd._resource_skill = {"sunflower_field": ("alchemy", 1)}
    gd._resource_locations = {"sunflower_field": [(4, 4)]}
    state = scenario_state(
        ScenarioCharacter(name="t", level=5, skills={"alchemy": 1}), gd)
    goal = next_grind_goal("alchemy", state, gd)
    assert isinstance(goal, GatherMaterialsGoal)
    assert goal.skill_grind is True
    assert goal.needed == {"sunflower": 1}
