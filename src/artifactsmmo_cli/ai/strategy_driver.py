"""Tier-3 → planner bridge: map the strategy's chosen step to a parameterized
existing goal.

Lives above goals/ and tiers/ (imports both) to avoid the goals→tiers cycle."""

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
from artifactsmmo_cli.ai.consumable_supply import best_held_heal
from artifactsmmo_cli.ai.craft_plan_gen import generate_next_craft_action
from artifactsmmo_cli.ai.craft_relief import craft_relief_candidates
from artifactsmmo_cli.ai.doomed_memo import DoomedMemo
from artifactsmmo_cli.ai.equipment.bank_tool_fills import bank_tool_fills
from artifactsmmo_cli.ai.equipment.empty_slot_fills import empty_slot_rank_fills
from artifactsmmo_cli.ai.expected_damage import expected_damage_per_fight
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gather_skill_resource import best_gather_resource_drop
from artifactsmmo_cli.ai.gather_step_target import gather_step_target
from artifactsmmo_cli.ai.goals.accept_task_goal import AcceptTaskGoal
from artifactsmmo_cli.ai.goals.base import Goal
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
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from artifactsmmo_cli.ai.goals.provision_marginal_fight import ProvisionMarginalFightGoal
from artifactsmmo_cli.ai.goals.pursue_task import PursueTaskGoal
from artifactsmmo_cli.ai.goals.reach_currency import ReachCurrencyGoal
from artifactsmmo_cli.ai.goals.reach_skill import ReachSkillGoal
from artifactsmmo_cli.ai.goals.reach_unlock_level import ReachUnlockLevelGoal
from artifactsmmo_cli.ai.goals.recycle_surplus import RecycleSurplusGoal
from artifactsmmo_cli.ai.goals.restore_hp import RestoreHPGoal
from artifactsmmo_cli.ai.goals.sell_inventory import SellInventoryGoal
from artifactsmmo_cli.ai.goals.task_cancel import TaskCancelGoal
from artifactsmmo_cli.ai.goals.task_exchange import TaskExchangeGoal, tasks_coin_total
from artifactsmmo_cli.ai.goals.unlock_bank import UnlockBankGoal
from artifactsmmo_cli.ai.goals.wait import WaitGoal
from artifactsmmo_cli.ai.goals.withdraw_tools import WithdrawToolsGoal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.objective_step_fight_core import objective_step_is_fight_pure
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.potion_provision_qty import potion_provision_qty_pure
from artifactsmmo_cli.ai.recipe_closure import closure_demand
from artifactsmmo_cli.ai.recycle_surplus import recyclable_surplus, recycle_urgency
from artifactsmmo_cli.ai.task_batch import task_batch_size
from artifactsmmo_cli.ai.task_feasibility import task_requirement
from artifactsmmo_cli.ai.task_reservation import consumes_reserved, task_reserved_demand
from artifactsmmo_cli.ai.thresholds import UTILITY_SLOT_MAX_STACK
from artifactsmmo_cli.ai.tiers.guards import (
    GuardKind,
    SelectionContext,
    _gear_protected,
    _used_fraction,
    active_guards,
    active_profile,
    recycle_protected_codes,
)
from artifactsmmo_cli.ai.tiers.means import (
    SELL_PRESSURE_FRACTION,
    MeansKind,
    active_means,
)
from artifactsmmo_cli.ai.tiers.means_worth import means_serves
from artifactsmmo_cli.ai.tiers.meta_goal import (
    MetaGoal,
    ObtainItem,
    ReachCharLevel,
    ReachSkillLevel,
)
from artifactsmmo_cli.ai.tiers.next_tier_cap import (
    next_tier_cap_pure,
    next_tier_dampened_pure,
)
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective, _permanent_vendor_purchases
from artifactsmmo_cli.ai.tiers.objective_needs import objective_needs
from artifactsmmo_cli.ai.tiers.owned_count import owned_count_pure
from artifactsmmo_cli.ai.tiers.skill_grind_target import build_grind_candidates
from artifactsmmo_cli.ai.tiers.skill_step_dispatch import (
    DispatchCandidate,
    FlagInputs,
    cannibalize_pure,
    dispatch_candidate_flags,
    skill_step_dispatch_pure,
)
from artifactsmmo_cli.ai.tiers.skill_target_curve import SkillItem
from artifactsmmo_cli.ai.tiers.strategy import actionable_step
from artifactsmmo_cli.ai.world_state import WorldState

