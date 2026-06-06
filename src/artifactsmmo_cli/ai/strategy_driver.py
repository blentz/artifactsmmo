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
from artifactsmmo_cli.ai.goals.task_exchange import TaskExchangeGoal
from artifactsmmo_cli.ai.goals.unlock_bank import UnlockBankGoal
from artifactsmmo_cli.ai.goals.wait import WaitGoal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.task_batch import task_batch_size
from artifactsmmo_cli.ai.task_feasibility import task_requirement
from artifactsmmo_cli.ai.tiers.guards import GuardKind, SelectionContext, active_guards
from artifactsmmo_cli.ai.tiers.means import MeansKind, active_means
from artifactsmmo_cli.ai.tiers.meta_goal import (
    MetaGoal,
    ObtainItem,
    ReachCharLevel,
    ReachSkillLevel,
)
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

def _materials_in_hand(item: str, state: WorldState, game_data: GameData) -> bool:
    """True if every direct recipe material for `item` is fully covered by
    inventory + bank (so the craft+equip plan is short and reachable)."""
    recipe = game_data._crafting_recipes.get(item) or {}
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
        return DiscardOverstockGoal(game_data=game_data)
    if kind is GuardKind.BANK_UNLOCK:
        return UnlockBankGoal(
            bank_locked=not ctx.bank_accessible,
            initial_xp=ctx.initial_xp,
            target_monster=ctx.bank_unlock_monster,
        )
    if kind is GuardKind.REACH_UNLOCK_LEVEL:
        return ReachUnlockLevelGoal(target_level=ctx.bank_required_level)
    if kind is GuardKind.DEPOSIT_FULL:
        return DepositInventoryGoal(bank_accessible=ctx.bank_accessible, game_data=game_data)
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
        recipe = game_data._crafting_recipes.get(item) or {}
        needed = {mat: qty for mat, qty in recipe.items()}
        return GatherMaterialsGoal(target_item=item, needed=needed)
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
        return TaskExchangeGoal(min_coins=ctx.task_exchange_min_coins)
    if kind is MeansKind.BANK_EXPAND:
        return ExpandBankGoal(bank_accessible=ctx.bank_accessible, game_data=game_data)
    if kind is MeansKind.WAIT:
        return WaitGoal()
    raise ValueError(f"Unknown MeansKind: {kind!r}")


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
            return UpgradeEquipmentGoal(
                initial_equipment=state.equipment,
                committed_target=(step.code, slots[0]),
            )
        # Intermediate step: if the chain root is an equippable, plan
        # against the root directly. UpgradeEquipmentGoal's planner
        # walks the recipe chain (craft intermediates + final + equip)
        # while GatherMaterialsGoal stops at the intermediate.
        if isinstance(root, ObtainItem) and root.code != step.code:
            root_stats = game_data.item_stats(root.code)
            root_slots = ITEM_TYPE_TO_SLOTS.get(root_stats.type_) if root_stats is not None else None
            if root_slots:
                return UpgradeEquipmentGoal(
                    initial_equipment=state.equipment,
                    committed_target=(root.code, root_slots[0]),
                )
        return GatherMaterialsGoal(target_item=step.code, needed={step.code: step.quantity})
    if isinstance(step, ReachSkillLevel):
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
    ) -> tuple[Goal | None, list[Action], list[dict[str, object]]]:
        """Select the first plannable goal from the ordered candidate list.

        decision must have a .chosen_step attribute (MetaGoal | None).

        Candidates whose repr is in `suppressed` are skipped, EXCEPT TaskCancel
        which is never suppressed (it is the escape hatch for a stuck task).

        Returns (goal, plan, goals_tried).
        """
        self.goals_tried = []

        def is_suppressed(goal: Goal) -> bool:
            r = repr(goal)
            return r != "TaskCancel" and r in suppressed

        chosen_step: MetaGoal | None = getattr(decision, "chosen_step", None)
        chosen_root: MetaGoal | None = getattr(decision, "chosen_root", None)
        fallback_steps: list[MetaGoal] = getattr(decision, "fallback_steps", [])
        fallback_roots: list[MetaGoal] = getattr(decision, "fallback_roots", [])

        guard_kinds = active_guards(state, game_data, self._history, ctx)
        collect_kinds, discretionary_kinds = active_means(state, game_data, self._history, ctx)

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
        if step_goal is None:
            # First pass: prefer UpgradeEquipmentGoal (one-step equip).
            for idx, alt in enumerate(fallback_steps):
                alt_root = fallback_roots[idx] if idx < len(fallback_roots) else None
                candidate = objective_step_goal(alt, state, game_data, ctx, root=alt_root)
                if isinstance(candidate, UpgradeEquipmentGoal):
                    step_goal = candidate
                    chosen_step = alt
                    break
            # Second pass: any non-None goal in ranking order.
            if step_goal is None:
                for idx, alt in enumerate(fallback_steps):
                    alt_root = fallback_roots[idx] if idx < len(fallback_roots) else None
                    step_goal = objective_step_goal(alt, state, game_data, ctx, root=alt_root)
                    if step_goal is not None:
                        chosen_step = alt
                        break

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
        if (MeansKind.PURSUE_TASK in discretionary_kinds
                and isinstance(step_goal, GatherMaterialsGoal)
                and step_goal._target_item in _task_recipe_inputs(state.task_code, game_data)):
            step_goal = None

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
        if (MeansKind.PURSUE_TASK in discretionary_kinds
                and state.task_type == "items"
                and isinstance(step_goal, GatherMaterialsGoal)
                and step_goal._target_item == state.task_code
                and state.inventory.get(state.task_code, 0) > 0):
            step_goal = None

        # Trace 2026-05-19 (cycles 318-342): with task_code=None, the bot
        # locked into a Gather→Discard loop — meta-objective step
        # GatherMaterials(copper_ring) ran every other cycle pulling
        # copper_ore that DISCARD_HIGH immediately deleted because the
        # overstock cap had no task floor to lean on. AcceptTask was in
        # the discretionary kinds the whole time but sat positionally
        # AFTER the meta-step, so it never won. When there's no active
        # task, accepting one is the cheap unblock: it gives PursueTask a
        # target, brings the task-chain keep-set online, and gives the
        # gathered materials a destination other than the trash. Suppress
        # the meta-step in this state so AcceptTask wins the walk.
        if (state.task_code is None
                and MeansKind.ACCEPT_TASK in discretionary_kinds):
            step_goal = None

        # Build ordered candidates: guards, collect, step + fallback-step
        # chain, discretionary.
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
        if chosen is None:
            # Last resort: Wait (special-cased to a single WaitAction).
            wait = next((c for c in candidates if isinstance(c.goal, WaitGoal)), None)
            if wait is not None and not is_suppressed(wait.goal):
                chosen, plan, new_committed = wait.goal, [WaitAction()], self._committed_repr

        self._committed_repr = new_committed
        # The two-pass walk probes a non-guard candidate at most twice (cheap
        # then full budget); collapse those to the LAST (full-budget) attempt so
        # goals_tried stays one record per goal (the planner-attempt telemetry is
        # diagnostic-only; the final attempt carries the authoritative stats).
        deduped: dict[str, dict[str, object]] = {}
        for attempt in self.goals_tried:
            deduped[str(attempt["goal"])] = attempt
        self.goals_tried = list(deduped.values())
        return chosen, plan, self.goals_tried
