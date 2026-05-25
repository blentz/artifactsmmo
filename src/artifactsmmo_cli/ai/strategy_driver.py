"""Tier-3 → planner bridge: map the strategy's chosen step to a parameterized
existing goal.

Lives above goals/ and tiers/ (imports both) to avoid the goals→tiers cycle."""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.equipment import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.goals.claim_pending import ClaimPendingGoal
from artifactsmmo_cli.ai.goals.combat import AcceptTaskGoal, CompleteTaskGoal
from artifactsmmo_cli.ai.goals.discard_overstock import DiscardOverstockGoal
from artifactsmmo_cli.ai.goals.expand_bank import ExpandBankGoal
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.grind_character_xp import GrindCharacterXPGoal
from artifactsmmo_cli.ai.goals.level_skill import LevelSkillGoal
from artifactsmmo_cli.ai.goals.low_yield_cancel import LowYieldCancelGoal
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from artifactsmmo_cli.ai.goals.pursue_task import PursueTaskGoal
from artifactsmmo_cli.ai.goals.reach_unlock_level import ReachUnlockLevelGoal
from artifactsmmo_cli.ai.goals.sell_inventory import SellInventoryGoal
from artifactsmmo_cli.ai.goals.survival import DepositInventoryGoal, RestoreHPGoal
from artifactsmmo_cli.ai.goals.task_cancel import TaskCancelGoal
from artifactsmmo_cli.ai.goals.task_exchange import TaskExchangeGoal
from artifactsmmo_cli.ai.goals.unlock_bank import UnlockBankGoal
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

LEVEL_LOOKAHEAD = 3
"""How many levels ahead the objective step / task skill-gate targets, replacing
the old hard current+1. The planner re-plans every cycle and executes only
plan[0], so this steers search reachability/direction, not commitment. Tunable:
raise toward 5 if traces show 90s-budget headroom; deeper risks a no_plan
timeout on a long recipe chain."""

# ---------------------------------------------------------------------------
# Flat map functions + StrategyArbiter
# ---------------------------------------------------------------------------

def map_guard(kind: GuardKind, game_data: GameData, ctx: SelectionContext) -> Goal:
    """Map a GuardKind to a parameterized Goal instance."""
    if kind is GuardKind.HP_CRITICAL:
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
                                  initial_skill_xp=state.skill_xp.get(req.skill, 0))
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
    raise ValueError(f"Unknown MeansKind: {kind!r}")


def objective_step_goal(
    step: MetaGoal | None,
    state: WorldState,
    game_data: GameData,
    ctx: SelectionContext,
) -> Goal | None:
    """Map the strategy's chosen step to a Goal."""
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
        return GatherMaterialsGoal(target_item=step.code, needed={step.code: step.quantity})
    if isinstance(step, ReachSkillLevel):
        current = state.skills.get(step.skill, 0)
        target = min(step.level, current + LEVEL_LOOKAHEAD)
        return LevelSkillGoal(skill_name=step.skill, target_level=target,
                              initial_skill_xp=state.skill_xp.get(step.skill, 0))
    if isinstance(step, ReachCharLevel):
        if ctx.combat_monster is None:
            return None
        if (state.task_type == "items" and state.task_code
                and state.task_total > 0 and state.task_progress < state.task_total):
            return None        # grind can't advance an items task; let PURSUE_TASK run
        return GrindCharacterXPGoal(target_monster=ctx.combat_monster, initial_xp=state.xp,
                                    game_data=game_data)
    return None


def _precedes(
    candidates: list[tuple[Goal, bool]],
    a_repr: str,
    b_repr: str,
) -> bool:
    """Return True if the candidate with repr a_repr appears before b_repr in the list."""
    a_idx = next((i for i, (g, _) in enumerate(candidates) if repr(g) == a_repr), None)
    b_idx = next((i for i, (g, _) in enumerate(candidates) if repr(g) == b_repr), None)
    if a_idx is None or b_idx is None:
        return False
    return a_idx < b_idx


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

    def _plans(
        self,
        goal: Goal,
        state: WorldState,
        game_data: GameData,
        actions: list[Action],
    ) -> list[Action]:
        """Attempt to plan goal; record attempt in goals_tried; return plan ([] = failed)."""
        plan = self._planner.plan(state, goal, actions, game_data, self._history)
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

        guard_kinds = active_guards(state, game_data, self._history, ctx)
        collect_kinds, discretionary_kinds = active_means(state, game_data, self._history, ctx)

        step_goal = objective_step_goal(chosen_step, state, game_data, ctx)

        # Build ordered candidates: (goal, is_means)
        candidates: list[tuple[Goal, bool]] = []
        for gk in guard_kinds:
            candidates.append((map_guard(gk, game_data, ctx), False))
        for mk in collect_kinds:
            candidates.append((map_means(mk, game_data, ctx, state), True))
        if step_goal is not None:
            candidates.append((step_goal, True))
        for mk in discretionary_kinds:
            candidates.append((map_means(mk, game_data, ctx, state), True))

        # Sticky: if we have a committed means repr, check if it still fires and plans
        # (and no guard candidate precedes it)
        tried_repr: str | None = None
        if self._committed_repr is not None:
            committed_goal: Goal | None = next(
                (g for g, is_means in candidates if is_means and repr(g) == self._committed_repr),
                None,
            )
            if (committed_goal is not None and not committed_goal.is_satisfied(state)
                    and not is_suppressed(committed_goal)):
                # Check that no guard precedes the committed goal
                guard_reprs = [repr(g) for g, is_means in candidates if not is_means]
                guard_precedes = any(
                    _precedes(candidates, gr, self._committed_repr) for gr in guard_reprs
                )
                if not guard_precedes:
                    plan = self._plans(committed_goal, state, game_data, actions)
                    tried_repr = self._committed_repr
                    if plan:
                        return committed_goal, plan, self.goals_tried

        # Walk candidates in order; return first that plans
        for goal, is_means in candidates:
            # Skip if already attempted in the sticky block above
            if repr(goal) == tried_repr:
                continue
            # Skip suppressed candidates (TaskCancel is never suppressed)
            if is_suppressed(goal):
                continue
            # Skip satisfied goals early to avoid unnecessary planning
            if goal.is_satisfied(state):
                continue
            plan = self._plans(goal, state, game_data, actions)
            if plan:
                self._committed_repr = repr(goal) if is_means else None
                return goal, plan, self.goals_tried

        # Nothing plans
        self._committed_repr = None
        return None, [], self.goals_tried
