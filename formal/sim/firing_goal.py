"""Python port of `Formal.Liveness.StateRegions.regionOf` and the Phase-20b
`FiringGoal` dispatch.

Byte-equivalent to the Lean dispatch in
`formal/Formal/Liveness/StateRegions.lean` (region order, predicates) and
the Phase-20b NoDeadlock dispatch in
`formal/Formal/Liveness/NoDeadlock.lean` (region -> firing goal).

Used by `formal/diff/test_no_deadlock_diff.py` to bridge from a
production `WorldState` into the firing-goal verdict that the Lean
theorem asserts is non-empty.

ONE behavioural class per file: this module defines `FiringGoal` (an
Enum, exempt per CLAUDE.md) plus pure functions. No behavioural class.
"""

from enum import Enum

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.accept_task_goal import AcceptTaskGoal
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.goals.claim_pending import ClaimPendingGoal
from artifactsmmo_cli.ai.goals.complete_task_goal import CompleteTaskGoal
from artifactsmmo_cli.ai.goals.discard_overstock import DiscardOverstockGoal
from artifactsmmo_cli.ai.goals.pursue_task import PursueTaskGoal
from artifactsmmo_cli.ai.goals.reach_unlock_level import ReachUnlockLevelGoal
from artifactsmmo_cli.ai.goals.restore_hp import RestoreHPGoal
from artifactsmmo_cli.ai.goals.unlock_bank import UnlockBankGoal
from artifactsmmo_cli.ai.world_state import WorldState


class FiringGoal(Enum):
    """One value per region of `Formal.Liveness.StateRegions.Region`."""

    RESTORE_HP = "restore_hp"
    CLAIM_PENDING = "claim_pending"
    COMPLETE_TASK = "complete_task"
    ACCEPT_TASK = "accept_task"
    DISCARD_OVERSTOCK = "discard_overstock"
    REACH_UNLOCK_LEVEL = "reach_unlock_level"
    UNLOCK_BANK = "unlock_bank"
    PURSUE_TASK = "pursue_task"


# Liveness-side modeled flags (Lean State.bankLocked / bankXpExceeded /
# bankUnreachable / unlockTargetLevel / pendingItems). The production
# `WorldState` doesn't carry these as direct fields — the planner derives
# them from API surfaces. The differential test injects them as
# parameters alongside the state so the Lean<->Python bridge is explicit.
class LivenessInputs:
    """Bundle of liveness-only inputs needed by `region_of`.

    Mirrors the Lean `State` extension that StateRegions/NoDeadlock
    consume. Carried alongside `WorldState` so the Python port can match
    Lean's `regionOf` predicates exactly.
    """

    def __init__(
        self,
        pending_items: bool,
        bank_locked: bool,
        bank_xp_exceeded: bool,
        bank_unreachable: bool,
        unlock_target_level: int,
    ) -> None:
        self.pending_items = pending_items
        self.bank_locked = bank_locked
        self.bank_xp_exceeded = bank_xp_exceeded
        self.bank_unreachable = bank_unreachable
        self.unlock_target_level = unlock_target_level


def is_critical_hp(state: WorldState) -> bool:
    """Mirror `isCriticalHP`: `maxHp > 0 ∧ 4 * hp < maxHp`."""
    return state.max_hp > 0 and 4 * state.hp < state.max_hp


def is_inventory_full(state: WorldState) -> bool:
    """Mirror `isInventoryFull`: `inventoryUsed >= inventoryMax`."""
    return state.inventory_used >= state.inventory_max


def is_task_complete(state: WorldState) -> bool:
    """Mirror `isTaskComplete`: task accepted AND progress >= total > 0."""
    return (
        state.task_code is not None
        and state.task_total > 0
        and state.task_progress >= state.task_total
    )


def is_no_task(state: WorldState) -> bool:
    """Mirror `isNoTask`: `taskCode.isNone`."""
    return state.task_code is None


def is_level_blocker(state: WorldState, liv: LivenessInputs) -> bool:
    """Mirror `isLevelBlocker`: unlockTargetLevel > 0 ∧ level < target ∧ gap ≤ 5."""
    return (
        liv.unlock_target_level > 0
        and state.level < liv.unlock_target_level
        and liv.unlock_target_level - state.level <= 5
    )


def is_bank_locked_fightable(liv: LivenessInputs) -> bool:
    """Mirror `isBankLockedFightable`: locked ∧ ¬xpExceeded ∧ ¬unreachable."""
    return liv.bank_locked and (not liv.bank_xp_exceeded) and (not liv.bank_unreachable)


def region_of(state: WorldState, liv: LivenessInputs) -> FiringGoal:
    """Python port of `Formal.Liveness.StateRegions.regionOf` composed with
    the Phase-20b `goalValueOf` dispatch.

    First-match dispatch — same order as the Lean if-chain. Returns the
    `FiringGoal` whose Phase-18 value function the matching `RegionFiring`
    lemma proves strictly positive.
    """
    if is_critical_hp(state):
        return FiringGoal.RESTORE_HP
    if liv.pending_items:
        return FiringGoal.CLAIM_PENDING
    if is_task_complete(state):
        return FiringGoal.COMPLETE_TASK
    if is_no_task(state):
        return FiringGoal.ACCEPT_TASK
    if is_inventory_full(state):
        return FiringGoal.DISCARD_OVERSTOCK
    if is_level_blocker(state, liv):
        return FiringGoal.REACH_UNLOCK_LEVEL
    if is_bank_locked_fightable(liv):
        return FiringGoal.UNLOCK_BANK
    return FiringGoal.PURSUE_TASK


def production_goal_for(
    firing: FiringGoal,
    state: WorldState,
    liv: LivenessInputs,
    game_data: GameData,
) -> Goal:
    """Construct the production `Goal` instance the Lean `FiringGoal`
    corresponds to.

    Construction inputs are taken from `state` / `liv` exactly as the
    Phase-18 value functions in the corresponding RegionFiring lemma
    consume them. No mocks; real production constructors.
    """
    if firing is FiringGoal.RESTORE_HP:
        return RestoreHPGoal()
    if firing is FiringGoal.CLAIM_PENDING:
        return ClaimPendingGoal()
    if firing is FiringGoal.COMPLETE_TASK:
        return CompleteTaskGoal()
    if firing is FiringGoal.ACCEPT_TASK:
        return AcceptTaskGoal()
    if firing is FiringGoal.DISCARD_OVERSTOCK:
        return DiscardOverstockGoal(game_data)
    if firing is FiringGoal.REACH_UNLOCK_LEVEL:
        return ReachUnlockLevelGoal(target_level=liv.unlock_target_level)
    if firing is FiringGoal.UNLOCK_BANK:
        # initial_xp is set so `state.xp > initial_xp` is False — matches
        # the Lean firing condition where the goal is not yet satisfied.
        return UnlockBankGoal(
            bank_locked=liv.bank_locked,
            initial_xp=state.xp,
            target_monster=None,
        )
    # PURSUE_TASK
    return PursueTaskGoal(
        task_code=state.task_code or "",
        initial_progress=state.task_progress,
        batch=1,
    )
