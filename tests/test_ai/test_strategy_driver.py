from dataclasses import dataclass

import pytest

import artifactsmmo_cli.ai.strategy_driver as sd
from artifactsmmo_cli.ai.actions.accept_task import AcceptTaskAction
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.actions.task_cancel import TaskCancelAction
from artifactsmmo_cli.ai.actions.wait import WaitAction
from artifactsmmo_cli.ai.actions.task_trade import TaskTradeAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from artifactsmmo_cli.ai.goals.accept_task_goal import AcceptTaskGoal
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.goals.claim_pending import ClaimPendingGoal
from artifactsmmo_cli.ai.goals.complete_task_goal import CompleteTaskGoal
from artifactsmmo_cli.ai.goals.deposit_inventory import DepositInventoryGoal
from artifactsmmo_cli.ai.goals.discard_overstock import DiscardOverstockGoal
from artifactsmmo_cli.ai.goals.expand_bank import ExpandBankGoal
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.grind_character_xp import GrindCharacterXPGoal
from artifactsmmo_cli.ai.goals.level_skill import LevelSkillGoal
from artifactsmmo_cli.ai.goals.low_yield_cancel import LowYieldCancelGoal
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from artifactsmmo_cli.ai.goals.pursue_task import PursueTaskGoal  # noqa: F401 (used in repr checks)
from artifactsmmo_cli.ai.goals.reach_unlock_level import ReachUnlockLevelGoal
from artifactsmmo_cli.ai.goals.restore_hp import RestoreHPGoal
from artifactsmmo_cli.ai.goals.sell_inventory import SellInventoryGoal
from artifactsmmo_cli.ai.goals.task_cancel import TaskCancelGoal
from artifactsmmo_cli.ai.goals.task_exchange import TaskExchangeGoal
from artifactsmmo_cli.ai.goals.unlock_bank import UnlockBankGoal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.arbiter_select import Candidate, _precedes, select_pure
from artifactsmmo_cli.ai.doomed_memo import DoomedMemo
from artifactsmmo_cli.ai.strategy_driver import (
    LEVEL_LOOKAHEAD,
    StrategyArbiter,
    _equippable_goal,
    _gather_goal_for_unreachable_equippable,
    _task_recipe_inputs,
    map_guard,
    map_means,
    objective_step_goal,
)
from artifactsmmo_cli.ai.task_batch import task_batch_size
from artifactsmmo_cli.ai.tiers.guards import GuardKind, SelectionContext
import artifactsmmo_cli.ai.tiers.means as means_module
from artifactsmmo_cli.ai.tiers.means import MeansKind
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachCharLevel, ReachSkillLevel
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
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


def _ctx(**kw):
    base = dict(bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
                initial_xp=0, task_exchange_min_coins=1, combat_monster=None,
                gear_review_active=False)
    base.update(kw)
    return SelectionContext(**base)


# ---------------------------------------------------------------------------
# map_guard unit tests
# ---------------------------------------------------------------------------

def test_map_guard_hp_critical():
    assert isinstance(map_guard(GuardKind.HP_CRITICAL, GameData(), _ctx()), RestoreHPGoal)


def test_map_guard_discard_critical():
    g = map_guard(GuardKind.DISCARD_CRITICAL, GameData(), _ctx())
    assert isinstance(g, DiscardOverstockGoal)


def test_map_guard_discard_high():
    g = map_guard(GuardKind.DISCARD_HIGH, GameData(), _ctx())
    assert isinstance(g, DiscardOverstockGoal)


def test_map_guard_bank_unlock():
    ctx = _ctx(bank_accessible=False, bank_unlock_monster="chicken", initial_xp=100)
    g = map_guard(GuardKind.BANK_UNLOCK, GameData(), ctx)
    assert isinstance(g, UnlockBankGoal)


def test_map_guard_reach_unlock_level():
    ctx = _ctx(bank_required_level=5)
    g = map_guard(GuardKind.REACH_UNLOCK_LEVEL, GameData(), ctx)
    assert isinstance(g, ReachUnlockLevelGoal)


def test_map_guard_deposit_full():
    g = map_guard(GuardKind.DEPOSIT_FULL, GameData(), _ctx())
    assert isinstance(g, DepositInventoryGoal)


def test_map_guard_unknown_raises():
    with pytest.raises(ValueError):
        map_guard("bogus", GameData(), _ctx())  # type: ignore[arg-type]


def test_map_guard_gear_review_gathers_when_materials_missing():
    gd = GameData()
    gd._item_stats = {"copper_boots": ItemStats(code="copper_boots", level=1, type_="boots",
                                                crafting_skill="gearcrafting", crafting_level=1)}
    gd._crafting_recipes = {"copper_boots": {"copper_bar": 8}, "copper_bar": {"copper_ore": 10}}
    state = make_state(level=4, inventory={}, bank_items={})
    goal = map_guard(GuardKind.GEAR_REVIEW, gd, _ctx(gear_review_active=True), state)
    assert isinstance(goal, GatherMaterialsGoal)


def _deep_chain_gd():
    """steel_boots <- 6 steel_bar <- 8 iron_bar <- 10 iron_ore = 480 raw from
    scratch — the depth-unreachable deep equippable chain (Piece D)."""
    gd = GameData()
    gd._item_stats = {
        "steel_boots": ItemStats(code="steel_boots", level=2, type_="boots",
                                 crafting_skill="gearcrafting", crafting_level=1),
        "steel_bar": ItemStats(code="steel_bar", level=1, type_="resource",
                               crafting_skill="gearcrafting", crafting_level=1),
        "iron_bar": ItemStats(code="iron_bar", level=1, type_="resource",
                              crafting_skill="gearcrafting", crafting_level=1),
        "iron_ore": ItemStats(code="iron_ore", level=1, type_="resource"),
    }
    gd._crafting_recipes = {"steel_boots": {"steel_bar": 6},
                            "steel_bar": {"iron_bar": 8},
                            "iron_bar": {"iron_ore": 10}}
    gd._resource_drops = {"iron_rocks": "iron_ore"}
    gd._resource_locations = {"iron_rocks": [(2, 0)]}
    return gd


def test_gear_review_deep_chain_routes_to_flat_leaf_not_explosive_recipe():
    """Piece D: from-scratch deep equippable (steel_boots = 480 raw) is
    depth-UNREACHABLE. The GEAR_REVIEW guard must NOT build the explosive
    GatherMaterials(steel_boots, {steel_bar: 6}) (whose plan gathers 480 units
    through the multi-level recipe — 655k nodes / 90s timeout offline). It routes
    to the FLAT deepest actionable step (iron_ore), a linear, budget-feasible
    gather. Pins the macro/micro bound so a regression to the deep goal fails."""
    gd = _deep_chain_gd()
    state = make_state(level=2, inventory={}, bank_items={})
    goal = map_guard(GuardKind.GEAR_REVIEW, gd, _ctx(gear_review_active=True), state)
    assert isinstance(goal, GatherMaterialsGoal)
    # The target is the raw leaf, NOT the equippable root nor its direct recipe.
    assert goal._needed == {"iron_ore": 10}
    assert goal._target_item == "iron_ore"


def test_equippable_goal_deep_chain_routes_to_flat_leaf():
    """Same Piece-D bound on the objective-step _equippable_goal path: a
    depth-unreachable deep equippable routes to the deepest actionable step
    (never the explosive root recipe).

    No bank stock -> the deepest actionable step is the raw leaf iron_ore."""
    gd = _deep_chain_gd()
    state = make_state(level=2, inventory={}, bank_items={})
    goal = _equippable_goal("steel_boots", "boots_slot", state, gd)
    assert isinstance(goal, GatherMaterialsGoal)
    assert goal._needed == {"iron_ore": 10}


def test_equippable_goal_deep_chain_advances_step_as_leaf_accumulates():
    """The macro/micro progression: with enough raw iron_ore banked to make one
    iron_bar, the deepest ACTIONABLE step advances to iron_bar (its direct
    prereq, iron_ore, is now satisfiable). The routed sub-goal is at most ONE
    recipe level deep — bounded, never the 3-level explosive chain. Also exercises
    the bank-credit loop in the helper."""
    gd = _deep_chain_gd()
    state = make_state(level=2, inventory={}, bank_items={"iron_ore": 10})
    goal = _equippable_goal("steel_boots", "boots_slot", state, gd)
    assert isinstance(goal, GatherMaterialsGoal)
    # Step advanced one level up the chain; still NOT the steel_boots root recipe.
    assert goal._needed == {"iron_bar": 8}
    assert goal._target_item == "iron_bar"


