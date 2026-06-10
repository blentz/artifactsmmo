"""Tier-3 → planner bridge: map the strategy's chosen step to a parameterized
existing goal.

Lives above goals/ and tiers/ (imports both) to avoid the goals→tiers cycle."""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.actions.wait import WaitAction
from artifactsmmo_cli.ai.arbiter_select import Candidate, select_pure
from artifactsmmo_cli.ai.craft_relief import craft_relief_candidates
from artifactsmmo_cli.ai.doomed_memo import DoomedMemo
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gather_step_target import gather_step_target
from artifactsmmo_cli.ai.goals.accept_task_goal import AcceptTaskGoal
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.goals.claim_pending import ClaimPendingGoal
from artifactsmmo_cli.ai.goals.complete_task_goal import CompleteTaskGoal
from artifactsmmo_cli.ai.goals.craft_relief import CraftReliefGoal
from artifactsmmo_cli.ai.goals.deposit_inventory import DepositInventoryGoal
from artifactsmmo_cli.ai.goals.discard_overstock import DiscardOverstockGoal
from artifactsmmo_cli.ai.goals.expand_bank import ExpandBankGoal
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.grind_character_xp import GrindCharacterXPGoal
from artifactsmmo_cli.ai.goals.level_skill import LevelSkillGoal
from artifactsmmo_cli.ai.goals.low_yield_cancel import LowYieldCancelGoal
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from artifactsmmo_cli.ai.goals.pursue_task import PursueTaskGoal
from artifactsmmo_cli.ai.goals.reach_unlock_level import ReachUnlockLevelGoal
from artifactsmmo_cli.ai.goals.restore_hp import RestoreHPGoal
from artifactsmmo_cli.ai.goals.sell_inventory import SellInventoryGoal
from artifactsmmo_cli.ai.goals.task_cancel import TaskCancelGoal
from artifactsmmo_cli.ai.goals.task_exchange import TaskExchangeGoal, tasks_coin_total
from artifactsmmo_cli.ai.goals.unlock_bank import UnlockBankGoal
from artifactsmmo_cli.ai.goals.wait import WaitGoal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.task_batch import task_batch_size
from artifactsmmo_cli.ai.task_feasibility import task_requirement
from artifactsmmo_cli.ai.task_reservation import consumes_reserved
from artifactsmmo_cli.ai.tiers.guards import (
    GuardKind,
    SelectionContext,
    active_guards,
    active_profile,
)
from artifactsmmo_cli.ai.tiers.means import MeansKind, active_means
from artifactsmmo_cli.ai.tiers.means_worth import means_serves
from artifactsmmo_cli.ai.tiers.meta_goal import (
    MetaGoal,
    ObtainItem,
    ReachCharLevel,
    ReachSkillLevel,
)
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.objective_needs import objective_needs
from artifactsmmo_cli.ai.tiers.skill_grind_target import skill_grind_target
from artifactsmmo_cli.ai.tiers.strategy import actionable_step
from artifactsmmo_cli.ai.world_state import WorldState

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
              state: WorldState | None = None) -> Goal:
    """Map a GuardKind to a parameterized Goal instance.

    `state` is required for CRAFT_RELIEF (which inspects current inventory
    to pick its craft target); optional otherwise to preserve legacy
    callers / tests that constructed guards without a state."""
    if kind is GuardKind.HP_CRITICAL:
        return RestoreHPGoal()
    if kind is GuardKind.REST_FOR_COMBAT:
        return RestoreHPGoal()
    if kind is GuardKind.DISCARD_CRITICAL or kind is GuardKind.DISCARD_HIGH:
        profile = (active_profile(state, game_data, ctx) if state is not None else None)
        return DiscardOverstockGoal(game_data=game_data, profile=profile)
    if kind is GuardKind.BANK_UNLOCK:
        return UnlockBankGoal(
            bank_locked=not ctx.bank_accessible,
            initial_xp=ctx.initial_xp,
            target_monster=ctx.bank_unlock_monster,
        )
    if kind is GuardKind.REACH_UNLOCK_LEVEL:
        return ReachUnlockLevelGoal(target_level=ctx.bank_required_level)
    if kind is GuardKind.DEPOSIT_FULL:
        profile_codes = (frozenset(active_profile(state, game_data, ctx))
                         if state is not None else frozenset())
        return DepositInventoryGoal(bank_accessible=ctx.bank_accessible,
                                    game_data=game_data, profile_codes=profile_codes)
    if kind is GuardKind.CRAFT_RELIEF:
        if state is None:
            raise ValueError("CRAFT_RELIEF guard requires a state to pick a target")
        cands = craft_relief_candidates(
            state, game_data,
            target_gear=ctx.target_gear, target_tools=ctx.target_tools,
        )
        if not cands:
            raise ValueError("CRAFT_RELIEF mapped but no relief candidate available")
        top = cands[0]
        return CraftReliefGoal(
            target_item=top.item_code,
            initial_qty=state.inventory.get(top.item_code, 0),
            batch=top.quantity,
        )
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
    raise ValueError(f"Unknown GuardKind: {kind!r}")