RECYCLE_HOIST_URGENCY = 2
"""Urgency multiple (see `recycle_urgency`: every 5 surplus copies of the
largest pile = +1x) at which RecycleSurplus is materialized in the COLLECT band
instead of waiting in the starved discretionary tier — i.e. >5 spares of the
grind output. Below it, the pile is normal working slack."""

CHEAP_BUDGET_SECONDS = 10.0
"""Per-candidate budget for the arbiter's cheap first pass. Sized ABOVE the
I/O-bound planning time of a reachable goal under `--learn` (~7.5s; each A* node
issues LearningStore SQLite queries) so a legitimately-plannable goal — e.g. the
gear-chain GatherMaterials step — is found in the cheap pass instead of being
starved and forcing escalation. Width-unfindable goals still exceed 10s here and
are memoized. Guards bypass this and always get the full (300s) budget. Tunable;
see the tiered-budget spec. (A 1s value starved real goals on the live --learn
bot, which then escalated every doomed candidate at the full budget.)"""

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
        chain: dict[str, int] = {}
        closure_demand(code, missing, game_data, chain, frozenset())
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


def _gated_behind_skill(code: str, skill: str, current_level: int,
                        game_data: GameData) -> bool:
    """True when `code` is gear/tool crafted by `skill` at a level ABOVE
    `current_level` — i.e. it is SKILL-GATED behind the very skill being
    grinded. Its recipe materials must NOT be reserved against that grind: the
    grind toward `skill` is this objective's own legitimate bootstrap, and
    reserving the shared material self-locks (the copper_bar held for the gated
    copper_legs_armor is the same copper_bar the grind must spend to reach
    gearcrafting 5 and unlock it). Trace 2026-06-14 192617."""
    stats = game_data.item_stats(code)
    return (stats is not None and stats.crafting_skill == skill
            and stats.crafting_level > current_level)


