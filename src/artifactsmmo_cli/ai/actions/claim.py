"""ClaimPendingItemAction: claim the first available pending item."""

from dataclasses import dataclass

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_claim_pending_item_my_name_action_claim_item_id_post import sync as action_claim_item
from artifactsmmo_api_client.api.my_account.get_pending_items_my_pending_items_get import sync as get_pending_items

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

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        return bool(state.pending_items)

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        if not state.pending_items:
            return state
        item_id, item_code = state.pending_items[0]
        remaining = state.pending_items[1:]
        new_inventory = dict(state.inventory)
        new_inventory[item_code] = new_inventory.get(item_code, 0) + 1
        return WorldState(
            character=state.character,
            level=state.level,
            xp=state.xp,
            max_xp=state.max_xp,
            hp=state.hp,
            max_hp=state.max_hp,
            gold=state.gold,
            skills=state.skills,
            x=state.x,
            y=state.y,
            inventory=new_inventory,
            inventory_max=state.inventory_max,
            equipment=state.equipment,
            cooldown_expires=None,
            task_code=state.task_code,
            task_type=state.task_type,
            task_progress=state.task_progress,
            task_total=state.task_total,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
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
        )

    def __repr__(self) -> str:
        return "ClaimPendingItem"