def map_means(kind: MeansKind, game_data: GameData, ctx: SelectionContext,
              state: WorldState) -> Goal:
    """Map a MeansKind to a parameterized Goal instance."""
    if kind is MeansKind.CLAIM_PENDING:
        return ClaimPendingGoal()
    if kind is MeansKind.COMPLETE_TASK:
        return CompleteTaskGoal()
    if kind is MeansKind.SELL_PRESSURED or kind is MeansKind.SELL_IDLE:
        return SellInventoryGoal(bank_accessible=ctx.bank_accessible)
    if kind is MeansKind.LOW_YIELD_CANCEL:
        return LowYieldCancelGoal()
    if kind is MeansKind.TASK_CANCEL:
        return TaskCancelGoal()
    if kind is MeansKind.PURSUE_TASK:
        req = task_requirement(state, game_data)
        if req is not None and req.skill != "combat":
            current = state.skills.get(req.skill, 0)
            target = min(req.required_level, current + LEVEL_LOOKAHEAD)
            return LevelSkillGoal(skill_name=req.skill, target_level=target,
                                  initial_skill_xp=state.skill_xp.get(req.skill, 0),
                                  xp_curve=ctx.skill_xp_curves.get(req.skill))
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
        return ExpandBankGoal(bank_accessible=ctx.bank_accessible, game_data=game_data)
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
            game_data.crafting_recipes, owned, equip_max_depth)
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


