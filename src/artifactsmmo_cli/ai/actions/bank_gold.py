"""DepositGoldAction and WithdrawGoldAction: move gold between character and bank."""

from dataclasses import dataclass, field

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_deposit_bank_gold_my_name_action_bank_deposit_gold_post import sync as action_deposit_gold
from artifactsmmo_api_client.api.my_characters.action_withdraw_bank_gold_my_name_action_bank_withdraw_gold_post import sync as action_withdraw_gold
from artifactsmmo_api_client.models.deposit_withdraw_gold_schema import DepositWithdrawGoldSchema

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState


def _gold_apply(state: WorldState, dest: tuple[int, int], gold_delta: int, bank_gold_delta: int) -> WorldState:
    new_bank_gold = (state.bank_gold or 0) + bank_gold_delta if state.bank_gold is not None else None
    return WorldState(
        character=state.character,
        level=state.level, xp=state.xp, max_xp=state.max_xp,
        hp=state.hp, max_hp=state.max_hp,
        gold=state.gold + gold_delta,
        skills=state.skills, x=dest[0], y=dest[1],
        inventory=state.inventory, inventory_max=state.inventory_max,
        equipment=state.equipment, cooldown_expires=None,
        task_code=state.task_code, task_type=state.task_type,
        task_progress=state.task_progress, task_total=state.task_total,
        bank_items=state.bank_items,
        bank_gold=new_bank_gold,
        pending_items=state.pending_items,
    )


@dataclass
class DepositGoldAction(Action):
    """Deposit gold from character into bank."""

    quantity: int = 0
    bank_location: tuple[int, int] | None = field(default=None, repr=False)
    accessible: bool = True

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        if not self.accessible or self.bank_location is None:
            return False
        return state.gold >= self.quantity

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        dest = self.bank_location or (state.x, state.y)
        return _gold_apply(state, dest, gold_delta=-self.quantity, bank_gold_delta=self.quantity)

    def cost(self, state: WorldState, game_data: GameData) -> float:
        dest = self.bank_location or (state.x, state.y)
        return 2.0 + abs(dest[0] - state.x) + abs(dest[1] - state.y)

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        if self.bank_location and (state.x, state.y) != self.bank_location:
            state = MoveAction(x=self.bank_location[0], y=self.bank_location[1]).execute(state, client)
        body = DepositWithdrawGoldSchema(quantity=self.quantity)
        result = action_deposit_gold(client=client, name=state.character, body=body)
        result = Action._raise_for_error(result, f"DepositGold {self.quantity}")
        return WorldState.from_character_schema(
            result.data.character, bank_items=state.bank_items,
            bank_gold=state.bank_gold, pending_items=state.pending_items,
        )

    def __repr__(self) -> str:
        return f"DepositGold({self.quantity})"


@dataclass
class WithdrawGoldAction(Action):
    """Withdraw gold from bank to character."""

    quantity: int = 0
    bank_location: tuple[int, int] | None = field(default=None, repr=False)
    accessible: bool = True

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        if not self.accessible or self.bank_location is None:
            return False
        if state.bank_gold is None or state.bank_gold < self.quantity:
            return False
        return True

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        dest = self.bank_location or (state.x, state.y)
        return _gold_apply(state, dest, gold_delta=self.quantity, bank_gold_delta=-self.quantity)

    def cost(self, state: WorldState, game_data: GameData) -> float:
        dest = self.bank_location or (state.x, state.y)
        return 2.0 + abs(dest[0] - state.x) + abs(dest[1] - state.y)

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        if self.bank_location and (state.x, state.y) != self.bank_location:
            state = MoveAction(x=self.bank_location[0], y=self.bank_location[1]).execute(state, client)
        body = DepositWithdrawGoldSchema(quantity=self.quantity)
        result = action_withdraw_gold(client=client, name=state.character, body=body)
        result = Action._raise_for_error(result, f"WithdrawGold {self.quantity}")
        return WorldState.from_character_schema(
            result.data.character, bank_items=state.bank_items,
            bank_gold=state.bank_gold, pending_items=state.pending_items,
        )

    def __repr__(self) -> str:
        return f"WithdrawGold({self.quantity})"
