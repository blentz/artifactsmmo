"""Phase-1 headline: with LevelSkill in the action set, the GOAP planner plans
`grind-skill -> craft` for an under-skill craft target — the capability that
retires the SKILL_PREREQUISITE workaround. Drives GOAPPlanner directly (not the
arbiter), so the is_plannable under-skill fast-fail — still present in P1 — does
not intercept; P2 removes that fast-fail so the live arbiter reaches this path."""

from artifactsmmo_cli.ai.actions.factory import build_actions
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.level_skill import LevelSkill
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
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
        "gear_ore": ItemStats(code="gear_ore", level=1, type_="resource",
                              subtype="mob"),
    }
    gd._crafting_recipes = {"widget": {"gear_ore": 2}, "trinket": {"gear_ore": 1}}
    gd._resource_drops = {"gear_rocks": "gear_ore"}
    gd._resource_skill = {"gear_rocks": ("mining", 1)}
    gd._resource_locations = {"gear_rocks": [(3, 3)]}
    gd._workshop_locations = {"gearcrafting": (2, 2)}
    gd._bank_location = (0, 0)
    gd._taskmaster_location = (1, 1)
    return gd


def _gd_gated_gather() -> GameData:
    """A closure whose only material is a resource gated behind a GATHER skill
    the character is under (deep_ore ← deep_rocks, mining 10). Mirrors iron_ore
    ← iron_rocks in the l12_taskgated_bag scenario: the sole ore source is
    skill-locked, so the only route is LevelSkill(mining->10) then Gather."""
    gd = GameData()
    gd._item_stats = {
        "deep_ore": ItemStats(code="deep_ore", level=10, type_="resource",
                              subtype="mining"),
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource",
                                subtype="mining"),
    }
    gd._crafting_recipes = {}
    # copper_rocks (mining 1) is the low grindable rung LevelSkill(mining) climbs
    # from; deep_rocks (mining 10) is the skill-locked target source.
    gd._resource_drops = {"deep_rocks": "deep_ore", "copper_rocks": "copper_ore"}
    gd._resource_skill = {"deep_rocks": ("mining", 10), "copper_rocks": ("mining", 1)}
    gd._resource_locations = {"deep_rocks": [(3, 3)], "copper_rocks": [(4, 4)]}
    gd._workshop_locations = {}
    gd._bank_location = (0, 0)
    gd._taskmaster_location = (1, 1)
    return gd


def test_open_source_displaces_locked_no_forced_grind() -> None:
    """When a drop has BOTH an open source and a skill-locked one, admit only the
    open source — never force a grind for a workable material (the fishing-40
    salmon vs fishing-30 bass narrowing hazard). No LevelSkill for that gate."""
    gd = _gd_gated_gather()
    # shallow_rocks (mining 1, OPEN) also drops deep_ore — a workable source now.
    gd._item_stats["deep_ore"] = ItemStats(code="deep_ore", level=1,
                                            type_="resource", subtype="mining")
    gd._resource_drops["shallow_rocks"] = "deep_ore"
    gd._resource_skill["shallow_rocks"] = ("mining", 1)
    gd._resource_locations["shallow_rocks"] = [(5, 5)]
    state = scenario_state(
        ScenarioCharacter(name="t", level=12, skills={"mining": 1}), gd)
    objective = CharacterObjective.from_game_data(gd)
    actions = build_actions(gd, state, objective, bank_accessible=True,
                            task_exchange_min_coins=0)
    goal = GatherMaterialsGoal(target_item="deep_ore", needed={"deep_ore": 1})

    admitted = goal.relevant_actions(actions, state, gd)
    assert any(isinstance(a, GatherAction) and a.resource_code == "shallow_rocks"
               for a in admitted), "open shallow_rocks must be admitted"
    assert not any(isinstance(a, GatherAction) and a.resource_code == "deep_rocks"
                   for a in admitted), "locked deep_rocks must NOT displace open source"
    assert not [a for a in admitted if isinstance(a, LevelSkill)], \
        "no grind when a workable open source exists"


def test_gather_gate_above_ceiling_stays_excluded() -> None:
    """A source gated ABOVE the server skill ceiling has no LevelSkill route, so
    it stays excluded (preserving _skill_open's permanently-closed exclusion)."""
    gd = _gd_gated_gather()
    gd._resource_skill["deep_rocks"] = ("mining", gd.max_skill_level + 5)
    state = scenario_state(
        ScenarioCharacter(name="t", level=12, skills={"mining": 1}), gd)
    objective = CharacterObjective.from_game_data(gd)
    actions = build_actions(gd, state, objective, bank_accessible=True,
                            task_exchange_min_coins=0)
    goal = GatherMaterialsGoal(target_item="deep_ore", needed={"deep_ore": 1})

    admitted = goal.relevant_actions(actions, state, gd)
    assert not any(isinstance(a, GatherAction) and a.resource_code == "deep_rocks"
                   for a in admitted), "above-ceiling gather has no route — excluded"


def _gd_gated_gather_equippable() -> GameData:
    """An EQUIPPABLE whose sole material is behind a gather-skill gate.

    deep_helmet (helmet, gearcrafting 1) needs deep_ore, whose only source is
    deep_rocks at mining 10. The character is at mining 1, so the single route
    is LevelSkill(mining->10) then Gather(deep_rocks) then Craft.
    """
    gd = GameData()
    gd._item_stats = {
        "deep_helmet": ItemStats(code="deep_helmet", level=1, type_="helmet",
                                 subtype="", crafting_skill="gearcrafting",
                                 crafting_level=1, hp_bonus=50),
        "deep_ore": ItemStats(code="deep_ore", level=10, type_="resource",
                              subtype="mining"),
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource",
                                subtype="mining"),
    }
    gd._crafting_recipes = {"deep_helmet": {"deep_ore": 2}}
    gd._resource_drops = {"deep_rocks": "deep_ore", "copper_rocks": "copper_ore"}
    gd._resource_skill = {"deep_rocks": ("mining", 10), "copper_rocks": ("mining", 1)}
    gd._resource_locations = {"deep_rocks": [(3, 3)], "copper_rocks": [(4, 4)]}
    gd._workshop_locations = {"gearcrafting": (2, 2)}
    gd._bank_location = (0, 0)
    gd._taskmaster_location = (1, 1)
    return gd


