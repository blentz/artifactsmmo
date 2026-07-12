"""Phase-1 headline: with LevelSkill in the action set, the GOAP planner plans
`grind-skill -> craft` for an under-skill craft target — the capability that
retires the SKILL_PREREQUISITE workaround. Drives GOAPPlanner directly (not the
arbiter), so the is_plannable under-skill fast-fail — still present in P1 — does
not intercept; P2 removes that fast-fail so the live arbiter reaches this path."""

from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.factory import build_actions
from artifactsmmo_cli.ai.actions.level_skill import LevelSkill
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.planner import GOAPPlanner
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


def test_planner_sequences_level_skill_before_gated_craft() -> None:
    gd = _gd()
    state = scenario_state(
        ScenarioCharacter(name="t", level=5,
                          skills={"gearcrafting": 1, "mining": 1}), gd)
    objective = CharacterObjective.from_game_data(gd)
    actions = build_actions(gd, state, objective, bank_accessible=True,
                            task_exchange_min_coins=0)
    actions.append(LevelSkill(skill="gearcrafting", target_level=5))
    goal = GatherMaterialsGoal(target_item="widget", needed={"widget": 1})

    plan = GOAPPlanner().plan(state, goal, actions, gd, budget_seconds=10.0)

    reprs = [repr(a) for a in plan]
    craft_idx = next(i for i, a in enumerate(plan)
                     if isinstance(a, CraftAction) and a.code == "widget")
    level_idx = next(i for i, a in enumerate(plan)
                     if isinstance(a, LevelSkill))
    assert level_idx < craft_idx, f"LevelSkill must precede Craft(widget): {reprs}"