def test_deep_chain_flat_leaf_plans_within_budget():
    """The routed flat-leaf goal plans LINEARLY (no recipe sub-tree to interleave)
    — the whole point of the bound. Offline: the deep recipe goal hit 655k nodes /
    90s timeout; the flat leaf is ~50 nodes. Bound the live planner node count."""
    from artifactsmmo_cli.ai.actions.crafting import CraftAction
    from artifactsmmo_cli.ai.actions.deposit_all import DepositAllAction
    from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
    gd = _deep_chain_gd()
    gd._workshop_locations = {"gearcrafting": (0, 0)}
    state = make_state(level=2, inventory={}, bank_items={})
    goal = _equippable_goal("steel_boots", "boots_slot", state, gd)
    actions = [
        DepositAllAction(bank_location=(0, 0), accessible=True, game_data=gd),
        GatherAction(resource_code="iron_rocks", locations=frozenset({(2, 0)})),
    ]
    for code in gd._crafting_recipes:
        st = gd.item_stats(code)
        ws = gd.workshop_location(st.crafting_skill) if st.crafting_skill else None
        actions.append(CraftAction(code=code, quantity=1, workshop_location=ws))
        actions.append(WithdrawItemAction(code=code, quantity=1, bank_location=(0, 0),
                                          accessible=True))
    actions.append(WithdrawItemAction(code="iron_ore", quantity=1, bank_location=(0, 0),
                                       accessible=True))
    planner = GOAPPlanner()
    plan = planner.plan(state, goal, actions, gd, None, budget_seconds=30.0)
    assert plan  # a real plan is found (goal not abandoned)
    assert not planner.last_stats.timed_out
    # Linear, tiny node count — locks the bound. The deep recipe goal needed
    # 655k nodes; this stays under a generous 5k ceiling.
    assert planner.last_stats.nodes_explored < 5000, planner.last_stats.nodes_explored


def test_gather_helper_falls_back_to_direct_recipe_without_deeper_step():
    """When the actionable_step IS the root itself (a 1-level recipe whose only
    input is a raw leaf already at the root's depth), there is no deeper step to
    route to, so the helper returns the root's direct recipe (the total-function
    fallback branch)."""
    gd = GameData()
    gd._item_stats = {
        "plank": ItemStats(code="plank", level=1, type_="resource",
                           crafting_skill="woodcrafting", crafting_level=1),
        "wood": ItemStats(code="wood", level=1, type_="resource"),
    }
    # plank has an EMPTY recipe, so it has no deeper prerequisite; actionable_step
    # resolves to plank itself (step.code == root), the helper takes the
    # total-function fallback and returns the (empty) direct recipe.
    gd._crafting_recipes = {"plank": {}}  # empty recipe -> no deeper step
    gd._resource_drops = {"tree": "plank"}
    gd._resource_locations = {"tree": [(1, 0)]}
    state = make_state(inventory={}, bank_items={})
    goal = _gather_goal_for_unreachable_equippable("plank", state, gd, 15)
    assert isinstance(goal, GatherMaterialsGoal)
    # Empty recipe -> needed is the (empty) direct recipe fallback.
    assert goal._target_item == "plank"


def test_map_guard_gear_review_upgrades_when_materials_in_hand():
    gd = GameData()
    gd._item_stats = {"copper_boots": ItemStats(code="copper_boots", level=1, type_="boots",
                                                crafting_skill="gearcrafting", crafting_level=1)}
    gd._crafting_recipes = {"copper_boots": {"copper_bar": 8}, "copper_bar": {"copper_ore": 10}}
    state = make_state(level=4, inventory={"copper_bar": 8})
    goal = map_guard(GuardKind.GEAR_REVIEW, gd, _ctx(gear_review_active=True), state)
    assert isinstance(goal, UpgradeEquipmentGoal)


def test_map_guard_gear_review_no_state_raises():
    """map_guard(GEAR_REVIEW) without a state must raise ValueError (line 137)."""
    with pytest.raises(ValueError, match="GEAR_REVIEW guard requires a state"):
        map_guard(GuardKind.GEAR_REVIEW, GameData(), _ctx())


def test_map_guard_gear_review_no_upgrade_found_returns_upgrade_goal():
    """When find_upgrade_target returns None (empty game data, no upgrades),
    map_guard falls back to a plain UpgradeEquipmentGoal (line 143)."""
    state = make_state(level=1, inventory={}, equipment={})
    goal = map_guard(GuardKind.GEAR_REVIEW, GameData(), _ctx(gear_review_active=True), state)
    assert isinstance(goal, UpgradeEquipmentGoal)


def test_map_guard_rest_for_combat_is_restore_hp():
    """REST_FOR_COMBAT maps to a RestoreHPGoal (line 106-107)."""
    assert isinstance(map_guard(GuardKind.REST_FOR_COMBAT, GameData(), _ctx()),
                      RestoreHPGoal)


def test_map_guard_craft_relief_no_state_raises():
    """CRAFT_RELIEF needs a state to pick its target; without one it raises
    (line 121-122)."""
    with pytest.raises(ValueError, match="CRAFT_RELIEF guard requires a state"):
        map_guard(GuardKind.CRAFT_RELIEF, GameData(), _ctx())


def test_map_guard_craft_relief_no_candidate_raises():
    """CRAFT_RELIEF mapped with a state that has no craftable relief candidate
    raises rather than returning a bogus goal (line 127-128)."""
    # Empty inventory + no recipes -> craft_relief_candidates returns [].
    state = make_state(inventory={})
    with pytest.raises(ValueError, match="no relief candidate"):
        map_guard(GuardKind.CRAFT_RELIEF, GameData(), _ctx(), state)


def test_task_recipe_inputs_empty_for_no_task():
    """No task code -> empty input set (line 71-72)."""
    assert _task_recipe_inputs(None, GameData()) == frozenset()


def test_task_recipe_inputs_walks_chain_and_dedupes_shared_material():
    """Two recipe branches sharing a material visit it once (the `mat in chain`
    guard, line 79-80); the full transitive input set is returned."""
    gd = GameData()
    # dagger <- bar(+handle); bar <- ore; handle <- ore  (ore shared).
    gd._crafting_recipes = {
        "dagger": {"bar": 1, "handle": 1},
        "bar": {"ore": 2},
        "handle": {"ore": 1},
    }
    inputs = _task_recipe_inputs("dagger", gd)
    assert inputs == frozenset({"bar", "handle", "ore"})


# ---------------------------------------------------------------------------
# map_means unit tests
# ---------------------------------------------------------------------------

def test_map_means_claim_pending():
    assert isinstance(map_means(MeansKind.CLAIM_PENDING, GameData(), _ctx(), make_state()), ClaimPendingGoal)


def test_map_means_complete_task():
    assert isinstance(map_means(MeansKind.COMPLETE_TASK, GameData(), _ctx(), make_state()), CompleteTaskGoal)


def test_map_means_sell_pressured():
    assert isinstance(map_means(MeansKind.SELL_PRESSURED, GameData(), _ctx(), make_state()), SellInventoryGoal)


def test_map_means_sell_idle():
    assert isinstance(map_means(MeansKind.SELL_IDLE, GameData(), _ctx(), make_state()), SellInventoryGoal)


def test_map_means_low_yield_cancel():
    assert isinstance(map_means(MeansKind.LOW_YIELD_CANCEL, GameData(), _ctx(), make_state()), LowYieldCancelGoal)


def test_map_means_task_cancel():
    assert isinstance(map_means(MeansKind.TASK_CANCEL, GameData(), _ctx(), make_state()), TaskCancelGoal)


def test_map_means_accept_task():
    assert isinstance(map_means(MeansKind.ACCEPT_TASK, GameData(), _ctx(), make_state()), AcceptTaskGoal)


def test_map_means_task_exchange():
    g = map_means(MeansKind.TASK_EXCHANGE, GameData(), _ctx(task_exchange_min_coins=3), make_state())
    assert isinstance(g, TaskExchangeGoal)


def test_map_means_bank_expand():
    assert isinstance(map_means(MeansKind.BANK_EXPAND, GameData(), _ctx(), make_state()), ExpandBankGoal)


def test_map_means_unknown_raises():
    with pytest.raises(ValueError):
        map_means("bogus", GameData(), _ctx(), make_state())  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# objective_step_goal unit tests
# ---------------------------------------------------------------------------

def test_objective_step_obtain_gear():
    gd = _gd()
    step = ObtainItem("wooden_shield", 1)
    g = objective_step_goal(step, make_state(), gd, _ctx())
    assert isinstance(g, UpgradeEquipmentGoal)
    assert g._committed_target == ("wooden_shield", "shield_slot")


def test_objective_step_obtain_material():
    gd = _gd()
    step = ObtainItem("ash_plank", 6)
    g = objective_step_goal(step, make_state(), gd, _ctx())
    assert isinstance(g, GatherMaterialsGoal)
    assert g._needed == {"ash_plank": 6}


def test_objective_step_intermediate_maps_to_equippable_root():
    """An intermediate recipe-input step (ash_plank, no slots) whose chain ROOT
    is an equippable (wooden_shield) plans UpgradeEquipmentGoal against the
    ROOT so the whole craft+equip chain runs under one commit (lines 220-224)."""
    gd = _gd()
    step = ObtainItem("ash_plank", 6)
    root = ObtainItem("wooden_shield", 1)
    g = objective_step_goal(step, make_state(), gd, _ctx(), root=root)
    assert isinstance(g, UpgradeEquipmentGoal)
    assert g._committed_target == ("wooden_shield", "shield_slot")


