"""Gather re-arm activation: GatherMaterialsGoal must admit the per-skill
OptimizeLoadout action so the planner can actually equip the better tool.

Regression (trace 2026-07-05 16:22): WithdrawTools ferried copper_pickaxe into
the bag, but every subsequent cycle gathered with copper_dagger — the goal's
relevant_actions filtered OptimizeLoadout out, so GATHER_LOADOUT_PENALTY had no
action that could remove it and the re-arm was inert.
"""

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.optimize_loadout import OptimizeLoadoutAction
from artifactsmmo_cli.ai.craft_plan_gen import _with_rearm, generate_next_craft_action
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


def _gd_combat() -> GameData:
    """`_gd()` plus a `rat` monster so pick_loadout(Combat(rat)) can score the
    combat weapons (copper_dagger beats the mining copper_pickaxe)."""
    gd = _gd()
    gd._monster_attack = {"rat": {"earth": 3}}
    gd._monster_resistance = {"rat": {}}
    gd._monster_level = {"rat": 1}
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


def test_with_rearm_fronts_combat_swap_for_suboptimal_fight() -> None:
    """`_with_rearm` fronts OptimizeLoadout(monster) when a generated plan opens
    with a Fight whose equipped combat loadout is suboptimal — a mining
    copper_pickaxe is worn while a better combat weapon (copper_dagger) rides in
    the bag. Without the prepend the fast path runs plan[0]=Fight bare-handed,
    losing a winnable fight (the Task 3 loadout gate rejects it at execution).
    Kills the 'fight never front the re-arm' mutation."""
    gd = _gd_combat()
    state = make_state(inventory={"copper_dagger": 1},
                       equipment={"weapon_slot": "copper_pickaxe"},
                       skills={"mining": 12})
    fight = FightAction(monster_code="rat", locations=frozenset({(1, 1)}))
    result = _with_rearm([fight], state, gd)
    assert isinstance(result[0], OptimizeLoadoutAction), [type(a).__name__ for a in result]
    assert result[0].target_monster_code == "rat"
    assert result[1] is fight


def test_with_rearm_leaves_optimal_fight_bare() -> None:
    """When the equipped combat loadout is already optimal for the monster,
    `_with_rearm` does NOT front a redundant swap — OptimizeLoadout.is_applicable
    is False on an empty swap plan (self-guarding). Kills the 'fight front the
    re-arm unconditionally' mutation (which would prepend a no-op swap)."""
    gd = _gd_combat()
    state = make_state(equipment={"weapon_slot": "copper_dagger"},
                       skills={"mining": 12})
    fight = FightAction(monster_code="rat", locations=frozenset({(1, 1)}))
    result = _with_rearm([fight], state, gd)
    assert result == [fight]
