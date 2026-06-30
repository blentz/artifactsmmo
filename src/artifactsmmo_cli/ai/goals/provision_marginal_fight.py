"""ProvisionMarginalFightGoal: equip a win-rate-scaled stack of health potions into
a utility slot before a marginal fight. The heal code and quantity are chosen by the
caller (strategy_driver glue) from the proven `marginal_potion_qty_pure` core and the
strongest held heal. Satisfied once a utility slot holds a heal; re-fires after the
server consumes the stack to empty (observed via per-cycle state refresh)."""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.equip import EquipAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

# Above the grind (GrindCharacterXP ceiling 45) so provisioning runs before the
# fight, below survival/RestoreHP (110) so healing still preempts.
PROVISION_MARGINAL_VALUE = 50.0

_TARGET_SLOT = "utility1_slot"
_UTILITY_SLOTS = ("utility1_slot", "utility2_slot")


class ProvisionMarginalFightGoal(Goal):
    """Equip `quantity` of `heal_code` into a utility slot for a marginal target."""

    def __init__(self, target_monster: str, heal_code: str, quantity: int) -> None:
        self._target_monster = target_monster
        self._heal_code = heal_code
        self._quantity = quantity

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        return 0.0 if self.is_satisfied(state) else PROVISION_MARGINAL_VALUE

    def is_satisfied(self, state: WorldState) -> bool:
        return any(state.equipment.get(slot) is not None for slot in _UTILITY_SLOTS)

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        # One-action plan; the planner terminates on is_satisfied after the equip
        # flips equipment[utility1_slot]. Use the form Step 1 confirmed the planner
        # honors (return {} if it goal-tests via is_satisfied).
        return {}

    def relevant_actions(self, actions: list[Action], state: WorldState,
                         game_data: GameData) -> list[Action]:
        return [EquipAction(code=self._heal_code, slot=_TARGET_SLOT,
                            quantity=self._quantity)]

    def serialize(self) -> dict[str, object]:
        return {"type": "ProvisionMarginalFightGoal",
                "target_monster": self._target_monster,
                "heal_code": self._heal_code,
                "quantity": self._quantity}

    def __repr__(self) -> str:
        return (f"ProvisionMarginalFight({self._target_monster},"
                f"{self._heal_code}x{self._quantity})")