def test_objective_step_intermediate_unreachable_root_routes_to_deepest_step():
    """From-scratch DEEP equippable chain: the intermediate step maps to the
    equippable ROOT, but the root's UpgradeEquipment is depth-UNREACHABLE
    (min_gathers 480 >> max_depth 15). The old fallback built
    GatherMaterials(root, root's direct recipe) -> the planner exploded
    (1M+ nodes / 90s timeout / plan_len 0, then fall-through). The fix routes to
    the DEEPEST actionable step (the raw base material) as a FLAT gather that
    plans within budget. Piece-C feasibility gate."""
    gd = GameData()
    gd._item_stats = {
        "steel_boots": ItemStats(code="steel_boots", level=5, type_="boots",
                                 crafting_skill="gearcrafting", crafting_level=1),
        "steel_bar": ItemStats(code="steel_bar", level=1, type_="resource",
                               crafting_skill="weaponcrafting", crafting_level=1),
        "iron_bar": ItemStats(code="iron_bar", level=1, type_="resource",
                              crafting_skill="weaponcrafting", crafting_level=1),
        "iron_ore": ItemStats(code="iron_ore", level=1, type_="resource"),
    }
    gd._crafting_recipes = {"steel_boots": {"steel_bar": 6},
                            "steel_bar": {"iron_bar": 8},
                            "iron_bar": {"iron_ore": 10}}
    gd._resource_drops = {"iron_rocks": "iron_ore"}
    state = make_state(level=5, inventory={}, bank_items={})
    step = ObtainItem("iron_ore", 480)   # deepest actionable step
    root = ObtainItem("steel_boots", 1)
    g = objective_step_goal(step, state, gd, _ctx(), root=root)
    assert isinstance(g, GatherMaterialsGoal)
    # Targets the FLAT raw step, NOT the deep root recipe {steel_bar: 6}.
    assert g._needed == {"iron_ore": 480}


def test_objective_step_unreachable_root_credits_bank_then_routes_to_step():
    """The router credits inventory + BANK before deciding. Bank holds some
    intermediate but not enough to make the root depth-reachable, so it still
    routes to the deepest step (covers the bank-credit loop)."""
    gd = GameData()
    gd._item_stats = {
        "steel_boots": ItemStats(code="steel_boots", level=5, type_="boots",
                                 crafting_skill="gearcrafting", crafting_level=1),
        "steel_bar": ItemStats(code="steel_bar", level=1, type_="resource",
                               crafting_skill="weaponcrafting", crafting_level=1),
        "iron_bar": ItemStats(code="iron_bar", level=1, type_="resource",
                              crafting_skill="weaponcrafting", crafting_level=1),
        "iron_ore": ItemStats(code="iron_ore", level=1, type_="resource"),
    }
    gd._crafting_recipes = {"steel_boots": {"steel_bar": 6},
                            "steel_bar": {"iron_bar": 8},
                            "iron_bar": {"iron_ore": 10}}
    gd._resource_drops = {"iron_rocks": "iron_ore"}
    # Bank has 2 steel_bar (cuts the need to 4) but 4*8*10 = 320 ore >> 15.
    state = make_state(level=5, inventory={}, bank_items={"steel_bar": 2})
    step = ObtainItem("iron_ore", 320)
    root = ObtainItem("steel_boots", 1)
    g = objective_step_goal(step, state, gd, _ctx(), root=root)
    assert isinstance(g, GatherMaterialsGoal)
    assert g._needed == {"iron_ore": 320}


def test_objective_step_intermediate_reachable_root_keeps_upgrade():
    """When the root chain IS depth-reachable (materials in hand), the
    intermediate-step still maps to UpgradeEquipment(root) for the one-commit
    craft+equip — the ash_plank/wooden_shield design is preserved."""
    gd = _gd()  # wooden_shield <- ash_plank x6 <- ash_wood; shallow & in hand
    state = make_state(level=5, inventory={"ash_plank": 6})
    step = ObtainItem("ash_plank", 6)
    root = ObtainItem("wooden_shield", 1)
    g = objective_step_goal(step, state, gd, _ctx(), root=root)
    assert isinstance(g, UpgradeEquipmentGoal)
    assert g._committed_target == ("wooden_shield", "shield_slot")


def test_objective_step_reach_skill_level():
    step = ReachSkillLevel("mining", 10)
    # make_state() has mining level 3; target should be bounded to 3+LEVEL_LOOKAHEAD=6
    state = make_state(skills={"mining": 3}, skill_xp={"mining": 42})
    g = objective_step_goal(step, state, _gd(), _ctx())
    assert isinstance(g, LevelSkillGoal)
    assert g._skill_name == "mining"
    assert g._target_level == 6, f"expected target_level==6 (current+LEVEL_LOOKAHEAD), got {g._target_level}"
    assert g._initial_skill_xp == 42, f"expected initial_skill_xp==42, got {g._initial_skill_xp}"


def test_objective_step_reach_skill_level_bounds_to_current_plus_lookahead():
    """objective_step_goal must bound ReachSkillLevel target to current+LEVEL_LOOKAHEAD."""
    step = ReachSkillLevel("alchemy", 50)
    state = make_state(skills={"alchemy": 1}, skill_xp={"alchemy": 99})
    g = objective_step_goal(step, state, _gd(), _ctx())
    assert isinstance(g, LevelSkillGoal)
    assert g._target_level == 4, f"expected 4 (1+3), got {g._target_level}"
    assert g._initial_skill_xp == 99


def test_objective_step_reach_char_level_with_monster():
    step = ReachCharLevel(10)
    g = objective_step_goal(step, make_state(xp=50), _gd(), _ctx(combat_monster="chicken"))
    assert isinstance(g, GrindCharacterXPGoal)
    assert g._target_monster == "chicken" and g._initial_xp == 50


def test_objective_step_reach_char_level_no_monster():
    step = ReachCharLevel(10)
    g = objective_step_goal(step, make_state(), _gd(), _ctx(combat_monster=None))
    assert g is None


def test_objective_step_none_step():
    g = objective_step_goal(None, make_state(), _gd(), _ctx())
    assert g is None


# ---------------------------------------------------------------------------
# Helper stub for StrategyDecision (only chosen_step is used by StrategyArbiter)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _FakeDecision:
    chosen_step: ObtainItem | ReachCharLevel | ReachSkillLevel | None


def _make_planner_gd() -> GameData:
    """Minimal GameData that lets the planner resolve Accept/Fight/Rest actions."""
    gd = GameData()
    gd._monster_locations = {"chicken": [(1, 0)]}
    gd._monster_level = {"chicken": 1}
    gd._resource_locations = {}
    gd._workshop_locations = {}
    gd._bank_location = (4, 0)
    gd._item_stats = {}
    gd._crafting_recipes = {}
    gd._resource_skill = {}
    gd._resource_drops = {}
    fill_monster_stat_defaults(gd)
    return gd


# ---------------------------------------------------------------------------
# StrategyArbiter integration tests
# ---------------------------------------------------------------------------

def test_select_guard_preempts_means():
    """HP-critical guard fires: even if AcceptTask means is queued, RestoreHP wins."""
    planner = GOAPPlanner()
    gd = _make_planner_gd()
    # state: no task (AcceptTask fires), but HP is critical
    state = make_state(hp=10, max_hp=150, task_code=None, task_total=0)
    actions = [
        RestAction(),
        AcceptTaskAction(taskmaster_location=(2, 1)),
    ]
    ctx = _ctx(combat_monster="chicken")
    arbiter = StrategyArbiter(planner, history=None)
    decision = _FakeDecision(chosen_step=None)
    goal, plan, goals_tried = arbiter.select(decision, state, gd, actions, ctx)
    assert isinstance(goal, RestoreHPGoal), f"expected RestoreHPGoal, got {goal!r}"
    assert len(plan) >= 1


@dataclass(frozen=True)
class _FallbackDecision:
    """Decision stub carrying the fallback-step chain the arbiter reads via
    getattr (chosen_step + fallback_steps/roots)."""
    chosen_step: ObtainItem | ReachCharLevel | ReachSkillLevel | None
    fallback_steps: list
    fallback_roots: list


def test_select_promotes_upgrade_equipment_from_fallback_first_pass():
    """When the top chosen_step yields no goal, the fallback FIRST pass prefers
    a fallback step that maps to UpgradeEquipmentGoal (the one-step equip),
    promoting it over later fallbacks (lines 393-400)."""
    planner = GOAPPlanner()
    gd = _gd()  # has wooden_shield (equippable) + ash_plank recipe
    # wooden_shield owned in inventory -> UpgradeEquipmentGoal is a one-action
    # equip the planner can resolve.
    state = make_state(
        hp=100, max_hp=100, inventory={"wooden_shield": 1},
        equipment={"shield_slot": None}, inventory_max=20,
    )
    # No chosen_step; a fallback ObtainItem(wooden_shield) -> UpgradeEquipmentGoal.
    decision = _FallbackDecision(
        chosen_step=None,
        fallback_steps=[ObtainItem("wooden_shield", 1)],
        fallback_roots=[None],
    )
    goal, plan, goals_tried = arbiter_select_with(planner, decision, state, gd)
    tried_reprs = {str(e["goal"]) for e in goals_tried}
    assert any("UpgradeEquipment" in r for r in tried_reprs), tried_reprs