def objective_step_goal(
    step: MetaGoal | None,
    state: WorldState,
    game_data: GameData,
    ctx: SelectionContext,
    root: MetaGoal | None = None,
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
        stats = game_data.item_stats(step.code)
        slots = ITEM_TYPE_TO_SLOTS.get(stats.type_) if stats is not None else None
        if slots:
            return _equippable_goal(step.code, slots[0], state, game_data)
        # Intermediate step: if the chain root is an equippable, plan
        # against the root directly. UpgradeEquipmentGoal's planner
        # walks the recipe chain (craft intermediates + final + equip)
        # while GatherMaterialsGoal stops at the intermediate.
        if isinstance(root, ObtainItem) and root.code != step.code:
            root_stats = game_data.item_stats(root.code)
            root_slots = ITEM_TYPE_TO_SLOTS.get(root_stats.type_) if root_stats is not None else None
            if root_slots:
                upgrade = UpgradeEquipmentGoal(initial_equipment=state.equipment,
                                               committed_target=(root.code, root_slots[0]))
                if upgrade.is_plannable(state, game_data):
                    # Root chain depth-reachable (materials in hand/craftable):
                    # plan the whole craft+equip under one commit.
                    return upgrade
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
                owned: dict[str, int] = dict(state.inventory)
                for code, qty in (state.bank_items or {}).items():
                    owned[code] = owned.get(code, 0) + qty
                tgt_code, tgt_qty = gather_step_target(
                    root.code, step.code, step.quantity,
                    game_data.crafting_recipes, owned, upgrade.max_depth)
                return GatherMaterialsGoal(target_item=tgt_code, needed={tgt_code: tgt_qty})
        return GatherMaterialsGoal(target_item=step.code, needed={step.code: step.quantity})
    if isinstance(step, ReachSkillLevel):
        # Plannable craft-one: a "reach skill level N" step is width-unfindable as
        # a single GOAP goal (the planner can't simulate grinding many crafts).
        # Route it to crafting ONE shallow in-skill item per cycle; the per-cycle
        # replan grinds the skill incrementally and the step is always plannable.
        # Falls back to LevelSkillGoal only when nothing in-skill is craftable now.
        craft_one = skill_grind_target(step.skill, state, game_data)
        if craft_one is not None:
            return GatherMaterialsGoal(target_item=craft_one, needed={craft_one: 1})
        current = state.skills.get(step.skill, 0)
        target = min(step.level, current + LEVEL_LOOKAHEAD)
        return LevelSkillGoal(skill_name=step.skill, target_level=target,
                              initial_skill_xp=state.skill_xp.get(step.skill, 0),
                              xp_curve=ctx.skill_xp_curves.get(step.skill))
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
        bootstrap_gap = step.level - state.level
        if bootstrap_gap > 4 and (
                state.task_type == "items" and state.task_code
                and state.task_total > 0 and state.task_progress < state.task_total):
            return None        # long-haul grind, items task active → defer
        return GrindCharacterXPGoal(target_monster=ctx.combat_monster, initial_xp=state.xp,
                                    game_data=game_data)
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
        self._memo = DoomedMemo()
        self._cycle = 0

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
        # UpgradeEquipment(copper_boots) — 80 gathers vs max_depth 15 — from
        # stalling the first cycle.
        if not goal.is_plannable(state, game_data, self._history):
            self.goals_tried.append({
                "goal": repr(goal),
                "nodes": 0,
                "depth": 0,
                "timed_out": False,
                "plan_len": 0,
            })
            return []
        plan = self._planner.plan(state, goal, actions, game_data, self._history,
                                  budget_seconds=budget_seconds)
        stats = self._planner.last_stats
        self.goals_tried.append({
            "goal": repr(goal),
            "nodes": stats.nodes_explored,
            "depth": stats.max_depth_reached,
            "timed_out": stats.timed_out,
            "plan_len": len(plan),
        })
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

        guard_kinds = active_guards(state, game_data, self._history, ctx)
        collect_kinds, discretionary_kinds = active_means(state, game_data, self._history, ctx)

        step_goal = self._resolve_step_goal(
            chosen_step, chosen_root, fallback_steps, fallback_roots, state, game_data, ctx)
        step_goal = self._suppress_step_for_task(step_goal, discretionary_kinds, state, game_data)

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
            fallback_steps, fallback_roots, state, game_data, ctx)

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
        step_goal = objective_step_goal(chosen_step, state, game_data, ctx, root=chosen_root)
        if step_goal is not None:
            return step_goal
        # First pass: prefer UpgradeEquipmentGoal (one-step equip).
        for idx, alt in enumerate(fallback_steps):
            alt_root = fallback_roots[idx] if idx < len(fallback_roots) else None
            candidate = objective_step_goal(alt, state, game_data, ctx, root=alt_root)
            if isinstance(candidate, UpgradeEquipmentGoal):
                return candidate
        # Second pass: any non-None goal in ranking order.
        for idx, alt in enumerate(fallback_steps):
            alt_root = fallback_roots[idx] if idx < len(fallback_roots) else None
            candidate = objective_step_goal(alt, state, game_data, ctx, root=alt_root)
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
    ) -> list[Candidate]:
        """Candidate ordering: guards, collect, step + fallback-step chain, discretionary."""
        candidates: list[Candidate] = []
        for gk in guard_kinds:
            g = map_guard(gk, game_data, ctx, state)
            candidates.append(Candidate(goal=g, is_means=False, repr_=repr(g)))
        for mk in collect_kinds:
            g = map_means(mk, game_data, ctx, state)
            candidates.append(Candidate(goal=g, is_means=True, repr_=repr(g)))
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
            candidates.append(Candidate(goal=step_goal, is_means=True, repr_=r))
            added_reprs.add(r)
        for idx, alt in enumerate(fallback_steps):
            alt_root = fallback_roots[idx] if idx < len(fallback_roots) else None
            alt_goal = objective_step_goal(alt, state, game_data, ctx, root=alt_root)
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
            candidates.append(Candidate(goal=alt_goal, is_means=True, repr_=r))
        for mk in discretionary_kinds:
            g = map_means(mk, game_data, ctx, state)
            candidates.append(Candidate(goal=g, is_means=True, repr_=repr(g)))
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
        non_wait = [c for c in candidates if not isinstance(c.goal, WaitGoal)]

        def _budget_for(goal: Goal, cheap: bool) -> float | None:
            if repr(goal) in guard_reprs:
                return None  # guards: full budget always
            return CHEAP_BUDGET_SECONDS if cheap else None

        def _skip(goal: Goal) -> bool:
            # Memo only governs non-guard goals; guards are never memo-skipped.
            return repr(goal) not in guard_reprs and self._memo.is_doomed(
                repr(goal), state, self._cycle)

        def try_plan_cheap(goal: Goal) -> list[Action]:
            if _skip(goal):
                return []
            return self._plans(goal, state, game_data, actions, _budget_for(goal, cheap=True))

        def try_plan_full(goal: Goal) -> list[Action]:
            if _skip(goal):
                return []
            plan = self._plans(goal, state, game_data, actions, _budget_for(goal, cheap=False))
            if not plan and repr(goal) not in guard_reprs:
                self._memo.mark(repr(goal), state, self._cycle)
            else:
                self._memo.clear(repr(goal))
            return plan

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
