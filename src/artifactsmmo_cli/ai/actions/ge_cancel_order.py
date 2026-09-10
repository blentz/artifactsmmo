"""GeCancelOrderAction: cancel a posted GE order, reversing its escrow.

Cancelling frees the locked capital: a SELL order returns the escrowed item to the
inventory; a BUY order returns the escrowed gold. This is the on-need / TTL escape
that underwrites the liveness guarantee (no capital is locked forever). The exact
API return destination (inventory vs pending list) is a live-probe residual;
reconciliation (see reconcile_open_orders) corrects the predicted state from API
truth on the next cycle regardless.

The SELL escape is CONDITIONAL on bag room. Returning the stack is a mint, so a
full bag refuses the cancel (HTTP 497) and the capital stays locked until room
appears — `is_applicable` gates on that room rather than planning a step the
server refuses identically every cycle. `Formal/EscrowConservation.lean`'s
`sell_escrow_freed` is unconditional because its ledger has no bag cap; the cap
is modelled here and only here.
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
from artifactsmmo_cli.ai.actions.cost_core import distance_cost_pure
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.inventory_room import has_room
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

    @staticmethod
    def _room_terms(order: OpenOrder, state: WorldState) -> tuple[int, int]:
        """`(new_stacks, added_qty)` this cancel adds to the bag.

        A BUY cancel returns GOLD and mints nothing, so both terms are 0 and the
        room test passes trivially — gating it on bag space would strand the
        gold-short escape the guard exists for. A SELL cancel returns the
        escrowed stack, which needs a free slot when the code is not already
        held (mirrors `WithdrawItemAction`, the other stack-minting action)."""
        if order.side is OrderSide.BUY:
            return 0, 0
        new_stacks = 1 if (order.code not in state.inventory and order.qty > 0) else 0
        return new_stacks, order.qty

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        if self.ge_location is None:
            return False
        order = self._order(state)
        if order is None:
            return False
        # SLOT + QUANTITY ROOM. `apply` MINTS the escrowed stack back, so this
        # is a stack-creating action and carries the same guard every other one
        # does. Its absence made the action lie: the planner picked a cancel the
        # server refuses with HTTP 497 ("Character inventory is full"), the
        # order stayed open, `cancel_targets` named it again, and the guard
        # re-picked the SAME id forever. The goal's fire-and-lose liveness
        # argument holds only for a cancel that SUCCEEDS.
        #
        # Live 2026-09-09/10: 685 of 4465 cycles across five characters were
        # HTTP_497 cancels (`GeCancel(6aa2523fa4da349872694fc4)` alone 264
        # times, HAL pinned at 118/138), and the livelock is what drove Lor to
        # `stuck_exit`. Refusing the over-large cancel is not a lost escape: a
        # smaller order cancelled fine mid-burst, and DepositInventory /
        # DiscardOverstock free the room that re-admits this one next cycle.
        new_stacks, added_qty = self._room_terms(order, state)
        return has_room(
            new_stacks, added_qty=added_qty,
            slots_free=state.inventory_slots_free,
            qty_free=state.inventory_free,
        )

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        order = self._order(state)
        if order is None:
            raise AssertionError(
                f"GeCancelOrderAction.apply: order {self.order_id} not open — "
                f"is_applicable invariant violated"
            )
        # Mirror of the precondition — the chain-safe defense that crashes
        # loudly if a caller reaches apply without going through the gate.
        new_stacks, added_qty = self._room_terms(order, state)
        assert has_room(
            new_stacks, added_qty=added_qty,
            slots_free=state.inventory_slots_free,
            qty_free=state.inventory_free,
        ), (
            f"GeCancelOrderAction.apply requires room for {order.code}×{order.qty} "
            f"new_stacks={new_stacks} (slots_free={state.inventory_slots_free}, "
            f"qty_free={state.inventory_free})"
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
        return distance_cost_pure(1.0, dist)

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
