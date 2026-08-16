"""Tier-3 → planner bridge: map the strategy's chosen step to a parameterized
existing goal.

Lives above goals/ and tiers/ (imports both) to avoid the goals→tiers cycle."""

import time
from dataclasses import replace
from datetime import datetime, timezone

from artifactsmmo_cli.ai.accumulation_sell import bank_sellable_surplus, sell_targets
from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.actions.wait import WaitAction
from artifactsmmo_cli.ai.arbiter_select import (
    BAND_COLLECT,
    BAND_DISCRETIONARY,
    BAND_FALLBACK_STEP,
    BAND_GUARD,
    BAND_STEP,
    Candidate,
    select_pure,
)
from artifactsmmo_cli.ai.bank_drain import bank_drain_excess
from artifactsmmo_cli.ai.consumable_supply import best_held_heal
from artifactsmmo_cli.ai.craft_plan_gen import _closure_items, generate_next_craft_action
from artifactsmmo_cli.ai.craft_relief import craft_relief_candidates
from artifactsmmo_cli.ai.currency_grind_target import currency_grind_target_pure
from artifactsmmo_cli.ai.destructive_license import license_destructive_actions
from artifactsmmo_cli.ai.doomed_memo import DoomedMemo
from artifactsmmo_cli.ai.equipment.bank_tool_fills import bank_tool_fills
from artifactsmmo_cli.ai.equipment.empty_slot_fills import empty_slot_rank_fills
from artifactsmmo_cli.ai.event_plan_window import plan_fits_event_window
from artifactsmmo_cli.ai.expected_damage import expected_damage_per_fight
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gather_step_target import gather_step_target
from artifactsmmo_cli.ai.goals.accept_task_goal import AcceptTaskGoal
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.goals.cancel_orders import CancelOrdersGoal
from artifactsmmo_cli.ai.goals.claim_pending import ClaimPendingGoal
from artifactsmmo_cli.ai.goals.complete_task_goal import CompleteTaskGoal
from artifactsmmo_cli.ai.goals.craft_potions import CraftPotionsGoal
from artifactsmmo_cli.ai.goals.craft_relief import CraftReliefGoal
from artifactsmmo_cli.ai.goals.currency_demand import analyze_currency_leaves
from artifactsmmo_cli.ai.goals.deposit_inventory import DepositInventoryGoal
from artifactsmmo_cli.ai.goals.discard_overstock import DiscardOverstockGoal
from artifactsmmo_cli.ai.goals.drain_bank_junk import DrainBankJunkGoal
from artifactsmmo_cli.ai.goals.equip_owned_gear import EquipOwnedGoal
from artifactsmmo_cli.ai.goals.expand_bank import ExpandBankGoal
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.grind_character_xp import GrindCharacterXPGoal
from artifactsmmo_cli.ai.goals.low_yield_cancel import LowYieldCancelGoal
from artifactsmmo_cli.ai.goals.maintain_consumables import MaintainConsumablesGoal
from artifactsmmo_cli.ai.goals.participate_raid import ParticipateRaidGoal
from artifactsmmo_cli.ai.goals.post_buy_bid import PostBuyBidGoal
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from artifactsmmo_cli.ai.goals.provision_marginal_fight import ProvisionMarginalFightGoal
from artifactsmmo_cli.ai.goals.pursue_task import PursueTaskGoal
from artifactsmmo_cli.ai.goals.reach_currency import ReachCurrencyGoal
from artifactsmmo_cli.ai.goals.reach_skill import ReachSkillGoal
from artifactsmmo_cli.ai.goals.reach_unlock_level import ReachUnlockLevelGoal
from artifactsmmo_cli.ai.goals.recycle_surplus import RecycleSurplusGoal
from artifactsmmo_cli.ai.goals.restore_hp import RestoreHPGoal
from artifactsmmo_cli.ai.goals.sell_inventory import SellInventoryGoal
from artifactsmmo_cli.ai.goals.supply_bank import SupplyBankGoal
from artifactsmmo_cli.ai.goals.task_cancel import TaskCancelGoal
from artifactsmmo_cli.ai.goals.task_exchange import TaskExchangeGoal, tasks_coin_total
from artifactsmmo_cli.ai.goals.unlock_bank import UnlockBankGoal
from artifactsmmo_cli.ai.goals.wait import WaitGoal
from artifactsmmo_cli.ai.goals.withdraw_tools import WithdrawToolsGoal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.objective_step_fight_core import objective_step_is_fight_pure
from artifactsmmo_cli.ai.obtain_sources import Source, obtain_source_map
from artifactsmmo_cli.ai.planner import _SEARCH_BUDGET_SECONDS, GOAPPlanner
from artifactsmmo_cli.ai.potion_provision_qty import potion_provision_qty_pure
from artifactsmmo_cli.ai.raid_participation import raid_survivable_pure
from artifactsmmo_cli.ai.recycle_surplus import recyclable_surplus
from artifactsmmo_cli.ai.requirement_projections import demand_set
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.shed_urgency import bank_shed_hoist, shed_urgency
from artifactsmmo_cli.ai.task_batch import task_batch_size
from artifactsmmo_cli.ai.task_feasibility import task_requirement
from artifactsmmo_cli.ai.task_reservation import consumes_reserved, task_reserved_demand
from artifactsmmo_cli.ai.thresholds import UTILITY_SLOT_MAX_STACK
from artifactsmmo_cli.ai.tiers.guards import (
    GuardKind,
    SelectionContext,
    _used_fraction,
    active_guards,
    deposit_context,
)
from artifactsmmo_cli.ai.tiers.means import (
    SELL_PRESSURE_FRACTION,
    MeansKind,
    active_means,
    means_fires,
)
from artifactsmmo_cli.ai.tiers.means_worth import means_serves
from artifactsmmo_cli.ai.tiers.meta_goal import (
    MetaGoal,
    ObtainItem,
    ReachCharLevel,
)
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective, _permanent_vendor_purchases
from artifactsmmo_cli.ai.tiers.objective_needs import objective_needs
from artifactsmmo_cli.ai.tiers.strategy import actionable_step
from artifactsmmo_cli.ai.tiers.taskmaster_choice import choose_taskmaster
from artifactsmmo_cli.ai.world_state import WorldState

RECYCLE_HOIST_URGENCY = 2
"""Urgency multiple (see `ai/shed_urgency.shed_urgency`: every 5 surplus copies
of the largest pile = +1x) at which RecycleSurplus is materialized in the COLLECT
band instead of waiting in the starved discretionary tier — i.e. >5 spares of the
grind output. Below it, the pile is normal working slack."""

SHED_HOIST_URGENCY = RECYCLE_HOIST_URGENCY
"""The SAME threshold, for the BAG-side half of the SELL_IDLE hoist added on
2026-08-05 (part 2 of the disposal-unification epic).

BOUND, NOT RE-TYPED. Both rungs ask one question of one population ("is this
BAG-held pile past normal working slack?") on one ladder (`ai/shed_urgency`), so
two literals would be two chances to drift. The name is separate because they are
separate decisions and a future tuning of one must be a visible edit.

The BANK-side halves (the SELL_IDLE bank arm and the whole of DRAIN_BANK_JUNK)
deliberately do NOT use this threshold — they cost a round trip and are gated on
a full bag-load instead. See `ai/shed_urgency.bank_shed_hoist_pure`.

WHY A THRESHOLD AT ALL — it is what keeps the hoist CONDITIONAL. These candidates
are materialized in the COLLECT band, ABOVE the objective step, so an
unconditional hoist would outrank progression on every cycle forever."""

LEVEL_LOOKAHEAD = 3
"""How many levels ahead the objective step / task skill-gate targets, replacing
the old hard current+1. The planner re-plans every cycle and executes only
plan[0], so this steers search reachability/direction, not commitment. Tunable:
raise toward 5 if traces show 90s-budget headroom; deeper risks a no_plan
timeout on a long recipe chain."""


def _task_recipe_inputs(task_code: str | None, game_data: GameData) -> frozenset[str]:
    """All items the task's recipe transitively depends on (just the input
    set, not their quantities). Used to detect when an objective-step
    GatherMaterials goal is REDUNDANT with the active PursueTask — the task's
    own plan already gathers/crafts those items, so a separate meta-step for
    one of them is the marginal 1-cycle detour `step_suppression` guards
    against. An input that lives OUTSIDE the task chain (e.g. ash_wood for
    a wooden_shield while the task is copper_ore) is genuinely independent
    progress and must NOT be suppressed."""
    if not task_code:
        return frozenset()
    chain: set[str] = set()
    queue: list[str] = [task_code]
    while queue:
        code = queue.pop()
        recipe = game_data.crafting_recipe(code) or {}
        for mat in recipe:
            if mat in chain:
                continue
            chain.add(mat)
            queue.append(mat)
    return frozenset(chain)

def _reservation_consumption(step_goal: Goal, state: WorldState,
                             game_data: GameData) -> dict[str, int] | None:
    """The item->qty map a step-tier goal would CONSUME from the material
    pipeline, or None when it consumes nothing reservation-relevant.

    * GatherMaterialsGoal: its `needed` map (the craft closure is expanded by
      `consumes_reserved`).
    * UpgradeEquipmentGoal with a committed target NOT yet owned: the target's
      direct recipe (the craft+equip plan consumes those inputs). An owned
      copy is a ONE-action equip that consumes no materials — never deferred
      (preserves the trace-2026-06-06 ready-to-equip priority).
    * Anything else: None.
    """
    if isinstance(step_goal, GatherMaterialsGoal):
        return step_goal._needed
    if isinstance(step_goal, UpgradeEquipmentGoal):
        target = step_goal._committed_target
        if target is None:
            return None
        item, _slot = target
        bank = state.bank_items or {}
        if state.inventory.get(item, 0) + bank.get(item, 0) > 0:
            return None
        recipe = game_data.crafting_recipe(item) or {}
        return recipe or None
    return None


GRIND_BAG_RESERVE = 3
"""Bag reserve for a skill-XP grind gather's byproduct drop. A grind gather's
`needed` is `held + 1` (inventory + BANK), a perpetual never-satisfied target
whose DROP is a byproduct, not a demand — using it as the bag protection floor
locked the whole growing pile in the bag (live Robby: 137 sunflower, 114/114
full, during the alchemy L1->L5 grind). We instead protect only this small
reserve so surplus banks (re-withdrawable, and bank stock still counts toward
`held` so the grind keeps gathering for XP). Matches `inventory_caps.SAFETY_FLOOR`
intent: keep just enough not to re-gather what was banked."""


def _step_protection_profile(step_goal: Goal | None, state: WorldState,
                             game_data: GameData) -> dict[str, int] | None:
    """The resolved step goal's item->qty protection map for deposit/discard,
    or None when the step protects nothing.

    A GatherMaterialsGoal contributes its `needed` map PLUS the recipe closure
    of each needed item's still-missing quantity — the inputs the in-flight
    craft chain is accumulating. Run-5 trace 2026-06-11 23:05 (cycle 10):
    protecting only the target wooden_shield let DepositAll bank all ~59
    ash_wood the chain needed, costing a 14-cycle withdraw round-trip. Only
    the MISSING quantity's closure is protected (not needed × full closure) so
    already-held targets don't over-reserve input stock and paralyze deposit.
    Bank stock counts toward held: banked materials are withdrawable, the
    protection only has to stop the bag's working set from being banked."""
    if not isinstance(step_goal, GatherMaterialsGoal):
        return None
    profile = dict(step_goal.needed)
    bank = state.bank_items or {}
    for code, qty in step_goal.needed.items():
        missing = qty - state.inventory.get(code, 0) - bank.get(code, 0)
        if missing <= 0:
            continue
        chain = dict(demand_set(
            game_data.requirement_graph.graph(), [code], {code: missing}).quantities)
        for mat, mat_qty in chain.items():
            if mat_qty > profile.get(mat, 0):
                profile[mat] = mat_qty
    if step_goal.skill_grind:
        # The grind's `needed` target is `held + 1` (a perpetual XP-grind hack,
        # not a real demand); its drop is a byproduct. Cap the bag reserve so
        # surplus banks instead of locking the whole growing pile in the bag —
        # bank stock still counts toward `held`, so the grind keeps gathering.
        for code in step_goal.needed:
            profile[code] = min(profile[code], GRIND_BAG_RESERVE)
    return profile


