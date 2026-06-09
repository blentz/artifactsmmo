"""Tests for gating_skills: which craft skills block a strategic want."""

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.skill_gates import (
    GateSource,
    SkillGate,
    gating_skills,
)
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "iron_helm": ItemStats(code="iron_helm", level=5, type_="helmet",
                               crafting_skill="gearcrafting", crafting_level=5),
        "iron_dagger": ItemStats(code="iron_dagger", level=10, type_="weapon",
                                 crafting_skill="weaponcrafting", crafting_level=10),
        "cooked_trout": ItemStats(code="cooked_trout", level=8, type_="consumable",
                                  crafting_skill="cooking", crafting_level=8),
        "ruby_ring": ItemStats(code="ruby_ring", level=3, type_="ring",
                               crafting_skill="jewelrycrafting", crafting_level=1),
        "ruby_gem": ItemStats(code="ruby_gem", level=3, type_="resource",
                              crafting_skill="jewelrycrafting", crafting_level=12),
        "iron_pick": ItemStats(code="iron_pick", level=10, type_="tool",
                               crafting_skill="weaponcrafting", crafting_level=10),
        "plank_helm": ItemStats(code="plank_helm", level=5, type_="helmet",
                                crafting_skill="gearcrafting", crafting_level=5),
        "coal": ItemStats(code="coal", level=20, type_="resource"),
        "trout": ItemStats(code="trout", level=8, type_="resource"),
    }
    gd._crafting_recipes = {
        "iron_helm": {"iron_bar": 5},
        "iron_dagger": {"iron_bar": 6},
        "cooked_trout": {"trout": 1},
        "ruby_ring": {"ruby_gem": 2},
        "ruby_gem": {"coal": 3},
        "iron_pick": {"iron_bar": 8},
        "plank_helm": {"plain_plank": 3},
        "plain_plank": {"raw_log": 2},
    }
    gd._resource_drops = {"trout_spot": "trout", "coal_rocks": "coal"}
    gd._resource_skill = {"trout_spot": ("fishing", 8), "coal_rocks": ("mining", 20)}
    return gd


def _obj(gd: GameData, gear=None, tools=None) -> CharacterObjective:
    return CharacterObjective(
        target_char_level=50,
        target_skill_levels={},
        target_gear=gear or {},
        _game_data=gd,
        target_tools=tools or {},
    )


def test_gear_gate_surfaces_with_gear_source():
    gd = _gd()
    obj = _obj(gd, gear={"helmet_slot": "iron_helm"})
    state = make_state(skills={"gearcrafting": 1})
    gates = gating_skills(state, gd, obj, combat_weapon=None)
    assert gates["gearcrafting"] == SkillGate(required_level=5, source=GateSource.GEAR)


def test_owned_gear_is_not_gating():
    gd = _gd()
    obj = _obj(gd, gear={"helmet_slot": "iron_helm"})
    state = make_state(skills={"gearcrafting": 1}, inventory={"iron_helm": 1})
    gates = gating_skills(state, gd, obj, combat_weapon=None)
    assert "gearcrafting" not in gates


def test_skill_already_high_enough_is_not_gating():
    gd = _gd()
    obj = _obj(gd, gear={"helmet_slot": "iron_helm"})
    state = make_state(skills={"gearcrafting": 5})
    gates = gating_skills(state, gd, obj, combat_weapon=None)
    assert "gearcrafting" not in gates


def test_active_items_task_gate_has_task_item_source():
    gd = _gd()
    obj = _obj(gd)
    state = make_state(skills={"cooking": 1}, task_type="items",
                       task_code="cooked_trout", task_total=10, task_progress=0)
    gates = gating_skills(state, gd, obj, combat_weapon=None)
    assert gates["cooking"] == SkillGate(required_level=8, source=GateSource.TASK_ITEM)


def test_combat_weapon_gate_has_combat_source():
    gd = _gd()
    obj = _obj(gd)
    state = make_state(skills={"weaponcrafting": 1})
    gates = gating_skills(state, gd, obj, combat_weapon="iron_dagger")
    assert gates["weaponcrafting"] == SkillGate(required_level=10, source=GateSource.COMBAT)


def test_closure_intermediate_craft_gate_surfaces():
    gd = _gd()
    obj = _obj(gd, gear={"ring1_slot": "ruby_ring"})
    state = make_state(skills={"jewelrycrafting": 1})
    gates = gating_skills(state, gd, obj, combat_weapon=None)
    assert gates["jewelrycrafting"] == SkillGate(required_level=12, source=GateSource.GEAR)


def test_gather_gate_is_excluded():
    gd = _gd()
    obj = _obj(gd)
    state = make_state(skills={"cooking": 8, "fishing": 1, "mining": 1},
                       task_type="items", task_code="cooked_trout",
                       task_total=10, task_progress=0)
    gates = gating_skills(state, gd, obj, combat_weapon=None)
    assert "fishing" not in gates
    assert "mining" not in gates


def test_tool_gate_has_tool_source():
    gd = _gd()
    obj = _obj(gd, tools={"weapon_slot": "iron_pick"})
    state = make_state(skills={"weaponcrafting": 1})
    gates = gating_skills(state, gd, obj, combat_weapon=None)
    assert gates["weaponcrafting"] == SkillGate(required_level=10, source=GateSource.TOOL)


def test_closure_node_without_item_stats_is_skipped():
    gd = _gd()
    obj = _obj(gd, gear={"helmet_slot": "plank_helm"})
    state = make_state(skills={"gearcrafting": 1})
    gates = gating_skills(state, gd, obj, combat_weapon=None)
    # plain_plank is in the recipe closure but has no item_stats (None) -> skipped.
    assert gates["gearcrafting"] == SkillGate(required_level=5, source=GateSource.GEAR)


def test_same_skill_two_wants_keeps_max_level_and_strongest_source():
    gd = _gd()
    gd._item_stats["wc_task"] = ItemStats(
        code="wc_task", level=6, type_="consumable",
        crafting_skill="weaponcrafting", crafting_level=6)
    gd._crafting_recipes["wc_task"] = {"iron_bar": 1}
    obj = _obj(gd)
    state = make_state(skills={"weaponcrafting": 1}, task_type="items",
                       task_code="wc_task", task_total=5, task_progress=0)
    gates = gating_skills(state, gd, obj, combat_weapon="iron_dagger")
    assert gates["weaponcrafting"] == SkillGate(required_level=10,
                                                source=GateSource.TASK_ITEM)


def test_gear_then_task_item_merges_to_stronger_task_item_source():
    # Gear want recorded FIRST (weaker), task-item want recorded LATER (stronger).
    # Exercises _record merge and _stronger_source's `else b` arm.
    gd = _gd()
    gd._item_stats["gc_gear"] = ItemStats(
        code="gc_gear", level=4, type_="helmet",
        crafting_skill="gearcrafting", crafting_level=4)
    gd._item_stats["gc_task"] = ItemStats(
        code="gc_task", level=7, type_="consumable",
        crafting_skill="gearcrafting", crafting_level=7)
    gd._crafting_recipes["gc_gear"] = {"iron_bar": 1}
    gd._crafting_recipes["gc_task"] = {"iron_bar": 1}
    obj = _obj(gd, gear={"helmet_slot": "gc_gear"})
    state = make_state(skills={"gearcrafting": 1}, task_type="items",
                       task_code="gc_task", task_total=5, task_progress=0)
    gates = gating_skills(state, gd, obj, combat_weapon=None)
    assert gates["gearcrafting"] == SkillGate(required_level=7,
                                              source=GateSource.TASK_ITEM)
