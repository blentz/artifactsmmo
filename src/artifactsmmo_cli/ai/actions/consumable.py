"""UseConsumableAction: eat food from inventory to restore HP."""

from dataclasses import dataclass, field

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_use_item_my_name_action_use_post import sync as action_use_item
from artifactsmmo_api_client.models.simple_item_schema import SimpleItemSchema

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.world_state import WorldState


def _best_consumable(inventory: dict[str, int], item_stats: dict[str, ItemStats]) -> tuple[str, int] | None:
    """Return (item_code, hp_restore) for the highest-restore consumable in inventory."""
    best: tuple[str, int] | None = None
    for code, qty in inventory.items():
        if qty <= 0:
            continue
        stats = item_stats.get(code)
        if stats is None or stats.hp_restore <= 0:
            continue
        if best is None or stats.hp_restore > best[1]:
            best = (code, stats.hp_restore)
    return best


@dataclass
class UseConsumableAction(Action):
    """Use the best available consumable from inventory to restore HP.

    In the planning model, eating any food fully heals the character — this
    approximation keeps the planner chain simple while real execution partially
    heals and subsequent loop iterations handle remaining deficit via Rest.
    """

    _item_stats: dict[str, ItemStats] = field(default_factory=dict, repr=False)

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        if state.hp >= state.max_hp:
            return False
        return _best_consumable(state.inventory, self._item_stats) is not None

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        best = _best_consumable(state.inventory, self._item_stats)
        assert best is not None
        item_code, _ = best
        new_inventory = dict(state.inventory)
        new_inventory[item_code] -= 1
        if new_inventory[item_code] == 0:
            del new_inventory[item_code]
        return WorldState(
            character=state.character,
            level=state.level,
            xp=state.xp,
            max_xp=state.max_xp,
            hp=state.max_hp,  # full-heal assumption: planning treats food as solving the problem
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
            pending_items=state.pending_items,
        )

    def cost(self, state: WorldState, game_data: GameData) -> float:
        return 2.0

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        best = _best_consumable(state.inventory, self._item_stats)
        if best is None:
            raise RuntimeError("UseConsumable: no consumable in inventory at execute time")
        item_code, _ = best
        result = action_use_item(client=client, name=state.character, body=SimpleItemSchema(code=item_code, quantity=1))
        result = Action._raise_for_error(result, f"UseConsumable({item_code})")
        return WorldState.from_character_schema(
            result.data.character,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
        )

    def __repr__(self) -> str:
        return "UseConsumable"