def _materials_in_hand(item: str, state: WorldState, game_data: GameData) -> bool:
    """True if every direct recipe material for `item` is fully covered by
    inventory + bank (so the craft+equip plan is short and reachable)."""
    recipe = game_data.crafting_recipe(item) or {}
    bank = state.bank_items or {}
    return bool(recipe) and all(
        state.inventory.get(mat, 0) + bank.get(mat, 0) >= qty for mat, qty in recipe.items())


# ---------------------------------------------------------------------------
# Flat map functions + StrategyArbiter
# ---------------------------------------------------------------------------

def map_guard(kind: GuardKind, game_data: GameData, ctx: SelectionContext,
              state: WorldState | None = None,
              step_profile: dict[str, int] | None = None,
              history: LearningStore | None = None) -> Goal:
    """Map a GuardKind to a parameterized Goal instance.

    `state` is required for CRAFT_RELIEF (which inspects current inventory
    to pick its craft target); optional otherwise to preserve legacy
    callers / tests that constructed guards without a state.

    `step_profile` is the resolved step goal's needed map; it must reach the
    deposit/discard goals through the SAME `deposit_context` merge the firing
    predicate used (trace 2026-06-11 22:36 cycle 30: DiscardOverstock deleted
    the active grind goal's own wooden_shield), so predicate and goal stay
    coherent."""
    if kind is GuardKind.HP_CRITICAL:
        return RestoreHPGoal()
    if kind is GuardKind.REST_FOR_COMBAT:
        return RestoreHPGoal()
    if kind is GuardKind.DISCARD_CRITICAL or kind is GuardKind.DISCARD_HIGH:
        # The goal sheds `discard_surplus.discardable_surplus` copies, so it needs the
        # SAME ctx the firing predicate used — its `step_profile` is the
        # GOAL_MATERIALS keep reason. (`active_profile`'s blanket code-set is gone:
        # every reason it merged is now a QUANTITY in the keep registry.)
        return DiscardOverstockGoal(game_data=game_data,
                                    ctx=deposit_context(ctx, step_profile),
                                    bank_accessible=ctx.bank_accessible)
    if kind is GuardKind.BANK_UNLOCK:
        return UnlockBankGoal(
            bank_locked=not ctx.bank_accessible,
            initial_xp=ctx.initial_xp,
            target_monster=ctx.bank_unlock_monster,
        )
    if kind is GuardKind.REACH_UNLOCK_LEVEL:
        return ReachUnlockLevelGoal(target_level=ctx.bank_required_level)
    if kind is GuardKind.DEPOSIT_FULL:
        # The goal deposits `inventory_keep.bankable` copies, so it needs the SAME
        # ctx the firing predicate used — its `step_profile` is the GOAL_MATERIALS
        # keep reason. (`active_profile`'s blanket code-set is gone: every reason it
        # merged is now a QUANTITY in the keep registry.)
        return DepositInventoryGoal(bank_accessible=ctx.bank_accessible,
                                    game_data=game_data,
                                    ctx=deposit_context(ctx, step_profile))
    if kind is GuardKind.CRAFT_RELIEF:
        if state is None:
            raise ValueError("CRAFT_RELIEF guard requires a state to pick a target")
        cands = craft_relief_candidates(
            state, game_data,
            step_items=frozenset(step_profile or ()),
        )
        if not cands:
            raise ValueError("CRAFT_RELIEF mapped but no relief candidate available")
        top = cands[0]
        return CraftReliefGoal(
            target_item=top.item_code,
            initial_qty=state.inventory.get(top.item_code, 0),
            batch=top.quantity,
        )
    if kind is GuardKind.RECYCLE_RELIEF:
        return RecycleSurplusGoal(
            game_data=game_data, ctx=ctx,
            initial_total=sum(recyclable_surplus(
                state, game_data, ctx).values()) if state else None)
    if kind is GuardKind.SELL_RELIEF:
        # relief=True: this guard's own predicate is `not bank_has_room`, so the
        # ratio gate (whose point is "bank it instead of selling it") has no
        # object — the goal may sell the WHOLE licensed surplus. It also takes
        # `deposit_context(ctx, step_profile)`, the same merged context
        # DEPOSIT_FULL/RECYCLE_RELIEF use, so the active step's materials are not
        # SOLD out from under it either (a sale is irreversible).
        return SellInventoryGoal(game_data=game_data,
                                 ctx=deposit_context(ctx, step_profile),
                                 bank_accessible=ctx.bank_accessible,
                                 relief=True)
    if kind is GuardKind.GEAR_REVIEW:
        if state is None:
            raise ValueError("GEAR_REVIEW guard requires a state")
        probe = UpgradeEquipmentGoal(initial_equipment=state.equipment)
        target = probe.find_upgrade_target(state, game_data)
        if target is None:
            # No upgrade found — defensive fallback (active_guards gates on ctx,
            # so this branch is only reachable if the latch fired without an upgrade).
            return UpgradeEquipmentGoal(initial_equipment=state.equipment)
        item, slot = target
        if state.inventory.get(item, 0) > 0 or _materials_in_hand(item, state, game_data):
            return UpgradeEquipmentGoal(initial_equipment=state.equipment,
                                        committed_target=(item, slot))
        # Materials not in hand: route to the FLAT deepest actionable step rather
        # than GatherMaterials(item, DIRECT recipe). For a from-scratch deep chain
        # the direct-recipe goal must gather through the multi-level recipe and
        # explodes the GOAP search (655k nodes / 90s timeout at qty 480 offline);
        # the flat leaf gather is linear and budget-feasible, and the macro chain
        # is reached by repeated cycle execution. Reuses the proved
        # gather_step_target core (see _gather_goal_for_unreachable_equippable).
        committed = UpgradeEquipmentGoal(initial_equipment=state.equipment,
                                         committed_target=(item, slot))
        routed = _gather_goal_for_unreachable_equippable(
            item, state, game_data, committed.max_depth, ctx)
        # None means gather_step_target decided the root itself fits the
        # depth budget (see the helper's docstring) -- plan it directly
        # rather than wrapping it in a second GatherMaterials pass.
        return routed if routed is not None else committed
    if kind is GuardKind.CRAFT_POTIONS:
        # `state=` seeds the goal's frozen craft target. Without it the goal
        # re-resolves its target per planner node and can demand one its own
        # (seed-frozen) action set never provides — see CraftPotionsGoal.__init__.
        return CraftPotionsGoal(combat_monster=ctx.combat_monster, game_data=game_data,
                                history=history, state=state)
    if kind is GuardKind.GE_CANCEL:
        # needed_items = the active step's material demand (step_profile codes), the
        # same per-cycle demand the firing predicate used; need_gold=0 (no per-step
        # required-spend is exposed), so the goal cancels on item-need + TTL.
        return CancelOrdersGoal(game_data=game_data, need_gold=0,
                                needed_items=frozenset(step_profile or ()),
                                sibling_claims=ctx.sibling_order_claims)
    raise ValueError(f"Unknown GuardKind: {kind!r}")


def map_means(kind: MeansKind, game_data: GameData, ctx: SelectionContext,
              state: WorldState, history: LearningStore | None = None) -> Goal:
    """Map a MeansKind to a parameterized Goal instance."""
    if kind is MeansKind.CLAIM_PENDING:
        return ClaimPendingGoal()
    if kind is MeansKind.COMPLETE_TASK:
        return CompleteTaskGoal()
    if kind is MeansKind.SELL_PRESSURED or kind is MeansKind.SELL_IDLE:
        # No `relief`: a bank route still exists (SELL_RELIEF is the guard that
        # fires when it does not), so only the RATIO-gated hoards are sold —
        # banking is reversible and preferred.
        #
        # No `state=` either, so NO bank arm: the arm withdraws copies INTO the
        # bag, and neither of these two rungs wants that. SELL_PRESSURED fires at
        # or above SELL_PRESSURE_FRACTION — minting more into a pressured bag is
        # the opposite of its job — and a SELL_IDLE that reached the discretionary
        # band at all is one the COLLECT-band hoist declined, i.e. a pile below
        # SHED_HOIST_URGENCY that is not worth a bank trip. The bank arm belongs
        # to the hoist, which is where its snapshot bound is set.
        return SellInventoryGoal(game_data=game_data, ctx=ctx,
                                 bank_accessible=ctx.bank_accessible)
    if kind is MeansKind.RECYCLE_SURPLUS:
        return RecycleSurplusGoal(
            game_data=game_data, ctx=ctx,
            initial_total=sum(recyclable_surplus(
                state, game_data, ctx).values()))
    if kind is MeansKind.DRAIN_BANK_JUNK:
        # `initial_total` exactly as RECYCLE_SURPLUS above: without it the goal is
        # all-or-nothing and UNPLANNABLE for any pile deeper than the bag, so the
        # discretionary rung would be dead even on the cycles it wins.
        return DrainBankJunkGoal(game_data=game_data, ctx=ctx,
                                 bank_accessible=ctx.bank_accessible,
                                 initial_total=sum(bank_drain_excess(
                                     state, game_data, ctx).values()))
    if kind is MeansKind.GE_BID:
        return PostBuyBidGoal(game_data=game_data, ctx=ctx)
    if kind is MeansKind.LOW_YIELD_CANCEL:
        return LowYieldCancelGoal()
    if kind is MeansKind.TASK_CANCEL:
        return TaskCancelGoal()
    if kind is MeansKind.PURSUE_TASK:
        req = task_requirement(state, game_data)
        if req is not None and req.skill != "combat":
            current = state.skills.get(req.skill, 0)
            target = min(req.required_level, current + LEVEL_LOOKAHEAD)
            # P3a Task 2: route the task-skill grind through the planner-native
            # LevelSkill action (via ReachSkillGoal) instead of LevelSkillGoal
            # (retired in P3b). Arbiter ordering is unchanged (both fire at 55.0).
            return ReachSkillGoal(skill_name=req.skill, target_level=target)
        assert state.task_code is not None  # _fires guarantees an active task
        return PursueTaskGoal(task_code=state.task_code,
                              initial_progress=state.task_progress,
                              batch=task_batch_size(state, game_data))
    if kind is MeansKind.ACCEPT_TASK:
        # Synergy Wave 4: steer the task DISTRIBUTION toward the master whose pool
        # best serves the pursued gear (spec §4). `ctx.target_gear` is the live
        # gear demand B available at this site; the choice returns None (no second
        # master, or neither pool has a level-appropriate task), meaning fall back
        # to today's default master.
        chosen = choose_taskmaster(state, game_data, ctx.target_gear)
        if chosen is None:
            return AcceptTaskGoal()
        code, tile = chosen
        return AcceptTaskGoal(taskmaster_location=tile, taskmaster_code=code)
    if kind is MeansKind.TASK_EXCHANGE:
        # ONE-batch semantics: capture the construction-time coin total so the
        # goal is satisfied after a single exchange (initial - min_coins), not
        # after draining every coin (which exceeded max_depth and stormed the
        # planner budget).
        return TaskExchangeGoal(min_coins=ctx.task_exchange_min_coins,
                                initial_total=tasks_coin_total(state))
    if kind is MeansKind.BANK_EXPAND:
        return ExpandBankGoal(
            bank_accessible=ctx.bank_accessible,
            game_data=game_data,
            history=history,
            combat_monster=ctx.combat_monster,
            # gather_skills is not in SelectionContext; the recent-window inside
            # active_bank_space_cost still contributes via history. Pass empty
            # frozenset for the current-cycle gather parameter.
            gather_skills=frozenset(),
        )
    if kind is MeansKind.MAINTAIN_CONSUMABLES:
        return MaintainConsumablesGoal(game_data=game_data)
    if kind is MeansKind.SUPPLY_BANK:
        assert ctx.supply_target is not None  # _fires guarantees a target
        item_code, quantity, demand = ctx.supply_target
        return SupplyBankGoal(item_code=item_code, quantity=quantity, demand=demand)
    if kind is MeansKind.WAIT:
        return WaitGoal()
    raise ValueError(f"Unknown MeansKind: {kind!r}")


