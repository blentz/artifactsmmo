import json
from dataclasses import dataclass

import pytest

import artifactsmmo_cli.ai.strategy_driver as sd
from artifactsmmo_cli.ai.actions.accept_task import AcceptTaskAction
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.equip import EquipAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.actions.task_cancel import TaskCancelAction
from artifactsmmo_cli.ai.actions.task_trade import TaskTradeAction
from artifactsmmo_cli.ai.actions.wait import WaitAction
from artifactsmmo_cli.ai.arbiter_select import Candidate, _precedes, select_pure
from artifactsmmo_cli.ai.doomed_memo import DoomedMemo
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.accept_task_goal import AcceptTaskGoal
from artifactsmmo_cli.ai.goals.claim_pending import ClaimPendingGoal
from artifactsmmo_cli.ai.goals.complete_task_goal import CompleteTaskGoal
from artifactsmmo_cli.ai.goals.craft_potions import CraftPotionsGoal
from artifactsmmo_cli.ai.goals.deposit_inventory import DepositInventoryGoal
from artifactsmmo_cli.ai.goals.discard_overstock import DiscardOverstockGoal
from artifactsmmo_cli.ai.goals.equip_owned_gear import EquipOwnedGoal
from artifactsmmo_cli.ai.goals.expand_bank import ExpandBankGoal
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.grind_character_xp import GrindCharacterXPGoal
from artifactsmmo_cli.ai.goals.low_yield_cancel import LowYieldCancelGoal
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from artifactsmmo_cli.ai.goals.provision_marginal_fight import ProvisionMarginalFightGoal
from artifactsmmo_cli.ai.goals.pursue_task import PursueTaskGoal  # noqa: F401 (used in repr checks)
from artifactsmmo_cli.ai.goals.reach_currency import ReachCurrencyGoal
from artifactsmmo_cli.ai.goals.reach_unlock_level import ReachUnlockLevelGoal
from artifactsmmo_cli.ai.goals.recycle_surplus import RecycleSurplusGoal
from artifactsmmo_cli.ai.goals.restore_hp import RestoreHPGoal
from artifactsmmo_cli.ai.goals.sell_inventory import SellInventoryGoal
from artifactsmmo_cli.ai.goals.task_cancel import TaskCancelGoal
from artifactsmmo_cli.ai.goals.task_exchange import TaskExchangeGoal
from artifactsmmo_cli.ai.goals.unlock_bank import UnlockBankGoal
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.planner import GOAPPlanner, PlanStats
from artifactsmmo_cli.ai.strategy_driver import (
    LEVEL_LOOKAHEAD,
    StrategyArbiter,
    _equippable_goal,
    _gather_goal_for_unreachable_equippable,
    _recipe_has_combat_drop_input,
    _task_recipe_inputs,
    map_guard,
    map_means,
    monster_drop_inputs,
    objective_step_goal,
)
from artifactsmmo_cli.ai.task_batch import task_batch_size
from artifactsmmo_cli.ai.tiers.guards import GuardKind, SelectionContext
from artifactsmmo_cli.ai.tiers.means import MeansKind
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachCharLevel
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.personality import BalancedPersonality
from artifactsmmo_cli.ai.tiers.strategy import StrategyEngine
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
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


def test_map_guard_recycle_relief():
    """RECYCLE_RELIEF maps to RecycleSurplusGoal, same as RECYCLE_SURPLUS means."""
    gd = GameData()
    gd._item_stats = {
        "copper_helmet": ItemStats(code="copper_helmet", level=1, type_="helmet",
                                   crafting_skill="gearcrafting", crafting_level=1),
    }
    gd._crafting_recipes = {"copper_helmet": {"copper_bar": 6}}
    gd._workshop_locations = {"gearcrafting": (2, 1)}
    g = map_guard(GuardKind.RECYCLE_RELIEF, gd, _ctx(target_gear=frozenset({"copper_helmet"})))
    assert isinstance(g, RecycleSurplusGoal)


def test_map_guard_sell_relief():
    """SELL_RELIEF maps to SellInventoryGoal."""
    g = map_guard(GuardKind.SELL_RELIEF, GameData(), _ctx(bank_accessible=True))
    assert isinstance(g, SellInventoryGoal)


def test_map_guard_unknown_raises():
    with pytest.raises(ValueError):
        map_guard("bogus", GameData(), _ctx())  # type: ignore[arg-type]


def test_map_guard_returns_craft_potions_goal():
    assert isinstance(map_guard(GuardKind.CRAFT_POTIONS, _gd(), _ctx()), CraftPotionsGoal)


def test_map_guard_gear_review_gathers_when_materials_missing():
    gd = GameData()
    gd._item_stats = {"copper_boots": ItemStats(code="copper_boots", level=1, type_="boots",
                                                crafting_skill="gearcrafting", crafting_level=1)}
    gd._crafting_recipes = {"copper_boots": {"copper_bar": 8}, "copper_bar": {"copper_ore": 10}}
    state = make_state(level=4, inventory={}, bank_items={})
    goal = map_guard(GuardKind.GEAR_REVIEW, gd, _ctx(gear_review_active=True), state)
    assert isinstance(goal, GatherMaterialsGoal)


def test_map_guard_discard_merges_step_profile():
    """Run-4 trace 2026-06-11 22:36 (cycle 30): map_guard must hand
    DiscardOverstock the SAME step-enriched profile the firing predicate used,
    so the constructed goal cannot delete the active step goal's target item
    while still shedding genuinely-overstocked items."""
    gd = GameData()
    gd._crafting_recipes = {"wooden_shield": {"ash_plank": 6},
                            "ash_plank": {"ash_wood": 10}}
    # Both equipped-dup items are capped at 1 under pressure; only the
    # step-profile-protected shield must survive victim selection.
    state = make_state(
        hp=100, max_hp=100,
        inventory={"wooden_shield": 2, "old_helmet": 2, "ash_wood": 47},
        inventory_max=60,
        equipment={"shield_slot": "wooden_shield", "helmet_slot": "old_helmet"},
        bank_items={},
    )
    goal = map_guard(GuardKind.DISCARD_HIGH, gd, _ctx(), state,
                     step_profile={"wooden_shield": 3})
    acts = goal.relevant_actions([], state, gd)
    assert acts, "old_helmet overstock should still produce a discard action"
    assert any("old_helmet" in repr(a) for a in acts), acts
    assert all("wooden_shield" not in repr(a) for a in acts), acts


def test_skill_grind_gather_caps_bag_reserve():
    """A perpetual skill-XP grind gather (needed = held+1, byproduct drop) must
    NOT reserve its entire growing pile in the bag — only GRIND_BAG_RESERVE, so
    surplus banks (re-withdrawable; bank stock still counts toward held so the
    grind keeps gathering for XP). Regression: live Robby held 137 sunflower and
    the held+1 profile locked all of them in the bag (114/114) during the alchemy
    L1->L5 grind."""
    gd = GameData()
    gd._crafting_recipes = {}  # sunflower is a raw resource (no sub-recipe)
    state = make_state(inventory={"sunflower": 40}, bank_items={"sunflower": 97})
    # held = 40 + 97 = 137 -> grind target = held + 1 = 138
    grind = GatherMaterialsGoal(target_item="sunflower",
                                needed={"sunflower": 138}, skill_grind=True)
    profile = sd._step_protection_profile(grind, state, gd)
    assert profile is not None
    assert profile["sunflower"] == sd.GRIND_BAG_RESERVE  # capped, NOT 138


def test_non_grind_gather_keeps_full_needed_protection():
    """A normal (non-grind) GatherMaterials protects its full needed target —
    the byproduct-reserve cap applies ONLY to skill-grind gathers, so a real
    craft-input accumulation is never under-protected."""
    gd = GameData()
    gd._crafting_recipes = {}
    state = make_state(inventory={"steel_bar": 2}, bank_items={})
    normal = GatherMaterialsGoal(target_item="steel_bar", needed={"steel_bar": 6})
    profile = sd._step_protection_profile(normal, state, gd)
    assert profile is not None
    assert profile["steel_bar"] == 6  # full needed still protected


