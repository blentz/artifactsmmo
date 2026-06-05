"""Guard tier: state-pressure interrupts + prerequisite gates that preempt every
instrumental means. The only surviving priority ladder, scoped to guards.

Pure: predicates read state/game_data/history + an explicit SelectionContext
(player runtime flags). No Goal-class imports — the driver maps GuardKind to goals."""

from dataclasses import dataclass, field
from enum import Enum

from artifactsmmo_cli.ai.bank_selection import select_bank_deposits
from artifactsmmo_cli.ai.craft_relief import craft_relief_candidates
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.inventory_caps import overstocked_items
from artifactsmmo_cli.ai.learning.skill_xp_curve import SkillXpCurve
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

CRITICAL_HP_FRACTION = 0.25
CRAFT_RELIEF_FRACTION = 0.70
"""When inv pressure crosses this fraction AND a goal-item is craftable
from current inventory, the CRAFT_RELIEF guard fires AHEAD of DEPOSIT_FULL.
Catches the case where raw materials would otherwise be banked or deleted
while the bot was one Craft action from converting them into task progress."""
DEPOSIT_FULL_FRACTION = 0.80
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


class GuardKind(Enum):
    HP_CRITICAL = "hp_critical"
    BANK_UNLOCK = "bank_unlock"
    REACH_UNLOCK_LEVEL = "reach_unlock_level"
    DISCARD_CRITICAL = "discard_critical"
    CRAFT_RELIEF = "craft_relief"
    DEPOSIT_FULL = "deposit_full"
    DISCARD_HIGH = "discard_high"


GUARD_ORDER: tuple[GuardKind, ...] = (
    GuardKind.HP_CRITICAL,
    GuardKind.BANK_UNLOCK,
    GuardKind.REACH_UNLOCK_LEVEL,
    GuardKind.DISCARD_CRITICAL,
    GuardKind.CRAFT_RELIEF,  # craft-before-deposit/discard when applicable
    GuardKind.DEPOSIT_FULL,
    GuardKind.DISCARD_HIGH,
)


def _used_fraction(state: WorldState) -> float:
    if state.inventory_max <= 0:
        return 0.0
    return state.inventory_used / state.inventory_max


def _fires(kind: GuardKind, state: WorldState, game_data: GameData,
           history: LearningStore | None, ctx: SelectionContext) -> bool:
    if kind is GuardKind.HP_CRITICAL:
        return state.hp_percent < CRITICAL_HP_FRACTION
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
        return bool(overstocked_items(state, game_data)) and _used_fraction(state) >= DISCARD_CRITICAL_FRACTION
    if kind is GuardKind.CRAFT_RELIEF:
        if _used_fraction(state) < CRAFT_RELIEF_FRACTION:
            return False
        return bool(craft_relief_candidates(
            state, game_data,
            target_gear=ctx.target_gear, target_tools=ctx.target_tools,
        ))
    if kind is GuardKind.DEPOSIT_FULL:
        return (ctx.bank_accessible and _used_fraction(state) >= DEPOSIT_FULL_FRACTION
                and bool(select_bank_deposits(state, game_data)))
    if kind is GuardKind.DISCARD_HIGH:
        return bool(overstocked_items(state, game_data)) and _used_fraction(state) >= DISCARD_HIGH_FRACTION
    return False


def active_guards(state: WorldState, game_data: GameData,
                  history: LearningStore | None, ctx: SelectionContext) -> list[GuardKind]:
    """Triggered guards in ladder (preemption) order.

    history is accepted for signature parity with future learning-aware guards (currently unused).
    """
    return [k for k in GUARD_ORDER if _fires(k, state, game_data, history, ctx)]
