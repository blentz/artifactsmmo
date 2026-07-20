"""NpcBuyAction: purchase an item from an NPC merchant."""

import dataclasses
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_npc_buy_item_my_name_action_npc_buy_post import (
    sync as action_npc_buy,
)
from artifactsmmo_api_client.models.npc_merchant_buy_schema import NpcMerchantBuySchema

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.actions.npc_buy_core import (
    npc_buy_apply_pure,
    npc_buy_currency_apply_pure,
    npc_buy_currency_is_applicable_pure,
    npc_buy_is_applicable_pure,
)
from artifactsmmo_cli.ai.event_availability import event_npc_tradeable
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState


@dataclass
class NpcBuyAction(Action):
    """Move to an NPC merchant and purchase an item."""

    tags: ClassVar[frozenset[str]] = frozenset({"npc"})

    npc_code: str
    item_code: str
    quantity: int = 1
    npc_location: tuple[int, int] | None = field(default=None, repr=False)

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        if self.npc_location is None:
            return False
        price = game_data.npc_sells_item(self.npc_code, self.item_code)
        if price is None:
            return False
        # The vendor's pay currency decides the affordability gate: 'gold' pays
        # from gold, any other code pays from that item's inventory count
        # (NPCItem.currency: "if it's not gold, it's the item code"). A bare price
        # is ambiguous without it (a rune at "100" may be 100 sandwhisper_coin).
        currency = game_data.npc_purchase_currency(self.npc_code, self.item_code) or "gold"
        if currency == "gold":
            # Slot-floor + gold gate (delegates to the proved pure core).
            # The slot precondition mirrors GatherAction's MIN_FREE_SLOTS shape:
            # without it, `apply` would mint past `inventory_max` (REAL BUG #6).
            if not npc_buy_is_applicable_pure(
                inv_used=state.inventory_used,
                inv_max=state.inventory_max,
                quantity=self.quantity,
                gold=state.gold,
                price=price,
            ):
                return False
        else:
            # Item-currency purchase: need a free slot for the bought item AND
            # `price * quantity` of the currency item on hand. Delegates to the
            # proved core (Formal.NpcBuyInventory.isApplicableCurrency).
            if not npc_buy_currency_is_applicable_pure(
                inv_used=state.inventory_used,
                inv_max=state.inventory_max,
                quantity=self.quantity,
                currency_on_hand=state.inventory.get(currency, 0),
                total_spent=price * self.quantity,
            ):
                return False
        return event_npc_tradeable(
            self.npc_code, game_data,
            x=state.x, y=state.y,
            active_events=state.active_events,
            now=datetime.now(timezone.utc),
        )

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        # Defense in depth: assert the slot-floor precondition before mutating.
        # Matches Phase-3 OptimizeLoadoutAction.apply shape — any precondition
        # bypass (planner skipped is_applicable, etc.) crashes loudly rather
        # than silently overflowing the inventory cap.
        if state.inventory_free < self.quantity:
            raise AssertionError(
                f"NpcBuyAction.apply: inventory_free={state.inventory_free} "
                f"< quantity={self.quantity} — is_applicable invariant violated"
            )
        price = game_data.npc_sells_item(self.npc_code, self.item_code) or 0
        currency = game_data.npc_purchase_currency(self.npc_code, self.item_code) or "gold"
        if currency == "gold":
            new_inventory = npc_buy_apply_pure(state.inventory, self.item_code, self.quantity)
            new_gold = state.gold - price * self.quantity
        else:
            # Pay in the currency item: gold is untouched, the currency stack is
            # drawn down by price*quantity (delegates to the proved core
            # Formal.NpcBuyInventory.applyCurrency; is_applicable guarantees enough).
            new_gold = state.gold
            new_inventory = npc_buy_currency_apply_pure(
                state.inventory, self.item_code, self.quantity,
                currency, price * self.quantity)
        dest = self.npc_location or (state.x, state.y)
        return dataclasses.replace(
            state,
            gold=new_gold,
            x=dest[0],
            y=dest[1],
            inventory=new_inventory,
            cooldown_expires=None,
        )

    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        dest = self.npc_location or (state.x, state.y)
        dist = abs(dest[0] - state.x) + abs(dest[1] - state.y)
        price = game_data.npc_sells_item(self.npc_code, self.item_code) or 0
        currency = game_data.npc_purchase_currency(self.npc_code, self.item_code) or "gold"
        # Gold cost scaled to action cost: 1 unit per 10 gold. An item-currency
        # purchase spends no gold, so only the travel + base cost applies (the
        # currency was already earned).
        gold_term = price * self.quantity / 10.0 if currency == "gold" else 0.0
        return 2.0 + dist + gold_term

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        if self.npc_location and (state.x, state.y) != self.npc_location:
            state = MoveAction(x=self.npc_location[0], y=self.npc_location[1]).execute(state, client)
        body = NpcMerchantBuySchema(code=self.item_code, quantity=self.quantity)
        result = action_npc_buy(client=client, name=state.character, body=body)
        result = Action._raise_for_error(result, f"NpcBuy {self.item_code}×{self.quantity} from {self.npc_code}")
        return WorldState.from_character_schema(
            result.data.character,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
            active_events=state.active_events,
            raids=state.raids,
        )

    def __repr__(self) -> str:
        return f"NpcBuy({self.item_code}×{self.quantity}@{self.npc_code})"
