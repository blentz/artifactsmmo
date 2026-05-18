"""UnlockBankGoal: fight to satisfy the achievement required to access the bank."""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState


class UnlockBankGoal(Goal):
    """Fight monsters to satisfy the achievement gating bank access (HTTP 496)."""

    def __init__(self, bank_locked: bool, initial_xp: int, target_monster: str | None = None) -> None:
        self._bank_locked = bank_locked
        self._initial_xp = initial_xp
        self._target_monster = target_monster

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if not self._bank_locked or state.xp > self._initial_xp:
            return 0.0
        # If the target monster is known to be unreachable (way over-level), don't
        # fire at all — burning chickens won't satisfy the achievement and just
        # creates a loop. Defer until char levels up enough to attempt the target.
        if self._target_monster_is_unreachable(state, game_data):
            return 0.0
        # If inventory is critical AND we have a faster way to free it (NPC sell),
        # defer to SellInventoryGoal — selling is faster than grinding achievement.
        if state.inventory_max > 0:
            used_fraction = state.inventory_used / state.inventory_max
            if used_fraction >= 0.85:
                has_sellable = any(
                    game_data.npcs_buying_item(code)
                    for code, qty in state.inventory.items() if qty > 0
                )
                if has_sellable:
                    return 30.0   # defer to SellInventoryGoal (caps at 100)
        return 90.0

    def is_satisfied(self, state: WorldState) -> bool:
        # The only true satisfaction signal is bank access being restored.
        # `state.xp > initial_xp` was a stand-in but any fight bumps XP — that
        # made killing a chicken "satisfy" the goal while the bank stayed locked.
        return not self._bank_locked

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {}

    def relevant_actions(self, actions: list[Action], state: WorldState, game_data: GameData) -> list[Action]:
        # ONLY allow combat on the actual target monster. Falling back to all
        # fights makes the planner happily grind chickens forever while the
        # achievement that actually unlocks the bank stays incomplete.
        fight_actions: list[Action] = [
            a for a in actions
            if isinstance(a, FightAction) and (
                self._target_monster is None or a.monster_code == self._target_monster
            )
        ]
        cleanup_actions: list[Action] = [a for a in actions if "cleanup" in a.tags]
        recovery_actions: list[Action] = [a for a in actions if "recovery" in a.tags]
        return fight_actions + cleanup_actions + recovery_actions

    def _target_monster_is_unreachable(self, state: WorldState, game_data: GameData) -> bool:
        """True when the target monster is over-level enough that combat is hopeless."""
        if not self._target_monster:
            return False
        target_level = game_data.monster_level(self._target_monster)
        if target_level <= 0:
            return False  # unknown monster level — let planner try and fail
        # FightAction.is_applicable already requires level >= monster_level - 1;
        # mirror that so we don't fire when the planner will return [] anyway.
        return state.level < target_level - 1

    def __repr__(self) -> str:
        return f"UnlockBank({self._target_monster or '?'})"
