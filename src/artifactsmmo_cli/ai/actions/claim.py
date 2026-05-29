"""ClaimPendingItemAction: claim the first available pending item."""

import dataclasses
from dataclasses import dataclass
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_account.get_pending_items_my_pending_items_get import sync as get_pending_items
from artifactsmmo_api_client.api.my_characters.action_claim_pending_item_my_name_action_claim_item_id_post import (
    sync as action_claim_item,
)

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState


@dataclass
class ClaimPendingItemAction(Action):
    """Claim the first pending item available on the account.

    Pending items require no movement — they can be claimed from anywhere.
    The action uses the first (id, code) tuple in state.pending_items.
    """

    tags: ClassVar[frozenset[str]] = frozenset({"claim"})

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        # Defense in depth: claiming mints `+1` of the pending item into
        # inventory. Without a slot-floor check, a claim on a full bag would
        # overflow inventory_max (apply produced used=cap+1). Mirrors the
        # NpcBuy / Gather chain_safe shape.
        if not state.pending_items:
            return False
        return state.inventory_free >= 1

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        if not state.pending_items:
            return state
        assert state.inventory_free >= 1, (
            f"ClaimPendingItemAction.apply requires inventory_free >= 1 "
            f"({state.inventory_free} < 1)"
        )
        item_id, item_code = state.pending_items[0]
        remaining = state.pending_items[1:]
        new_inventory = dict(state.inventory)
        new_inventory[item_code] = new_inventory.get(item_code, 0) + 1
        return dataclasses.replace(
            state,
            inventory=new_inventory,
            cooldown_expires=None,
            pending_items=remaining if remaining else None,
        )

    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        return 1.0

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        pending = get_pending_items(client=client)
        if pending is None or not pending.data:
            return state

        item = pending.data[0]
        result = action_claim_item(client=client, name=state.character, id=item.id)
        result = Action._raise_for_error(result, f"ClaimPendingItem({item.id})")

        remaining_ids = {entry.id for entry in pending.data[1:]}
        remaining = tuple(
            (eid, ec) for eid, ec in (state.pending_items or ())
            if eid in remaining_ids
        ) or None
        return WorldState.from_character_schema(
            result.data.character,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=remaining,
            active_events=state.active_events,
        )

    def __repr__(self) -> str:
        return "ClaimPendingItem"
