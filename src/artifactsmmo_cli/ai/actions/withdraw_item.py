"""WithdrawItemAction: move to bank and withdraw a specific item."""

import dataclasses
from dataclasses import dataclass, field
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_withdraw_bank_item_my_name_action_bank_withdraw_item_post import (
    sync as withdraw_item,
)
from artifactsmmo_api_client.models.simple_item_schema import SimpleItemSchema

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.inventory_room import has_room
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState


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
        if state.bank_items.get(self.code, 0) < self.quantity:
            return False
        # SLOT + QUANTITY ROOM: the game enforces both a per-slot cap and a
        # total-quantity cap. Withdrawing a code NOT already held mints a new
        # distinct stack and needs a free slot; growing an already-held stack
        # only needs quantity headroom. `added_qty=self.quantity` against
        # `qty_free` subsumes the old `inventory_free >= quantity` check.
        # Pre-fix defense-in-depth note (kept for history): a bare `>= 1`
        # slot check allowed a withdraw of N items while only 1 slot was
        # free, and apply minted `+N`, overflowing the cap.
        # A new distinct stack is created only when withdrawing >=1 of a code
        # not already held; withdrawing 0 (a degenerate no-op) mints nothing
        # and needs no slot, so new_stacks stays 0 (keeps parity with the
        # quantity-only chain-safe Lean model in InventoryChainSafe.lean,
        # which the withdraw differential pins — the slot term only bites in
        # real states where slots_max < inventory_max).
        new_stacks = 1 if (self.code not in state.inventory
                           and self.quantity > 0) else 0
        return has_room(
            new_stacks, added_qty=self.quantity,
            slots_free=state.inventory_slots_free,
            qty_free=state.inventory_free,
        )

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        # Mirror the is_applicable precondition. The planner re-checks
        # is_applicable on every popped node; this assert is the
        # chain_safe defense that crashes loudly if a caller bypasses the gate.
        new_stacks = 1 if (self.code not in state.inventory
                           and self.quantity > 0) else 0
        assert has_room(
            new_stacks, added_qty=self.quantity,
            slots_free=state.inventory_slots_free,
            qty_free=state.inventory_free,
        ), (
            f"WithdrawItemAction.apply requires room for quantity={self.quantity} "
            f"new_stacks={new_stacks} "
            f"(slots_free={state.inventory_slots_free}, qty_free={state.inventory_free})"
        )
        dest = self.bank_location
        new_inventory = dict(state.inventory)
        new_inventory[self.code] = new_inventory.get(self.code, 0) + self.quantity
        new_bank = dict(state.bank_items or {})
        new_bank[self.code] = new_bank.get(self.code, 0) - self.quantity
        if new_bank[self.code] <= 0:
            del new_bank[self.code]
        return dataclasses.replace(
            state,
            x=dest[0],
            y=dest[1],
            inventory=new_inventory,
            cooldown_expires=None,
            bank_items=new_bank,
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
            raids=state.raids,
        )

    def __repr__(self) -> str:
        return f"Withdraw({self.code}×{self.quantity})"