def _gather_step_target_is_root(tgt_code: str, root_code: str) -> bool:
    """True when `gather_step_target` targeted the ROOT itself by name.

    Shared by every one of `gather_step_target`'s callers
    (`grep -rn "gather_step_target(" src/` — two direct call sites:
    `_gather_goal_for_unreachable_equippable` and `objective_step_goal`) so
    the check exists exactly once rather than as a re-typed `== root_code`
    at each site — the `ai/gather_skill_gate.py` failure mode this repo
    documents (one predicate, two sites, drift).

    A `True` result is `gather_step_target`'s own contract, not the
    caller's: its module docstring states as a PRECONDITION of ITS caller
    that "when the root chain IS depth-reachable the caller never reaches
    here" — i.e. this is a signal to plan the root directly (e.g.
    `UpgradeEquipment`), never license to wrap the root in a second
    `GatherMaterials` pass over itself. `GatherMaterialsGoal`'s
    `relevant_actions` search a WIDER action pool (recycle sources,
    currency legs) than `UpgradeEquipmentGoal`'s closure-locked one, so
    "wrap and gather" is not merely redundant — measured on the real
    321-recipe catalog (R2D2, empty bank), direct vs. wrapped:

        wooden_staff     5,839 / 0.50s   vs  102,286 / 11.0s
        feather_coat    81,690 / 15.3s   vs   76,213 / 15.3s
        leather_gloves  47,288 / 15.2s   vs   43,412 / 15.3s

    all three finding no plan either way. Only `wooden_staff` is actually
    faster direct (20x); `feather_coat`/`leather_gloves` exceed the search
    budget regardless of which goal is planned — this predicate is NEUTRAL
    for those two, not a fix, and they remain unsolved (a residual for the
    spec, not this function)."""
    return tgt_code == root_code


def _gather_goal_for_unreachable_equippable(
    code: str, state: WorldState, game_data: GameData, equip_max_depth: int,
    ctx: SelectionContext = NO_PROFILE_CONTEXT,
    step: ObtainItem | None = None,
) -> GatherMaterialsGoal | None:
    """Build a budget-FEASIBLE GatherMaterials goal for a depth-unreachable
    equippable `code` (its full craft chain exceeds `equip_max_depth`), or
    `None` when `_gather_step_target_is_root` says `gather_step_target`
    targeted `code` itself — see that function's docstring for why, and for
    the measurements backing it. `None` means: don't wrap the root in a
    second `GatherMaterials` pass over itself; the caller must fall through
    to its own reachable-root goal (`_equippable_goal`'s `upgrade`, the
    `GEAR_REVIEW` guard's `committed`, `objective_step_goal`'s `upgrade`).

    `step` is the caller's already-computed `actionable_step` result, passed
    so the traversal runs once per decision instead of twice (once to decide
    whether to route here, once inside). `None` means "derive it here" — kept
    for callers that have not computed it themselves.

    `ctx` (the caller's per-cycle `SelectionContext`) is forwarded to
    `actionable_step` so the routed step stops at a node with any ready
    `ai/obtain_sources` route instead of falling into its recipe
    (one-obtain-model epic, Task 5; originally the recycle-as-acquisition
    epic's bespoke `recoverable` map). Defaults to `NO_PROFILE_CONTEXT` for
    every caller that doesn't wire it in.

    The naive fallback — GatherMaterials(code, code's DIRECT recipe) — must plan a
    chain that gathers `min_gathers(code)` raw units THROUGH the multi-level recipe;
    for a from-scratch DEEP chain (empty bank, e.g. steel_boots ← 6 steel_bar ←
    8 iron_bar ← 10 iron_ore = 480 raw) the GOAP search over the gather/craft/deposit
    interleavings EXPLODES super-linearly (measured offline: 655k nodes / 90s timeout
    / plan_len 0 at qty 480; live: 1M+ nodes). Piece A (bank-credited shopping_list)
    prunes NOTHING here — there is no bank stock to credit.

    The fix is the SAME macro/micro bound Piece C wired into `objective_step_goal`:
    route to the strategy's DEEPEST actionable step (the raw base material), whose
    gather is FLAT (`min_gathers == qty`, no recipe sub-tree to interleave) and
    therefore LINEAR in the planner (measured offline: ~38 nodes/unit, 18k nodes /
    0.8s at qty 480 — well within budget). Gathering the leaf makes real incremental
    progress; once it accumulates the next recipe level becomes the actionable step,
    and UpgradeEquipment fires the craft+equip when the materials are in hand. The
    macro PLAN (gather leaf → craft up the chain → equip) is reached by REPEATED
    cycle execution; each cycle descends to micro only for the committed flat batch.

    Reuses the proved cores `actionable_step`
    (formal/Formal/StrategyTraversal.lean `actStep`) + `gather_step_target`
    (formal/Formal/StepDispatch.lean `gatherTarget_*`): the routed step is a genuine
    prerequisite ON the root's recipe path and never harder than the declined root,
    so PlannerAdmissibility is preserved (a reachable root is never abandoned)."""
    owned: dict[str, int] = dict(state.inventory)
    for owned_code, qty in (state.bank_items or {}).items():
        owned[owned_code] = owned.get(owned_code, 0) + qty
    resolved = step if step is not None else actionable_step(
        ObtainItem(code=code, quantity=1), state, game_data, ctx)
    if isinstance(resolved, ObtainItem) and resolved.code != code:
        tgt_code, tgt_qty = gather_step_target(
            code, resolved.code, resolved.quantity,
            game_data.crafting_recipes, owned, equip_max_depth,
            game_data.max_gather_yield)
        if _gather_step_target_is_root(tgt_code, code):
            return None
        return GatherMaterialsGoal(target_item=tgt_code, needed={tgt_code: tgt_qty})
    # No deeper actionable step (the root itself is the actionable leaf, or the
    # chain is cyclically blocked): fall back to the direct recipe. `_equippable_goal`
    # never reaches here recipe-less — its `if recipe:` guard filters that before
    # calling in. `map_guard`'s GEAR_REVIEW branch makes no such guarantee:
    # `find_upgrade_target` can surface a BANK-ONLY item via `_find_inventory_upgrade`
    # (inventory OR bank, no recipe required — see that method's docstring), and the
    # GEAR_REVIEW gate at `:335` checks `state.inventory` but not the bank, while
    # `_materials_in_hand` requires `bool(recipe)` and so also fails. A bank-only
    # recipe-less equippable (46 of the real ones have no recipe, e.g.
    # `corrupted_skull`/`life_crystal`/`forest_ring`) therefore DOES reach this
    # line with `recipe = {}`, returning `GatherMaterialsGoal(code, {})`. Not a
    # soundness break: that goal's own `is_satisfied` short-circuits True for a
    # target held in inventory OR bank when the target is not itself a key of
    # `needed` (see `GatherMaterialsGoal.is_satisfied`'s docstring) — `needed={}`
    # makes that always the case here, so it fires zero actions rather than a
    # wrong one. Whether the bank-held item then actually gets withdrawn and
    # equipped is a different goal's job, not this fallback's. Neither caller
    # consults `is_plannable` to decide whether to call in.
    recipe = game_data.crafting_recipe(code) or {}
    return GatherMaterialsGoal(target_item=code, needed=dict(recipe))


