"""Guard tier: state-pressure interrupts + prerequisite gates that preempt every
instrumental means. The only surviving priority ladder, scoped to guards.

Pure: predicates read state/game_data/history + an explicit SelectionContext
(player runtime flags). No Goal-class imports — the driver maps GuardKind to goals."""

from dataclasses import dataclass, field, replace
from enum import Enum

from artifactsmmo_cli.ai.bank_selection import select_bank_deposits
from artifactsmmo_cli.ai.combat import predict_win
from artifactsmmo_cli.ai.craft_relief import (
    CRAFT_RELIEF_FRACTION,
    craft_relief_candidates,
)
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.inventory_caps import overstocked_items
from artifactsmmo_cli.ai.inventory_profile import inventory_profile
from artifactsmmo_cli.ai.learning.skill_xp_curve import SkillXpCurve
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

CRITICAL_HP_FRACTION = 0.25
# CRAFT_RELIEF_FRACTION (0.70) lives in craft_relief.py (re-imported above)
# so the candidate batch sizing and the guard predicate share one threshold.
DEPOSIT_FULL_FRACTION = 0.90
"""Space-driven (spec 2026-06-07): deposit pressure only appears near-full so
the player uses most of the bag. Kept STRICTLY ABOVE
DepositInventoryGoal._RAMP_START (0.85) so the DEPOSIT_FULL guard only fires
where the deposit goal already has strictly-positive value — the proven
liveness invariant `fires(DEPOSIT_FULL) ⇒ depositInventoryValue > 0`
(Formal.Liveness.MeansFiring) requires DEPOSIT_FULL_FRACTION > _RAMP_START."""
DISCARD_HIGH_FRACTION = 0.85
DISCARD_CRITICAL_FRACTION = 0.95
MAX_ACHIEVABLE_GAP = 5


@dataclass(frozen=True)
class SelectionContext:
    bank_accessible: bool
    bank_required_level: int
    bank_unlock_monster: str | None
    initial_xp: int
    task_exchange_min_coins: int
    combat_monster: str | None
    # Learned SkillXpCurve per skill, sourced from history. Used by
    # LevelSkillGoal to convert `projected_skill_xp_delta` into a real
    # "would cross the level threshold" satisfaction check; with an empty
    # entry the projection-based satisfaction is inert and only the
    # server-snapshot path applies.
    skill_xp_curves: dict[str, SkillXpCurve] = field(default_factory=dict)
    # Long-term gear and tool codes — fed by player from the
    # CharacterObjective so the CRAFT_RELIEF guard can score gear/tool
    # craft candidates alongside the active task item. Empty fallback
    # leaves the guard task-only.
    target_gear: frozenset[str] = field(default_factory=frozenset)
    target_tools: frozenset[str] = field(default_factory=frozenset)
    # Post-level-up / post-fight-loss gear prioritization latch. Set by the
    # player's GearLatch and cleared when no craftable upgrade remains.
    gear_review_active: bool = False


class GuardKind(Enum):
    HP_CRITICAL = "hp_critical"
    REST_FOR_COMBAT = "rest_for_combat"  # combat target winnable at max_hp but not at current_hp
    BANK_UNLOCK = "bank_unlock"
    REACH_UNLOCK_LEVEL = "reach_unlock_level"
    DISCARD_CRITICAL = "discard_critical"
    CRAFT_RELIEF = "craft_relief"
    DEPOSIT_FULL = "deposit_full"
    DISCARD_HIGH = "discard_high"
    GEAR_REVIEW = "gear_review"  # post-level-up / post-loss gear prioritization


GUARD_ORDER: tuple[GuardKind, ...] = (
    GuardKind.HP_CRITICAL,
    GuardKind.REST_FOR_COMBAT,  # preempts the next Fight when current hp is insufficient
    GuardKind.BANK_UNLOCK,
    GuardKind.REACH_UNLOCK_LEVEL,
    GuardKind.DISCARD_CRITICAL,
    GuardKind.CRAFT_RELIEF,  # craft-before-deposit/discard when applicable
    GuardKind.DEPOSIT_FULL,
    GuardKind.DISCARD_HIGH,
    GuardKind.GEAR_REVIEW,  # lowest-priority guard, still above all means
)


def _used_fraction(state: WorldState) -> float:
    if state.inventory_max <= 0:
        return 0.0
    return state.inventory_used / state.inventory_max