def arbiter_select_with(planner, decision, state, gd):
    arbiter = StrategyArbiter(planner, history=None)
    arbiter.set_cycle(0)
    return arbiter.select(decision, state, gd, [], _ctx())


def test_select_returns_objective_step_when_calm():
    """No guards, no collect-reward means; chosen_step→GrindCharacterXP plans."""
    planner = GOAPPlanner()
    gd = GameData()
    gd._monster_locations = {"chicken": [(1, 0)]}
    gd._monster_level = {"chicken": 1}
    gd._resource_locations = {}
    gd._workshop_locations = {}
    gd._bank_location = (4, 0)
    gd._item_stats = {}
    gd._crafting_recipes = {}
    gd._resource_skill = {}
    gd._resource_drops = {}
    fill_monster_stat_defaults(gd)
    # Level 1 char with HP full, a non-items task active so AcceptTask
    # does NOT fire (`task_code=None` would suppress the step in favor of
    # AcceptTask per the post-4e771a2 rule). The original test used
    # task_code=None and relied on positional priority; that's no longer
    # the contract — see test_select_suppresses_step_when_no_task below.
    state = make_state(level=1, hp=150, max_hp=150, xp=0, max_xp=500,
                       task_code="chicken", task_type="monsters",
                       task_progress=0, task_total=10)
    actions = [FightAction(monster_code="chicken", locations=frozenset([(1, 0)]))]
    ctx = _ctx(combat_monster="chicken")
    arbiter = StrategyArbiter(planner, history=None)
    decision = _FakeDecision(chosen_step=ReachCharLevel(5))
    goal, plan, goals_tried = arbiter.select(decision, state, gd, actions, ctx)
    assert isinstance(goal, GrindCharacterXPGoal), f"expected GrindCharacterXPGoal, got {goal!r}"
    assert len(plan) >= 1


def test_select_suppresses_step_when_no_task():
    """Trace 2026-05-19 (cycles 318-342): with task_code=None, a positional
    walk had GatherMaterials(copper_ring) step preempting AcceptTask
    every other cycle, locking the bot into a Gather→Discard loop (gather
    1 copper_ore → DISCARD_HIGH deletes 1 → repeat for 12+ cycles).
    Suppressing the meta-objective step when no task is active and
    AcceptTask is available lets AcceptTask win, breaking the loop.

    Setup mirrors the production trace: step_goal is a plannable
    GatherMaterials (copper_ring chain — Gather(copper_rocks) is
    available) AND AcceptTaskAction is available. Pre-fix the step won
    positionally and the bot grabbed a copper_ore; post-fix AcceptTask
    wins because the step is suppressed in the no-task state, breaking
    the discard cycle."""
    planner = GOAPPlanner()
    gd = _make_planner_gd()
    gd._crafting_recipes["copper_ring"] = {"copper_ore": 6}
    gd._resource_locations = {"copper_rocks": [(1, 0)]}
    gd._resource_drops["copper_rocks"] = "copper_ore"
    gd._resource_skill["copper_rocks"] = ("mining", 1)
    state = make_state(level=3, hp=130, max_hp=130, xp=0, max_xp=350,
                       task_code=None, task_type=None, task_progress=0, task_total=0,
                       skills={"mining": 3})
    actions = [
        GatherAction(resource_code="copper_rocks",
                     locations=frozenset([(1, 0)])),
        AcceptTaskAction(taskmaster_location=(2, 1)),
    ]
    ctx = _ctx(combat_monster="chicken")
    arbiter = StrategyArbiter(planner, history=None)
    decision = _FakeDecision(chosen_step=ObtainItem("copper_ring"))
    goal, plan, tried = arbiter.select(decision, state, gd, actions, ctx)
    # AcceptTask must win: the loop-breaker contract.
    assert isinstance(goal, AcceptTaskGoal), (
        f"expected AcceptTaskGoal to win over meta-step when no task active, "
        f"got {goal!r}; goals_tried={tried}"
    )
    # The construction-time AcceptTask-null-step suppression was removed (it is
    # replaced by the worth gate, which is inactive here since no objective is
    # passed). The GatherMaterials step may now be tried, but it cannot plan in
    # the no-task state (plan_len=0), so AcceptTask still wins the walk — the
    # loop-breaker contract holds via plannability rather than suppression.
    gather_attempts = [t for t in tried if "GatherMaterials" in str(t["goal"])]
    assert all(t["plan_len"] == 0 for t in gather_attempts), (
        f"meta-step must fail to plan in the no-task state; goals_tried={tried}"
    )
    assert len(plan) >= 1


def test_select_falls_through_unplannable_to_next():
    """No guard fires; chosen_step can't plan (no FightAction); AcceptTask CAN → returns AcceptTask."""
    planner = GOAPPlanner()
    gd = _make_planner_gd()
    # Calm state: HP full, no bag pressure, no task (so AcceptTask fires as discretionary)
    state = make_state(hp=150, max_hp=150, task_code=None, task_total=0)
    # Provide AcceptTaskAction but NO FightAction → ReachCharLevel (GrindCharacterXP) cannot plan,
    # AcceptTaskGoal CAN plan via AcceptTaskAction.
    actions = [AcceptTaskAction(taskmaster_location=(2, 1))]
    # chosen_step is ReachCharLevel → maps to GrindCharacterXPGoal which needs FightAction
    ctx = _ctx(combat_monster="chicken")
    arbiter = StrategyArbiter(planner, history=None)
    decision = _FakeDecision(chosen_step=ReachCharLevel(5))
    goal, plan, goals_tried = arbiter.select(decision, state, gd, actions, ctx)
    assert isinstance(goal, AcceptTaskGoal), f"expected AcceptTaskGoal, got {goal!r}"
    assert len(plan) >= 1


def test_select_returns_none_when_nothing_plans():
    """No plannable goal → (None, [], goals_tried).

    WaitGoal is suppressed because it is the always-firing last-resort
    means added in Phase 20e-v2; without suppression it would always
    short-circuit this path.
    """
    planner = GOAPPlanner()
    gd = _make_planner_gd()
    state = make_state(hp=150, max_hp=150, task_code="chicken", task_type="monster",
                       task_progress=0, task_total=5)
    actions: list = []  # no actions at all
    ctx = _ctx()
    arbiter = StrategyArbiter(planner, history=None)
    decision = _FakeDecision(chosen_step=None)
    goal, plan, goals_tried = arbiter.select(
        decision, state, gd, actions, ctx, suppressed={"Wait"})
    assert goal is None
    assert plan == []


class _SpyPlanner:
    """Records plan() calls so a test can prove the arbiter skipped the search."""

    def __init__(self) -> None:
        self.calls = 0
        self.last_stats = GOAPPlanner().last_stats

    def plan(self, state, goal, actions, game_data, history=None, *, budget_seconds=None):
        self.calls += 1
        return []


def test_plans_skips_unplannable_goal_without_searching():
    """A goal whose is_plannable() is False is never handed to the planner: the
    arbiter records a skipped attempt and returns [] without the 90s search.
    UpgradeEquipment(copper_boots) needs 80 gathers ≫ max_depth 15 ⇒ unplannable."""
    gd = GameData()
    gd._crafting_recipes = {
        "copper_boots": {"copper_bar": 8},
        "copper_bar": {"copper_ore": 10},
    }
    spy = _SpyPlanner()
    arbiter = StrategyArbiter(spy, history=None)
    goal = UpgradeEquipmentGoal(committed_target=("copper_boots", "boots_slot"))
    state = make_state(inventory={}, bank_items={})
    plan = arbiter._plans(goal, state, gd, [])
    assert plan == []
    assert spy.calls == 0, "unplannable goal must NOT invoke the planner"
    assert arbiter.goals_tried[-1]["plan_len"] == 0


def test_plans_runs_planner_for_plannable_goal():
    """A goal with default is_plannable() True is handed to the planner."""
    spy = _SpyPlanner()
    arbiter = StrategyArbiter(spy, history=None)
    goal = AcceptTaskGoal()
    state = make_state(task_code=None, task_total=0)
    arbiter._plans(goal, state, _gd(), [AcceptTaskAction(taskmaster_location=(2, 1))])
    assert spy.calls == 1


def test_select_skips_suppressed_means():
    """A means whose repr is in `suppressed` is skipped, falling through."""
    planner = GOAPPlanner()
    gd = _make_planner_gd()
    state = make_state(hp=150, max_hp=150, task_code=None, task_total=0)
    actions = [AcceptTaskAction(taskmaster_location=(2, 1))]
    ctx = _ctx(combat_monster="chicken")
    arbiter = StrategyArbiter(planner, history=None)
    decision = _FakeDecision(chosen_step=ReachCharLevel(5))
    # Without suppression AcceptTask would be selected; suppress it.
    goal, plan, tried = arbiter.select(
        decision, state, gd, actions, ctx, suppressed={"AcceptTask"})
    assert goal is None or repr(goal) != "AcceptTask"
    assert not any(gt["goal"] == "AcceptTask" for gt in tried)