def _equippable_goal(code: str, slot: str, state: WorldState, game_data: GameData,
                     ctx: SelectionContext = NO_PROFILE_CONTEXT) -> Goal:
    """Map an equippable target to UpgradeEquipment when it is reachable, else to
    GatherMaterials for the strategy's next achievable step toward it.

    Routes on the STEP, not on a depth-bound proxy for it. `is_plannable`
    compares `min_plan_length` against `max_depth` 32, and `min_plan_length`
    maxes at 15 across all 321 real recipes (see `UpgradeEquipmentGoal.max_depth`'s
    SECOND RESIDUAL), so it never rejects — using it as a trigger here was dead
    code: the arbiter planned a 100,080-node search that timed out instead of
    the 2-node gather `actionable_step` had already identified. `is_plannable`
    is still consulted elsewhere as a waste-avoidance filter; it is not used
    by this function.

    The direct question this function asks is the one the helper asks
    internally: is the deepest achievable node (`actionable_step`) something
    OTHER than the goal itself? If not — the root's own direct prerequisites
    are already satisfied, or the traversal is cyclically blocked / every
    branch dead-ends (`actionable_step` returns `None`) — return
    `UpgradeEquipment` directly; a dead-ended chain is a bounded, fast-failing
    search, not a soundness break (see `test_objective_step_equippable_dead_ends_admit_the_root_cheaply`).
    Otherwise route to `_gather_goal_for_unreachable_equippable`'s flat-leaf
    step. The helper itself returns `None` (not a wrapped goal) when
    `gather_step_target` decides the root's own gather cost already fits
    `equip_max_depth` — see the helper's docstring for why that must be
    handled there, not re-checked here — and this function falls through to
    `upgrade` on that signal too. Self-corrects both ways across cycles —
    materials missing routes to the gather (which does craft, not just
    gather; the equip follows on a later cycle once the item is owned),
    materials banked or carried leafs at the root and fires the craft+equip —
    so there is no threshold to tune and no bound to rot.

    `ctx` is forwarded to `_gather_goal_for_unreachable_equippable`
    (one-obtain-model epic, Task 5); defaults to `NO_PROFILE_CONTEXT`."""
    upgrade = UpgradeEquipmentGoal(initial_equipment=state.equipment, committed_target=(code, slot))
    owned = (state.inventory.get(code, 0) > 0
             or (state.bank_items or {}).get(code, 0) > 0)
    if (game_data.crafting_recipe(code) is None and not owned
            and game_data.npc_purchases(code)):
        # UNOWNED, recipe-less, NPC-buy-only equippable (sandwhisper_bag):
        # UpgradeEquipment's closure lock restricts planning to the recipe
        # closure's crafts/gathers/withdraws + the equip — for a recipe-less
        # vendor item that set is EMPTY, so its search died at 2 nodes even
        # at full capability (probe 2026-07-06 @L50: plan_len=0 — a dead
        # gear root), while is_plannable over-admitted it ("recipe-less
        # needs at most one gather" assumes a gather exists). Route the
        # ACQUISITION through GatherMaterials, whose currency injection
        # (task #13) emits Fight xN (drop-farm capable) -> NpcBuy; once the
        # item is in hand this branch is skipped and UpgradeEquipment fires
        # the equip — one stepwise leg per cycle, as with every other root.
        #
        # UNAFFORDABLE item-currency: accumulate the currency in BATCHES via
        # `currency_grind_target_pure` — a one-shot plan for a 230-coin price
        # is ~120 fights deep and dies on max_depth (sandwhisper_bag probe
        # @L50: 28K nodes, plan_len=0), so the target must stay shallow. It
        # was `held + 1`, which stayed shallow but re-armed on EVERY
        # acquisition; since `needed` is part of the goal's identity that
        # churned the repr each cycle and reset sticky-commit keying. The
        # batch milestone is absolute, so it holds still within a batch while
        # still never running more than one batch ahead of `held`. Cheapest
        # PERMANENT located vendor decides the price (semantic key; event/
        # unlocated vendors mirror currency_demand's exclusion). Gold-priced
        # items skip the accumulation (gold is earned by normal play, not a
        # gatherable item) and fall through to the buy attempt.
        bank = state.bank_items or {}
        # A currency that accrues passively from normal combat (like gold, and like
        # event_ticket, which drops from 56/58 monsters) is NOT farmed on a
        # dedicated grind — it is earned while levelling. Excluding it here drops
        # through to the plain buy attempt, which is unplannable until affordable,
        # so the arbiter falls back to levelling (which accrues the currency). The
        # item is then bought once ordinary play has paid for it. (§synergy live
        # diagnosis 2026-07-23: over-boosted event_ticket grind out-ranked xp.)
        purchases = [(price, currency)
                     for price, currency in _permanent_vendor_purchases(code, game_data)
                     if currency != "gold"
                     and not game_data.currency_accrues_passively(currency)]
        if purchases:
            price, currency = min(purchases)
            held = state.inventory.get(currency, 0) + bank.get(currency, 0)
            if held < price:
                return GatherMaterialsGoal(
                    target_item=currency,
                    needed={currency: currency_grind_target_pure(held, price)})
        return GatherMaterialsGoal(target_item=code, needed={code: 1})
    # Route on the STEP, not on a depth-bound proxy for it. `is_plannable`
    # compares min_plan_length against max_depth 32, and min_plan_length maxes
    # at 15 across all 321 real recipes (see UpgradeEquipmentGoal.max_depth's
    # SECOND RESIDUAL), so it never rejects and this routing was dead — the
    # arbiter planned a 100,080-node search that timed out instead of the
    # 2-node gather `actionable_step` had already identified.
    #
    # The direct question is the one the helper asks internally: is the deepest
    # achievable node something OTHER than the goal itself? It self-corrects in
    # both directions — materials missing routes to the gather, materials
    # banked or carried leafs at the root and fires the craft — so there is no
    # threshold to tune and no bound to rot.
    step = actionable_step(ObtainItem(code=code, quantity=1), state, game_data, ctx)
    if not (isinstance(step, ObtainItem) and step.code != code):
        return upgrade
    recipe = game_data.crafting_recipe(code) or {}
    if recipe:
        # Depth-UNREACHABLE from-scratch deep chain: route to the FLAT deepest
        # actionable step instead of GatherMaterials(code, DIRECT recipe), whose
        # plan must gather through the multi-level recipe and explodes the GOAP
        # search (see _gather_goal_for_unreachable_equippable).
        routed = _gather_goal_for_unreachable_equippable(
            code, state, game_data, upgrade.max_depth, ctx, step=step)
        # None means gather_step_target decided the root itself fits the
        # depth budget (see the helper's docstring) -- plan it directly.
        return routed if routed is not None else upgrade
    # Unreachable in practice: `recipe` is only falsy for a recipe-less code,
    # and a recipe-less item's requirement-graph node has no outgoing edges
    # (`requirement_edges` returns {} — see `requirement_projections.py`), so
    # `actionable_step` can never descend PAST a recipe-less root: it either
    # returns the root itself (satisfied/producible) or None (blocked),
    # both of which are caught by the `not (isinstance(step, ObtainItem)
    # and step.code != code)` guard above and return `upgrade` before this
    # line. `step.code != code` therefore implies a non-empty recipe. Kept
    # as a total-function fallback.
    return upgrade  # pragma: no cover


def _recipe_has_combat_drop_input(
    code: str, game_data: GameData, visited: frozenset[str] = frozenset()) -> bool:
    """True when `code`'s recipe closure contains a PURE monster-drop leaf — an
    input obtained only by fighting (e.g. feather <- chicken), neither craftable
    nor a resource-node drop. Such an input forces the whole-chain GOAP plan to
    interleave fights with gathers/crafts, exploding the search; the caller routes
    to flat per-input steps instead. Cycle-safe."""
    if code in visited:
        return False
    recipe = game_data.crafting_recipe(code)
    if recipe is None:
        return (bool(game_data.monsters_dropping(code))
                and code not in game_data.gatherable_drop_items())
    nxt = visited | {code}
    return any(_recipe_has_combat_drop_input(mat, game_data, nxt) for mat in recipe)


def monster_drop_inputs(
    code: str, game_data: GameData, visited: frozenset[str] = frozenset()) -> list[str]:
    """The PURE monster-drop leaves in `code`'s recipe closure (inputs obtained only
    by fighting, e.g. feather). Used by the `plan` CLI to report whether those drops
    are winnable for the live loadout. Cycle-safe; deterministic order."""
    if code in visited:
        return []
    recipe = game_data.crafting_recipe(code)
    if recipe is None:
        if (game_data.monsters_dropping(code)
                and code not in game_data.gatherable_drop_items()):
            return [code]
        return []
    nxt = visited | {code}
    out: list[str] = []
    for mat in recipe:
        for leaf in monster_drop_inputs(mat, game_data, nxt):
            if leaf not in out:
                out.append(leaf)
    return out


def _marginal_provision_goal(ctx: SelectionContext, state: WorldState,
                             game_data: GameData,
                             history: LearningStore | None) -> Goal | None:
    """Return ProvisionMarginalFightGoal sized to the learned or seeded HP-need.

    Quantity = ceil(hp_need / restore), clamped to held and UTILITY_SLOT_MAX_STACK.
    hp_need comes from the learning store when >=5 winning Fight cycles exist,
    falling back to expected_damage_per_fight for cold-start seeding."""
    monster = ctx.combat_monster
    if monster is None or history is None:
        return None
    if any(state.equipment.get(s) is not None for s in ("utility1_slot", "utility2_slot")):
        return None  # already provisioned -> grind
    heal_code = best_held_heal(state, game_data)
    if heal_code is None:
        return None  # no utility-slot heal held -> fight unprovisioned
    held = state.inventory.get(heal_code, 0)
    restore = game_data.hp_restore_of(heal_code)
    learned = history.hp_healed_per_fight(monster, game_data.hp_restore_of) \
        if hasattr(history, "hp_healed_per_fight") else None
    hp_need = int(learned) if learned is not None \
        else expected_damage_per_fight(state, game_data, monster)
    qty = potion_provision_qty_pure(hp_need, restore, held,
                                    utility_slot_filled=False,
                                    max_stack=UTILITY_SLOT_MAX_STACK)
    if qty <= 0:
        return None
    return ProvisionMarginalFightGoal(target_monster=monster,
                                      heal_code=heal_code, quantity=qty)