def test_select_fallback_equip_not_shadowed_by_dead_upgrade_goal():
    """Run-18 trace 2026-06-12 17:31-18:33 (cycles 27-98): copper_legs_armor
    was crafted and sat in inventory for 73 cycles while Robby fought
    unarmored. The sticky root (feather_coat) mapped to an UNPLANNABLE
    UpgradeEquipment goal (feathers are monster drops; the goal's
    relevant_actions drop Fight actions) — and the rank-#1 fallback root's
    one-action equip goal was DEDUPED AWAY because UpgradeEquipmentGoal's
    repr was the bare "UpgradeEquipment" for every target. Distinct targets
    must produce distinct candidates; the live equip must win.

    Post-EquipOwnedGoal (COLLECT band): the owned copper_legs_armor into its
    empty slot is now served by the first-class `EquipOwnedGoal`, which
    outranks the (dead) UpgradeEquipment step — the equip still wins, via the
    dedicated equip-owned path."""
    planner = GOAPPlanner()
    gd = GameData()
    gd._item_stats = {
        "copper_legs_armor": ItemStats(code="copper_legs_armor", level=5,
                                       type_="leg_armor",
                                       crafting_skill="gearcrafting",
                                       crafting_level=5),
        "feather_coat": ItemStats(code="feather_coat", level=5,
                                  type_="body_armor",
                                  crafting_skill="gearcrafting",
                                  crafting_level=5),
    }
    gd._crafting_recipes = {
        "copper_legs_armor": {"copper_bar": 5, "feather": 2},
        "feather_coat": {"feather": 5, "ash_plank": 2},
    }
    gd._workshop_locations = {"gearcrafting": (3, 1)}
    gd._bank_location = (4, 0)
    fill_monster_stat_defaults(gd)
    # Legs OWNED but unequipped; nothing on hand for the feather_coat chain.
    state = make_state(
        level=7, hp=150, max_hp=150,
        skills={"gearcrafting": 5, "mining": 9, "woodcutting": 4},
        inventory={"copper_legs_armor": 1}, inventory_max=110,
        equipment={"leg_armor_slot": None, "body_armor_slot": None},
        bank_items={},
    )
    actions = [
        EquipAction(code="copper_legs_armor", slot="leg_armor_slot"),
        EquipAction(code="feather_coat", slot="body_armor_slot"),
        RestAction(),
    ]
    decision = _FallbackDecision(
        chosen_step=ObtainItem("feather_coat", 1),
        fallback_steps=[ObtainItem("copper_legs_armor", 1)],
        fallback_roots=[ObtainItem("copper_legs_armor", 1)],
    )
    arbiter = StrategyArbiter(planner, history=None)
    arbiter.set_cycle(0)
    goal, plan, goals_tried = arbiter.select(decision, state, gd, actions, _ctx())
    assert isinstance(goal, EquipOwnedGoal), (goal, goals_tried)
    assert plan and any(isinstance(a, EquipAction)
                        and a.code == "copper_legs_armor" for a in plan), plan


def test_upgrade_equipment_repr_distinguishes_targets():
    a = UpgradeEquipmentGoal(initial_equipment={},
                             committed_target=("copper_legs_armor", "leg_armor_slot"))
    b = UpgradeEquipmentGoal(initial_equipment={},
                             committed_target=("feather_coat", "body_armor_slot"))
    probe = UpgradeEquipmentGoal(initial_equipment={})
    assert repr(a) != repr(b)
    assert "copper_legs_armor" in repr(a)
    assert repr(probe) == "UpgradeEquipment"


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


# ---------------------------------------------------------------------------
# C4 Task 6: DEMAND ROUTING — route to ReachCurrencyGoal when the ObtainItem
# objective is blocked on an unaffordable currency-buy leaf (satchel <-
# jasper_crystal @ tasks_trader for 8 tasks_coin).
# ---------------------------------------------------------------------------

def _satchel_currency_gd():
    """satchel is a craftable bag whose only recipe input is jasper_crystal, a
    currency-buy leaf (non-craftable, not gathered, no monster drop, sold by
    tasks_trader for 8 tasks_coin). Skill gate OPEN (gearcrafting >= 1)."""
    gd = GameData()
    gd._crafting_recipes = {"satchel": {"jasper_crystal": 1}}
    gd._item_stats = {
        "satchel": ItemStats(code="satchel", level=1, type_="bag",
                             crafting_skill="gearcrafting", crafting_level=1),
    }
    gd._npc_stock = {"tasks_trader": {"jasper_crystal": 8}}
    gd._npc_buy_currency = {"tasks_trader": {"jasper_crystal": "tasks_coin"}}
    gd._task_coin_rewards = {"chicken": 1}  # C2 floor for funding-cycle calc
    gd._npc_locations = {"tasks_trader": (4, 1)}
    return gd


def test_objective_step_routes_to_reach_currency_when_leaf_unaffordable():
    """0 tasks_coin: GatherMaterials(satchel) is unplannable (jasper unaffordable),
    so the arbiter mapping returns ReachCurrencyGoal(tasks_coin, 8) to FUND the
    coin instead — a plannable funding goal the arbiter can select."""
    gd = _satchel_currency_gd()
    state = make_state(skills={"gearcrafting": 5}, inventory={}, bank_items={}, x=0, y=0)
    goal = objective_step_goal(ObtainItem("satchel", 1), state, gd, _ctx())
    assert isinstance(goal, ReachCurrencyGoal)
    assert goal._currency == "tasks_coin"
    assert goal._target == 8


def test_objective_step_gathers_satchel_when_currency_funded():
    """tasks_coin >= 8: jasper is affordable, so the mapping returns the craft
    path (a GatherMaterials/UpgradeEquipment goal targeting satchel), NOT a
    funding goal."""
    gd = _satchel_currency_gd()
    state = make_state(skills={"gearcrafting": 5}, inventory={"tasks_coin": 8},
                       bank_items={}, x=0, y=0)
    goal = objective_step_goal(ObtainItem("satchel", 1), state, gd, _ctx())
    assert not isinstance(goal, ReachCurrencyGoal)
    assert goal is not None


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


def test_map_means_task_exchange_threads_initial_total():
    """ONE-batch threading: map_means captures the construction-time
    inventory+bank coin total, so the goal is satisfied after a single
    batch is spent (7 -> 4 with min 3), not only when fully drained."""
    state = make_state(inventory={"tasks_coin": 4}, bank_items={"tasks_coin": 3})
    g = map_means(MeansKind.TASK_EXCHANGE, GameData(), _ctx(task_exchange_min_coins=3), state)
    assert g.is_satisfied(state) is False
    one_batch_spent = make_state(inventory={"tasks_coin": 1},
                                 bank_items={"tasks_coin": 3})
    assert g.is_satisfied(one_batch_spent) is True
    partial_spend = make_state(inventory={"tasks_coin": 2},
                               bank_items={"tasks_coin": 3})
    assert g.is_satisfied(partial_spend) is False


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


def test_objective_step_intermediate_chunks_toward_equippable_root():
    """An intermediate recipe-input step (ash_plank, no slots) whose chain ROOT is
    an equippable (wooden_shield) is pursued ONE PLANNABLE CHUNK at a time — a flat
    GatherMaterials toward the root's chain, NOT the whole-chain UpgradeEquipment.

    The old code returned UpgradeEquipmentGoal(root) here, but that hands the whole
    craft+equip chain to the A* at once; when the chain exceeds the planner depth
    budget (copper_boots from scratch: ~96 actions ≫ max_depth 32) the one-shot plan
    returns plan_len 0 and the bot abandons the gear for chicken grind (trace 2026-06-21).
    The committed root is unchanged — only its EXECUTION is chunked via
    gather_step_target, whose own depth check picks a budget-feasible target."""
    gd = _gd()
    step = ObtainItem("ash_plank", 6)
    root = ObtainItem("wooden_shield", 1)
    g = objective_step_goal(step, make_state(), gd, _ctx(), root=root)
    assert isinstance(g, GatherMaterialsGoal)
    # the chunk targets a node ON the wooden_shield chain (the root, an
    # intermediate, or a raw base material), never something off-chain.
    assert g._target_item in {"wooden_shield", "ash_plank", "ash_wood"}


