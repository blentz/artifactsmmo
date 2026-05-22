from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.grind_character_xp import GrindCharacterXPGoal
from artifactsmmo_cli.ai.goals.level_skill import LevelSkillGoal
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from artifactsmmo_cli.ai.strategy_driver import (
    FALLBACK_BAND,
    STRATEGY_BAND,
    MetaGoalAdapter,
    strategy_goal,
)
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachCharLevel, ReachSkillLevel
from tests.test_ai.fixtures import make_state


def _gd():
    gd = GameData()
    gd._item_stats = {
        "wooden_shield": ItemStats(code="wooden_shield", level=1, type_="shield",
                                   resistance={"earth": 5}, crafting_skill="gearcrafting", crafting_level=1),
        "ash_plank": ItemStats(code="ash_plank", level=1, type_="resource"),
    }
    gd._crafting_recipes = {"wooden_shield": {"ash_plank": 6}, "ash_plank": {"ash_wood": 1}}
    gd._resource_drops = {"ash_tree": "ash_wood"}
    gd._resource_skill = {"ash_tree": ("woodcutting", 1)}
    return gd


def test_adapter_delegates_and_fixes_priority():
    inner = GatherMaterialsGoal(target_item="ash_plank", needed={"ash_plank": 6})
    adapter = MetaGoalAdapter(inner, STRATEGY_BAND)
    s = make_state(inventory={"ash_plank": 6})
    assert adapter.is_satisfied(s) == inner.is_satisfied(s)
    assert adapter.desired_state(s, _gd()) == inner.desired_state(s, _gd())
    assert adapter.priority(make_state(), _gd()) == STRATEGY_BAND
    assert adapter.max_depth == inner.max_depth
    assert "GatherMaterials" in repr(adapter)
    gd = _gd()
    s2 = make_state()
    assert adapter.value(s2, gd) == inner.value(s2, gd)                       # delegates heuristic
    assert adapter.relevant_actions([], s2, gd) == inner.relevant_actions([], s2, gd)


def test_material_obtain_maps_to_gather_materials():
    g = strategy_goal(ObtainItem("ash_plank", 6), make_state(), _gd(), STRATEGY_BAND, "chicken")
    assert isinstance(g, MetaGoalAdapter)
    assert isinstance(g._inner, GatherMaterialsGoal)
    assert g._inner._needed == {"ash_plank": 6}


def test_gear_obtain_maps_to_upgrade_equipment_with_committed_target():
    g = strategy_goal(ObtainItem("wooden_shield", 1), make_state(), _gd(), STRATEGY_BAND, "chicken")
    assert isinstance(g._inner, UpgradeEquipmentGoal)
    assert g._inner._committed_target == ("wooden_shield", "shield_slot")


def test_skill_maps_to_level_skill():
    g = strategy_goal(ReachSkillLevel("mining", 50), make_state(), _gd(), STRATEGY_BAND, "chicken")
    assert isinstance(g._inner, LevelSkillGoal)
    assert g._inner._skill_name == "mining" and g._inner._target_level == 50


def test_char_level_maps_to_grind_with_initial_xp_and_monster():
    g = strategy_goal(ReachCharLevel(50), make_state(xp=120), _gd(), STRATEGY_BAND, "chicken")
    assert isinstance(g._inner, GrindCharacterXPGoal)
    assert g._inner._target_monster == "chicken" and g._inner._initial_xp == 120


def test_char_level_none_when_no_monster():
    assert strategy_goal(ReachCharLevel(50), make_state(), _gd(), STRATEGY_BAND, None) is None


def test_strategy_goal_none_for_none_step():
    assert strategy_goal(None, make_state(), _gd(), STRATEGY_BAND, "chicken") is None


def test_fallback_band_below_strategy_band():
    assert FALLBACK_BAND < STRATEGY_BAND