def test_select_never_suppresses_task_cancel(tmp_path):
    """TaskCancel is the escape hatch and must never be filtered by suppression."""
    planner = GOAPPlanner()
    gd = _make_planner_gd()
    # A monsters task far above the character's level → task_decision PIVOTs, so
    # TASK_CANCEL fires (requires a non-None history). No FightAction is given so
    # nothing else plans, forcing the walk to reach the (suppressed) TaskCancel.
    gd._monster_level["dragon"] = 50
    fill_monster_stat_defaults(gd)
    store = LearningStore(db_path=str(tmp_path / "tc.db"), character="hero")
    try:
        state = make_state(level=5, hp=150, max_hp=150, task_code="dragon",
                           task_type="monsters", task_progress=0, task_total=5)
        actions = [TaskCancelAction(taskmaster_location=(2, 1))]
        ctx = _ctx()
        arbiter = StrategyArbiter(planner, history=store)
        decision = _FakeDecision(chosen_step=None)
        _goal, _plan, tried = arbiter.select(
            decision, state, gd, actions, ctx, suppressed={"TaskCancel"})
        assert any(gt["goal"] == "TaskCancel" for gt in tried), (
            "TaskCancel must not be skipped even when suppressed"
        )
    finally:
        store.close()


def test_select_sticky_keeps_committed_means():
    """If a means committed on cycle 1 still fires and plans, cycle 2 returns same repr."""
    planner = GOAPPlanner()
    gd = _make_planner_gd()
    # No task: AcceptTask fires (discretionary)
    state = make_state(hp=150, max_hp=150, task_code=None, task_total=0)
    actions = [AcceptTaskAction(taskmaster_location=(2, 1))]
    ctx = _ctx()
    arbiter = StrategyArbiter(planner, history=None)
    decision = _FakeDecision(chosen_step=None)

    goal1, plan1, _ = arbiter.select(decision, state, gd, actions, ctx)
    assert isinstance(goal1, AcceptTaskGoal), f"cycle 1: expected AcceptTask, got {goal1!r}"

    # Cycle 2: state unchanged, AcceptTask still fires and plans
    goal2, plan2, _ = arbiter.select(decision, state, gd, actions, ctx)
    assert repr(goal2) == repr(goal1), f"cycle 2: expected sticky {goal1!r}, got {goal2!r}"


def test_select_no_double_count_when_committed_becomes_unplannable():
    """Fix 1: committed means unplannable on cycle 2 must not appear twice in goals_tried."""
    planner = GOAPPlanner()
    gd = _make_planner_gd()
    # No task: AcceptTask fires as discretionary; AcceptTaskAction enables it to plan.
    state = make_state(hp=150, max_hp=150, task_code=None, task_total=0)
    actions_with_accept = [AcceptTaskAction(taskmaster_location=(2, 1))]
    ctx = _ctx()
    arbiter = StrategyArbiter(planner, history=None)
    decision = _FakeDecision(chosen_step=None)

    # Cycle 1: AcceptTask commits
    goal1, plan1, _ = arbiter.select(decision, state, gd, actions_with_accept, ctx)
    assert isinstance(goal1, AcceptTaskGoal)
    assert arbiter._committed_repr is not None

    # Cycle 2: remove AcceptTaskAction so the committed goal can't plan;
    # provide no other plannable action either → expect (None, []).
    # WaitGoal suppressed: it is the always-firing last-resort means and
    # would otherwise short-circuit the (None, []) outcome under test.
    goal2, plan2, tried2 = arbiter.select(
        decision, state, gd, [], ctx, suppressed={"Wait"})
    assert goal2 is None

    # AcceptTask repr must appear at most once in goals_tried (not double-counted)
    accept_reprs = [e["goal"] for e in tried2 if e["goal"] == repr(AcceptTaskGoal())]
    assert len(accept_reprs) <= 1, f"double-counted: {tried2}"


def test_select_guard_clears_committed_repr():
    """Fix 2: when a guard fires and plans, _committed_repr is cleared (not left stale)."""
    planner = GOAPPlanner()
    gd = _make_planner_gd()
    state_calm = make_state(hp=150, max_hp=150, task_code=None, task_total=0)
    actions = [
        AcceptTaskAction(taskmaster_location=(2, 1)),
        RestAction(),
    ]
    ctx = _ctx()
    arbiter = StrategyArbiter(planner, history=None)
    decision = _FakeDecision(chosen_step=None)

    # Cycle 1: calm state — AcceptTask commits
    goal1, _, _ = arbiter.select(decision, state_calm, gd, actions, ctx)
    assert isinstance(goal1, AcceptTaskGoal)
    assert arbiter._committed_repr is not None

    # Cycle 2: HP now critical — RestoreHP guard fires and plans
    state_low_hp = make_state(hp=10, max_hp=150, task_code=None, task_total=0)
    goal2, plan2, _ = arbiter.select(decision, state_low_hp, gd, actions, ctx)
    assert isinstance(goal2, RestoreHPGoal), f"expected RestoreHPGoal, got {goal2!r}"
    assert len(plan2) >= 1
    # commitment must be cleared after a guard return
    assert arbiter._committed_repr is None


# ---------------------------------------------------------------------------
# Part B: targeted coverage tests
# ---------------------------------------------------------------------------

def test_objective_step_goal_none_for_no_step():
    """objective_step_goal(None, ...) returns None (line 90) and an unrecognized
    step type also falls through to the final return None (line 106)."""
    # None step → early return None
    assert objective_step_goal(None, make_state(), _gd(), _ctx()) is None

    # Unrecognized step type (not ObtainItem / ReachSkillLevel / ReachCharLevel)
    class _UnknownStep:
        pass

    assert objective_step_goal(_UnknownStep(), make_state(), _gd(), _ctx()) is None  # type: ignore[arg-type]


def test_precedes_false_when_target_absent():
    """_precedes returns False when either repr is not present in the candidates list."""
    goal_a = AcceptTaskGoal()
    candidates = [Candidate(goal=goal_a, is_means=True, repr_=repr(goal_a))]
    # "NotPresent" is not in the list → b_idx is None → return False
    assert _precedes(candidates, repr(goal_a), "NotPresent") is False
    # a_repr also absent → a_idx is None → return False
    assert _precedes(candidates, "AlsoAbsent", "NotPresent") is False


def test_select_pure_skips_satisfied_candidate():
    """select_pure skips a satisfied candidate (line 92-93) and returns the next
    plannable one. Pure unit test over injected closures — no planner/state."""
    sat_goal = AcceptTaskGoal()
    next_goal = AcceptTaskGoal()
    sat = Candidate(goal=sat_goal, is_means=True, repr_="Satisfied")
    nxt = Candidate(goal=next_goal, is_means=True, repr_="Next")

    def try_plan(g):
        return [object()]  # non-empty stand-in plan

    def is_satisfied(g):
        return g is sat_goal  # the first candidate is satisfied

    def is_suppressed(g):
        return False

    goal, plan, committed = select_pure(
        [sat, nxt], None, try_plan, is_satisfied, is_suppressed)
    assert goal is next_goal
    assert plan
    assert committed == "Next"


def test_select_pure_skips_suppressed_candidate():
    """A suppressed candidate is skipped (line 90-91) before the satisfied/plan
    checks, so a later candidate wins."""
    supp_goal = AcceptTaskGoal()
    next_goal = AcceptTaskGoal()
    supp = Candidate(goal=supp_goal, is_means=True, repr_="Suppressed")
    nxt = Candidate(goal=next_goal, is_means=True, repr_="Next")

    goal, plan, committed = select_pure(
        [supp, nxt], None,
        try_plan=lambda g: [object()],
        is_satisfied=lambda g: False,
        is_suppressed=lambda g: g is supp_goal,
    )
    assert goal is next_goal
    assert committed == "Next"


def test_select_pure_returns_none_when_nothing_plans():
    """When no candidate plans, select_pure returns the empty result."""
    g = Candidate(goal=AcceptTaskGoal(), is_means=True, repr_="Only")
    result = select_pure(
        [g], None,
        try_plan=lambda goal: [],
        is_satisfied=lambda goal: False,
        is_suppressed=lambda goal: False,
    )
    assert result == (None, [], None)