def test_objective_step_combat_drop_input_routes_to_flat_step():
    """A recipe with a MONSTER-DROP input (feather <- chicken) must NOT plan the
    whole craft+equip chain — the GOAP search interleaves fights/gathers/crafts and
    explodes (live: feather_coat 57k nodes, timeout, plan_len 0; bot fell to
    slime-grind). Route to the flat actionable step instead so inputs are collected
    incrementally (gather wood / hunt chickens), each within budget."""
    gd = GameData()
    gd._item_stats = {
        "feather_coat": ItemStats(code="feather_coat", level=1, type_="body_armor",
                                  crafting_skill="gearcrafting", crafting_level=1),
        "ash_plank": ItemStats(code="ash_plank", level=1, type_="resource"),
        "feather": ItemStats(code="feather", level=1, type_="resource"),
    }
    gd._crafting_recipes = {"feather_coat": {"ash_plank": 2, "feather": 2},
                            "ash_plank": {"ash_wood": 1}}
    gd._resource_drops = {"ash_tree": "ash_wood"}
    gd._monster_drops = {"chicken": [("feather", 8, 1, 1)]}
    state = make_state(level=1, inventory={}, bank_items={})
    root = ObtainItem("feather_coat", 1, "body_armor_slot")
    # Even when the chosen step IS an intermediate of the equippable root, the
    # combat-drop input forces flat per-input routing (NOT UpgradeEquipment).
    step = ObtainItem("ash_plank", 2)
    g = objective_step_goal(step, state, gd, _ctx(), root=root)
    assert isinstance(g, GatherMaterialsGoal)
    assert g._needed == {"ash_plank": 2}
    # Sibling combat-drop input routes to a flat feather hunt.
    g2 = objective_step_goal(ObtainItem("feather", 2), state, gd, _ctx(), root=root)
    assert isinstance(g2, GatherMaterialsGoal)
    assert g2._needed == {"feather": 2}


def test_monster_drop_inputs_collects_pure_drop_leaves():
    """monster_drop_inputs returns the recipe closure's pure monster-drop leaves
    (feather), skipping craftable/gatherable inputs (ash_plank/ash_wood)."""
    gd = GameData()
    gd._item_stats = {
        "feather_coat": ItemStats(code="feather_coat", level=1, type_="body_armor"),
        "ash_plank": ItemStats(code="ash_plank", level=1, type_="resource"),
        "feather": ItemStats(code="feather", level=1, type_="resource"),
    }
    gd._crafting_recipes = {"feather_coat": {"feather": 5, "ash_plank": 2},
                            "ash_plank": {"ash_wood": 1}}
    gd._resource_drops = {"ash_tree": "ash_wood"}
    gd._monster_drops = {"chicken": [("feather", 8, 1, 1)]}
    assert monster_drop_inputs("feather_coat", gd) == ["feather"]
    # No recipe / not a drop -> empty.
    assert monster_drop_inputs("ash_wood", gd) == []


def test_monster_drop_inputs_is_cycle_safe():
    gd = GameData()
    gd._crafting_recipes = {"a": {"b": 1}, "b": {"a": 1}}
    assert monster_drop_inputs("a", gd) == []


def test_recipe_has_combat_drop_input_is_cycle_safe():
    """A pathological cyclic recipe (a<-b, b<-a) must not infinite-loop the
    combat-drop closure walk; the per-path visited guard returns False."""
    gd = GameData()
    gd._crafting_recipes = {"a": {"b": 1}, "b": {"a": 1}}
    assert _recipe_has_combat_drop_input("a", gd) is False


