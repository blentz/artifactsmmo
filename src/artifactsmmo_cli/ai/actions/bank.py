"""Bank actions for GOAP planning."""

from dataclasses import dataclass, field
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_deposit_bank_item_my_name_action_bank_deposit_item_post import sync as deposit_item
from artifactsmmo_api_client.api.my_characters.action_withdraw_bank_item_my_name_action_bank_withdraw_item_post import sync as withdraw_item
from artifactsmmo_api_client.models.simple_item_schema import SimpleItemSchema

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState


@dataclass
class DepositAllAction(Action):
    """Move to bank and deposit all inventory items."""

    tags: ClassVar[frozenset[str]] = frozenset({"bank", "deposit"})

    bank_location: tuple[int, int] = field(default=(0, 0), repr=False)
    accessible: bool = True  # False when bank is gated behind an unmet achievement (HTTP 496)

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        return self.accessible and len(state.inventory) > 0

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        dest = self.bank_location
        new_bank = dict(state.bank_items or {})
        for code, qty in state.inventory.items():
            new_bank[code] = new_bank.get(code, 0) + qty
        return WorldState(
            character=state.character,
            level=state.level,
            xp=state.xp,
            max_xp=state.max_xp,
            hp=state.hp,
            max_hp=state.max_hp,
            gold=state.gold,
            skills=state.skills,
            x=dest[0],
            y=dest[1],
            inventory={},
            inventory_max=state.inventory_max,
            equipment=state.equipment,
            cooldown_expires=None,
            task_code=state.task_code,
            task_type=state.task_type,
            task_progress=state.task_progress,
            task_total=state.task_total,
            bank_items=new_bank,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
            active_events=state.active_events,
        )

    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        dest = self.bank_location
        dist = abs(dest[0] - state.x) + abs(dest[1] - state.y)
        return len(state.inventory) * 2.0 + dist

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        if (state.x, state.y) != self.bank_location:
            state = MoveAction(x=self.bank_location[0], y=self.bank_location[1]).execute(state, client)
        last_state = state
        for code, qty in list(state.inventory.items()):
            body = SimpleItemSchema(code=code, quantity=qty)
            result = deposit_item(client=client, name=state.character, body=[body])
            if result is not None and hasattr(result, "data") and result.data is not None:
                last_state = WorldState.from_character_schema(
                    result.data.character,
                    bank_items=last_state.bank_items,
                    bank_gold=last_state.bank_gold,
                    pending_items=last_state.pending_items,
                    active_events=last_state.active_events,
                )
        return last_state

    def __repr__(self) -> str:
        return "DepositAll"


@dataclass
class WithdrawItemAction(Action):
    """Move to bank and withdraw a specific item."""

    tags: ClassVar[frozenset[str]] = frozenset({"bank", "withdraw"})

    code: str
    quantity: int
    bank_location: tuple[int, int] = field(default=(0, 0), repr=False)
    accessible: bool = True  # False when bank is gated behind an unmet achievement (HTTP 496)

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        if not self.accessible or state.bank_items is None:
            return False
        return state.bank_items.get(self.code, 0) >= self.quantity and state.inventory_free > 0

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        dest = self.bank_location
        new_inventory = dict(state.inventory)
        new_inventory[self.code] = new_inventory.get(self.code, 0) + self.quantity
        new_bank = dict(state.bank_items or {})
        new_bank[self.code] = new_bank.get(self.code, 0) - self.quantity
        if new_bank[self.code] <= 0:
            del new_bank[self.code]
        return WorldState(
            character=state.character,
            level=state.level,
            xp=state.xp,
            max_xp=state.max_xp,
            hp=state.hp,
            max_hp=state.max_hp,
            gold=state.gold,
            skills=state.skills,
            x=dest[0],
            y=dest[1],
            inventory=new_inventory,
            inventory_max=state.inventory_max,
            equipment=state.equipment,
            cooldown_expires=None,
            task_code=state.task_code,
            task_type=state.task_type,
            task_progress=state.task_progress,
            task_total=state.task_total,
            bank_items=new_bank,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
            active_events=state.active_events,
        )

    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        dest = self.bank_location
        dist = abs(dest[0] - state.x) + abs(dest[1] - state.y)
        return 2.0 + dist

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        if (state.x, state.y) != self.bank_location:
            state = MoveAction(x=self.bank_location[0], y=self.bank_location[1]).execute(state, client)
        body = SimpleItemSchema(code=self.code, quantity=self.quantity)
        result = withdraw_item(client=client, name=state.character, body=[body])
        result = Action._raise_for_error(result, f"Withdraw {self.code}×{self.quantity}")
        return WorldState.from_character_schema(
            result.data.character,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
            active_events=state.active_events,
        )

    def __repr__(self) -> str:
        return f"Withdraw({self.code}×{self.quantity})"
