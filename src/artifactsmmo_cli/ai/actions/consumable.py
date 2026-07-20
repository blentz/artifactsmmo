"""UseConsumableAction: eat food from inventory to restore HP."""

import dataclasses
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_use_item_my_name_action_use_post import sync as action_use_item
from artifactsmmo_api_client.models.simple_item_schema import SimpleItemSchema

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.cost_core import OVERHEAL_CONSUMABLE_COST
from artifactsmmo_cli.ai.consumable_selection import select_consumable
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.learning.store import LearningStore
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

    tags: ClassVar[frozenset[str]] = frozenset({"recovery"})

    _item_stats: Mapping[str, ItemStats] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        # Only type="consumable" items (food) are use-able via the action/use
        # endpoint. A type="utility" heal (small_health_potion, subtype=potion)
        # carries hp_restore>0 but restores HP by being EQUIPPED into a utility
        # slot and consumed in combat — calling /use on it returns HTTP 476
        # "Invalid consumable item" (live deadlock 2026-07-02: Robby held 10
        # small_health_potion with empty utility slots and spun UseConsumable
        # forever). Filter them out here so select_consumable never picks one and
        # RestoreHP falls back to Rest / equipping. select_consumable (the proven
        # ConsumableSelection core) stays untouched — it just sees the food subset.
        self._item_stats = {
            code: stats for code, stats in self._item_stats.items()
            if stats.type_ == "consumable"
        }

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        if state.hp >= state.max_hp:
            return False
        deficit = state.max_hp - state.hp
        return select_consumable(state.inventory, self._item_stats, deficit) is not None

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        deficit = state.max_hp - state.hp
        best = select_consumable(state.inventory, self._item_stats, deficit)
        assert best is not None
        item_code, _ = best
        new_inventory = dict(state.inventory)
        new_inventory[item_code] -= 1
        if new_inventory[item_code] == 0:
            del new_inventory[item_code]
        return dataclasses.replace(
            state,
            hp=state.max_hp,  # full-heal assumption: planning treats food as solving the problem
            inventory=new_inventory,
            cooldown_expires=None,
        )

    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        # select_consumable is overheal-aware: it picks the best-FITTING consumable
        # for the deficit, only overhealing when NOTHING fits. So the Rest-forcing
        # sentinel fires only when even the chosen (least-overheal) item still
        # overshoots — i.e. no fitting consumable exists.
        deficit = state.max_hp - state.hp
        best = select_consumable(state.inventory, self._item_stats, deficit)
        if best is None:
            return 2.0                        # not applicable anyway; cheap default
        _, restore = best
        if restore <= deficit:
            return 2.0                        # fits the deficit -> beats Rest (<= REST_COST_MAX)
        # Overheal: prefer Rest over wasting the item. OVERHEAL_CONSUMABLE_COST is
        # derived from REST_COST_MAX (cost_core.py), so it stays dominant if the
        # Rest cost unit is ever rescaled.
        return OVERHEAL_CONSUMABLE_COST

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        deficit = state.max_hp - state.hp
        best = select_consumable(state.inventory, self._item_stats, deficit)
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
            active_events=state.active_events,
            raids=state.raids,
        )

    def __repr__(self) -> str:
        return "UseConsumable"