def test_select_skips_satisfied_step_goal_continues_to_next():
    """A candidate step_goal that is_satisfied(state) is skipped; a later
    plannable discretionary goal (AcceptTask) is returned instead."""
    planner = GOAPPlanner()
    gd = _gd()
    # Give GameData the monster/bank locations AcceptTask needs
    gd._monster_locations = {"chicken": [(1, 0)]}
    gd._monster_level = {"chicken": 1}
    gd._resource_locations = {}
    gd._workshop_locations = {}
    gd._bank_location = (4, 0)

    # State already has ash_plank: 6 in inventory so GatherMaterialsGoal is satisfied
    state = make_state(hp=150, max_hp=150, task_code=None, task_total=0,
                       inventory={"ash_plank": 6})
    # chosen_step → GatherMaterialsGoal(needed={"ash_plank": 6}) which is_satisfied → skipped
    # AcceptTaskAction is available so AcceptTask discretionary goal will plan
    actions = [AcceptTaskAction(taskmaster_location=(2, 1))]
    ctx = _ctx(combat_monster="chicken")
    arbiter = StrategyArbiter(planner, history=None)

    # Use ObtainItem("ash_plank", 6) as chosen_step; state already satisfies it
    decision = _FakeDecision(chosen_step=ObtainItem("ash_plank", 6))
    goal, plan, goals_tried = arbiter.select(decision, state, gd, actions, ctx)

    # The satisfied GatherMaterialsGoal must have been skipped (not attempted)
    attempted_reprs = [e["goal"] for e in goals_tried]
    gather_repr = repr(GatherMaterialsGoal(target_item="ash_plank", needed={"ash_plank": 6}))
    assert gather_repr not in attempted_reprs, (
        f"satisfied goal should be skipped, but appeared in goals_tried: {attempted_reprs}"
    )
    assert isinstance(goal, AcceptTaskGoal), f"expected AcceptTaskGoal, got {goal!r}"
    assert len(plan) >= 1


# ---------------------------------------------------------------------------
# LEVEL_LOOKAHEAD tests
# ---------------------------------------------------------------------------

class TestLevelLookahead:
    def test_constant_is_three(self):
        assert LEVEL_LOOKAHEAD == 3

    def test_skill_step_targets_current_plus_lookahead(self):
        state = make_state(skills={"weaponcrafting": 1})
        goal = objective_step_goal(ReachSkillLevel("weaponcrafting", 50), state, GameData(), _ctx())
        assert repr(goal) == "LevelSkill(weaponcrafting->4)"   # min(50, 1+3)

    def test_skill_step_caps_at_step_level(self):
        state = make_state(skills={"weaponcrafting": 48})
        goal = objective_step_goal(ReachSkillLevel("weaponcrafting", 50), state, GameData(), _ctx())
        assert repr(goal) == "LevelSkill(weaponcrafting->50)"   # min(50, 48+3)


# ---------------------------------------------------------------------------
# PURSUE_TASK mapping tests
# ---------------------------------------------------------------------------

class TestPursueTaskMapping:
    def test_feasible_items_task_maps_to_pursue_task(self):
        # no crafting recipe known -> task_requirement returns None -> feasible
        state = make_state(task_code="copper_bar", task_type="items",
                           task_total=20, task_progress=0)
        goal = map_means(MeansKind.PURSUE_TASK, GameData(), _ctx(), state)
        assert repr(goal) == "PursueTask(copper_bar)"

    def test_skill_gated_items_task_maps_to_level_skill(self):
        gd = GameData()
        gd._item_stats["copper_bar"] = ItemStats(
            code="copper_bar", type_="resource", level=1,
            crafting_skill="weaponcrafting", crafting_level=3,
        )
        state = make_state(task_code="copper_bar", task_type="items",
                           task_total=20, task_progress=0, skills={"weaponcrafting": 1})
        goal = map_means(MeansKind.PURSUE_TASK, gd, _ctx(), state)
        assert repr(goal) == "LevelSkill(weaponcrafting->3)"   # min(gate=3, 1+LEVEL_LOOKAHEAD=4) -> 3

    def test_pursue_task_goal_carries_batch(self):
        gd = GameData()
        gd._crafting_recipes = {"copper_bar": {"copper_ore": 10}}
        gd._resource_drops = {"copper_rocks": "copper_ore"}
        state = make_state(task_code="copper_bar", task_type="items",
                           task_total=20, task_progress=2, inventory={}, inventory_max=100)
        goal = map_means(MeansKind.PURSUE_TASK, gd, _ctx(), state)
        expected = 2 + task_batch_size(state, gd)
        assert goal.desired_state(state, gd) == {"task_progress": expected}
        assert task_batch_size(state, gd) > 1   # this state genuinely batches


# ---------------------------------------------------------------------------
# Items-task grind stand-down tests
# ---------------------------------------------------------------------------

class TestItemsTaskStandDown:
    def test_char_step_stands_down_for_items_task(self):
        state = make_state(task_code="copper_bar", task_type="items",
                           task_total=20, task_progress=0)
        assert objective_step_goal(ReachCharLevel(50), state, GameData(),
                                   _ctx(combat_monster="chicken")) is None

    def test_char_step_grinds_for_monster_task(self):
        state = make_state(task_code="chicken", task_type="monsters",
                           task_total=20, task_progress=0)
        goal = objective_step_goal(ReachCharLevel(50), state, GameData(),
                                   _ctx(combat_monster="chicken"))
        assert goal is not None and repr(goal).startswith("GrindCharacterXP")

    def test_char_step_grinds_with_no_task(self):
        goal = objective_step_goal(ReachCharLevel(50), make_state(), GameData(),
                                   _ctx(combat_monster="chicken"))
        assert goal is not None and repr(goal).startswith("GrindCharacterXP")

    def test_bootstrap_char_step_grinds_through_items_task(self):
        """Trace 2026-06-03/05: 0 fights across 3300+ cycles because items
        tasks chain indefinitely and the long-haul ReachCharLevel(50)
        stand-down meant char-grind NEVER fired. The bootstrap-class
        root (state.level + 2) MUST punch through the stand-down — it
        IS the critical-path nudge that unblocks combat XP."""
        state = make_state(level=3, task_code="copper_bar", task_type="items",
                           task_total=20, task_progress=0)
        # Bootstrap step: target = state.level + 2 = 5, gap = 2.
        goal = objective_step_goal(ReachCharLevel(5), state, GameData(),
                                   _ctx(combat_monster="chicken"))
        assert goal is not None and repr(goal).startswith("GrindCharacterXP"), (
            f"bootstrap ReachCharLevel(5) must grind through items-task "
            f"stand-down (was the only way to escape level 3); got {goal!r}"
        )

    def test_long_haul_char_step_still_stands_down_for_items_task(self):
        """Sanity: the original stand-down behavior is preserved for the
        long-haul ReachCharLevel(50) step. Only the small-gap bootstrap
        path bypasses it."""
        state = make_state(level=3, task_code="copper_bar", task_type="items",
                           task_total=20, task_progress=0)
        assert objective_step_goal(ReachCharLevel(50), state, GameData(),
                                   _ctx(combat_monster="chicken")) is None


# ---------------------------------------------------------------------------
# End-to-end arbiter test: items task selects PursueTask, not GrindCharacterXP
# ---------------------------------------------------------------------------