def _skill_dispatch_candidates(
    skill: str, state: WorldState, game_data: GameData,
    reserved_full: set[str], reserved_relaxed: set[str],
    current_level: int, objective_targets: frozenset[str],
    wanted_targets: frozenset[str],
) -> list[DispatchCandidate]:
    """Hoist in-skill grind candidates with the two reserved-set membership
    flags the proved dispatch core consumes (relaxed ⊆ full, so a candidate
    whose recipe avoids `reserved_full` also avoids `reserved_relaxed`).

    Reservation EXEMPTION (trace 2026-06-14 230824): a candidate that is itself
    an unowned, craftable-now committed OBJECTIVE target (in `objective_targets`)
    is exempt from the reserved flags. Crafting it advances BOTH a gear slot and
    the grinding skill — it is objective progress, never throwaway
    cannibalization — so it must not be blocked by the very reservation that
    protects its own materials. The unowned guard avoids re-grinding a target
    already in hand (the '6 helmets, 0 boots' over-craft); throwaway (non-target)
    in-skill items stay reservation-blocked.

    LAST-RESORT CANNIBALIZATION: a `ReachSkillLevel` grind is always skill-gated
    (we are here only because the objective needs a higher skill). When we
    already own ≥1 of EVERY craftable-now in-skill item — no unowned target left
    to skill up on — the FULL pass finds nothing and we would freeze. In that
    narrow corner only, free the RELAXED pass entirely so it may re-craft (eat a
    reserved material) to keep leveling. The full pass still respects every
    reservation, so cannibalization happens solely when there is genuinely no
    non-consuming option left."""
    equipped = [c for c in state.equipment.values() if c is not None]

    def owned(code: str) -> bool:
        return owned_count_pure(state.inventory, state.bank_items, equipped, code) >= 1

    raw = build_grind_candidates(skill, state, game_data)
    flag_inputs = [
        FlagInputs(code=gc.code,
                   recipe_mats=tuple(game_data.crafting_recipe(gc.code) or {}),
                   craft_level=gc.craft_level, obtainable=gc.obtainable,
                   is_target=gc.code in objective_targets, owned=owned(gc.code))
        for gc in raw
    ]
    cannibalize = cannibalize_pure(current_level, flag_inputs)
    rf, rr = frozenset(reserved_full), frozenset(reserved_relaxed)
    out: list[DispatchCandidate] = []
    for gc, fi in zip(raw, flag_inputs, strict=False):
        uses_full, uses_relaxed = dispatch_candidate_flags(fi, current_level, rf, rr, cannibalize)
        out.append(DispatchCandidate(
            code=gc.code, craft_skill=gc.craft_skill, craft_level=gc.craft_level,
            mats_missing=gc.mats_missing, obtainable=gc.obtainable,
            uses_reserved_full=uses_full, uses_reserved_relaxed=uses_relaxed,
            # Prefer crafting a real, usable-NOW gear/tool target (or the committed
            # objective item) over a throwaway for skill XP. NOTE: `wanted_targets`
            # is near-term (near_term_gear ∪ target_tools ∪ committed), NOT the
            # BiS `is_target` set used for reservation — at low char level no BiS
            # item is craftable, so is_target would never fire (dead-code trap).
            wanted=gc.code in wanted_targets,
        ))
    return out

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
    deposit/discard goals through the SAME `active_profile` merge the firing
    predicate used (trace 2026-06-11 22:36 cycle 30: DiscardOverstock deleted
    the active grind goal's own wooden_shield), so predicate and goal stay
    coherent."""
    if kind is GuardKind.HP_CRITICAL:
        return RestoreHPGoal()
    if kind is GuardKind.REST_FOR_COMBAT:
        return RestoreHPGoal()
    if kind is GuardKind.DISCARD_CRITICAL or kind is GuardKind.DISCARD_HIGH:
        profile = (active_profile(state, game_data, ctx, step_profile)
                   if state is not None else None)
        return DiscardOverstockGoal(game_data=game_data, profile=profile,
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
        profile_codes = (frozenset(active_profile(state, game_data, ctx, step_profile))
                         if state is not None else frozenset())
        return DepositInventoryGoal(bank_accessible=ctx.bank_accessible,
                                    game_data=game_data, profile_codes=profile_codes)
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
        protected = recycle_protected_codes(ctx)
        return RecycleSurplusGoal(
            game_data=game_data, protected_codes=protected,
            gear_keep=ctx.gear_keep or None,
            initial_total=sum(recyclable_surplus(
                state, game_data, protected,
                gear_keep=ctx.gear_keep or None).values()) if state else None)
    if kind is GuardKind.SELL_RELIEF:
        return SellInventoryGoal(bank_accessible=ctx.bank_accessible,
                                 gear_keep=ctx.gear_keep or None)
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
        return _gather_goal_for_unreachable_equippable(
            item, state, game_data, committed.max_depth)
    if kind is GuardKind.CRAFT_POTIONS:
        return CraftPotionsGoal(combat_monster=ctx.combat_monster, game_data=game_data,
                                history=history)
    raise ValueError(f"Unknown GuardKind: {kind!r}")


def map_means(kind: MeansKind, game_data: GameData, ctx: SelectionContext,
              state: WorldState, history: LearningStore | None = None) -> Goal:
    """Map a MeansKind to a parameterized Goal instance."""
    if kind is MeansKind.CLAIM_PENDING:
        return ClaimPendingGoal()
    if kind is MeansKind.COMPLETE_TASK:
        return CompleteTaskGoal()
    if kind is MeansKind.SELL_PRESSURED or kind is MeansKind.SELL_IDLE:
        return SellInventoryGoal(bank_accessible=ctx.bank_accessible,
                                 gear_keep=ctx.gear_keep or None)
    if kind is MeansKind.RECYCLE_SURPLUS:
        protected = recycle_protected_codes(ctx)
        return RecycleSurplusGoal(
            game_data=game_data, protected_codes=protected,
            gear_keep=ctx.gear_keep or None,
            initial_total=sum(recyclable_surplus(
                state, game_data, protected,
                gear_keep=ctx.gear_keep or None).values()))
    if kind is MeansKind.DRAIN_BANK_JUNK:
        return DrainBankJunkGoal(game_data=game_data,
                                 protected_codes=_gear_protected(ctx),
                                 bank_accessible=ctx.bank_accessible)
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
        return AcceptTaskGoal()
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
    if kind is MeansKind.WAIT:
        return WaitGoal()
    raise ValueError(f"Unknown MeansKind: {kind!r}")


def _gather_goal_for_unreachable_equippable(
    code: str, state: WorldState, game_data: GameData, equip_max_depth: int,
) -> GatherMaterialsGoal:
    """Build a budget-FEASIBLE GatherMaterials goal for a depth-unreachable
    equippable `code` (its full craft chain exceeds `equip_max_depth`).

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
    step = actionable_step(ObtainItem(code=code, quantity=1), state, game_data)
    if step is not None and isinstance(step, ObtainItem) and step.code != code:
        tgt_code, tgt_qty = gather_step_target(
            code, step.code, step.quantity,
            game_data.crafting_recipes, owned, equip_max_depth,
            game_data.max_gather_yield)
        return GatherMaterialsGoal(target_item=tgt_code, needed={tgt_code: tgt_qty})
    # No deeper actionable step (the root itself is the actionable leaf, or the
    # chain is cyclically blocked): fall back to the direct recipe. A recipe-less
    # root never reaches here (callers gate on a non-empty recipe / is_plannable).
    recipe = game_data.crafting_recipe(code) or {}
    return GatherMaterialsGoal(target_item=code, needed=dict(recipe))


def _equippable_goal(code: str, slot: str, state: WorldState, game_data: GameData) -> Goal:
    """Map an equippable target to UpgradeEquipment when it is reachable, else to
    GatherMaterials for its recipe.

    UpgradeEquipmentGoal.is_plannable is False when the target's materials aren't
    yet gathered (min_gathers > max_depth — the depth-reachability gate). Returning
    that depth-gated UpgradeEquipment would have the arbiter SKIP it (the gate
    short-circuits planning), and with nothing driving the gather, gear progress
    stalls and the cheap pass falls through to doomed discretionary goals
    (TaskExchange/LevelSkill) that escalate at the full budget — the live-bot
    stall. Instead, while the target is depth-unreachable, drive GatherMaterials
    for its direct recipe so the materials accumulate across cycles; once they are
    in hand UpgradeEquipment becomes plannable and fires the craft+equip. (Mirrors
    the GEAR_REVIEW guard's gather/upgrade split for the objective-step path.)"""
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
        # UNAFFORDABLE item-currency: accumulate the currency INCREMENTALLY
        # (needed = held+1, the grind-one-replan idiom) — a one-shot plan
        # for a 230-coin price is ~120 fights deep and dies on max_depth
        # (sandwhisper_bag probe @L50: 28K nodes, plan_len=0). Cheapest
        # PERMANENT located vendor decides the price (semantic key; event/
        # unlocated vendors mirror currency_demand's exclusion). Gold-priced
        # items skip the accumulation (gold is earned by normal play, not a
        # gatherable item) and fall through to the buy attempt.
        bank = state.bank_items or {}
        purchases = [(price, currency)
                     for price, currency in _permanent_vendor_purchases(code, game_data)
                     if currency != "gold"]
        if purchases:
            price, currency = min(purchases)
            held = state.inventory.get(currency, 0) + bank.get(currency, 0)
            if held < price:
                return GatherMaterialsGoal(target_item=currency,
                                           needed={currency: held + 1})
        return GatherMaterialsGoal(target_item=code, needed={code: 1})
    if upgrade.is_plannable(state, game_data):
        return upgrade
    recipe = game_data.crafting_recipe(code) or {}
    if recipe:
        # Depth-UNREACHABLE from-scratch deep chain: route to the FLAT deepest
        # actionable step instead of GatherMaterials(code, DIRECT recipe), whose
        # plan must gather through the multi-level recipe and explodes the GOAP
        # search (see _gather_goal_for_unreachable_equippable).
        return _gather_goal_for_unreachable_equippable(
            code, state, game_data, upgrade.max_depth)
    # Unreachable in practice: is_plannable is only False when min_gathers >
    # max_depth, which requires a non-empty recipe (a recipe-less item needs at
    # most one gather, so it is always plannable and returns above). Kept as a
    # total-function fallback.
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
            return _equippable_goal(step.code, dest_slot, state, game_data)
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
                # step. Routing to the root here is a dead end: the
                # gather_step_target root-return branch emits
                # GatherMaterials(root) whose own skill-gate fail-fast
                # rejects it (trace 2026-06-11 18:46 cycle 15-16: both
                # gear roots produced 0-node dead candidates and the
                # arbiter fell through to slime grinding with the bar
                # objective abandoned at 1/5). Once the materials are in
                # hand the strategy's actionable_step advances to
                # ReachSkillLevel(craft_skill, N) and the branch below
                # grinds the skill.
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
                tgt_code, tgt_qty = gather_step_target(
                    root.code, step.code, step.quantity,
                    game_data.crafting_recipes, owned, upgrade.max_depth,
                    game_data.max_gather_yield)
                return GatherMaterialsGoal(target_item=tgt_code, needed={tgt_code: tgt_qty})
        return GatherMaterialsGoal(target_item=step.code, needed={step.code: step.quantity})
    if isinstance(step, ReachSkillLevel):
        # A "reach skill level N" step is width-unfindable as a single GOAP goal
        # (the planner can't simulate grinding many crafts to cross a whole
        # level — trace 2026-06-14 192617: the old LevelSkillGoal fallback timed
        # out 25/25 cycles, 60968 nodes/90s/plan_len 0). Route it through the
        # PROVED skill_step_dispatch core: craft ONE level-appropriate in-skill
        # item this cycle, replan, repeat — always plannable. The core decides
        # SUPPRESS / GRIND(code) / NO_GRIND; see
        # formal/Formal/Extracted/SkillStepDispatch.lean and
        # docs/PLAN_skill_step_dispatch_proof.md.
        #
        # Reservation (trace 2026-06-14): the grind must not cannibalize the
        # committed objective's materials. `reserved_full` covers both roots and
        # the committed objective gear/tools; `reserved_relaxed` frees the mats of
        # any objective SKILL-GATED behind step.skill (its grind is its own
        # bootstrap — project_skill_gated_self_lock). The core prefers a
        # full-respecting grind and relaxes only when the full pass finds nothing.
        current = state.skills.get(step.skill, 0)
        committed_skill, committed_level = "", 0
        if isinstance(committed_root, ObtainItem):
            cs = game_data.item_stats(committed_root.code)
            if cs is not None and cs.crafting_skill:
                committed_skill, committed_level = cs.crafting_skill, cs.crafting_level
        committed_codes = frozenset(r.code for r in (root, committed_root)
                                     if isinstance(r, ObtainItem))
        # Items the bot WANTS a keeper of right now: the usable-now near-term gear
        # and tool targets plus the committed objective item(s). The grind prefers
        # crafting one of these over a throwaway (same skill XP, plus a keeper).
        # SATISFIED filter (trace 2026-06-24 cyc319-344): a wanted item stays
        # `wanted` only while the bot does NOT yet hold enough to fill its slot(s)
        # (rings/utility = 2, else 1). Without this, the `held + 1` grind quantity
        # ratchets a wanted single-slot item forever — Robby ground 11 wooden_shields
        # (6 ash_plank each), stuffing the bag until an expensive craft could not
        # fit (5 free < 6 needed) and the loop became Withdraw(ash_plank)↔DepositAll.
        # Once satisfied, the item is no longer wanted and the grind reverts to the
        # cheap throwaway (copper_helmet, 1 mat), which fits and skills up.
        equipped_now = [c for c in state.equipment.values() if c is not None]

        def _unsatisfied(code: str) -> bool:
            stats = game_data.item_stats(code)
            slots = ITEM_TYPE_TO_SLOTS.get(stats.type_) if stats is not None else None
            demand = len(slots) if slots else 1
            return owned_count_pure(state.inventory, state.bank_items, equipped_now, code) < demand

        wanted_targets = frozenset(
            c for c in (ctx.near_term_targets | committed_codes) if _unsatisfied(c))
        source_codes: list[str] = list(committed_codes)
        source_codes += list(ctx.target_gear | ctx.target_tools)
        reserved_full: set[str] = set()
        reserved_relaxed: set[str] = set()
        for code in source_codes:
            rec = game_data.crafting_recipe(code)
            if not rec:
                continue
            reserved_full.update(rec)
            if not _gated_behind_skill(code, step.skill, current, game_data):
                reserved_relaxed.update(rec)
        candidates = _skill_dispatch_candidates(
            step.skill, state, game_data, reserved_full, reserved_relaxed,
            current, ctx.target_gear | ctx.target_tools, wanted_targets)
        # Next-tier throwaway dampener (project next-tier skill-grind dampener):
        # when this gear-crafting skill can ALREADY craft every gear item in the
        # 10-level band one tier above the character's level, a speculative
        # throwaway grind only over-skills a tier the committed root already
        # covers. Hoist the SkillItem view (mirrors skill_target_curve) and let
        # the proved cores decide; the dispatch core suppresses only a NOT-wanted
        # grind under this flag (need-exemption preserved).
        # Only the step's own skill is needed (next_tier_cap_pure filters
        # craft_skill == skill), so restrict the hoist to it instead of building
        # a SkillItem for every crafting item of every skill each cycle.
        skill_items = [
            SkillItem(
                stats.crafting_skill, stats.crafting_level, stats.level,
                (stats.type_ in ITEM_TYPE_TO_SLOTS or stats.subtype == "tool"),
            )
            for stats in game_data.all_item_stats.values()
            if stats.crafting_skill == step.skill
        ]
        next_cap = next_tier_cap_pure(step.skill, state.level, skill_items,
                                      game_data.max_skill_level)
        dampened = next_tier_dampened_pure(current, next_cap)
        decision = skill_step_dispatch_pure(step.skill, current,
                                            committed_skill, committed_level,
                                            candidates, dampened=dampened)
        if decision.kind == "grind":
            bank = state.bank_items or {}
            held = state.inventory.get(decision.code, 0) + bank.get(decision.code, 0)
            return GatherMaterialsGoal(target_item=decision.code,
                                       needed={decision.code: held + 1},
                                       skill_grind=True)
        # SUPPRESS: committed root crafts its own gear — no objective-step goal.
        # NO_GRIND: no craftable to grind. If the skill is gatherable at the
        # current level, LEVEL IT BY GATHERING its resource (grind-one-replan) —
        # a gatherable-but-no-low-craftable skill (alchemy: lowest recipe L5,
        # sunflower_field gives XP at L1) climbs to its first craftable level this
        # way. Skills with no gather resource fall through to None (arbiter
        # advances). Mirrors the "grind" branch's grind-one-replan.
        if decision.kind == "no_grind":
            drop = best_gather_resource_drop(step.skill, current, game_data)
            if drop is not None:
                bank = state.bank_items or {}
                held = state.inventory.get(drop, 0) + bank.get(drop, 0)
                return GatherMaterialsGoal(target_item=drop, needed={drop: held + 1},
                                           skill_grind=True)
        return None
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
        # Phase B3 (docs/PLAN_c2_composed_liveness.md): the fired guard/means
        # kinds exactly as the most recent select() saw them. Emitted into the
        # per-cycle trace so the offline ladder lockstep replays selection
        # against observed fires instead of re-deriving opaque predicates.
        self.last_fires: dict[str, object] = {}
        self._memo = DoomedMemo()
        self._cycle = 0
        # Whether the most recent `_plans` call ended in a budget TIMEOUT (vs an
        # EXHAUSTIVE search or a definitive is_plannable=False / WaitGoal result).
        # The cheap pass only memoizes CONCLUSIVE no-plans, so a cheap timeout
        # still escalates instead of being skipped. See `_record_attempt`.
        self._last_timed_out: bool = False

    def set_cycle(self, cycle: int) -> None:
        """Player calls this each cycle so the memo's re-probe window advances."""
        self._cycle = cycle

    def _plans(
        self,
        goal: Goal,
        state: WorldState,
        game_data: GameData,
        actions: list[Action],
        budget_seconds: float | None = None,
    ) -> list[Action]:
        """Attempt to plan goal; record attempt in goals_tried; return plan ([] = failed).

        WaitGoal is special-cased: it is never satisfiable (is_satisfied always
        False) and its only action (WaitAction) is a no-op on WorldState, so
        A* would never terminate via the planner. Short-circuit to a
        single-step [WaitAction()] plan so the last-resort fallback always
        provides a firing candidate to select_pure.
        """
        if isinstance(goal, WaitGoal):
            wait_plan: list[Action] = [WaitAction()]
            self._last_timed_out = False
            self.goals_tried.append({
                "goal": repr(goal),
                "nodes": 0,
                "depth": 1,
                "timed_out": False,
                "plan_len": 1,
            })
            return wait_plan
        # Provably-sound pre-plan reachability gate: a goal whose minimum plan is
        # longer than its max_depth can never be planned (the planner never
        # returns a plan longer than max_depth — formal/Formal/PlannerDepthBound),
        # so skip it instead of burning the full 90s budget. This is what stops
        # UpgradeEquipment(copper_boots) — 80 gathers vs max_depth 32 — from
        # stalling the first cycle.
        if not goal.is_plannable(state, game_data, self._history):
            # A proven-unplannable goal is a CONCLUSIVE no-plan (not a timeout):
            # the cheap pass may safely memoize it.
            self._last_timed_out = False
            self.goals_tried.append({
                "goal": repr(goal),
                "nodes": 0,
                "depth": 0,
                "timed_out": False,
                "plan_len": 0,
            })
            return []
        # Fast-path: for a deterministic gather-craft closure (all leaves are
        # gatherable raws or skill-gated-met craftables) skip A* entirely.
        # O(closure) vs 52K-node search for copper_ring-style chains.
        # Falls back to None for monster-drop / NPC-buy / unmet-skill-gate goals.
        gen = generate_next_craft_action(goal, state, game_data, actions)
        if gen is not None:
            self._last_timed_out = False
            self.goals_tried.append({
                "goal": repr(goal),
                "nodes": 0,
                "depth": 0,
                "timed_out": False,
                "plan_len": len(gen),
            })
            return gen
        plan = self._planner.plan(state, goal, actions, game_data, self._history,
                                  budget_seconds=budget_seconds)
        stats = self._planner.last_stats
        self._last_timed_out = stats.timed_out
        self.goals_tried.append({
            "goal": repr(goal),
            "nodes": stats.nodes_explored,
            "depth": stats.max_depth_reached,
            "timed_out": stats.timed_out,
            "node_capped": stats.node_capped,
            "plan_len": len(plan),
        })
        return plan

    def _record_attempt(self, goal: Goal, plan: list[Action], timed_out: bool,
                        state: WorldState, guard_reprs: set[str], *,
                        mark_on_timeout: bool) -> list[Action]:
        """Update the doomed-memo from one planning attempt and return `plan`.

        - A found plan (or a guard goal) CLEARS any prior doomed mark.
        - A no-plan result MARKS the goal doomed when it is conclusive: always for
          the full pass (`mark_on_timeout=True`), but only on an EXHAUSTIVE search
          (`not timed_out`) for the cheap pass, so a cheap-budget timeout stays
          available for the full-budget escalation instead of being skipped.
        Guards bypass the memo entirely (they always get the full budget)."""
        r = repr(goal)
        if r in guard_reprs or plan:
            self._memo.clear(r)
        elif mark_on_timeout or not timed_out:
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

        chosen_step: MetaGoal | None = getattr(decision, "chosen_step", None)
        chosen_root: MetaGoal | None = getattr(decision, "chosen_root", None)
        fallback_steps: list[MetaGoal] = getattr(decision, "fallback_steps", [])
        fallback_roots: list[MetaGoal] = getattr(decision, "fallback_roots", [])

        collect_kinds, discretionary_kinds = active_means(state, game_data, self._history, ctx)

        step_goal = self._resolve_step_goal(
            chosen_step, chosen_root, fallback_steps, fallback_roots, state, game_data, ctx)
        step_goal = self._suppress_step_for_task(step_goal, discretionary_kinds, state, game_data)

        # The step goal is resolved BEFORE the guards so its needed map can
        # join the deposit/discard protection profile. Trace 2026-06-11 22:36
        # (cycle 30): DISCARD_HIGH deleted a wooden_shield the active
        # GatherMaterials grind goal (needed = held + 1) was accumulating —
        # the guard's profile only knew crafting_target/gear/tools/task.
        step_profile = _step_protection_profile(step_goal, state, game_data)
        guard_kinds = active_guards(state, game_data, self._history, ctx, step_profile)
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
            candidates, suppressed, worth_suppressed, state, game_data, actions)

        self._committed_repr = new_committed
        self.goals_tried = self._dedupe_goals_tried()
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
        recycle_surplus_map = recyclable_surplus(
            state, game_data, recycle_protected_codes(ctx),
            gear_keep=ctx.gear_keep or None)
        hoist_recycle = (recycle_urgency(recycle_surplus_map) >= RECYCLE_HOIST_URGENCY
                         and _used_fraction(state) < SELL_PRESSURE_FRACTION)
        if hoist_recycle:
            rs_goal = RecycleSurplusGoal(
                game_data=game_data,
                protected_codes=recycle_protected_codes(ctx),
                gear_keep=ctx.gear_keep or None,
                initial_total=sum(recycle_surplus_map.values()))
            candidates.append(Candidate(goal=rs_goal, is_means=True,
                                        repr_=repr(rs_goal), band=BAND_COLLECT))
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
            g = map_means(mk, game_data, ctx, state, self._history)
            candidates.append(Candidate(goal=g, is_means=True, repr_=repr(g), band=BAND_DISCRETIONARY))
        return candidates

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
    ) -> tuple[Goal | None, list[Action], str | None]:
        """Tier walk: cheap pass → full-budget escalation → worth-gate bypass → Wait fallback."""

        def _is_suppressed_base(goal: Goal) -> bool:
            r = repr(goal)
            return r != "TaskCancel" and r in suppressed

        _effective_suppressed = set(suppressed) | worth_suppressed

        def is_suppressed(goal: Goal) -> bool:
            r = repr(goal)
            return r != "TaskCancel" and r in _effective_suppressed

        # Partition: guard candidates always get the full budget and bypass the
        # memo (safety/gear-critical, few, rarely time out). Non-guard candidates
        # go through the cheap pass → escalation → memo machinery.
        guard_reprs = {c.repr_ for c in candidates if not c.is_means}
        # memo_bypass = guards PLUS memo-exempt goals (their plannability flips on
        # fast-churning HP/inventory the memo's (level, skills) signature can't
        # track, so a transient no-plan must not skip or mark them (Goal.memo_exempt).
        # Distinct from guard_reprs because exempt goals still take the CHEAP budget
        # (they plan in a few nodes); only guards earn the full budget.
        memo_bypass = guard_reprs | {c.repr_ for c in candidates if c.goal.memo_exempt}
        non_wait = [c for c in candidates if not isinstance(c.goal, WaitGoal)]

        def _budget_for(goal: Goal, cheap: bool) -> float | None:
            if repr(goal) in guard_reprs:
                return None  # guards: full budget always
            return CHEAP_BUDGET_SECONDS if cheap else None

        def _skip(goal: Goal) -> bool:
            # Memo never skips guards or memo-exempt goals.
            return repr(goal) not in memo_bypass and self._memo.is_doomed(
                repr(goal), state, self._cycle)

        def try_plan_cheap(goal: Goal) -> list[Action]:
            if _skip(goal):
                return []
            plan = self._plans(goal, state, game_data, actions, _budget_for(goal, cheap=True))
            # Cheap pass: memoize only a CONCLUSIVE no-plan (search exhausted, not a
            # budget timeout). A cheap timeout stays unmemoized so it can escalate.
            # This is the feather_coat 99%-CPU fix: a doomed goal passed over in the
            # cheap walk (because a LATER goal plans) is now recorded instead of
            # re-exploding every cycle (the full pass that used to mark it never ran).
            return self._record_attempt(goal, plan, self._last_timed_out, state,
                                        memo_bypass, mark_on_timeout=False)

        def try_plan_full(goal: Goal) -> list[Action]:
            if _skip(goal):
                return []
            plan = self._plans(goal, state, game_data, actions, _budget_for(goal, cheap=False))
            # Full (last-resort) pass: mark on ANY no-plan, timeout included — the
            # pragmatic backoff trigger (the exponential window re-probes later).
            return self._record_attempt(goal, plan, self._last_timed_out, state,
                                        memo_bypass, mark_on_timeout=True)

        def satisfied(goal: Goal) -> bool:
            return goal.is_satisfied(state)

        # Cheap pass over non-Wait candidates (guards inside still get full budget).
        chosen, plan, new_committed = select_pure(
            candidates=non_wait, committed_repr=self._committed_repr,
            try_plan=try_plan_cheap, is_satisfied=satisfied, is_suppressed=is_suppressed)
        if chosen is None:
            # Escalation pass at full budget; memoize timeouts.
            chosen, plan, new_committed = select_pure(
                candidates=non_wait, committed_repr=self._committed_repr,
                try_plan=try_plan_full, is_satisfied=satisfied, is_suppressed=is_suppressed)
        if chosen is None and worth_suppressed:
            # Last resort: objective step unplannable AND every need-serving means
            # failed, leaving only worth-suppressed task means. Re-run WITHOUT the
            # worth gate so the bot keeps earning instead of idling. Mark the trace
            # so "objective stalled, doing income" is observable.
            chosen, plan, new_committed = select_pure(
                candidates=non_wait, committed_repr=self._committed_repr,
                try_plan=try_plan_full, is_satisfied=satisfied,
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
        """Telemetry: collapse the two-pass probes to one record per goal (the last, full-budget attempt wins)."""
        # The two-pass walk probes a non-guard candidate at most twice (cheap
        # then full budget); collapse those to the LAST (full-budget) attempt so
        # goals_tried stays one record per goal (the planner-attempt telemetry is
        # diagnostic-only; the final attempt carries the authoritative stats).
        deduped: dict[str, dict[str, object]] = {}
        for attempt in self.goals_tried:
            deduped[str(attempt["goal"])] = attempt
        return list(deduped.values())
