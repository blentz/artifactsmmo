"""UnlockBankGoal: fight to satisfy the achievement required to access the bank."""

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.consumable import UseConsumableAction
from artifactsmmo_cli.ai.actions.delete import DeleteItemAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.world_state import WorldState


class UnlockBankGoal(Goal):
    """Fight monsters to satisfy the achievement gating bank access (HTTP 496)."""

    def __init__(self, bank_locked: bool, initial_xp: int, target_monster: str | None = None) -> None:
        self._bank_locked = bank_locked
        self._initial_xp = initial_xp
        self._target_monster = target_monster

    def value(self, state: WorldState, game_data: GameData) -> float:
        if not self._bank_locked or state.xp > self._initial_xp:
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
        return state.xp > self._initial_xp

    def desired_state(self, state: WorldState, game_data: GameData) -> dict:
        return {}

    def relevant_actions(self, actions: list, state: WorldState, game_data: GameData) -> list:
        fight_actions = [a for a in actions if isinstance(a, FightAction)]
        if self._target_monster:
            targeted = [a for a in fight_actions if a.monster_code == self._target_monster]
            if targeted:
                fight_actions = targeted
        delete_actions = [a for a in actions if isinstance(a, DeleteItemAction)]
        consume_actions = [a for a in actions if isinstance(a, UseConsumableAction)]
        return fight_actions + delete_actions + consume_actions

    def __repr__(self) -> str:
        return f"UnlockBank({self._target_monster or '?'})"
