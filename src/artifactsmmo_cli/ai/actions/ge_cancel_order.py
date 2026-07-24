"""GeCancelOrderAction: cancel a posted GE order, reversing its escrow.

Cancelling frees the locked capital: a SELL order returns the escrowed item to the
inventory; a BUY order returns the escrowed gold. This is the on-need / TTL escape
that underwrites the liveness guarantee (no capital is locked forever). The exact
API return destination (inventory vs pending list) is a live-probe residual;
reconciliation (see reconcile_open_orders) corrects the predicted state from API
truth on the next cycle regardless.
"""

import dataclasses
from dataclasses import dataclass, field
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_ge_cancel_order_my_name_action_grandexchange_cancel_post import (
    sync as action_ge_cancel_order,
)
from artifactsmmo_api_client.models.ge_cancel_order_schema import GECancelOrderSchema

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.open_order import OpenOrder, OrderSide
from artifactsmmo_cli.ai.world_state import WorldState


@dataclass
class GeCancelOrderAction(Action):
    """Move to the Grand Exchange and cancel a posted order, reversing its escrow."""

    tags: ClassVar[frozenset[str]] = frozenset({"npc"})

    order_id: str
    ge_location: tuple[int, int] | None = field(default=None, repr=False)

    def _order(self, state: WorldState) -> OpenOrder | None:
        for o in state.open_orders:
            if o.id == self.order_id:
                return o
        return None

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        if self.ge_location is None:
            return False
        return self._order(state) is not None

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        order = self._order(state)
        if order is None:
            raise AssertionError(
                f"GeCancelOrderAction.apply: order {self.order_id} not open — "
                f"is_applicable invariant violated"
            )
        new_gold = state.gold
        new_inventory = dict(state.inventory)
        if order.side is OrderSide.BUY:
            new_gold += order.price * order.qty
        else:
            new_inventory[order.code] = new_inventory.get(order.code, 0) + order.qty
        remaining = tuple(o for o in state.open_orders if o.id != self.order_id)
        dest = self.ge_location or (state.x, state.y)
        return dataclasses.replace(
            state, gold=new_gold, x=dest[0], y=dest[1],
            inventory=new_inventory, open_orders=remaining, cooldown_expires=None,
        )

    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        dest = self.ge_location or (state.x, state.y)
        dist = abs(dest[0] - state.x) + abs(dest[1] - state.y)
        return 1.0 + dist

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        if self.ge_location and (state.x, state.y) != self.ge_location:
            state = MoveAction(x=self.ge_location[0], y=self.ge_location[1]).execute(state, client)
        body = GECancelOrderSchema(id=self.order_id)
        result = action_ge_cancel_order(client=client, name=state.character, body=body)
        result = Action._raise_for_error(result, f"GeCancel {self.order_id}")
        return WorldState.from_character_schema(
            result.data.character,
            bank_items=state.bank_items, bank_gold=state.bank_gold,
            pending_items=state.pending_items, active_events=state.active_events,
            raids=state.raids,
            open_orders=tuple(o for o in state.open_orders if o.id != self.order_id),
        )

    def __repr__(self) -> str:
        return f"GeCancel({self.order_id})"
