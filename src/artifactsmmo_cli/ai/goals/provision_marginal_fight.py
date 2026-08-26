"""ProvisionMarginalFightGoal: equip an HP-need-scaled stack of health potions into
a utility slot before a marginal fight. The heal code and quantity are chosen by the
caller (strategy_driver glue) from the proven `potion_provision_qty_pure` core and the
strongest held heal. Satisfied once a utility slot holds a heal; re-fires after the
server consumes the stack to empty (observed via per-cycle state refresh)."""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.equip import EquipAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.utility_slot import already_provisioned, utility_slot_for
from artifactsmmo_cli.ai.world_state import WorldState

# Above the grind (GrindCharacterXP ceiling 45) so provisioning runs before the
# fight, below survival/RestoreHP (110) so healing still preempts.
PROVISION_MARGINAL_VALUE = 50.0


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
        return already_provisioned(state)

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        # One-action plan; the planner terminates on is_satisfied after the equip
        # flips one utility slot off None. Use the form Step 1 confirmed the
        # planner honors (return {} if it goal-tests via is_satisfied).
        return {}

    def relevant_actions(self, actions: list[Action], state: WorldState,
                         game_data: GameData) -> list[Action]:
        # The slot comes from the ONE producer (`utility_slot_for`), not from a
        # second hard-coded "utility1_slot" here. `is_satisfied` above means
        # this goal only ever plans with BOTH slots empty, so the answer is
        # always slot 1 today — but it is now the same answer craft_ladder gets,
        # and it stays right if the satisfaction rule ever narrows.
        return [EquipAction(code=self._heal_code,
                            slot=utility_slot_for(self._heal_code, state),
                            quantity=self._quantity)]

    def serialize(self) -> dict[str, object]:
        return {"type": "ProvisionMarginalFightGoal",
                "target_monster": self._target_monster,
                "heal_code": self._heal_code,
                "quantity": self._quantity}

    def __repr__(self) -> str:
        return (f"ProvisionMarginalFight({self._target_monster},"
                f"{self._heal_code}x{self._quantity})")