def active_profile(state: WorldState, game_data: GameData,
                   ctx: SelectionContext,
                   step_profile: dict[str, int] | None = None) -> dict[str, int]:
    """The active goal's SOFT inventory profile, derived from the
    SelectionContext's long-term gear/tool codes + the committed
    crafting_target + active items-task (spec 2026-06-07). Deposit/discard
    never bank/delete a profile item below its target.

    `step_profile` is the resolved objective-step goal's needed map
    (item_code -> target_qty), merged at per-code max. Trace 2026-06-11 22:36
    (cycle 30): DISCARD_HIGH deleted a wooden_shield the active
    GatherMaterials grind goal was accumulating (held 2, needed 3) because the
    step goal's targets were invisible to this profile — it only covered
    crafting_target/gear/tools/task."""
    profile = inventory_profile(state, game_data,
                                target_gear=ctx.target_gear,
                                target_tools=ctx.target_tools)
    if step_profile:
        for code, qty in step_profile.items():
            if qty > profile.get(code, 0):
                profile[code] = qty
    return profile


def _fires(kind: GuardKind, state: WorldState, game_data: GameData,
           history: LearningStore | None, ctx: SelectionContext,
           step_profile: dict[str, int] | None = None) -> bool:
    if kind is GuardKind.HP_CRITICAL:
        return state.hp_percent < CRITICAL_HP_FRACTION
    if kind is GuardKind.REST_FOR_COMBAT:
        # Trace 2026-06-06 session 05:26: Robby kept firing FightAction at
        # hp=76 vs yellow_slime, losing each time because predict_win at
        # current_hp returned False while the picker's max_hp projection
        # said winnable. The cheap FightAction.is_applicable level filter
        # passed, so no Rest was inserted. This guard preempts the
        # Fight-at-low-HP path by forcing RestoreHP whenever:
        #   (a) a combat target is selected,
        #   (b) state.hp < state.max_hp (Rest is actionable),
        #   (c) predict_win at current hp is False, AND
        #   (d) predict_win at max_hp is True (i.e. resting MEANS we can
        #       then win — otherwise this isn't a hp problem, it's a gear
        #       problem and the picker should have rejected the target).
        if ctx.combat_monster is None:
            return False
        if state.hp >= state.max_hp:
            return False
        if predict_win(state, game_data, ctx.combat_monster):
            return False
        return predict_win(replace(state, hp=state.max_hp), game_data, ctx.combat_monster)
    if kind is GuardKind.BANK_UNLOCK:
        if ctx.bank_unlock_monster is None or ctx.bank_accessible:
            return False
        if state.xp > ctx.initial_xp:
            return False
        target_level = game_data.monster_level(ctx.bank_unlock_monster)
        # target_level == 0 means unknown; let the planner try and fail naturally.
        return target_level == 0 or state.level >= target_level - 1
    if kind is GuardKind.REACH_UNLOCK_LEVEL:
        return (ctx.bank_required_level > 0
                and state.level < ctx.bank_required_level
                and ctx.bank_required_level - state.level <= MAX_ACHIEVABLE_GAP)
    if kind is GuardKind.DISCARD_CRITICAL:
        return (bool(overstocked_items(state, game_data,
                                       profile=active_profile(state, game_data, ctx,
                                                              step_profile)))
                and _used_fraction(state) >= DISCARD_CRITICAL_FRACTION)
    if kind is GuardKind.CRAFT_RELIEF:
        if _used_fraction(state) < CRAFT_RELIEF_FRACTION:
            return False
        return bool(craft_relief_candidates(
            state, game_data,
            target_gear=ctx.target_gear, target_tools=ctx.target_tools,
            step_items=frozenset(step_profile or ()),
        ))
    if kind is GuardKind.DEPOSIT_FULL:
        return (ctx.bank_accessible and _used_fraction(state) >= DEPOSIT_FULL_FRACTION
                and bool(select_bank_deposits(
                    state, game_data,
                    frozenset(active_profile(state, game_data, ctx, step_profile)))))
    if kind is GuardKind.DISCARD_HIGH:
        return (bool(overstocked_items(state, game_data,
                                       profile=active_profile(state, game_data, ctx,
                                                              step_profile)))
                and _used_fraction(state) >= DISCARD_HIGH_FRACTION)
    if kind is GuardKind.GEAR_REVIEW:
        return ctx.gear_review_active
    return False


def active_guards(state: WorldState, game_data: GameData,
                  history: LearningStore | None, ctx: SelectionContext,
                  step_profile: dict[str, int] | None = None) -> list[GuardKind]:
    """Triggered guards in ladder (preemption) order.

    history is accepted for signature parity with future learning-aware guards (currently unused).
    `step_profile` (the resolved step goal's needed map) joins the
    deposit/discard protection profile — see `active_profile`.
    """
    return [k for k in GUARD_ORDER
            if _fires(k, state, game_data, history, ctx, step_profile)]