class TestPursueTaskEndToEnd:
    """Reconstruct the production stall: copper_bar 0/20 items task, feasible
    (no skill gap), ReachCharLevel(50) as chosen_step → arbiter must return
    PursueTask(copper_bar), NOT GrindCharacterXP."""

    def test_items_task_selects_pursue_not_grind(self, monkeypatch, tmp_path):
        # Patch task_decision in means so PURSUE_TASK fires without needing a
        # populated LearningStore.
        monkeypatch.setattr(means_module, "task_decision", lambda *_: means_module.PURSUE)

        planner = GOAPPlanner()
        gd = _make_planner_gd()
        # No crafting recipe for copper_bar → task_requirement returns None → feasible
        # State: items task active, one copper_bar already in inventory (so
        # TaskTradeAction is immediately applicable). task_total=1 ensures
        # task_batch_size returns 1, so PursueTaskGoal(batch=1) is satisfied
        # after trading the single bar.
        state = make_state(
            level=5, hp=150, max_hp=150, xp=0, max_xp=500,
            task_code="copper_bar", task_type="items",
            task_progress=0, task_total=1,
            skills={"weaponcrafting": 5},
            inventory={"copper_bar": 1},
        )
        # TaskTradeAction lets PursueTaskGoal plan in one step.
        actions = [TaskTradeAction(code="copper_bar", quantity=1, taskmaster_location=(2, 1))]
        ctx = _ctx(combat_monster="chicken")

        # Use a real (empty) LearningStore so history is not None (required for
        # PURSUE_TASK._fires), but task_decision is patched so it always PURSUEs.
        store = LearningStore(db_path=str(tmp_path / "e2e.db"), character="testchar")
        try:
            arbiter = StrategyArbiter(planner, history=store)
            decision = _FakeDecision(chosen_step=ReachCharLevel(50))
            goal, plan, _ = arbiter.select(decision, state, gd, actions, ctx)
        finally:
            store.close()

        assert repr(goal) == "PursueTask(copper_bar)", (
            f"expected PursueTask(copper_bar), got {goal!r}"
        )
        assert len(plan) >= 1

    def test_meta_step_suppressed_when_redundant_with_task_chain(self, monkeypatch, tmp_path):
        """Suppression contract: when an items-task is being pursued AND the
        meta-objective's chosen_step is a GatherMaterials goal whose target
        sits INSIDE the task's recipe chain, the step is suppressed (the
        task's PursueTask plan already gathers it; a separate cycle would
        be a redundant 1-cycle detour).

        Setup: task=ash_plank with recipe ash_plank<-ash_wood. chosen_step
        = ObtainItem(ash_wood) is exactly the input the task chain produces.
        Expected: GatherMaterials(ash_wood) does not appear in goals_tried."""
        monkeypatch.setattr(means_module, "task_decision", lambda *_: means_module.PURSUE)

        planner = GOAPPlanner()
        gd = _make_planner_gd()
        # ash_plank<-ash_wood recipe so the task chain consumes ash_wood.
        gd._crafting_recipes["ash_plank"] = {"ash_wood": 1}
        gd._resource_locations = {"ash_tree": [(3, 0)]}
        gd._resource_drops["ash_tree"] = "ash_wood"
        gd._resource_skill["ash_tree"] = ("woodcutting", 1)

        state = make_state(
            level=5, hp=150, max_hp=150, xp=0, max_xp=500,
            task_code="ash_plank", task_type="items",
            task_progress=0, task_total=1,
            skills={"woodcutting": 1, "weaponcrafting": 5},
            inventory={"ash_plank": 1},
        )
        actions = [TaskTradeAction(code="ash_plank", quantity=1, taskmaster_location=(2, 1))]
        ctx = _ctx(combat_monster="chicken")

        store = LearningStore(db_path=str(tmp_path / "step_redundant.db"), character="testchar")
        try:
            arbiter = StrategyArbiter(planner, history=store)
            decision = _FakeDecision(chosen_step=ObtainItem("ash_wood"))
            goal, _plan, tried = arbiter.select(decision, state, gd, actions, ctx)
        finally:
            store.close()

        assert repr(goal) == "PursueTask(ash_plank)", (
            f"expected PursueTask, got {goal!r}"
        )
        assert all(gt["goal"] != "GatherMaterials(ash_wood)" for gt in tried), (
            f"ash-wood step is REDUNDANT with the task's own chain — should "
            f"be suppressed, but goals_tried={tried}"
        )

    def test_meta_step_allowed_when_independent_of_task_chain(self, monkeypatch, tmp_path):
        """Counterpart contract: when chosen_step's target is NOT in the
        active task's recipe chain, the step is INDEPENDENT progress (e.g.
        gear chain) and must run despite the active task. Pre-refinement,
        14e3830 suppressed the step indiscriminately, which is why Robby
        never crafted gear — every meta-step nudge got dropped.

        Setup: task=copper_bar with recipe copper_bar<-copper_ore.
        chosen_step = ObtainItem(ash_wood) which is unrelated (e.g. for a
        wooden_shield upgrade). Expected: GatherMaterials(ash_wood) appears
        in goals_tried — the step is allowed to compete."""
        monkeypatch.setattr(means_module, "task_decision", lambda *_: means_module.PURSUE)

        planner = GOAPPlanner()
        gd = _make_planner_gd()
        gd._crafting_recipes["copper_bar"] = {"copper_ore": 10}
        gd._resource_locations = {"ash_tree": [(3, 0)]}
        gd._resource_drops["ash_tree"] = "ash_wood"
        gd._resource_skill["ash_tree"] = ("woodcutting", 1)

        state = make_state(
            level=5, hp=150, max_hp=150, xp=0, max_xp=500,
            task_code="copper_bar", task_type="items",
            task_progress=0, task_total=1,
            skills={"weaponcrafting": 5, "woodcutting": 1},
            inventory={"copper_bar": 1},
        )
        actions = [TaskTradeAction(code="copper_bar", quantity=1, taskmaster_location=(2, 1))]
        ctx = _ctx(combat_monster="chicken")

        store = LearningStore(db_path=str(tmp_path / "step_indep.db"), character="testchar")
        try:
            arbiter = StrategyArbiter(planner, history=store)
            decision = _FakeDecision(chosen_step=ObtainItem("ash_wood"))
            _goal, _plan, tried = arbiter.select(decision, state, gd, actions, ctx)
        finally:
            store.close()

        # The step is tried (independent chain). Whether it wins depends on
        # whether it plans + position — we only assert that the candidate
        # is no longer SUPPRESSED at construction time.
        assert any(gt["goal"] == "GatherMaterials(ash_wood)" for gt in tried), (
            f"ash-wood step is INDEPENDENT of the copper_bar task chain — "
            f"should be allowed to compete, but goals_tried={tried}"
        )

    def test_task_trade_ready_suppresses_fallback_gather(self, monkeypatch, tmp_path):
        """Trace 2026-06-06 14:40 (cycles 25-26): task=items/copper_bar at
        20/21 with 1 copper_bar in inventory; the gear-chain fallback
        step GatherMaterials(copper_bar, needed=8) for ObtainItem(copper_boots)
        ran INSTEAD of PursueTask's TaskTrade. One trade would complete
        the task; bot gathered MORE copper_ore for armor while the held
        bar sat unused.

        Contract: when fallback step targets the task code AND inventory
        holds at least one unit, the fallback is SUPPRESSED so PursueTask
        wins the cycle and TaskTrade can fire.
        """
        monkeypatch.setattr(means_module, "task_decision", lambda *_: means_module.PURSUE)

        planner = GOAPPlanner()
        gd = _make_planner_gd()
        # copper_bar recipe so GatherMaterials(copper_bar) is a plausible step;
        # 'copper_bar' itself is NOT in _task_recipe_inputs("copper_bar")
        # (which returns {copper_ore}), so the EXISTING suppression rule does
        # NOT fire. Only the NEW trade-ready rule should suppress.
        gd._crafting_recipes["copper_bar"] = {"copper_ore": 10}
        gd._resource_locations = {"copper_rocks": [(1, 0)]}
        gd._resource_drops["copper_rocks"] = "copper_ore"
        gd._resource_skill["copper_rocks"] = ("mining", 1)

        state = make_state(
            level=4, hp=135, max_hp=135, xp=0, max_xp=500,
            task_code="copper_bar", task_type="items",
            task_progress=20, task_total=21,
            skills={"mining": 12, "weaponcrafting": 2},
            inventory={"copper_bar": 1},
        )
        actions = [
            TaskTradeAction(code="copper_bar", quantity=1, taskmaster_location=(2, 1)),
            GatherAction(resource_code="copper_rocks", locations=frozenset([(1, 0)])),
        ]
        ctx = _ctx(combat_monster="chicken")

        store = LearningStore(db_path=str(tmp_path / "trade_ready.db"), character="testchar")
        try:
            arbiter = StrategyArbiter(planner, history=store)
            # chosen_step matches the fallback case: ObtainItem(copper_bar, 8)
            # maps via objective_step_goal to GatherMaterialsGoal(copper_bar).
            decision = _FakeDecision(chosen_step=ObtainItem("copper_bar", 8))
            goal, plan, tried = arbiter.select(decision, state, gd, actions, ctx)
        finally:
            store.close()

        attempted = [gt["goal"] for gt in tried]
        assert "GatherMaterials(copper_bar)" not in attempted, (
            f"trade-ready suppression must drop the fallback GatherMaterials, "
            f"but goals_tried={attempted}"
        )
        assert repr(goal) == "PursueTask(copper_bar)", (
            f"expected PursueTask to win when inventory holds the task item, "
            f"got {goal!r}"
        )
        assert any(isinstance(a, TaskTradeAction) for a in plan), (
            f"PursueTask plan must include TaskTrade, got plan={plan}"
        )


# ---------------------------------------------------------------------------
# Task 4: _plans forwards budget; arbiter owns a DoomedMemo
# ---------------------------------------------------------------------------

def test_plans_forwards_budget_to_planner():
    """_plans passes its budget_seconds through to planner.plan."""
    captured = {}

    class _BudgetSpy:
        def __init__(self):
            self.last_stats = GOAPPlanner().last_stats

        def plan(self, state, goal, actions, game_data, history=None, *, budget_seconds=None):
            captured["budget"] = budget_seconds
            return []

    arbiter = StrategyArbiter(_BudgetSpy(), history=None)
    arbiter._plans(AcceptTaskGoal(), make_state(task_code=None, task_total=0), _gd(),
                   [AcceptTaskAction(taskmaster_location=(2, 1))], budget_seconds=1.0)
    assert captured["budget"] == 1.0


def test_arbiter_has_doomed_memo():
    arbiter = StrategyArbiter(GOAPPlanner(), history=None)
    assert isinstance(arbiter._memo, DoomedMemo)


def _gd_boots_chain():
    gd = GameData()
    gd._item_stats = {"copper_boots": ItemStats(code="copper_boots", level=1, type_="boots",
                                                crafting_skill="gearcrafting", crafting_level=1)}
    gd._crafting_recipes = {"copper_boots": {"copper_bar": 8}, "copper_bar": {"copper_ore": 10}}
    return gd


def test_objective_step_equippable_gathers_when_depth_unreachable():
    """An equippable step whose materials aren't gathered (UpgradeEquipment
    depth-unreachable: 8 bars = 80 ore >> max_depth) maps to GatherMaterials so
    the arbiter accumulates the materials, instead of a depth-gated
    UpgradeEquipment the arbiter would skip (the live-bot stall)."""
    gd = _gd_boots_chain()
    state = make_state(level=4, inventory={"copper_ore": 29})
    goal = objective_step_goal(ObtainItem("copper_boots", 1), state, gd, _ctx())
    assert isinstance(goal, GatherMaterialsGoal)


