"""UseGoldBagAction: consume a gold-bag consumable to credit its gold."""

import dataclasses
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_use_item_my_name_action_use_post import (
    sync as action_use_item,
)
from artifactsmmo_api_client.models.simple_item_schema import SimpleItemSchema

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.item_catalog import ItemStats
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

USE_GOLD_BAG_COST = 2.0


@dataclass
class UseGoldBagAction(Action):
    """Consume the highest-value owned gold-bag (effect `gold`) to add its gold to pocket.

    Tiebreak: when multiple gold-bags are in inventory, picks max by
    ``(gold_value, code)`` — highest gold_value wins; on a value tie the
    lexicographically largest code wins, making the result deterministic.
    """

    tags: ClassVar[frozenset[str]] = frozenset({"currency"})

    _item_stats: Mapping[str, ItemStats] = field(default_factory=dict, repr=False)

    def _best_bag(self, state: WorldState) -> tuple[str, int] | None:
        """Return (code, gold_value) for the highest-value owned gold-bag, or None."""
        candidates = [
            (code, s.gold_value)
            for code, qty in state.inventory.items()
            if qty > 0
            and (s := self._item_stats.get(code)) is not None
            and s.gold_value > 0
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda cb: (cb[1], cb[0]))

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        return self._best_bag(state) is not None

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        bag = self._best_bag(state)
        assert bag is not None
        code, gold_value = bag
        new_inv = dict(state.inventory)
        new_inv[code] -= 1
        if new_inv[code] == 0:
            del new_inv[code]
        return dataclasses.replace(
            state,
            gold=state.gold + gold_value,
            inventory=new_inv,
            cooldown_expires=None,
        )

    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        return USE_GOLD_BAG_COST

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        bag = self._best_bag(state)
        if bag is None:
            raise RuntimeError("UseGoldBag: no gold-bag in inventory at execute time")
        code, _ = bag
        result = action_use_item(
            client=client,
            name=state.character,
            body=SimpleItemSchema(code=code, quantity=1),
        )
        result = Action._raise_for_error(result, f"UseGoldBag({code})")
        return WorldState.from_character_schema(
            result.data.character,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
            active_events=state.active_events,
            raids=state.raids,
        )

    def __repr__(self) -> str:
        return "UseGoldBag"