def objective_step_goal(
    step: MetaGoal | None,
    state: WorldState,
    game_data: GameData,
    ctx: SelectionContext,
    root: MetaGoal | None = None,
    committed_root: MetaGoal | None = None,
    history: LearningStore | None = None,
) -> Goal | None:
    """Map the strategy's chosen step to a Goal.

    When `root` is provided and is an equippable ObtainItem (e.g.
    copper_boots) while `step` is an intermediate recipe-input
    ObtainItem (e.g. copper_bar) along the root's chain, return
    UpgradeEquipmentGoal targeting the ROOT so the planner crafts the
    whole chain (intermediates + final + equip) under one goal commit
    instead of stopping at the intermediate.
    """
    if step is None:
        return None
    if isinstance(step, ObtainItem):
        # DEMAND ROUTING (C4 Task 6): if obtaining this item is BLOCKED on an
        # unaffordable currency-buy leaf in its recipe closure (e.g. satchel <-
        # jasper_crystal @ tasks_trader for 8 tasks_coin, with 0 tasks_coin), the
        # GatherMaterials/UpgradeEquipment goal built below is unplannable
        # (GatherMaterialsGoal.is_plannable fast-fails — currency_afford_plannable_pure).
        # Route to ReachCurrencyGoal to FUND the currency instead, so the arbiter
        # has a plannable funding goal to select. Once funded the leaf becomes
        # affordable and the next pass builds the craft path (buy + craft). Shares
        # the ONE closure walk with is_plannable (analyze_currency_leaves). Only a
        # tasks_coin-funded leaf yields a funding_target — a gold/event-only leaf is
        # `blocked` (is_plannable prunes it) but NOT routed here (ReachCurrencyGoal
        # mints only tasks_coin, so funding a gold leaf would chase an unreachable
        # goal).
        analysis = analyze_currency_leaves(
            {step.code: step.quantity}, state, game_data)
        if analysis.funding_target is not None:
            currency, amount = analysis.funding_target
            return ReachCurrencyGoal(currency=currency, target=amount)
        stats = game_data.item_stats(step.code)
        slots = ITEM_TYPE_TO_SLOTS.get(stats.type_) if stats is not None else None
        if slots:
            dest_slot = step.slot if step.slot is not None else slots[0]
            return _equippable_goal(step.code, dest_slot, state, game_data, ctx)
        # Intermediate step: if the chain root is an equippable, plan
        # against the root directly. UpgradeEquipmentGoal's planner
        # walks the recipe chain (craft intermediates + final + equip)
        # while GatherMaterialsGoal stops at the intermediate.
        if isinstance(root, ObtainItem) and root.code != step.code:
            root_stats = game_data.item_stats(root.code)
            root_slots = ITEM_TYPE_TO_SLOTS.get(root_stats.type_) if root_stats is not None else None
            if root_slots:
                # Recipe with a MONSTER-DROP input (feather <- chicken): planning the
                # whole craft+equip chain EXPLODES — the GOAP A* must interleave
                # fights, gathers, crafts and travel across the chicken spawn /
                # resource node / workshop, which times out (live: feather_coat 57k
                # nodes, depth 23, plan_len 0). The recipe is deterministic but the
                # search is not. Collect inputs INCREMENTALLY: route to the flat
                # actionable step (gather wood / craft plank / hunt chickens for
                # feathers, one at a time). Each flat GatherMaterials plans within
                # budget — GatherMaterials(feather) emits Fight(chicken) and is a flat
                # hunt — and once every input is in hand the final craft is shallow.
                if _recipe_has_combat_drop_input(root.code, game_data):
                    return GatherMaterialsGoal(target_item=step.code,
                                               needed={step.code: step.quantity})
                dest_slot = root.slot if root.slot is not None else root_slots[0]
                owned: dict[str, int] = dict(state.inventory)
                for code, qty in (state.bank_items or {}).items():
                    owned[code] = owned.get(code, 0) + qty
                upgrade = UpgradeEquipmentGoal(initial_equipment=state.equipment,
                                               committed_target=(root.code, dest_slot))
                # Pursue the committed gear root one PLANNABLE CHUNK at a time — never
                # hand the whole craft+equip chain to the A* at once. The old code
                # returned the whole-chain `upgrade` whenever `upgrade.is_plannable`,
                # but is_plannable means "achievable ever", NOT "the A* finds it within
                # max_depth". A from-scratch copper_boots chain is ~96 actions (80 ore
                # gathers + 8 bar crafts + boots + equip) ≫ max_depth 32, so the one-shot
                # plan returned plan_len 0 and the bot abandoned boots for chicken grind
                # (trace 2026-06-21). A depth
                # predicate can't save it either: min_plan_length is only a LOWER bound
                # (omits travel + the final assembly), so `<= max_depth` never PROVES the
                # plan fits. So we always chunk: when the step is an intermediate, route
                # to the deepest flat gather (gather_step_target), which plans within
                # budget and makes incremental progress; once the materials accumulate
                # the strategy's actionable_step advances to the next recipe level, and
                # when every input is in hand the step becomes the root itself (handled
                # by the equippable branch above as a shallow craft+equip). The root
                # objective commitment is unchanged — only its EXECUTION is chunked.
                #
                # Root craft SKILL-GATED (not a depth problem): the final
                # craft is blocked until the crafting skill rises, but the
                # step's materials are needed regardless — plan the literal
                # step, even when the root's raw-gather depth already fits
                # the budget below. `gather_step_target`'s root-return check
                # (`_gather_step_target_is_root`) only weighs MATERIAL gather
                # depth against `equip_max_depth` — it has no notion of a
                # crafting-skill gap, so a materially-shallow root can still
                # fall through to `upgrade` there. Handing `upgrade` (the
                # WHOLE craft+equip chain, now also carrying a LevelSkill
                # grind for the gap) to the A* before the materials are even
                # in hand is the one-shot-chain explosion the chunking above
                # exists to avoid — the same skill-gated dead end this guard
                # was written to prevent (trace 2026-06-11 18:46 cycle 15-16:
                # both gear roots stalled and the arbiter fell through to
                # slime grinding with the bar objective abandoned at 1/5).
                # Once the materials are in hand AND the skill has risen
                # enough, the equippable branch above hands the now-bounded
                # remaining chunk to `upgrade` — UpgradeEquipmentGoal grinds
                # the crafting skill planner-natively via the LevelSkill
                # action (epic P3).
                if (root_stats is not None and root_stats.crafting_skill
                        and state.skills.get(root_stats.crafting_skill, 1)
                        < root_stats.crafting_level):
                    return GatherMaterialsGoal(target_item=step.code,
                                               needed={step.code: step.quantity})
                # Root chain depth-UNREACHABLE (from-scratch deep recipe). The
                # old fallback GatherMaterials(root, root's DIRECT recipe) needs a
                # plan that gathers min_gathers(root) raw units THROUGH the deep
                # recipe — the GOAP search over gather/deposit/craft interleavings
                # EXPLODES (live: 1M+ nodes, 90s timeout, plan_len 0, then
                # fall-through; the gear chain never progresses). Route instead to
                # the strategy's DEEPEST actionable step (the raw base material),
                # whose gather is FLAT and budget-feasible and makes incremental
                # progress; once it accumulates the next recipe level becomes the
                # actionable step. Sound: the step is a prerequisite ON the root's
                # path and never harder than the root (gather_step_target +
                # formal/Formal/StepDispatch.lean gatherTarget_*).
                #
                # gather_step_target can also decide the ROOT's own gather cost
                # already fits the depth budget and return it BY NAME — its own
                # module docstring states that as a precondition of THIS call
                # site ("the caller plans the root chain directly"), not
                # license to wrap the root in a second GatherMaterials pass
                # over itself (see `_gather_step_target_is_root`, shared with
                # `_gather_goal_for_unreachable_equippable`, for the mechanism
                # and the measured cost of getting this wrong). `upgrade` above
                # is already the root's reachable-root goal to fall through to.
                tgt_code, tgt_qty = gather_step_target(
                    root.code, step.code, step.quantity,
                    game_data.crafting_recipes, owned, upgrade.max_depth,
                    game_data.max_gather_yield)
                if _gather_step_target_is_root(tgt_code, root.code):
                    return upgrade
                return GatherMaterialsGoal(target_item=tgt_code, needed={tgt_code: tgt_qty})
        return GatherMaterialsGoal(target_item=step.code, needed={step.code: step.quantity})
    if isinstance(step, ReachCharLevel):
        if ctx.combat_monster is None:
            return None
        # Items-task stand-down was designed for the LONG-HAUL
        # ReachCharLevel(50) root: don't preempt PURSUE_TASK's
        # gold / tasks_coin / skill-XP / gear-progression payout
        # with a 47-level combat grind. Items tasks DO NOT award
        # character XP — combat is the only source (verified in
        # trace: all 1229 char-XP gain events attributed to
        # `Fight(...)`, zero to `CompleteTask` or `TaskTrade`). But
        # items tasks chain indefinitely (one finishes, another
        # starts), so the unconditional stand-down meant the bot
        # NEVER fought — trace 2026-06-03/05 showed zero combat
        # across 3300+ cycles and Robby permanently parked at
        # level 3.
        #
        # Bootstrap roots (`ReachCharLevel(state.level + horizon)`,
        # see tiers.prerequisite_graph._CHAR_LEVEL_BOOTSTRAP_HORIZON)
        # are the critical-path nudge that breaks this. A small-gap
        # step (target - current <= 4) is the bootstrap path: let it
        # grind through even when an items task is active. The
        # bootstrap target advances with each level-up so the bot is
        # never grinding more than `horizon` levels at a time. The
        # long-haul level-50 step still stands down — its grind would
        # be 40+ unbroken combat cycles, which is the wrong trade for
        # an in-progress items task that's paying out gold + skill XP
        # + task rewards every batch.
        # Fire-as-Fight decision extracted to the pure boundary
        # `objective_step_is_fight_pure` (objective_step_fight_core.py) — the
        # SAME predicate the Lean liveness Bool `objectiveStepIsFight` binds to
        # via the differential gate. False here = long-haul grind deferred to an
        # active items task.
        if not objective_step_is_fight_pure(
                is_reach_char_level=True,
                target=step.level,
                level=state.level,
                has_combat_monster=ctx.combat_monster is not None,
                task_type=state.task_type,
                task_code=state.task_code,
                task_total=state.task_total,
                task_progress=state.task_progress):
            return None        # long-haul grind, items task active → defer
        provision = _marginal_provision_goal(ctx, state, game_data, history)
        if provision is not None:
            return provision
        return GrindCharacterXPGoal(target_monster=ctx.combat_monster, initial_xp=state.xp)
    return None


