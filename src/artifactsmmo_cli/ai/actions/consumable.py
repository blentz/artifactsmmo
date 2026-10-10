"""UseConsumableAction: eat food from inventory to restore HP."""

import dataclasses
from collections.abc import Mapping
from dataclasses import dataclass, field
from fractions import Fraction
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_use_item_my_name_action_use_post import sync as action_use_item
from artifactsmmo_api_client.models.simple_item_schema import SimpleItemSchema

from artifactsmmo_cli.ai.actions.base import ANY_REGION, Action
from artifactsmmo_cli.ai.actions.cost_core import (
    CONSUMABLE_COOLDOWN_SECONDS,
)
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.loop_rate_core import recovery_choice
from artifactsmmo_cli.ai.world_state import WorldState


@dataclass
class UseConsumableAction(Action):
    """Eat food from the bag to restore HP: k units of one food in one use.

    In the planning model, eating restores the chosen item's `hp_restore`, capped
    at `max_hp` — what the server does, and what `Formal.CycleInvariants`
    models (`min maxHp (hp + gain)`). It used to heal to full, so one 50-hp
    gudgeon looked like it closed a 178-hp deficit and craft+eat beat Rest
    where four rounds were really dearer.
    """

    travel_region = ANY_REGION  # no folded movement: plannable in any region

    tags: ClassVar[frozenset[str]] = frozenset({"recovery"})

    _item_stats: Mapping[str, ItemStats] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        # Only type="consumable" items (food) are use-able via the action/use
        # endpoint. A type="utility" heal (small_health_potion, subtype=potion)
        # carries hp_restore>0 but restores HP by being EQUIPPED into a utility
        # slot and consumed in combat — calling /use on it returns HTTP 476
        # "Invalid consumable item" (live deadlock 2026-07-02: Robby held 10
        # small_health_potion with empty utility slots and spun UseConsumable
        # forever). Filter them out here so the eat never picks one and
        # RestoreHP falls back to Rest / equipping.
        self._item_stats = {
            code: stats for code, stats in self._item_stats.items()
            if stats.type_ == "consumable"
        }

    def _choice(self, state: WorldState) -> tuple[str, int, int] | None:
        """(food, units, restore) of this recovery's next eat, or None when
        Rest is the cheaper recovery.

        ONE MODEL WITH THE LOOP RATE (USER 2026-10-10): the eat is
        `loop_rate_core.recovery_choice` over the BAG's foods usable at the
        character's level (held units are free; nothing past them is eaten
        here), with the published flat cooldown — "a fixed cooldown of 3
        seconds, regardless of the quantity used" (docs.artifactsmmo.com,
        resting_and_using_items). So k units of one food are ONE use, and an
        overheal is chosen exactly when it is still the cheaper recovery. It
        used to eat one unit a request and price an overheal at a sentinel, so
        RestoreHP and the loop model could pick differently on the same state.
        The first food the choice eats is this use; the rest follow as further
        uses or a Rest, as the plan finds."""
        deficit = state.max_hp - state.hp
        if deficit <= 0:
            return None
        codes = [code for code, stats in self._item_stats.items()
                 if state.inventory.get(code, 0) > 0 and stats.hp_restore > 0
                 and stats.level <= state.level]
        food = [(self._item_stats[code].hp_restore, None, state.inventory[code])
                for code in codes]
        _, counts = recovery_choice(deficit, state.max_hp, food,
                                    Fraction(CONSUMABLE_COOLDOWN_SECONDS))
        for code, units in zip(codes, counts, strict=True):
            if units > 0:
                return code, units, self._item_stats[code].hp_restore
        return None

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        return self._choice(state) is not None

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        choice = self._choice(state)
        assert choice is not None
        code, units, restore = choice
        new_inventory = dict(state.inventory)
        new_inventory[code] -= units
        if new_inventory[code] == 0:
            del new_inventory[code]
        return dataclasses.replace(
            state,
            hp=min(state.max_hp, state.hp + units * restore),
            inventory=new_inventory,
            cooldown_expires=None,
        )

    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        # One use, the published flat cooldown whatever the quantity.
        return CONSUMABLE_COOLDOWN_SECONDS

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        choice = self._choice(state)
        if choice is None:
            raise RuntimeError("UseConsumable: no food to eat at execute time")
        code, units, _ = choice
        result = action_use_item(client=client, name=state.character,
                                 body=SimpleItemSchema(code=code, quantity=units))
        result = Action._raise_for_error(result, f"UseConsumable({code}×{units})")
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