def test_objective_step_equippable_upgrades_when_materials_in_hand():
    """With the recipe materials in hand the target is depth-reachable, so the
    step maps to UpgradeEquipment for the craft+equip."""
    gd = _gd_boots_chain()
    state = make_state(level=4, inventory={"copper_bar": 8})
    goal = objective_step_goal(ObtainItem("copper_boots", 1), state, gd, _ctx())
    assert isinstance(goal, UpgradeEquipmentGoal)


# ---------------------------------------------------------------------------
# Skill-gate prioritization (LIV-SKILL-2 deadlock) integration test
# ---------------------------------------------------------------------------

def test_objective_step_reachskill_returns_craft_one_when_craftable():
    gd = GameData()
    gd._item_stats = {
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                   crafting_skill="weaponcrafting", crafting_level=1),
    }
    gd._crafting_recipes = {"copper_dagger": {"copper_bar": 6}}
    state = make_state(skills={"weaponcrafting": 1})
    goal = objective_step_goal(ReachSkillLevel("weaponcrafting", 5), state, gd, _ctx())
    assert isinstance(goal, GatherMaterialsGoal)
    assert repr(goal) == "GatherMaterials(copper_dagger)"


def test_objective_step_reachskill_falls_back_to_levelskill_when_nothing_craftable():
    gd = GameData()
    gd._item_stats = {
        "iron_dagger": ItemStats(code="iron_dagger", level=10, type_="weapon",
                                 crafting_skill="weaponcrafting", crafting_level=10),
    }
    gd._crafting_recipes = {"iron_dagger": {"iron_bar": 6}}
    state = make_state(skills={"weaponcrafting": 1})  # nothing craftable at level 1
    goal = objective_step_goal(ReachSkillLevel("weaponcrafting", 5), state, gd, _ctx())
    assert isinstance(goal, LevelSkillGoal)


def test_worth_gate_breaks_sticky_pursue_task(monkeypatch):
    """Committed PursueTask that serves no weapon need is worth-suppressed, so the
    sticky short-circuit breaks and the weapon-grind objective step wins."""
    arbiter = StrategyArbiter(GOAPPlanner(), history=None)
    # Stub planning so EVERY goal plans trivially — isolate the SELECTION logic.
    monkeypatch.setattr(arbiter, "_plans", lambda goal, *a, **k: [WaitAction()])

    gd = GameData()
    gd._item_stats = {
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                   crafting_skill="weaponcrafting", crafting_level=1),
        "iron_sword": ItemStats(code="iron_sword", level=10, type_="weapon",
                                crafting_skill="weaponcrafting", crafting_level=10),
        "cooked_gudgeon": ItemStats(code="cooked_gudgeon", level=1, type_="consumable",
                                    crafting_skill="cooking", crafting_level=1),
    }
    gd._crafting_recipes = {"copper_dagger": {}, "iron_sword": {"copper_dagger": 6},
                            "cooked_gudgeon": {}}
    obj = CharacterObjective(target_char_level=50, target_skill_levels={},
                             target_gear={"weapon_slot": "iron_sword"}, _game_data=gd,
                             target_tools={})
    state = make_state(skills={"weaponcrafting": 1, "cooking": 1},
                       task_type="items", task_code="cooked_gudgeon",
                       task_total=10, task_progress=0)
    weapon_grind = GatherMaterialsGoal("copper_dagger", {"copper_dagger": 1})
    monkeypatch.setattr(sd, "objective_step_goal",
                        lambda step, st, g, c, root=None: weapon_grind)
    monkeypatch.setattr(sd, "active_guards", lambda *a, **k: [])
    monkeypatch.setattr(sd, "active_means",
                        lambda *a, **k: ([], [sd.MeansKind.PURSUE_TASK]))
    decision = type("D", (), {"chosen_step": ReachSkillLevel("weaponcrafting", 5),
                              "chosen_root": ObtainItem("iron_sword"),
                              "fallback_steps": [], "fallback_roots": []})()
    ctx = _ctx(combat_monster=None)
    # Simulate prior sticky commitment to PursueTask.
    arbiter._committed_repr = repr(sd.map_means(sd.MeansKind.PURSUE_TASK, gd, ctx, state))

    goal, _plan, _tried = arbiter.select(decision, state, gd, [], ctx, objective=obj)
    assert isinstance(goal, GatherMaterialsGoal)
    assert repr(goal) == "GatherMaterials(copper_dagger)"


def test_worth_gate_bypassed_last_resort_selects_task_when_step_unplannable(monkeypatch):
    """Last-resort pass: the objective step cannot plan AND the only means are
    worth-suppressed task means. The worth gate suppresses PursueTask, the step
    fails, so the ungated re-run selects PursueTask and appends the
    `worth_gate_bypassed` trace marker (the bot earns instead of idling)."""
    arbiter = StrategyArbiter(GOAPPlanner(), history=None)
    # Objective-step goal (GatherMaterials) is UNPLANNABLE; everything else plans.
    monkeypatch.setattr(
        arbiter, "_plans",
        lambda goal, *a, **k: [] if isinstance(goal, GatherMaterialsGoal) else [WaitAction()])

    gd = GameData()
    gd._item_stats = {
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                   crafting_skill="weaponcrafting", crafting_level=1),
        "iron_sword": ItemStats(code="iron_sword", level=10, type_="weapon",
                                crafting_skill="weaponcrafting", crafting_level=10),
        "cooked_gudgeon": ItemStats(code="cooked_gudgeon", level=1, type_="consumable",
                                    crafting_skill="cooking", crafting_level=1),
    }
    gd._crafting_recipes = {"copper_dagger": {}, "iron_sword": {"copper_dagger": 6},
                            "cooked_gudgeon": {}}
    obj = CharacterObjective(target_char_level=50, target_skill_levels={},
                             target_gear={"weapon_slot": "iron_sword"}, _game_data=gd,
                             target_tools={})
    state = make_state(skills={"weaponcrafting": 1, "cooking": 1},
                       task_type="items", task_code="cooked_gudgeon",
                       task_total=10, task_progress=0)
    weapon_grind = GatherMaterialsGoal("copper_dagger", {"copper_dagger": 1})
    monkeypatch.setattr(sd, "objective_step_goal",
                        lambda step, st, g, c, root=None: weapon_grind)
    monkeypatch.setattr(sd, "active_guards", lambda *a, **k: [])
    monkeypatch.setattr(sd, "active_means",
                        lambda *a, **k: ([], [sd.MeansKind.PURSUE_TASK]))
    decision = type("D", (), {"chosen_step": ReachSkillLevel("weaponcrafting", 5),
                              "chosen_root": ObtainItem("iron_sword"),
                              "fallback_steps": [], "fallback_roots": []})()
    ctx = _ctx(combat_monster=None)

    goal, _plan, tried = arbiter.select(decision, state, gd, [], ctx, objective=obj)
    assert repr(goal).startswith("PursueTask")
    assert any(t["goal"] == "worth_gate_bypassed" for t in tried)


def test_no_objective_keeps_committed_pursue_task(monkeypatch):
    """Control: with NO objective (no worth gate), the committed PursueTask still
    wins via sticky — proving the suppression, not ordering, caused the switch."""
    arbiter = StrategyArbiter(GOAPPlanner(), history=None)
    monkeypatch.setattr(arbiter, "_plans", lambda goal, *a, **k: [WaitAction()])
    gd = GameData()
    gd._item_stats = {"cooked_gudgeon": ItemStats(code="cooked_gudgeon", level=1,
                      type_="consumable", crafting_skill="cooking", crafting_level=1)}
    gd._crafting_recipes = {"cooked_gudgeon": {}}
    state = make_state(skills={"cooking": 1}, task_type="items",
                       task_code="cooked_gudgeon", task_total=10, task_progress=0)
    weapon_grind = GatherMaterialsGoal("copper_dagger", {"copper_dagger": 1})
    monkeypatch.setattr(sd, "objective_step_goal",
                        lambda step, st, g, c, root=None: weapon_grind)
    monkeypatch.setattr(sd, "active_guards", lambda *a, **k: [])
    monkeypatch.setattr(sd, "active_means",
                        lambda *a, **k: ([], [sd.MeansKind.PURSUE_TASK]))
    decision = type("D", (), {"chosen_step": ReachSkillLevel("weaponcrafting", 5),
                              "chosen_root": ObtainItem("iron_sword"),
                              "fallback_steps": [], "fallback_roots": []})()
    ctx = _ctx(combat_monster=None)
    pursue = sd.map_means(sd.MeansKind.PURSUE_TASK, gd, ctx, state)
    arbiter._committed_repr = repr(pursue)
    goal, _plan, _tried = arbiter.select(decision, state, gd, [], ctx)  # objective=None
    assert repr(goal) == repr(pursue)  # committed task kept (sticky), no worth gate