class StrategyArbiter:
    """Compose guards → collect-reward → objective step → discretionary.

    Returns the first candidate that plans. Owns sticky commitment so a
    committed means goal is kept across cycles unless a guard preempts it
    or it becomes satisfied / unplannable.
    """

    def __init__(self, planner: GOAPPlanner, history: LearningStore | None) -> None:
        self._planner = planner
        self._history = history
        self._committed_repr: str | None = None
        self.goals_tried: list[dict[str, object]] = []
        # The FIRST candidate this cycle's walk actually attempted, when it
        # produced no plan and a LOWER-ranked candidate ran instead. None on
        # every other cycle. See `select` for why it is derived from
        # `goals_tried` rather than reported by `select_pure`.
        self.objective_unplannable: dict[str, object] | None = None
        # Phase B3 (docs/PLAN_c2_composed_liveness.md): the fired guard/means
        # kinds exactly as the most recent select() saw them. Emitted into the
        # per-cycle trace so the offline ladder lockstep replays selection
        # against observed fires instead of re-deriving opaque predicates.
        self.last_fires: dict[str, object] = {}
        self._memo = DoomedMemo()
        self._cycle = 0
        # Whether the most recent `_plans` call ended in a budget TIMEOUT (vs an
        # EXHAUSTIVE search or a definitive is_plannable=False / WaitGoal result).
        # Telemetry only: `_record_attempt` marks the memo on ANY no-plan, so
        # nothing branches on this flag any more — it rides `goals_tried` into
        # the trace so a reader can tell a dead end from a search blow-up.
        self._last_timed_out: bool = False
        # Monotonic instant this cycle's cooldown expires — the window the whole
        # walk may search inside, set by the player once per cycle. None on any
        # cycle with no cooldown to spend (first cycle, an error cycle), which
        # falls back to the planner's own default budget.
        self._planning_deadline: float | None = None

    def set_cycle(self, cycle: int) -> None:
        """Player calls this each cycle so the memo's re-probe window advances."""
        self._cycle = cycle

    def set_planning_deadline(self, deadline_monotonic: float | None) -> None:
        """Player calls this each cycle with the cooldown's expiry instant.

        The search now runs DURING the cooldown instead of after it, so the
        cooldown is the cycle's free planning window: spending it costs the bot
        nothing it was not already going to idle away."""
        self._planning_deadline = deadline_monotonic

    def _cycle_budget_seconds(self) -> float | None:
        """The budget for one candidate's search: whatever is left of this
        cycle's cooldown window, FLOORED at the planner's default budget.

        A per-cycle deadline (rather than a per-call budget) is what keeps the
        walk from overrunning the cooldown N times over for N candidates. The
        floor is not a convenience: `_record_attempt` marks ANY no-plan doomed,
        so an attempt squeezed into the tail of a 3s cooldown would shelve a
        goal for a whole re-probe window on evidence no weaker search ever had
        to produce before. Flooring at the default means no candidate is ever
        judged on less search than it used to get.

        None (no deadline) leaves `planner.plan` on its own default."""
        if self._planning_deadline is None:
            return None
        return max(_SEARCH_BUDGET_SECONDS, self._planning_deadline - time.monotonic())

    def _plans(
        self,
        goal: Goal,
        state: WorldState,
        game_data: GameData,
        actions: list[Action],
        ctx: SelectionContext,
        budget_seconds: float | None = None,
    ) -> list[Action]:
        """Attempt to plan goal; record attempt in goals_tried; return plan ([] = failed).

        WaitGoal is special-cased: it is never satisfiable (is_satisfied always
        False) and its only action (WaitAction) is a no-op on WorldState, so
        A* would never terminate via the planner. Short-circuit to a
        single-step [WaitAction()] plan so the last-resort fallback always
        provides a firing candidate to select_pure.
        """
        # Recorded on every attempt because this is the ONLY place the goal
        # OBJECT is still in scope — `goals_tried` carries reprs, so a consumer
        # downstream cannot recover it. The trace's `goal_rank` used to emit a
        # hardcoded 0.0 here, and both TUI consumers filter on `priority > 0`,
        # so that panel rendered empty on every cycle ever traced.
        priority = goal.priority(state, game_data, self._history)
        if isinstance(goal, WaitGoal):
            wait_plan: list[Action] = [WaitAction()]
            self._last_timed_out = False
            self.goals_tried.append({
                "goal": repr(goal),
                "nodes": 0,
                "depth": 1,
                "timed_out": False,
                "plan_len": 1,
                "priority": priority,
            })
            return wait_plan
        # Pre-plan reachability gate: a goal whose minimum plan is longer than
        # its max_depth can never be planned (the planner never returns a plan
        # longer than max_depth — formal/Formal/PlannerDepthBound), so skip it
        # instead of burning `planner._SEARCH_BUDGET_SECONDS` (named, never a
        # literal — this comment said "90s" through a 300s era and a 15s one).
        #
        # NOT "provably sound", and the word was removed rather than softened:
        # the gate consumes `min_plan_length`, whose docstring RETRACTS the
        # citation it used to carry ("that theorem has never existed",
        # min_plan_length.py:5-7). Treat it as an A*-budget heuristic.
        #
        # STALE EXAMPLE, LEFT AS A HISTORICAL MARKER (corrected 2026-08-13,
        # whole-branch review): this comment used to end "This is what stops
        # UpgradeEquipment(copper_boots) — 80 gathers vs max_depth 32 — from
        # stalling the first cycle." That is now FALSE in both numbers. Task 3
        # swapped the mint term to `min_gather_steps`, so copper_boots costs 4,
        # not 80, and `test_upgrade_reachability_gate.py
        # ::test_is_plannable_admits_from_scratch_copper_boots` asserts exactly
        # the opposite of the old claim. The identical example was corrected in
        # `goals/progression.py:223` and this copy was missed — the same
        # cross-file duplication this branch keeps being bitten by.
        #
        # The honest statement: over all 321 real recipes the maximum
        # `min_plan_length` is 15 against a threshold of 32, ZERO exceeding, so
        # this branch is LIVE-DEAD on today's data. See `progression.py`'s
        # `max_depth` docstring for the full account.
        if not goal.is_plannable(state, game_data, self._history):
            # A proven-unplannable goal is a CONCLUSIVE no-plan, not a timeout.
            self._last_timed_out = False
            self.goals_tried.append({
                "goal": repr(goal),
                "nodes": 0,
                "depth": 0,
                "timed_out": False,
                "plan_len": 0,
                "priority": priority,
            })
            return []
        # Fast-path: for a deterministic gather-craft closure (all leaves are
        # gatherable raws, skill-gated-met craftables, or served by THE ONE
        # OBTAIN MODEL) skip A* entirely. O(closure) vs 52K-node search for
        # copper_ring-style chains. Falls back to None for genuinely
        # unmodeled leaves / unmet-skill-gate goals with no grind rung.
        #
        # The source map is built ONCE here (not per closure item, and only
        # for a GatherMaterialsGoal — every other goal shape short-circuits
        # generate_next_craft_action immediately) via obtain_source_map, THE
        # shared model every route beyond bare gather/craft/withdraw reads.
        sources: dict[str, list[Source]] = {}
        if isinstance(goal, GatherMaterialsGoal):
            closure_items = _closure_items(dict(game_data.crafting_recipes), goal.needed)
            sources = obtain_source_map(closure_items, state, game_data, ctx)
        gen = generate_next_craft_action(goal, state, game_data, actions, sources)
        if gen is not None:
            self._last_timed_out = False
            self.goals_tried.append({
                "goal": repr(goal),
                "nodes": 0,
                "depth": 0,
                "timed_out": False,
                "plan_len": len(gen),
                "priority": priority,
            })
            return gen
        plan = self._planner.plan(state, goal, actions, game_data, self._history,
                                  budget_seconds=budget_seconds)
        stats = self._planner.last_stats
        self._last_timed_out = stats.timed_out
        # P2: a plan that depends on event-ONLY content is worthless if the window
        # shuts before it finishes. Dropped rather than returned, so the candidate
        # is rejected and the arbiter moves on to something reachable. Only plans
        # that actually touch event-only content are affected -- content with a
        # permanent spawn is never gated, and a plan with no event content at all
        # short-circuits before any cost is summed.
        if plan and not plan_fits_event_window(plan, state, game_data,
                                               datetime.now(timezone.utc)):
            plan = []
        self.goals_tried.append({
            "goal": repr(goal),
            "nodes": stats.nodes_explored,
            "depth": stats.max_depth_reached,
            "timed_out": stats.timed_out,
            "node_capped": stats.node_capped,
            "plan_len": len(plan),
            "priority": priority,
        })
        return plan

    def _record_attempt(self, goal: Goal, plan: list[Action], timed_out: bool,
                        state: WorldState, guard_reprs: set[str]) -> list[Action]:
        """Update the doomed-memo from one planning attempt and return `plan`.

        - A found plan (or a memo-bypassing goal) CLEARS any prior doomed mark.
        - Any no-plan result MARKS the goal doomed, TIMEOUT INCLUDED.

        The timeout carve-out is deleted. It existed to keep a cheap-budget
        timeout available for a full-budget escalation that, in a fleet with an
        always-plannable fallback grind, was never reached: `select_pure` takes
        the first candidate that plans, `GrindCharacterXP` plans in 2 nodes, so
        `chosen` was never None and the escalation pass never ran. The carve-out
        therefore only ever meant "never mark", and the same 3873-node search
        re-ran on 955 consecutive cycles (live traces 2026-08-12).

        `timed_out` is kept in the signature because it is the ONE fact a caller
        cannot re-derive here, and dropping it from the parameter list would
        invite re-introducing the carve-out later; it now only documents the
        attempt (the trace carries it via `goals_tried`).

        `guard_reprs` is the memo-bypass set: guards plus `Goal.memo_exempt`
        goals, whose plannability flips on state the memo's signature cannot
        track."""
        r = repr(goal)
        if r in guard_reprs or plan:
            self._memo.clear(r)
        else:
            self._memo.mark(r, state, self._cycle)
        return plan

    def select(
        self,
        decision: object,
        state: WorldState,
        game_data: GameData,
        actions: list[Action],
        ctx: SelectionContext,
        suppressed: frozenset[str] | set[str] = frozenset(),
        objective: CharacterObjective | None = None,
    ) -> tuple[Goal | None, list[Action], list[dict[str, object]]]:
        """Select the first plannable goal from the ordered candidate list.

        decision must have a .chosen_step attribute (MetaGoal | None).

        Candidates whose repr is in `suppressed` are skipped, EXCEPT TaskCancel
        which is never suppressed (it is the escape hatch for a stuck task).

        Returns (goal, plan, goals_tried).
        """
        self.goals_tried = []
        self.objective_unplannable = None

        chosen_step: MetaGoal | None = getattr(decision, "chosen_step", None)
        chosen_root: MetaGoal | None = getattr(decision, "chosen_root", None)
        fallback_steps: list[MetaGoal] = getattr(decision, "fallback_steps", [])
        fallback_roots: list[MetaGoal] = getattr(decision, "fallback_roots", [])

        step_goal = self._resolve_step_goal(
            chosen_step, chosen_root, fallback_steps, fallback_roots, state, game_data, ctx)
        # Task suppression needs ONE means predicate (PURSUE_TASK), and that one
        # reads no ctx field at all (state.task_* + history), so it is evaluated
        # here — before the step profile exists. Every OTHER means is evaluated
        # below, on the BOUND ctx: SELL_IDLE / RECYCLE_SURPLUS / DRAIN_BANK_JUNK
        # ask the keep authority what may be shed, and the authority reads
        # `ctx.step_profile`. Firing them on the unbound (empty-profile) ctx let a
        # means fire on surplus its own goal — running on the FULL profile — then
        # refused to shed, producing a satisfied goal and a zero-length plan.
        task_means = [k for k in (MeansKind.PURSUE_TASK,)
                      if means_fires(k, state, game_data, self._history, ctx)]
        step_goal = self._suppress_step_for_task(step_goal, task_means, state, game_data)

        # The step goal is resolved BEFORE the guards so its needed map can
        # join the deposit/discard protection profile. Trace 2026-06-11 22:36
        # (cycle 30): DISCARD_HIGH deleted a wooden_shield the active
        # GatherMaterials grind goal (needed = held + 1) was accumulating —
        # the guard's profile only knew crafting_target/gear/tools/task.
        step_profile = _step_protection_profile(step_goal, state, game_data)
        # ...and the SAME map rides the ctx from here down, so the keep authority
        # (`ai/inventory_keep.KeepReason.GOAL_MATERIALS`) protects exactly the
        # quantities the guards' disposal predicates protect. This is the one
        # point where the resolved step goal exists: the goal is resolved FROM
        # `ctx` (`_resolve_step_goal`), so the player cannot fill `step_profile`
        # in when it builds the ctx — it would have to re-resolve the step goal
        # WITHOUT the fallback walk and task suppression above, and the two
        # derivations would drift. Re-binding the frozen ctx here keeps one source.
        ctx = replace(ctx, step_profile=dict(step_profile or {}))
        # EVERY consumer of the ctx below sees the bound profile: the means/guard
        # predicates, the goals they map to, and the destructive-action licence.
        collect_kinds, discretionary_kinds = active_means(state, game_data, self._history, ctx)
        guard_kinds = active_guards(state, game_data, self._history, ctx, step_profile)
        # THE DESTRUCTION CHOKEPOINT (item-protection-authority epic): the factory's
        # shared pool carries a quantity=1 Recycle / NpcSell / Delete for codes it
        # knows nothing about, and `Goal.relevant_actions` DEFAULTS to the whole pool
        # — so ~10 goals that have no business destroying anything (CompleteTask,
        # AcceptTask, ClaimPending, …) could satisfy a Fight's `inventory_free >= 1`
        # precondition by DELETING an item, and `delete_cost` ranks a sellable item
        # (25) CHEAPER than an ingredient (50), which made the working copper_axe a
        # PREFERRED victim. Licence the pool HERE, at the one point where the ctx is
        # fully bound, so no goal can bypass the authority.
        actions = license_destructive_actions(actions, state, game_data, ctx)
        # Phase B3: snapshot the fired kinds for the trace (selection-time
        # truth; recomputing at emit time would drift on ctx-dependent flags).
        self.last_fires = {
            "guards": [k.value for k in guard_kinds],
            "collect": [k.value for k in collect_kinds],
            "discretionary": [k.value for k in discretionary_kinds],
            "step_present": step_goal is not None,
        }

        # Trace 2026-05-19 (cycles 318-342): with task_code=None, the bot
        # locked into a Gather→Discard loop — meta-objective step
        # GatherMaterials(copper_ring) ran every other cycle pulling
        # copper_ore that DISCARD_HIGH immediately deleted because the
        # overstock cap had no task floor to lean on. AcceptTask was in
        # the discretionary kinds the whole time but sat positionally
        # AFTER the meta-step, so it never won. When there's no active
        # task, accepting one is the cheap unblock: it gives PursueTask a
        # target, brings the task-chain keep-set online, and gives the
        # gathered materials a destination other than the trash. The worth
        # gate below replaces this intent: ACCEPT_TASK is worth-gated, so when
        # the objective has unmet needs the step competes; when needs are
        # empty, ACCEPT_TASK is not suppressed and still wins.

        candidates = self._build_candidates(
            guard_kinds, collect_kinds, discretionary_kinds, step_goal,
            fallback_steps, fallback_roots, state, game_data, ctx, step_profile,
            chosen_root=chosen_root)

        worth_suppressed = self._worth_gate_suppressed(
            objective, chosen_root, discretionary_kinds, state, game_data, ctx)

        chosen, plan, new_committed = self._arbitrate(
            candidates, suppressed, worth_suppressed, state, game_data, actions, ctx)

        self._committed_repr = new_committed
        self.goals_tried = self._dedupe_goals_tried()
        # THE FIRST CANDIDATE ACTUALLY ATTEMPTED, when it produced no plan and
        # something LOWER-ranked ran instead. Not "ranked[0]": `select_pure`
        # short-circuits to the sticky-committed goal before walking the ranked
        # list, so under a live commitment the first attempt is the committed
        # objective — which is precisely the objective the arbiter was pursuing
        # and abandoned. A SATISFIED or SUPPRESSED candidate never reaches
        # `try_plan`, so it never appears here: it was not attempted, so it was
        # not abandoned.
        #
        # Derived from `goals_tried` rather than reported by `select_pure`,
        # which is mirrored in formal/Formal/ArbiterSelect.lean and stays pure.
        #
        # The fall-through to a lower-ranked goal is INTENDED; its silence was
        # not. Live traces 2026-08-12 show UpgradeEquipment(greater_wooden_staff)
        # ranked first and abandoned on 955 consecutive cycles with nothing
        # recorded, so 31 hours of runtime read as a deliberate choice to grind.
        #
        # There is deliberately NO `repr(chosen) != first["goal"]` conjunct: it
        # cannot be false, so it would be a vacuous guard. `select_pure` returns
        # a goal only when its `try_plan` came back NON-EMPTY, and the dedupe
        # above keeps each goal's LAST attempt — so `first["plan_len"] == 0`
        # already proves `first` is not what ran.
        first = self.goals_tried[0] if self.goals_tried else None
        if first is not None and not first["plan_len"] and chosen is not None:
            self.objective_unplannable = dict(first)
        return chosen, plan, self.goals_tried

    def _resolve_step_goal(
        self,
        chosen_step: MetaGoal | None,
        chosen_root: MetaGoal | None,
        fallback_steps: list[MetaGoal],
        fallback_roots: list[MetaGoal],
        state: WorldState,
        game_data: GameData,
        ctx: SelectionContext,
    ) -> Goal | None:
        """Objective step tier: map the top strategy step to a Goal, walking fallbacks (equip-first) when it is None."""
        # Walk: top step first, then fallbacks in ranking order. First
        # non-None goal wins. Closes the 2026-06-06 09:59 gap where
        # bootstrap step returned None (no winnable target) and gear roots
        # below it (ranked 1.0) were never tried — bot dropped straight
        # to discretionary PursueTask instead of pursuing the runner-up.
        # Prefer UpgradeEquipment steps over GatherMaterials steps when both
        # exist in the fallback chain. Trace 2026-06-06 12:28: bot crafted
        # 2 copper_daggers via CraftRelief guard but never equipped — the
        # fallback walk hit copper_boots (step=copper_ore→GatherMaterials)
        # before copper_dagger (step=copper_dagger→UpgradeEquipment), so
        # arbiter sticky-committed to GatherMaterials forever while
        # copper_dagger sat in inventory. An owned-but-unequipped target
        # is a ONE-action win (EquipAction) vs a multi-cycle GatherMaterials
        # chain; the ready-to-equip path is always preferable.
        step_goal = objective_step_goal(chosen_step, state, game_data, ctx,
                                        root=chosen_root, committed_root=chosen_root,
                                        history=self._history)
        if step_goal is not None:
            return step_goal
        # First pass: prefer UpgradeEquipmentGoal (one-step equip).
        for idx, alt in enumerate(fallback_steps):
            alt_root = fallback_roots[idx] if idx < len(fallback_roots) else None
            candidate = objective_step_goal(alt, state, game_data, ctx, root=alt_root,
                                          committed_root=chosen_root,
                                          history=self._history)
            if isinstance(candidate, UpgradeEquipmentGoal):
                return candidate
        # Second pass: any non-None goal in ranking order.
        for idx, alt in enumerate(fallback_steps):
            alt_root = fallback_roots[idx] if idx < len(fallback_roots) else None
            candidate = objective_step_goal(alt, state, game_data, ctx, root=alt_root,
                                          committed_root=chosen_root,
                                          history=self._history)
            if candidate is not None:
                return candidate
        return None

    def _suppress_step_for_task(
        self,
        step_goal: Goal | None,
        discretionary_kinds: list[MeansKind],
        state: WorldState,
        game_data: GameData,
    ) -> Goal | None:
        """Step-suppression: drop a step the active items task already covers,
        can trade now, or whose craft would EAT the task's reserved materials."""
        if MeansKind.PURSUE_TASK not in discretionary_kinds:
            return step_goal
        # Task-material reservation (P0 2026-06-09): a step whose craft closure
        # CONSUMES a reserved item without surplus is deferred this cycle —
        # otherwise GatherMaterials(copper_helmet) eats the 6 copper_bars the
        # copper_bar items task just pooled and the task restarts from zero,
        # forever. Surplus above the remaining task need passes; re-evaluated
        # every cycle (defer, not ban). Covers GatherMaterials AND a committed
        # UpgradeEquipment whose craft consumes reserved inputs.
        if step_goal is not None:
            needed = _reservation_consumption(step_goal, state, game_data)
            if needed is not None and consumes_reserved(needed, state, game_data):
                return None
        if not isinstance(step_goal, GatherMaterialsGoal):
            return step_goal
        # An active items-task pursuit suppresses the meta-objective's
        # GatherMaterials step ONLY when that step targets an item the task's
        # OWN recipe chain already produces — PursueTask plans the same
        # gather, so the meta-step is a redundant 1-cycle detour. A step
        # whose target lives outside the task chain (e.g. ash_wood for a
        # wooden_shield while the task is copper_ore) is independent gear
        # progress and must not be suppressed; without it the bot never
        # crafts equipment because the chain never gets cycles to
        # accumulate. Non-GatherMaterials steps (UpgradeEquipment, LevelSkill)
        # are sustained, high-value goals and always allowed to compete.
        if step_goal._target_item in _task_recipe_inputs(state.task_code, game_data):
            return None
        # Trade-ready PursueTask wins over fallback gear-chain gathering.
        # Trace 2026-06-06 14:40 (cycles 25-26): task=items/copper_bar at
        # 20/21, 1 copper_bar in inventory; gear-chain fallback
        # ObtainItem(copper_boots) → GatherMaterials(copper_bar, needed=8)
        # ran instead of PursueTask's TaskTrade. One trade would complete
        # the task; the bot instead gathered MORE copper_ore for armor
        # while the held bar sat unused.
        # When the fallback step's target IS the task code AND the bot
        # holds that item, defer the fallback for one cycle so
        # PursueTask's TaskTrade can immediately advance task_progress.
        # After TaskComplete + rotation (or after trading), the suppression
        # clears and fallback resumes the gear chain.
        if (state.task_type == "items"
                and step_goal._target_item == state.task_code
                and state.inventory.get(state.task_code, 0) > 0):
            return None
        return step_goal

    def _build_candidates(
        self,
        guard_kinds: list[GuardKind],
        collect_kinds: list[MeansKind],
        discretionary_kinds: list[MeansKind],
        step_goal: Goal | None,
        fallback_steps: list[MetaGoal],
        fallback_roots: list[MetaGoal],
        state: WorldState,
        game_data: GameData,
        ctx: SelectionContext,
        step_profile: dict[str, int] | None = None,
        chosen_root: MetaGoal | None = None,
    ) -> list[Candidate]:
        """Candidate ordering: guards, collect, step + fallback-step chain, discretionary."""
        candidates: list[Candidate] = []
        for gk in guard_kinds:
            g = map_guard(gk, game_data, ctx, state, step_profile, self._history)
            candidates.append(Candidate(goal=g, is_means=False, repr_=repr(g), band=BAND_GUARD))
        for mk in collect_kinds:
            g = map_means(mk, game_data, ctx, state, self._history)
            candidates.append(Candidate(goal=g, is_means=True, repr_=repr(g), band=BAND_COLLECT))
        # Equip-owned-gear (COLLECT band): a first-class objective that equips
        # already-OWNED positive-Rank gear into currently-EMPTY slots, so free
        # gear is worn before the bot grinds for more (COLLECT outranks the
        # step/grind tier). Materialized directly here — like the objective
        # step_goal below and unlike the `active_means` MeansKinds — so it stays
        # OUT of `COLLECT_REWARD_ORDER` and the liveness ladder it mirrors: this
        # candidate is a bounded, one-action, self-satisfying equip (fires only
        # while `fills` is non-empty, then `is_satisfied`), never a blocker. The
        # reserved set is the active items-task's material reservation
        # (`task_reserved_demand`) — the same pipeline `_suppress_step_for_task`
        # protects — so an owned item still owed to a task is not equipped away.
        equip_fills = empty_slot_rank_fills(
            state, game_data, frozenset(task_reserved_demand(state, game_data)))
        if equip_fills:
            eq_goal = EquipOwnedGoal(fills=equip_fills)
            candidates.append(Candidate(goal=eq_goal, is_means=True,
                                        repr_=repr(eq_goal), band=BAND_COLLECT))
        # Withdraw-tools (COLLECT band): same materialized-here contract as
        # EquipOwnedGoal — bounded, self-satisfying, never a blocker. Ferries a
        # strictly-better BANKED gathering tool into the bag; the proven gather
        # re-arm (GATHER_LOADOUT_PENALTY + OptimizeLoadout(Gather)) equips it,
        # and `_best_gathering_tools` in the deposit keep-set stops the
        # ping-pong back to the bank. pick_loadout scans only owned items, so
        # without this ferry a banked tool is invisible forever (trace
        # 2026-07-05: copper_pickaxe banked, 261/300 cycles bare-handed mining).
        bank_tile = game_data.bank_location_or_none
        if ctx.bank_accessible and bank_tile is not None:
            tool_fills = bank_tool_fills(
                state, game_data, frozenset(task_reserved_demand(state, game_data)))
            if tool_fills:
                wt_goal = WithdrawToolsGoal(fills=tool_fills, bank_location=bank_tile,
                                            accessible=ctx.bank_accessible)
                candidates.append(Candidate(goal=wt_goal, is_means=True,
                                            repr_=repr(wt_goal), band=BAND_COLLECT))
        # Urgent-hoard recycle (COLLECT band): the discretionary RECYCLE_SURPLUS
        # means is starved while a step goal stays plannable, so a skill grind
        # feeds its output pile unboundedly (copper_helmet x30, trace
        # 2026-07-05). Past RECYCLE_HOIST_URGENCY (every 5 surplus copies of the
        # largest pile = +1x urgency, see recycle_urgency) the goal is
        # materialized here — same bounded, self-satisfying, never-a-blocker
        # contract as EquipOwnedGoal — so the hoard melts back to its keep-cap
        # before more grinding. Pressure-gated like the discretionary means:
        # recycling MINTS materials into the bag, so under space pressure the
        # deposit/discard guards own the bag instead.
        recycle_surplus_map = recyclable_surplus(state, game_data, ctx)
        hoist_recycle = (shed_urgency(recycle_surplus_map) >= RECYCLE_HOIST_URGENCY
                         and _used_fraction(state) < SELL_PRESSURE_FRACTION)
        if hoist_recycle:
            rs_goal = RecycleSurplusGoal(
                game_data=game_data, ctx=ctx,
                initial_total=sum(recycle_surplus_map.values()))
            candidates.append(Candidate(goal=rs_goal, is_means=True,
                                        repr_=repr(rs_goal), band=BAND_COLLECT))
        # Urgent-hoard SELL and DRAIN (COLLECT band) — 2026-08-05, part 2 of the
        # disposal-unification epic. The recycle hoist above fixed exactly ONE of
        # the three starved shed rungs; the other two kept firing and kept losing.
        # Measured over the five `play-trace-*.jsonl` runs in the worktree (54
        # cycles): `drain_bank_junk` fired 44 times and was selected 0, `sell_idle`
        # fired 32 and was selected 0, while the bank grew to 2273 shedable copies
        # across 18 codes. The objective step is essentially always plannable, so a
        # rung below it is not low-priority, it is unreachable.
        #
        # SAFE ONLY NOW. Hoisting these before part 1 would have converted a static
        # hoard into a withdraw->redeposit livelock, because the drain licensed
        # what the disposal route banked straight back. That contradiction is now
        # arithmetically impossible — one `ai/keep_valuation.worth_keeping` feeds
        # both sides, and `formal/Formal/DisposalRoute.lean` proves
        # `drained_is_never_deposited` and, in the post-withdraw state,
        # `withdrawn_is_never_redeposited`.
        #
        # ORDER WITHIN THE BAND: recycle, then sell, then drain — most to least
        # value recovered. Recycling returns materials, a sale returns gold, and
        # the drain's terminal route for true junk is DELETE. Same bounded,
        # self-satisfying, never-a-blocker contract as EquipOwnedGoal, and the same
        # pressure gate as the discretionary means: both MINT items into the bag,
        # so under space pressure the deposit/discard guards own it instead.
        #
        # TWO THRESHOLDS, ONE PER POPULATION (see `ai/shed_urgency`): a BAG-side
        # pile is already in hand and sheds in one action, so it uses the same
        # >5-spares ladder the recycle hoist has used since 2026-07-05; a
        # BANK-side pile costs a withdraw-then-shed round trip that carries at
        # most one bag-load, so it must be worth a FULL load. The bag rule
        # applied to the bank hoisted on 30 banked `nettle_leaf` and preempted a
        # winnable fight — ordinary bank stock is not a hoard.
        sell_bag = sell_targets(state, game_data, ctx)
        sell_bank = bank_sellable_surplus(state, game_data, ctx)
        hoist_sell = ((shed_urgency(sell_bag) >= SHED_HOIST_URGENCY
                       or bank_shed_hoist(sell_bank, state.inventory_max))
                      and _used_fraction(state) < SELL_PRESSURE_FRACTION)
        if hoist_sell:
            # `state=` arms AND bounds the bank arm (SellInventoryGoal.__init__):
            # without the snapshot the arm has no termination bound and the goal
            # keeps its bag-only behaviour.
            si_goal = SellInventoryGoal(game_data=game_data, ctx=ctx,
                                        bank_accessible=ctx.bank_accessible,
                                        state=state)
            candidates.append(Candidate(goal=si_goal, is_means=True,
                                        repr_=repr(si_goal), band=BAND_COLLECT))
        drain_excess_map = bank_drain_excess(state, game_data, ctx)
        hoist_drain = (bank_shed_hoist(drain_excess_map, state.inventory_max)
                       and ctx.bank_accessible
                       and _used_fraction(state) < SELL_PRESSURE_FRACTION)
        if hoist_drain:
            # `initial_total` is what makes the rung plannable AT ALL: the
            # all-or-nothing form is unreachable for a pile deeper than the bag
            # (probe 2026-08-05: 1993 licensed copies -> nodes_explored=8,
            # plan_len=0, no timeout). See DrainBankJunkGoal.is_satisfied.
            db_goal = DrainBankJunkGoal(game_data=game_data, ctx=ctx,
                                        bank_accessible=ctx.bank_accessible,
                                        initial_total=sum(drain_excess_map.values()))
            candidates.append(Candidate(goal=db_goal, is_means=True,
                                        repr_=repr(db_goal), band=BAND_COLLECT))
        # Append step_goal + every fallback-step goal in ranking order so
        # select_pure walks them all before reaching discretionary. Trace
        # 2026-06-06 16:34 (cycles 0-1): top step's GrindCharacterXP
        # produced plan_len=0 (yellow_slime fails level filter) and the
        # arbiter dropped straight to TaskExchange (timed out, 18260
        # nodes), emitting Wait. Including fallback steps lets the gear
        # chain (GatherMaterials/UpgradeEquipment) get tried even when the
        # top combat step can't plan.
        added_reprs: set[str] = set()
        if step_goal is not None:
            r = repr(step_goal)
            candidates.append(Candidate(goal=step_goal, is_means=True, repr_=r, band=BAND_STEP))
            added_reprs.add(r)
        for idx, alt in enumerate(fallback_steps):
            alt_root = fallback_roots[idx] if idx < len(fallback_roots) else None
            alt_goal = objective_step_goal(alt, state, game_data, ctx, root=alt_root,
                                          committed_root=chosen_root,
                                          history=self._history)
            # Route every fallback-alt step goal through the SAME task
            # suppression as the top step (reservation + redundancy +
            # trade-ready). Pre-fix these were re-appended UNSUPPRESSED, so a
            # goal the reservation deferred leaked back in via the fallback
            # chain and still ate the task's pooled materials.
            alt_goal = self._suppress_step_for_task(
                alt_goal, discretionary_kinds, state, game_data)
            if alt_goal is None:
                continue
            r = repr(alt_goal)
            if r in added_reprs:
                continue
            added_reprs.add(r)
            candidates.append(Candidate(goal=alt_goal, is_means=True, repr_=r, band=BAND_FALLBACK_STEP))
        for mk in discretionary_kinds:
            if hoist_recycle and mk is MeansKind.RECYCLE_SURPLUS:
                # Already materialized in the COLLECT band this cycle; a second
                # "RecycleSurplus" candidate would duplicate the repr the
                # sticky-commitment machinery keys on.
                continue
            if hoist_sell and mk is MeansKind.SELL_IDLE:
                # Same dedup, for the hoisted sell. The discretionary twin would
                # carry the SAME "SellInventory" repr but NO bank-arm snapshot, so
                # leaving it in would also give the sticky machinery two goals with
                # one key and different behaviour. (SELL_PRESSURED maps to the same
                # repr from the COLLECT band, but it and this hoist are mutually
                # exclusive: it fires at or above SELL_PRESSURE_FRACTION and the
                # hoist is gated strictly below it.)
                continue
            if hoist_drain and mk is MeansKind.DRAIN_BANK_JUNK:
                # Same dedup, for the hoisted drain — and here the discretionary
                # twin is worse than redundant: built without `initial_total` it is
                # the all-or-nothing goal that can never plan.
                continue
            g = map_means(mk, game_data, ctx, state, self._history)
            candidates.append(Candidate(goal=g, is_means=True, repr_=repr(g), band=BAND_DISCRETIONARY))
        for raid_goal in self._raid_candidates(state, game_data):
            candidates.append(Candidate(goal=raid_goal, is_means=True,
                                        repr_=repr(raid_goal), band=BAND_DISCRETIONARY))
        return candidates

    def _raid_candidates(self, state: WorldState,
                         game_data: GameData) -> list[ParticipateRaidGoal]:
        """One participation goal per OPEN raid whose boss is worth engaging.

        Deliberately NOT a MeansKind: a new kind ripples through the ladder,
        DecideKey.lean and the E-tower rows. A plain discretionary candidate
        yields to every guard and objective step, which is the right priority for
        a timed bonus.

        Gated on (window open, tile known, survivable, worth-positive). The worth
        gate uses the raid's remaining window in FIGHTS, which is unknown offline,
        so it is skipped when the window is not known -- the survivability gate
        still applies, and a raid the bot cannot survive is never offered.
        """
        out: list[ParticipateRaidGoal] = []
        for raid in state.active_raids:
            if not game_data.raid_location_tiles(raid.code):
                continue
            damage = expected_damage_per_fight(state, game_data, raid.monster)
            if not raid_survivable_pure(state.hp, state.max_hp, damage):
                continue
            out.append(ParticipateRaidGoal(raid_code=raid.code,
                                           monster_code=raid.monster,
                                           xp_floor=state.xp))
        return out

    def _worth_gate_suppressed(
        self,
        objective: CharacterObjective | None,
        chosen_root: MetaGoal | None,
        discretionary_kinds: list[MeansKind],
        state: WorldState,
        game_data: GameData,
        ctx: SelectionContext,
    ) -> set[str]:
        """Worth gate: reprs of discretionary task means serving none of the committed objective's unmet needs."""
        # ── Worth gate ─────────────────────────────────────────────────────
        # Suppress discretionary task means (PursueTask/AcceptTask) that serve
        # NONE of the committed objective's unmet needs. A suppressed committed
        # task is skipped before the sticky check, so the objective step (earlier
        # in the candidate order) wins instead of an always-plannable distraction
        # task. See spec 2026-06-09 Components 3/4.
        worth_suppressed: set[str] = set()
        if objective is None or chosen_root is None:
            return worth_suppressed
        needs = objective_needs(chosen_root, state, game_data)
        if not needs.is_empty:
            for mk in (MeansKind.PURSUE_TASK, MeansKind.ACCEPT_TASK):
                if mk not in discretionary_kinds:
                    continue
                g = map_means(mk, game_data, ctx, state)
                if not means_serves(mk, g, needs, state, game_data):
                    worth_suppressed.add(repr(g))
        return worth_suppressed

    def _arbitrate(
        self,
        candidates: list[Candidate],
        suppressed: frozenset[str] | set[str],
        worth_suppressed: set[str],
        state: WorldState,
        game_data: GameData,
        actions: list[Action],
        ctx: SelectionContext,
    ) -> tuple[Goal | None, list[Action], str | None]:
        """Ordered walk → worth-gate bypass → Wait fallback.

        ONE walk at ONE budget. The cheap/full two-pass this replaced escalated
        only `if chosen is None`, and a fallback combat grind always plans, so
        the escalation was unreachable in practice and the cheap budget was the
        real budget for every objective."""

        def _is_suppressed_base(goal: Goal) -> bool:
            r = repr(goal)
            return r != "TaskCancel" and r in suppressed

        _effective_suppressed = set(suppressed) | worth_suppressed

        def is_suppressed(goal: Goal) -> bool:
            r = repr(goal)
            return r != "TaskCancel" and r in _effective_suppressed

        # memo_bypass = guard candidates PLUS memo-exempt goals. Guards are
        # safety/gear-critical, few, and rarely time out; memo-exempt goals have a
        # plannability that flips on fast-churning HP/inventory the memo's
        # (level, skills) signature cannot track, so a transient no-plan must not
        # skip or mark them (`Goal.memo_exempt`). Both sets bypass the memo alone —
        # there is no longer a second budget for either to earn.
        memo_bypass = ({c.repr_ for c in candidates if not c.is_means}
                       | {c.repr_ for c in candidates if c.goal.memo_exempt})
        non_wait = [c for c in candidates if not isinstance(c.goal, WaitGoal)]

        def _skip(goal: Goal) -> bool:
            # Memo never skips guards or memo-exempt goals.
            return repr(goal) not in memo_bypass and self._memo.is_doomed(
                repr(goal), state, self._cycle)

        def try_plan(goal: Goal) -> list[Action]:
            if _skip(goal):
                return []
            # The cooldown window, floored at the one budget
            # (`planner._SEARCH_BUDGET_SECONDS`) — None when there is no
            # cooldown to spend. See `_cycle_budget_seconds`.
            plan = self._plans(goal, state, game_data, actions, ctx,
                               self._cycle_budget_seconds())
            return self._record_attempt(goal, plan, self._last_timed_out, state,
                                        memo_bypass)

        def satisfied(goal: Goal) -> bool:
            return goal.is_satisfied(state)

        # THE walk over non-Wait candidates, in band order.
        chosen, plan, new_committed = select_pure(
            candidates=non_wait, committed_repr=self._committed_repr,
            try_plan=try_plan, is_satisfied=satisfied, is_suppressed=is_suppressed)
        if chosen is None and worth_suppressed:
            # Last resort: objective step unplannable AND every need-serving means
            # failed, leaving only worth-suppressed task means. Re-run WITHOUT the
            # worth gate so the bot keeps earning instead of idling. Mark the trace
            # so "objective stalled, doing income" is observable.
            chosen, plan, new_committed = select_pure(
                candidates=non_wait, committed_repr=self._committed_repr,
                try_plan=try_plan, is_satisfied=satisfied,
                is_suppressed=_is_suppressed_base)
            if chosen is not None:
                self.goals_tried.append({"goal": "worth_gate_bypassed", "nodes": 0,
                                         "depth": 0, "timed_out": False,
                                         "plan_len": len(plan)})
        if chosen is None:
            # Last resort: Wait (special-cased to a single WaitAction).
            wait = next((c for c in candidates if isinstance(c.goal, WaitGoal)), None)
            if wait is not None and not is_suppressed(wait.goal):
                chosen, plan, new_committed = wait.goal, [WaitAction()], self._committed_repr
        return chosen, plan, new_committed

    def _dedupe_goals_tried(self) -> list[dict[str, object]]:
        """Telemetry: one record per goal (the LAST attempt wins, first-seen order kept)."""
        # KEPT after the two-pass walk was deleted, because a goal can still be
        # probed twice in one cycle: when nothing plans AND the worth gate
        # suppressed something, `_arbitrate` re-runs the walk without the gate,
        # and a MEMO-BYPASSING candidate (guard or `memo_exempt`) is not skipped
        # the second time, so it plans again and appends a second record. Only
        # memo-marked candidates are skipped on the re-run.
        #
        # dict insertion order keeps the FIRST-SEEN position of each goal while
        # the VALUE is the last attempt — `select`'s `objective_unplannable`
        # depends on both halves of that.
        deduped: dict[str, dict[str, object]] = {}
        for attempt in self.goals_tried:
            deduped[str(attempt["goal"])] = attempt
        return list(deduped.values())
