"""Gather re-arm activation: GatherMaterialsGoal must admit the per-skill
OptimizeLoadout action so the planner can actually equip the better tool.

Regression (trace 2026-07-05 16:22): WithdrawTools ferried copper_pickaxe into
the bag, but every subsequent cycle gathered with copper_dagger — the goal's
relevant_actions filtered OptimizeLoadout out, so GATHER_LOADOUT_PENALTY had no
action that could remove it and the re-arm was inert.
"""

from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.optimize_loadout import OptimizeLoadoutAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.planner import GOAPPlanner
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "copper_pickaxe": ItemStats(code="copper_pickaxe", level=1, type_="weapon",
                                    attack={"earth": 5}, skill_effects={"mining": -10}),
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                   attack={"air": 6}, critical_strike=35),
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
    }
    gd._resource_drops = {"copper_rocks": "copper_ore"}
    gd._resource_skill = {"copper_rocks": ("mining", 1)}
    gd._resource_locations = {"copper_rocks": [(2, 0)]}
    return gd


def _actions() -> list:
    return [
        GatherAction(resource_code="copper_rocks", locations=frozenset({(2, 0)})),
        CraftAction(code="copper_bar", quantity=1, workshop_location=(5, 0)),
        OptimizeLoadoutAction(target_skill="mining", game_data=None),
        OptimizeLoadoutAction(target_skill="fishing", game_data=None),
    ]


def test_relevant_actions_include_needed_skill_optimizer() -> None:
    gd = _gd()
    goal = GatherMaterialsGoal(target_item="copper_ore", needed={"copper_ore": 6})
    state = make_state(inventory={"copper_pickaxe": 1},
                       equipment={"weapon_slot": "copper_dagger"})
    result = goal.relevant_actions(_actions(), state, gd)
    optimizers = [a for a in result if isinstance(a, OptimizeLoadoutAction)]
    assert [a.target_skill for a in optimizers] == ["mining"]  # fishing filtered


def test_planner_equips_tool_before_gathering() -> None:
    """With the pickaxe IN THE BAG and the dagger equipped, the cheapest plan
    re-arms once (removing GATHER_LOADOUT_PENALTY from every gather) and then
    gathers — the exact sequence the live bot never produced pre-fix."""
    gd = _gd()
    goal = GatherMaterialsGoal(target_item="copper_ore", needed={"copper_ore": 3})
    state = make_state(x=2, y=0, inventory={"copper_pickaxe": 1},
                       equipment={"weapon_slot": "copper_dagger"},
                       skills={"mining": 12})
    actions = goal.relevant_actions(_actions(), state, gd)
    plan = GOAPPlanner().plan(state, goal, actions, gd)
    kinds = [type(a).__name__ for a in plan]
    assert kinds[0] == "OptimizeLoadoutAction", kinds
    assert "GatherAction" in kinds


def test_generator_plan_prepends_rearm_when_tool_in_bag() -> None:
    """The recipe-directed craft-plan generator (nodes=0 path) bypasses A* and
    its cost model entirely, so GATHER_LOADOUT_PENALTY never spoke there —
    live 2026-07-05: every generated helmet plan opened with Gather while the
    ferried pickaxe rode in the bag. The generator must front the re-arm."""
    from artifactsmmo_cli.ai.craft_plan_gen import generate_next_craft_action
    gd = _gd()
    gd._item_stats["copper_bar"] = ItemStats(
        code="copper_bar", level=1, type_="resource",
        crafting_skill="mining", crafting_level=1)
    gd._crafting_recipes = {"copper_bar": {"copper_ore": 10}}
    gd._workshop_locations = {"mining": (5, 0)}
    goal = GatherMaterialsGoal(target_item="copper_bar", needed={"copper_bar": 1})
    state = make_state(x=2, y=0, inventory={"copper_pickaxe": 1},
                       equipment={"weapon_slot": "copper_dagger"},
                       skills={"mining": 12})
    plan = generate_next_craft_action(goal, state, gd, _actions())
    assert plan is not None
    assert isinstance(plan[0], OptimizeLoadoutAction), [type(a).__name__ for a in plan]
    assert plan[0].target_skill == "mining"


def test_generator_plan_unchanged_when_loadout_already_optimal() -> None:
    from artifactsmmo_cli.ai.craft_plan_gen import generate_next_craft_action
    gd = _gd()
    gd._item_stats["copper_bar"] = ItemStats(
        code="copper_bar", level=1, type_="resource",
        crafting_skill="mining", crafting_level=1)
    gd._crafting_recipes = {"copper_bar": {"copper_ore": 10}}
    gd._workshop_locations = {"mining": (5, 0)}
    goal = GatherMaterialsGoal(target_item="copper_bar", needed={"copper_bar": 1})
    state = make_state(x=2, y=0, equipment={"weapon_slot": "copper_pickaxe"},
                       skills={"mining": 12})
    plan = generate_next_craft_action(goal, state, gd, _actions())
    assert plan is not None
    assert isinstance(plan[0], GatherAction), [type(a).__name__ for a in plan]