def test_objective_step_intermediate_unreachable_root_routes_to_deepest_step():
    """From-scratch DEEP equippable chain: the intermediate step maps to the
    equippable ROOT, but the root's UpgradeEquipment is depth-UNREACHABLE
    (min_gathers 480 >> max_depth 32). The old fallback built
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
    # Bank has 2 steel_bar (cuts the need to 4) but 4*8*10 = 320 ore >> 32.
    state = make_state(level=5, inventory={}, bank_items={"steel_bar": 2})
    step = ObtainItem("iron_ore", 320)
    root = ObtainItem("steel_boots", 1)
    g = objective_step_goal(step, state, gd, _ctx(), root=root)
    assert isinstance(g, GatherMaterialsGoal)
    assert g._needed == {"iron_ore": 320}


def test_objective_step_intermediate_reachable_root_chunks_the_craft():
    """Even when the root chain is shallow & in hand (ash_plank x6 ready), the
    intermediate-step is pursued via a plannable CHUNK (GatherMaterials toward the
    shield's chain), NOT a one-shot UpgradeEquipment(root). The craft chunk fits the
    depth budget; the EQUIP follows next cycle through the equippable branch once the
    shield is owned (prerequisites() returns [] for owned-but-unequipped gear, so the
    actionable step becomes the root itself). Robust: a flat chunk is always
    plannable, where the whole craft+equip chain can overflow max_depth."""
    gd = _gd()  # wooden_shield <- ash_plank x6 <- ash_wood; shallow & in hand
    state = make_state(level=5, inventory={"ash_plank": 6})
    step = ObtainItem("ash_plank", 6)
    root = ObtainItem("wooden_shield", 1)
    g = objective_step_goal(step, state, gd, _ctx(), root=root)
    assert isinstance(g, GatherMaterialsGoal)
    assert g._target_item in {"wooden_shield", "ash_plank", "ash_wood"}


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
    chosen_step: ObtainItem | ReachCharLevel | None


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
    goal, plan, _goals_tried = arbiter.select(decision, state, gd, actions, ctx)
    assert isinstance(goal, RestoreHPGoal), f"expected RestoreHPGoal, got {goal!r}"
    assert len(plan) >= 1


@dataclass(frozen=True)
class _FallbackDecision:
    """Decision stub carrying the fallback-step chain the arbiter reads via
    getattr (chosen_step + fallback_steps/roots)."""
    chosen_step: ObtainItem | ReachCharLevel | None
    fallback_steps: list
    fallback_roots: list


def test_fallback_serves_when_top_step_yields_no_goal():
    """Zombie-commitment release: when the top chosen_step's objective_step_goal
    is None (e.g. ReachCharLevel with no winnable monster, or a reservation-
    starved skill grind), a fallback still serves the cycle, so select
    returns a goal instead of leaving the player idle (weaponcrafting
    level-5 plateau, trace 2026-06-19)."""
    planner = GOAPPlanner()
    gd = _gd()
    state = make_state(hp=100, max_hp=100, inventory={"wooden_shield": 1},
                       equipment={"shield_slot": None})
    actions = [EquipAction(code="wooden_shield", slot="shield_slot"), RestAction()]
    decision = _FallbackDecision(
        chosen_step=ReachCharLevel(level=10),          # ctx.combat_monster=None -> None goal
        fallback_steps=[ObtainItem("wooden_shield", 1)],
        fallback_roots=[ObtainItem("wooden_shield", 1)])
    arbiter = StrategyArbiter(planner, history=None)
    arbiter.set_cycle(0)
    goal, _plan, _gt = arbiter.select(decision, state, gd, actions, _ctx())
    assert goal is not None, "a fallback must still serve the cycle"


def test_select_returns_top_step_goal_when_it_yields_a_goal():
    """The complement: a chosen_step that DOES map to a goal (here an owned
    wooden_shield -> EquipOwnedGoal, the one-action equip path) is returned
    directly — select never falls through to the fallback chain when the top
    step is alive."""
    planner = GOAPPlanner()
    gd = _gd()
    state = make_state(hp=100, max_hp=100, inventory={"wooden_shield": 1},
                       equipment={"shield_slot": None})
    actions = [EquipAction(code="wooden_shield", slot="shield_slot"), RestAction()]
    decision = _FallbackDecision(
        chosen_step=ObtainItem("wooden_shield", 1),
        fallback_steps=[], fallback_roots=[])
    arbiter = StrategyArbiter(planner, history=None)
    arbiter.set_cycle(0)
    goal, _plan, _gt = arbiter.select(decision, state, gd, actions, _ctx())
    assert isinstance(goal, EquipOwnedGoal)


def test_select_prefers_equip_owned_gear_over_fallback_upgrade():
    """When the top chosen_step yields no goal, an owned wooden_shield into its
    empty slot is served by the first-class `EquipOwnedGoal` in the COLLECT
    band, which outranks (and thus preempts) the UpgradeEquipment fallback —
    the owned shield still gets equipped, via the dedicated equip-owned path."""
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
    _goal, _plan, goals_tried = arbiter_select_with(planner, decision, state, gd)
    tried_reprs = {str(e["goal"]) for e in goals_tried}
    assert any("EquipOwnedGear" in r for r in tried_reprs), tried_reprs


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
    goal, plan, _goals_tried = arbiter.select(decision, state, gd, actions, ctx)
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
    goal, plan, _goals_tried = arbiter.select(decision, state, gd, actions, ctx)
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
    goal, plan, _goals_tried = arbiter.select(
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
    UpgradeEquipment(copper_boots) needs 80 gathers ≫ max_depth 32 ⇒ unplannable."""
    gd = GameData()
    gd._crafting_recipes = {
        "copper_boots": {"copper_bar": 8},
        "copper_bar": {"copper_ore": 10},
    }
    spy = _SpyPlanner()
    arbiter = StrategyArbiter(spy, history=None)
    goal = UpgradeEquipmentGoal(committed_target=("copper_boots", "boots_slot"))
    state = make_state(inventory={}, bank_items={})
    plan = arbiter._plans(goal, state, gd, [], _ctx())
    assert plan == []
    assert spy.calls == 0, "unplannable goal must NOT invoke the planner"
    assert arbiter.goals_tried[-1]["plan_len"] == 0


def test_plans_runs_planner_for_plannable_goal():
    """A goal with default is_plannable() True is handed to the planner."""
    spy = _SpyPlanner()
    arbiter = StrategyArbiter(spy, history=None)
    goal = AcceptTaskGoal()
    state = make_state(task_code=None, task_total=0)
    arbiter._plans(goal, state, _gd(), [AcceptTaskAction(taskmaster_location=(2, 1))], _ctx())
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
    goal, _plan, tried = arbiter.select(
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

    goal1, _plan1, _ = arbiter.select(decision, state, gd, actions, ctx)
    assert isinstance(goal1, AcceptTaskGoal), f"cycle 1: expected AcceptTask, got {goal1!r}"

    # Cycle 2: state unchanged, AcceptTask still fires and plans
    goal2, _plan2, _ = arbiter.select(decision, state, gd, actions, ctx)
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
    goal1, _plan1, _ = arbiter.select(decision, state, gd, actions_with_accept, ctx)
    assert isinstance(goal1, AcceptTaskGoal)
    assert arbiter._committed_repr is not None

    # Cycle 2: remove AcceptTaskAction so the committed goal can't plan;
    # provide no other plannable action either → expect (None, []).
    # WaitGoal suppressed: it is the always-firing last-resort means and
    # would otherwise short-circuit the (None, []) outcome under test.
    goal2, _plan2, tried2 = arbiter.select(
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

    # Unrecognized step type (not ObtainItem / ReachCharLevel)
    class _UnknownStep:
        pass

    assert objective_step_goal(_UnknownStep(), make_state(), _gd(), _ctx()) is None  # type: ignore[arg-type]


def test_precedes_false_when_target_absent():
    """_precedes returns False when either repr is not present in the candidates list."""
    goal_a = AcceptTaskGoal()
    candidates = [Candidate(goal=goal_a, is_means=True, repr_=repr(goal_a), band=2)]
    # "NotPresent" is not in the list → b_idx is None → return False
    assert _precedes(candidates, repr(goal_a), "NotPresent") is False
    # a_repr also absent → a_idx is None → return False
    assert _precedes(candidates, "AlsoAbsent", "NotPresent") is False


def test_select_pure_skips_satisfied_candidate():
    """select_pure skips a satisfied candidate (line 92-93) and returns the next
    plannable one. Pure unit test over injected closures — no planner/state."""
    sat_goal = AcceptTaskGoal()
    next_goal = AcceptTaskGoal()
    sat = Candidate(goal=sat_goal, is_means=True, repr_="Satisfied", band=2)
    nxt = Candidate(goal=next_goal, is_means=True, repr_="Next", band=2)

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
    supp = Candidate(goal=supp_goal, is_means=True, repr_="Suppressed", band=2)
    nxt = Candidate(goal=next_goal, is_means=True, repr_="Next", band=2)

    goal, _plan, committed = select_pure(
        [supp, nxt], None,
        try_plan=lambda g: [object()],
        is_satisfied=lambda g: False,
        is_suppressed=lambda g: g is supp_goal,
    )
    assert goal is next_goal
    assert committed == "Next"


def test_select_pure_returns_none_when_nothing_plans():
    """When no candidate plans, select_pure returns the empty result."""
    g = Candidate(goal=AcceptTaskGoal(), is_means=True, repr_="Only", band=2)
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
    fill_monster_stat_defaults(gd)  # craft_potions_fires → unlock_boost_target → predict_win needs full stats
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
        # Bounding lives on the PURSUE_TASK skill-gated path (objective path no
        # longer builds LevelSkillGoal). Task requires weaponcrafting 50, current
        # 1 -> target bounded to current+LEVEL_LOOKAHEAD=4.
        gd = GameData()
        gd._item_stats["copper_bar"] = ItemStats(
            code="copper_bar", type_="resource", level=1,
            crafting_skill="weaponcrafting", crafting_level=50)
        state = make_state(task_code="copper_bar", task_type="items",
                           task_total=20, task_progress=0, skills={"weaponcrafting": 1})
        goal = map_means(MeansKind.PURSUE_TASK, gd, _ctx(), state)
        assert repr(goal) == "ReachSkill(weaponcrafting->4)"   # min(50, 1+3)

    def test_skill_step_caps_at_required_level(self):
        # current+LEVEL_LOOKAHEAD overshoots the gate -> cap at the required level.
        gd = GameData()
        gd._item_stats["copper_bar"] = ItemStats(
            code="copper_bar", type_="resource", level=1,
            crafting_skill="weaponcrafting", crafting_level=50)
        state = make_state(task_code="copper_bar", task_type="items",
                           task_total=20, task_progress=0, skills={"weaponcrafting": 48})
        goal = map_means(MeansKind.PURSUE_TASK, gd, _ctx(), state)
        assert repr(goal) == "ReachSkill(weaponcrafting->50)"   # min(50, 48+3)


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
        assert repr(goal) == "ReachSkill(weaponcrafting->3)"   # min(gate=3, 1+LEVEL_LOOKAHEAD=4) -> 3

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

    def test_items_task_selects_pursue_not_grind(self, tmp_path):
        # copper_bar has no item_stats / recipe in this GameData, so
        # task_requirement is None and the REAL task_decision returns PURSUE
        # even with an empty LearningStore — no patching needed.
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

    def test_meta_step_suppressed_when_redundant_with_task_chain(self, tmp_path):
        """Suppression contract: when an items-task is being pursued AND the
        meta-objective's chosen_step is a GatherMaterials goal whose target
        sits INSIDE the task's recipe chain, the step is suppressed (the
        task's PursueTask plan already gathers it; a separate cycle would
        be a redundant 1-cycle detour).

        Setup: task=ash_plank with recipe ash_plank<-ash_wood. chosen_step
        = ObtainItem(ash_wood) is exactly the input the task chain produces.
        Expected: GatherMaterials(ash_wood) does not appear in goals_tried.

        ash_plank has no item_stats entry (no crafting-skill gate), so
        task_requirement is None and the REAL task_decision returns PURSUE —
        PURSUE_TASK fires without patching."""
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
        assert all(not gt["goal"].startswith("GatherMaterials(ash_wood") for gt in tried), (
            f"ash-wood step is REDUNDANT with the task's own chain — should "
            f"be suppressed, but goals_tried={tried}"
        )

    def test_meta_step_allowed_when_independent_of_task_chain(self, tmp_path):
        """Counterpart contract: when chosen_step's target is NOT in the
        active task's recipe chain, the step is INDEPENDENT progress (e.g.
        gear chain) and must run despite the active task. Pre-refinement,
        14e3830 suppressed the step indiscriminately, which is why Robby
        never crafted gear — every meta-step nudge got dropped.

        Setup: task=copper_bar with recipe copper_bar<-copper_ore.
        chosen_step = ObtainItem(ash_wood) which is unrelated (e.g. for a
        wooden_shield upgrade). Expected: GatherMaterials(ash_wood) appears
        in goals_tried — the step is allowed to compete.

        copper_bar has no item_stats entry (no crafting-skill gate), so the
        REAL task_decision returns PURSUE — PURSUE_TASK fires unpatched."""
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
        assert any(gt["goal"].startswith("GatherMaterials(ash_wood") for gt in tried), (
            f"ash-wood step is INDEPENDENT of the copper_bar task chain — "
            f"should be allowed to compete, but goals_tried={tried}"
        )

    def test_task_trade_ready_suppresses_fallback_gather(self, tmp_path):
        """Trace 2026-06-06 14:40 (cycles 25-26): task=items/copper_bar at
        20/21 with 1 copper_bar in inventory; the gear-chain fallback
        step GatherMaterials(copper_bar, needed=8) for ObtainItem(copper_boots)
        ran INSTEAD of PursueTask's TaskTrade. One trade would complete
        the task; bot gathered MORE copper_ore for armor while the held
        bar sat unused.

        Contract: when fallback step targets the task code AND inventory
        holds at least one unit, the fallback is SUPPRESSED so PursueTask
        wins the cycle and TaskTrade can fire.

        copper_bar has no item_stats entry (no crafting-skill gate), so the
        REAL task_decision returns PURSUE — PURSUE_TASK fires unpatched.
        """
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
        assert not any(a.startswith("GatherMaterials(copper_bar") for a in attempted), (
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
                   [AcceptTaskAction(taskmaster_location=(2, 1))], _ctx(), budget_seconds=1.0)
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


def _gd_skill_gated_chain():
    """copper_legs_armor needs gearcrafting 5 (Robby has 2) — the trace
    2026-06-11 18:46 dead-route shape."""
    gd = GameData()
    gd._item_stats = {
        "copper_legs_armor": ItemStats(code="copper_legs_armor", level=6,
                                       type_="leg_armor",
                                       crafting_skill="gearcrafting",
                                       crafting_level=5),
    }
    gd._crafting_recipes = {"copper_legs_armor": {"copper_bar": 5},
                            "copper_bar": {"copper_ore": 10}}
    return gd


def test_objective_step_skill_gated_root_plans_literal_step():
    """Skill-gated root (gearcrafting 2 < 5) with an intermediate step:
    routing to the ROOT is a dead end (GatherMaterials(root) is rejected by
    its own skill-gate fail-fast — trace 2026-06-11 18:46 cycles 15-16,
    0-node dead candidates, objective abandoned at 1/5 bars). The dispatch
    must plan the LITERAL step instead: its materials are needed regardless,
    and the skill grind follows once they're in hand."""
    gd = _gd_skill_gated_chain()
    state = make_state(level=6, inventory={"copper_ore": 36},
                       skills={"gearcrafting": 2, "mining": 4, "woodcutting": 1,
                               "fishing": 1, "weaponcrafting": 1, "jewelrycrafting": 1,
                               "cooking": 1, "alchemy": 1})
    goal = objective_step_goal(ObtainItem("copper_bar", 5), state, gd, _ctx(),
                               root=ObtainItem("copper_legs_armor", 1))
    assert isinstance(goal, GatherMaterialsGoal)
    assert repr(goal) == "GatherMaterials(copper_bar, {copper_bar:5})"
    # And the goal it returns is actually plannable (bars craft on mining).
    assert goal.is_plannable(state, gd) is True
    assert goal.is_satisfied(state) is False


class _TrivialPlanner:
    """Constructor-injected GOAPPlanner stand-in: plans every goal as a single
    WaitAction (goal types listed in `unplannable` fail instead), so arbiter
    tests exercise the SELECTION logic without a real A* search. The planner is
    a collaborator of StrategyArbiter and arrives through the existing
    constructor parameter — the unit under test is never patched."""

    def __init__(self, unplannable: tuple[type, ...] = ()) -> None:
        self._unplannable = unplannable
        self.last_stats = PlanStats()

    def plan(self, state, goal, actions, game_data, history, budget_seconds=None):
        if isinstance(goal, self._unplannable):
            return []
        return [WaitAction()]


def _worth_gate_gd() -> GameData:
    """GameData for the worth-gate trio: a weaponcrafting craft-one target
    (copper_dagger, non-empty recipe so skill_grind_target selects it), the
    gear-need root (iron_sword), and the active distraction task item
    (cooked_gudgeon, no skill gap so the REAL task_decision PURSUEs)."""
    gd = GameData()
    gd._item_stats = {
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                   crafting_skill="weaponcrafting", crafting_level=1),
        "iron_sword": ItemStats(code="iron_sword", level=10, type_="weapon",
                                crafting_skill="weaponcrafting", crafting_level=10),
        "cooked_gudgeon": ItemStats(code="cooked_gudgeon", level=1, type_="consumable",
                                    crafting_skill="cooking", crafting_level=1),
    }
    gd._crafting_recipes = {"copper_dagger": {"copper_ore": 1},
                            "iron_sword": {"copper_dagger": 6},
                            "cooked_gudgeon": {}}
    # copper_ore is GATHERABLE so the iron_sword need-set has no buy-only
    # leaves (a buy-only need would make ANY income task serve the objective
    # and the worth gate would never suppress PursueTask).
    gd._resource_locations = {"copper_rocks": [(1, 0)]}
    gd._resource_drops = {"copper_rocks": "copper_ore"}
    gd._resource_skill = {"copper_rocks": ("mining", 1)}
    return gd


def test_worth_gate_breaks_sticky_pursue_task(tmp_path):
    """Committed PursueTask that serves no weapon need is worth-suppressed, so the
    sticky short-circuit breaks and the weapon-grind objective step wins.

    Everything except planning runs REAL: active_guards is [] (healthy state),
    active_means fires PURSUE_TASK (items task + empty LearningStore + no skill
    gap → task_decision PURSUEs), and the objective step for copper_dagger (a
    weapon) yields UpgradeEquipment(copper_dagger->weapon_slot)."""
    gd = _worth_gate_gd()
    obj = CharacterObjective(target_char_level=50, target_skill_levels={},
                             target_gear={"weapon_slot": "iron_sword"}, _game_data=gd,
                             target_tools={})
    state = make_state(hp=150, max_hp=150,
                       skills={"weaponcrafting": 1, "cooking": 1},
                       task_type="items", task_code="cooked_gudgeon",
                       task_total=10, task_progress=0)
    decision = type("D", (), {"chosen_step": ObtainItem("copper_dagger", 1),
                              "chosen_root": ObtainItem("iron_sword"),
                              "fallback_steps": [], "fallback_roots": []})()
    ctx = _ctx(combat_monster=None)
    store = LearningStore(db_path=str(tmp_path / "worth_sticky.db"), character="testchar")
    try:
        arbiter = StrategyArbiter(_TrivialPlanner(), history=store)
        # Simulate prior sticky commitment to PursueTask.
        arbiter._committed_repr = repr(sd.map_means(sd.MeansKind.PURSUE_TASK, gd, ctx, state))
        goal, _plan, _tried = arbiter.select(decision, state, gd, [], ctx, objective=obj)
    finally:
        store.close()
    assert isinstance(goal, UpgradeEquipmentGoal)
    assert repr(goal) == "UpgradeEquipment(copper_dagger->weapon_slot)"


def test_worth_gate_bypassed_last_resort_selects_task_when_step_unplannable(tmp_path):
    """Last-resort pass: the objective step cannot plan AND the only means are
    worth-suppressed task means. The worth gate suppresses PursueTask, the step
    fails, so the ungated re-run selects PursueTask and appends the
    `worth_gate_bypassed` trace marker (the bot earns instead of idling).

    Same real-fixture setup as test_worth_gate_breaks_sticky_pursue_task; the
    injected planner fails the objective-step UpgradeEquipment goal and plans
    everything else."""
    gd = _worth_gate_gd()
    obj = CharacterObjective(target_char_level=50, target_skill_levels={},
                             target_gear={"weapon_slot": "iron_sword"}, _game_data=gd,
                             target_tools={})
    state = make_state(hp=150, max_hp=150,
                       skills={"weaponcrafting": 1, "cooking": 1},
                       task_type="items", task_code="cooked_gudgeon",
                       task_total=10, task_progress=0)
    decision = type("D", (), {"chosen_step": ObtainItem("copper_dagger", 1),
                              "chosen_root": ObtainItem("iron_sword"),
                              "fallback_steps": [], "fallback_roots": []})()
    ctx = _ctx(combat_monster=None)
    store = LearningStore(db_path=str(tmp_path / "worth_bypass.db"), character="testchar")
    try:
        arbiter = StrategyArbiter(
            _TrivialPlanner(unplannable=(UpgradeEquipmentGoal,)), history=store)
        goal, _plan, tried = arbiter.select(decision, state, gd, [], ctx, objective=obj)
    finally:
        store.close()
    assert repr(goal).startswith("PursueTask")
    assert any(t["goal"] == "worth_gate_bypassed" for t in tried)


def test_no_objective_keeps_committed_pursue_task(tmp_path):
    """Control: with NO objective (no worth gate), the committed PursueTask still
    wins via sticky — proving the suppression, not ordering, caused the switch.

    Same real-fixture setup as test_worth_gate_breaks_sticky_pursue_task: the
    weapon-grind step GatherMaterials(copper_dagger) is present and plannable,
    but the sticky committed task is tried first and kept."""
    gd = _worth_gate_gd()
    state = make_state(hp=150, max_hp=150,
                       skills={"weaponcrafting": 1, "cooking": 1},
                       task_type="items", task_code="cooked_gudgeon",
                       task_total=10, task_progress=0)
    decision = type("D", (), {"chosen_step": ObtainItem("copper_dagger", 1),
                              "chosen_root": ObtainItem("iron_sword"),
                              "fallback_steps": [], "fallback_roots": []})()
    ctx = _ctx(combat_monster=None)
    pursue = sd.map_means(sd.MeansKind.PURSUE_TASK, gd, ctx, state)
    store = LearningStore(db_path=str(tmp_path / "no_obj.db"), character="testchar")
    try:
        arbiter = StrategyArbiter(_TrivialPlanner(), history=store)
        arbiter._committed_repr = repr(pursue)
        goal, _plan, _tried = arbiter.select(decision, state, gd, [], ctx)  # objective=None
    finally:
        store.close()
    assert repr(goal) == repr(pursue)  # committed task kept (sticky), no worth gate


def test_equip_step_uses_root_slot_for_second_ring():
    """A slot-tagged ring2 gear root equips copper_ring into ring2_slot (not the
    type's first slot), so a 2nd copper_ring fills the empty second ring slot."""
    gd = GameData()
    gd._item_stats = {"copper_ring": ItemStats(code="copper_ring", level=1, type_="ring",
                                               attack={"fire": 2})}
    gd._crafting_recipes = {"copper_ring": {"bar": 1}}
    gd._resource_drops = {"rocks": "bar"}
    # ring1 already worn; a spare copper_ring in inventory to equip into ring2.
    state = make_state(level=5, inventory={"copper_ring": 1},
                       equipment={"ring1_slot": "copper_ring"})
    step = ObtainItem("copper_ring", slot="ring2_slot")
    g = objective_step_goal(step, state, gd, _ctx(), root=step)
    assert isinstance(g, UpgradeEquipmentGoal)
    assert g._committed_target == ("copper_ring", "ring2_slot")


def test_arbiter_equips_second_ring_into_empty_slot():
    """Reported 2026-06-14: copper_ring worn in ring1, spare in inventory, ring2
    empty -> the spare is ACTUALLY equippable into ring2_slot and the projected
    result wears copper_ring in BOTH ring slots. Before the 2026-06-14 carve-out
    the one-slot-per-code guard rejected this and the dual-ring feature was inert
    (this asserted only that the root was chosen); the live server returns HTTP
    200 for a duplicate ring."""
    gd = GameData()
    gd._item_stats = {"copper_ring": ItemStats(code="copper_ring", level=1, type_="ring",
                                               attack={"fire": 6})}
    gd._crafting_recipes = {"copper_ring": {"bar": 1}}
    gd._resource_drops = {"rocks": "bar"}
    gd._resource_skill = {"rocks": ("mining", 1)}
    obj = CharacterObjective.from_game_data(gd)
    state = make_state(level=5, inventory={"copper_ring": 1},
                       equipment={"ring1_slot": "copper_ring"})
    # The arbiter targets the empty ring2 slot...
    eng = StrategyEngine(obj, BalancedPersonality())
    d = eng.decide(state, gd)
    assert d.chosen_root == ObtainItem("copper_ring", slot="ring2_slot")
    # ...and the equip is ACTUALLY applicable + lands the ring in ring2_slot.
    # (This is what was inert before the guard carve-out — it must FAIL on the
    # pre-2026-06-14 guard and PASS now.)
    equip = EquipAction(code="copper_ring", slot="ring2_slot")
    assert equip.is_applicable(state, gd) is True
    result = equip.apply(state, gd)
    assert result.equipment["ring2_slot"] == "copper_ring"
    assert result.equipment["ring1_slot"] == "copper_ring"


def test_second_ring_not_equippable_without_a_spare():
    """Realizability boundary (mirrors Lean pickLoadout_single_ring_no_dup_fill):
    copper_ring worn in ring1 with NO spare in inventory -> the 2nd-slot equip is
    NOT applicable. The rings carve-out must not produce an unrealizable double-
    equip when only one copy is owned."""
    gd = GameData()
    gd._item_stats = {"copper_ring": ItemStats(code="copper_ring", level=1, type_="ring",
                                               attack={"fire": 6})}
    state = make_state(level=5, inventory={},
                       equipment={"ring1_slot": "copper_ring"})
    equip = EquipAction(code="copper_ring", slot="ring2_slot")
    assert equip.is_applicable(state, gd) is False


def test_non_ring_keeps_one_slot_per_code():
    """The carve-out is rings-only: a non-ring code worn in one slot is still
    NOT equippable into a sibling slot (server HTTP 485) even with spare copies —
    e.g. a 2nd small_health_potion into utility2 while utility1 wears it. Proves
    the relaxation did not over-broaden past DUPLICATE_SLOT_TYPES."""
    gd = GameData()
    gd._item_stats = {"small_health_potion": ItemStats(
        code="small_health_potion", level=1, type_="utility")}
    state = make_state(level=5, inventory={"small_health_potion": 5},
                       equipment={"utility1_slot": "small_health_potion"})
    equip = EquipAction(code="small_health_potion", slot="utility2_slot")
    assert equip.is_applicable(state, gd) is False


# ---------------------------------------------------------------------------
# objective_step_goal depth-routing: feather_coat (deep chain)
# ---------------------------------------------------------------------------

def _gd_feather_coat() -> GameData:
    """feather_coat body armour (gearcrafting-5): needs ash_plank×2 + feather×5.
    feather is a monster drop (no crafting recipe). ash_plank is woodcrafted
    from ash_wood×20. With ash_wood×10 in inventory, the full chain still needs
    30 more ash_wood (2 planks × 20 = 40 total, minus 10 owned = 30 remaining)
    plus 5 feathers = 35 raw gathers; add crafts + 1 equip → min_plan_length far
    exceeds max_depth 32 → UpgradeEquipmentGoal.is_plannable returns False by
    depth-reject alone.
    The router must fall through to branch-3 (GatherMaterials on the step)."""
    gd = GameData()
    gd._item_stats = {
        "feather_coat": ItemStats(code="feather_coat", level=5, type_="body_armor",
                                  crafting_skill="gearcrafting", crafting_level=5),
        "ash_plank": ItemStats(code="ash_plank", level=1, type_="resource",
                               crafting_skill="woodcutting", crafting_level=1),
        "ash_wood": ItemStats(code="ash_wood", level=1, type_="resource"),
        "feather": ItemStats(code="feather", level=1, type_="resource"),
    }
    gd._crafting_recipes = {
        "feather_coat": {"ash_plank": 2, "feather": 5},
        "ash_plank": {"ash_wood": 20},
    }
    gd._resource_drops = {"ash_tree": "ash_wood"}
    gd._resource_skill = {"ash_tree": ("woodcutting", 1)}
    return gd


def test_deep_gear_routes_to_incremental_gather_not_empty_upgrade():
    """feather_coat from scratch: objective_step_goal returns a GatherMaterials
    step (incremental progress), not the over-deep UpgradeEquipment.

    Recipe: feather_coat = {ash_plank:2, feather:5}, ash_plank = {ash_wood:20}.
    With ash_wood×10 in inventory: need 30 more ash_wood + 5 feathers = 35 gathers
    + crafts + 1 equip ≫ max_depth 32. UpgradeEquipmentGoal.is_plannable
    returns False by depth-reject ALONE (no extra guard needed). The router must
    reach branch-3 (gather_step_target → GatherMaterialsGoal)."""
    gd = _gd_feather_coat()
    state = make_state(
        skills={"gearcrafting": 5, "woodcutting": 3},
        inventory={"ash_wood": 10},
        equipment={"body_armor_slot": None},
        bank_items={},
    )
    step = ObtainItem("ash_plank", 2)
    root = ObtainItem("feather_coat", 1, slot="body_armor_slot")
    # Confirm WHY it routes: depth-reject (≫ max_depth 32), not a fixture artifact.
    upgrade = UpgradeEquipmentGoal(initial_equipment=state.equipment,
                                   committed_target=("feather_coat", "body_armor_slot"))
    assert upgrade.is_plannable(state, gd) is False, (
        "is_plannable must be False (min_plan_length ≫ max_depth 32) "
        "so the depth-reject — not any extra guard — drives the route"
    )
    goal = objective_step_goal(step, state, gd, _ctx(), root=root, committed_root=root)
    assert goal is not None
    assert type(goal).__name__ == "GatherMaterialsGoal"


# ---------------------------------------------------------------------------
# _marginal_provision_goal routing tests (Task 8)
# ---------------------------------------------------------------------------

def _record_mixed(history: LearningStore, action_repr: str, wins: int, losses: int) -> None:
    """Seed the history DB with win+loss cycles for action_repr."""
    session_id = history.start_session()
    for i in range(wins):
        history.record_cycle(Cycle(
            ts=f"2026-01-01T00:{i:02d}:00+00:00",
            session_id=session_id, cycle_index=i,
            character="r", action_repr=action_repr, outcome="ok",
        ))
    for j in range(losses):
        history.record_cycle(Cycle(
            ts=f"2026-01-01T01:{j:02d}:00+00:00",
            session_id=session_id, cycle_index=wins + j,
            character="r", action_repr=action_repr, outcome="fail",
        ))


def _record_fight_wins_with_consumables(
    history: LearningStore, monster_code: str, n: int,
    consumables_json: str,
) -> None:
    """Seed n winning Fight(monster_code) cycles each with consumables_expended_json."""
    session_id = history.start_session()
    for i in range(n):
        history.record_cycle(Cycle(
            ts=f"2026-01-02T00:{i:02d}:00+00:00",
            session_id=session_id, cycle_index=i,
            character="r", action_repr=f"Fight({monster_code})", outcome="ok",
            consumables_expended_json=consumables_json,
        ))


def _gd_with_utility_heal(code: str, hp_restore: int) -> GameData:
    """Utility-slot-equippable heal (type=utility): the only kind best_held_heal
    can provision into a utility slot."""
    gd = GameData()
    gd._item_stats = {code: ItemStats(code=code, level=1, type_="utility",
                                      hp_restore=hp_restore)}
    return gd


def _gd_with_food(code: str, hp_restore: int) -> GameData:
    """Eaten heal (type=consumable): carries hp_restore but is NOT utility-slot
    equippable, so it can never back a ProvisionMarginalFightGoal."""
    gd = GameData()
    gd._item_stats = {code: ItemStats(code=code, level=1, type_="consumable",
                                      hp_restore=hp_restore)}
    return gd


# Both tests below rely on make_state's default empty utility slots (no explicit equipment kwarg).
def test_marginal_target_routes_to_provision_goal(tmp_path):
    state = make_state(level=3, inventory={"small_health_potion": 100})
    gd = _gd_with_utility_heal("small_health_potion", hp_restore=60)
    history = LearningStore(db_path=str(tmp_path / "l.db"), character="r")
    # Seed 8 wins each consuming 2 potions at 60 HP restore = 120 HP healed → qty = ceil(120/60) = 2
    _record_fight_wins_with_consumables(
        history, "green_slime", 8,
        json.dumps({"small_health_potion": 2}),
    )
    ctx = _ctx(combat_monster="green_slime")
    goal = objective_step_goal(ReachCharLevel(level=5), state, gd, ctx, history=history)
    assert isinstance(goal, ProvisionMarginalFightGoal)
    history.close()


def test_reliable_target_still_grinds(tmp_path):
    state = make_state(level=3, inventory={"small_health_potion": 100})
    gd = _gd_with_utility_heal("small_health_potion", hp_restore=60)
    history = LearningStore(db_path=str(tmp_path / "l.db"), character="r")
    # no consumables_expended_json → learned HP-need=0; no monster entry → expected_damage=0 → qty=0 → grind
    _record_mixed(history, "Fight(green_slime)", wins=20, losses=0)
    ctx = _ctx(combat_monster="green_slime")
    goal = objective_step_goal(ReachCharLevel(level=5), state, gd, ctx, history=history)
    assert isinstance(goal, GrindCharacterXPGoal)
    history.close()


def test_utility_slot_already_filled_routes_to_grind(tmp_path) -> None:
    """_marginal_provision_goal early-exits when a utility slot is already occupied."""
    equipment = {
        "weapon_slot": None, "shield_slot": None, "helmet_slot": None,
        "body_armor_slot": None, "leg_armor_slot": None, "boots_slot": None,
        "ring1_slot": None, "ring2_slot": None, "amulet_slot": None,
        "artifact1_slot": None, "artifact2_slot": None, "artifact3_slot": None,
        "utility1_slot": "small_health_potion", "utility2_slot": None,
        "bag_slot": None, "rune_slot": None,
    }
    state = make_state(level=3, inventory={"small_health_potion": 100},
                       equipment=equipment)
    gd = _gd_with_utility_heal("small_health_potion", hp_restore=60)
    history = LearningStore(db_path=str(tmp_path / "l.db"), character="r")
    _record_mixed(history, "Fight(green_slime)", wins=8, losses=2)  # 80% < 0.95
    ctx = _ctx(combat_monster="green_slime")
    goal = objective_step_goal(ReachCharLevel(level=5), state, gd, ctx, history=history)
    assert isinstance(goal, GrindCharacterXPGoal)
    history.close()


def test_marginal_target_with_only_consumable_heal_routes_to_grind(tmp_path) -> None:
    """An L3 char holding ONLY a consumable-type food (eaten heal, not utility-
    slot equippable) against a marginal target must NOT build a provision goal
    (its equip would be unapplicable) — it falls through to an unprovisioned
    grind, never to discretionary gear (the copper_helmet livelock)."""
    state = make_state(level=3, inventory={"cooked_fish": 100})
    gd = _gd_with_food("cooked_fish", hp_restore=60)
    history = LearningStore(db_path=str(tmp_path / "l.db"), character="r")
    _record_mixed(history, "Fight(green_slime)", wins=8, losses=2)  # 80% < 0.95
    ctx = _ctx(combat_monster="green_slime")
    goal = objective_step_goal(ReachCharLevel(level=5), state, gd, ctx, history=history)
    assert isinstance(goal, GrindCharacterXPGoal)
    history.close()


def test_no_heal_held_routes_to_grind(tmp_path) -> None:
    """_marginal_provision_goal early-exits when inventory holds no heal."""
    state = make_state(level=3, inventory={})  # no heal on hand
    gd = _gd_with_utility_heal("small_health_potion", hp_restore=60)
    history = LearningStore(db_path=str(tmp_path / "l.db"), character="r")
    _record_mixed(history, "Fight(green_slime)", wins=8, losses=2)
    ctx = _ctx(combat_monster="green_slime")
    goal = objective_step_goal(ReachCharLevel(level=5), state, gd, ctx, history=history)
    assert isinstance(goal, GrindCharacterXPGoal)
    history.close()


def test_marginal_provision_uses_learned_hp_need(tmp_path) -> None:
    """_marginal_provision_goal sizes qty from learned HP-need (ceil(healed/restore))."""
    heal_code = "small_health_potion"
    store = LearningStore(db_path=str(tmp_path / "l.db"), character="r")
    # 5 wins, each consuming 3 potions at 30 HP restore = 90 HP healed avg
    _record_fight_wins_with_consumables(
        store, "red_slime", 5, json.dumps({heal_code: 3})
    )
    gd = GameData()
    gd._item_stats = {heal_code: ItemStats(code=heal_code, level=1, type_="utility",
                                           hp_restore=30)}
    state = make_state(level=5, inventory={heal_code: 10})
    ctx = _ctx(combat_monster="red_slime")
    goal = sd._marginal_provision_goal(ctx, state, gd, store)
    assert isinstance(goal, ProvisionMarginalFightGoal)
    assert goal._quantity == 3  # ceil(90 / 30) = 3
    store.close()


def test_marginal_provision_seeds_from_expected_damage_when_cold(tmp_path) -> None:
    """When no history exists for the monster, qty = ceil(expected_damage / restore)."""
    heal_code = "small_health_potion"
    store = LearningStore(db_path=str(tmp_path / "l.db"), character="r")
    store.start_session()
    # No Fight(red_slime) cycles — cold store for this monster

    gd = GameData()
    gd._item_stats = {heal_code: ItemStats(code=heal_code, level=1, type_="utility",
                                           hp_restore=30)}
    # Monster: fire attack=10, HP=30, no resistance, crit=0 → expected_damage=30
    # (monster_per_turn = _element_damage(10,0,0) = 10; player hits same → 3 rounds)
    gd._monster_level = {"red_slime": 3}
    gd._monster_hp = {"red_slime": 30}
    gd._monster_attack = {"red_slime": {"fire": 10}}
    gd._monster_resistance = {"red_slime": {}}
    gd._monster_critical_strike = {"red_slime": 0}
    gd._monster_initiative = {"red_slime": 0}
    gd._monster_type = {"red_slime": "normal"}

    # Player has matching fire attack so player_kill_step > 0
    state = make_state(level=5, inventory={heal_code: 10}, attack={"fire": 10})
    ctx = _ctx(combat_monster="red_slime")
    goal = sd._marginal_provision_goal(ctx, state, gd, store)
    assert isinstance(goal, ProvisionMarginalFightGoal)
    # expected_damage = round(10) * ceil(30/10) = 10 * 3 = 30 → qty = ceil(30/30) = 1
    assert goal._quantity == 1
    store.close()


def test_marginal_provision_sizes_by_equipped_potion_not_held_food(tmp_path) -> None:
    """qty = ceil(hp_need / potion_restore), NOT ceil(hp_need / food_restore).

    When the inventory also holds a food item (type=consumable) with a HIGHER
    hp_restore than the equipped utility potion, best_held_heal_restore would
    overstate the restore and produce qty=2 (ceil(90/60)).  The fix sizes by
    game_data.hp_restore_of(heal_code) — the equipped potion's own restore —
    giving qty=3 (ceil(90/30))."""
    heal_code = "small_health_potion"
    food_code = "cooked_chicken"
    store = LearningStore(db_path=str(tmp_path / "l.db"), character="r")
    # 5 wins, each consuming 3 potions at 30 HP restore = 90 HP healed avg
    _record_fight_wins_with_consumables(
        store, "red_slime", 5, json.dumps({heal_code: 3})
    )
    gd = GameData()
    gd._item_stats = {
        heal_code: ItemStats(code=heal_code, level=1, type_="utility", hp_restore=30),
        food_code: ItemStats(code=food_code, level=1, type_="consumable", hp_restore=60),
    }
    # Both held in inventory — food's hp_restore (60) is higher than potion's (30)
    state = make_state(level=5, inventory={heal_code: 10, food_code: 5})
    ctx = _ctx(combat_monster="red_slime")
    goal = sd._marginal_provision_goal(ctx, state, gd, store)
    assert isinstance(goal, ProvisionMarginalFightGoal)
    # Must be 3 = ceil(90/30), sized by the POTION's restore — NOT 2 = ceil(90/60)
    assert goal._quantity == 3
    store.close()


def _vendor_bag_gd() -> GameData:
    """A recipe-less, NPC-only equippable (bag) sold for a monster-drop
    currency by a permanent vendor — the sandwhisper_bag shape."""
    gd = GameData()
    gd._item_stats = {
        "dune_bag": ItemStats(code="dune_bag", level=1, type_="bag",
                              inventory_space=10),
    }
    gd._npc_stock = {"dune_trader": {"dune_bag": 3}}
    gd._npc_buy_currency = {"dune_trader": {"dune_bag": "dune_coin"}}
    gd._npc_locations = {"dune_trader": (4, 1)}
    gd._monster_level = {"dune_rat": 1}
    gd._monster_hp = {"dune_rat": 10}
    gd._monster_locations = {"dune_rat": (2, 2)}
    fill_monster_stat_defaults(gd)
    gd._monster_drops = {"dune_rat": [("dune_coin", 50, 1, 1)]}
    return gd


def test_equippable_goal_routes_unowned_vendor_only_item_to_currency_grind():
    """An UNOWNED, recipe-less, NPC-buy-only equippable with the currency
    NOT yet affordable must map to an INCREMENTAL currency accumulation
    (needed = held+1, the grind-one-replan idiom): a one-shot plan for a
    230-coin price is ~120 fights deep and dies on max_depth
    (sandwhisper_bag probe 2026-07-06 @L50: 28K nodes, plan_len=0), while
    UpgradeEquipment's closure lock could never emit the buy at all."""
    gd = _vendor_bag_gd()
    state = make_state(level=5, attack={"air": 50}, inventory={}, bank_items={})
    goal = objective_step_goal(ObtainItem("dune_bag", 1, slot="bag_slot"),
                               state, gd, _ctx(), root=ObtainItem("dune_bag", 1, slot="bag_slot"))
    assert isinstance(goal, GatherMaterialsGoal), repr(goal)
    assert goal.needed == {"dune_coin": 1}, repr(goal)


def test_equippable_goal_routes_affordable_vendor_only_item_to_buy():
    """Currency in hand (>= price): the goal targets the item itself — its
    Task-13 currency injection emits the single NpcBuy leg."""
    gd = _vendor_bag_gd()
    state = make_state(level=5, attack={"air": 50},
                       inventory={"dune_coin": 3}, bank_items={})
    goal = objective_step_goal(ObtainItem("dune_bag", 1, slot="bag_slot"),
                               state, gd, _ctx(), root=ObtainItem("dune_bag", 1, slot="bag_slot"))
    assert isinstance(goal, GatherMaterialsGoal), repr(goal)
    assert goal.needed == {"dune_bag": 1}, repr(goal)


def test_equippable_goal_keeps_upgrade_path_when_vendor_item_owned():
    """Once the vendor item is IN HAND the normal UpgradeEquipment equip
    path applies (withdraw/equip are in its closure lock)."""
    gd = _vendor_bag_gd()
    state = make_state(level=5, attack={"air": 50},
                       inventory={"dune_bag": 1}, bank_items={})
    goal = objective_step_goal(ObtainItem("dune_bag", 1, slot="bag_slot"),
                               state, gd, _ctx(), root=ObtainItem("dune_bag", 1, slot="bag_slot"))
    assert isinstance(goal, UpgradeEquipmentGoal), repr(goal)
