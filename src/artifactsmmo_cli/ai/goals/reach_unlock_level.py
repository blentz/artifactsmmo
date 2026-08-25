"""ReachUnlockLevelGoal: drive character XP grinding to satisfy a learned
blocker that requires reaching a specific character level (e.g. the bank
unlock achievement needs level N to kill the gating monster).

Fires only when a blocker is known AND the character is still under the
required level. Priority sits above DepositInventory's ramp so the bot
pivots to combat instead of looping on locked-bank failures.
"""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

# Above DepositInventory's max (80) and FarmItems (35+bonus); below RestoreHP (110).
# Inlined from retired priorities.py (REACH_UNLOCK_LEVEL = 85.0).
PRIORITY_WHEN_BLOCKER_ACTIVE = 85.0
"""Above DepositInventory's max (80) and FarmItems (35+bonus) so the bot
clears the prerequisite first. Below RestoreHP critical (110) and the
hard survival floor."""

MAX_ACHIEVABLE_GAP = 5
"""TWO DEFINITIONS OF THIS NUMBER, AND THE OTHER ONE DECIDES. `tiers/guards.py`
declares its own `MAX_ACHIEVABLE_GAP = 5` and `_fires(REACH_UNLOCK_LEVEL)` uses
it as `ctx.bank_required_level - state.level <= MAX_ACHIEVABLE_GAP`; the branch
below is the exact complement (`> MAX_ACHIEVABLE_GAP -> 0.0`). So the goal-side
test is UNREACHABLE in production — `map_guard` builds this goal only after that
guard fired, and the other construction site
(`strategy_driver`'s HORIZON_LEVEL_UP arm) passes `state.level + 1`, a gap of
one. Swept 2026-08-25 for the `TaskCancelGoal` R4 defect ("`value()` re-derives a
condition owned by a predicate that also decides it"): this IS a re-derivation,
but it cannot disagree while the two literals agree, and it cannot be reached
while the guard owns the gate. Keep them in step, or delete this branch when a
caller can no longer reach it.

Don't fire when the gap to target_level exceeds this. A bigger gap means
the prerequisite is effectively unreachable (e.g. bank locked behind a
level-45 monster while char is level 2). Goal stays at 0 priority and the
bot operates as if the blocker doesn't exist — UpgradeEquipment /
FarmMonster naturally take over and the goal will re-activate later if
the char does eventually close the gap."""


class ReachUnlockLevelGoal(Goal):
    """Grind character XP until state.level >= target_level."""

    def __init__(self, target_level: int, blocker_code: str = "bank") -> None:
        self._target_level = target_level
        self._blocker_code = blocker_code

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if self.is_satisfied(state):
            return 0.0
        if self._target_level <= 0:
            return 0.0
        # Unreachable gap: defer indefinitely. Bot operates as if blocker
        # doesn't exist; goal re-activates when the gap narrows.
        if self._target_level - state.level > MAX_ACHIEVABLE_GAP:
            return 0.0
        return PRIORITY_WHEN_BLOCKER_ACTIVE

    def is_satisfied(self, state: WorldState) -> bool:
        return state.level >= self._target_level

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"level": self._target_level}

    def relevant_actions(self, actions: list[Action], state: WorldState, game_data: GameData) -> list[Action]:
        """Any monster the character can actually beat + HP recovery."""
        result: list[Action] = []
        for action in actions:
            if isinstance(action, FightAction):
                ml = game_data.monster_level(action.monster_code)
                if ml > 0 and state.level >= ml - 1:
                    result.append(action)
            elif "recovery" in action.tags:
                result.append(action)
            elif "equip" in action.tags and (target := getattr(action, "target_monster_code", None)):
                ml = game_data.monster_level(target)
                if ml > 0 and state.level >= ml - 1:
                    result.append(action)
        return result

    def __repr__(self) -> str:
        return f"ReachUnlockLevel({self._target_level})"
