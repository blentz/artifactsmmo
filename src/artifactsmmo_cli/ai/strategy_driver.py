"""Tier-3 → planner bridge: map the strategy's chosen step to a parameterized
existing goal.

Lives above goals/ and tiers/ (imports both) to avoid the goals→tiers cycle."""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.arbiter_select import Candidate, select_pure
from artifactsmmo_cli.ai.game_data import GameData
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
from artifactsmmo_cli.ai.goals.pursue_task import PursueTaskGoal
from artifactsmmo_cli.ai.goals.reach_unlock_level import ReachUnlockLevelGoal
from artifactsmmo_cli.ai.goals.restore_hp import RestoreHPGoal
from artifactsmmo_cli.ai.goals.sell_inventory import SellInventoryGoal
from artifactsmmo_cli.ai.goals.task_cancel import TaskCancelGoal
from artifactsmmo_cli.ai.goals.task_exchange import TaskExchangeGoal
from artifactsmmo_cli.ai.goals.unlock_bank import UnlockBankGoal
from artifactsmmo_cli.ai.goals.wait import WaitGoal
from artifactsmmo_cli.ai.actions.wait import WaitAction
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
                              initial_skill_xp=state.skill_xp.get(step.skill, 0),
                              xp_curve=ctx.skill_xp_curves.get(step.skill))
    if isinstance(step, ReachCharLevel):
        if ctx.combat_monster is None:
            return None
        if (state.task_type == "items" and state.task_code
                and state.task_total > 0 and state.task_progress < state.task_total):
            return None        # grind can't advance an items task; let PURSUE_TASK run
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

    def _plans(
        self,
        goal: Goal,
        state: WorldState,
        game_data: GameData,
        actions: list[Action],
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

        # Build ordered candidates: guards, collect, step, discretionary.
        candidates: list[Candidate] = []
        for gk in guard_kinds:
            g = map_guard(gk, game_data, ctx)
            candidates.append(Candidate(goal=g, is_means=False, repr_=repr(g)))
        for mk in collect_kinds:
            g = map_means(mk, game_data, ctx, state)
            candidates.append(Candidate(goal=g, is_means=True, repr_=repr(g)))
        if step_goal is not None:
            candidates.append(Candidate(goal=step_goal, is_means=True, repr_=repr(step_goal)))
        for mk in discretionary_kinds:
            g = map_means(mk, game_data, ctx, state)
            candidates.append(Candidate(goal=g, is_means=True, repr_=repr(g)))

        def try_plan(goal: Goal) -> list[Action]:
            return self._plans(goal, state, game_data, actions)

        def satisfied(goal: Goal) -> bool:
            return goal.is_satisfied(state)

        chosen, plan, new_committed = select_pure(
            candidates=candidates,
            committed_repr=self._committed_repr,
            try_plan=try_plan,
            is_satisfied=satisfied,
            is_suppressed=is_suppressed,
        )
        self._committed_repr = new_committed
        return chosen, plan, self.goals_tried
