"""Sell inventory items to NPCs to clear space when bank is inaccessible."""

from datetime import datetime, timezone

from artifactsmmo_cli.ai.accumulation_sell import (
    SEVERE_STEPS,
    sellable_accumulation,
    worst_accumulation_steps,
)
from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.npc_sell import NpcSellAction
from artifactsmmo_cli.ai.event_availability import event_npc_tradeable
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.goals.deposit_inventory import MIN_FREE_SLOTS
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

SEIZE_WINDOW_VALUE = 60.0
"""Goal value when a reachable merchant event is live and we hold sellable
stock — high enough to opportunistically sell during the rare window, but
below the bank-locked near-full urgency (which can reach ~100)."""

ACCUM_BASE = 18.0
ACCUM_STEP = 3.0
DISCRETIONARY_CEIL = 48.0
"""Idle accumulation-sell value, all within the discretionary band (strictly
below progression 50 / survival 70 — never derails active leveling): a SEVERE
hoard (`steps >= SEVERE_STEPS`, i.e. held >= 32x the keep-cap) goes straight to
`DISCRETIONARY_CEIL` so it sheds first among housekeeping; a moderate hoard
ramps `min(ACCUM_BASE + steps*ACCUM_STEP, DISCRETIONARY_CEIL)`."""


class SellInventoryGoal(Goal):
    """Recover gold by selling inventory items when the bank is locked."""

    def __init__(self, bank_accessible: bool = True,
                 gear_keep: dict[str, int] | None = None) -> None:
        self._bank_accessible = bank_accessible
        # Active-profile gear-demand keep map (spec
        # 2026-06-28-gear-loadout-profiles): forwarded to the accumulation-sell
        # cap so equippable gear sells down to its active-profile demand
        # (un-profiled, not-in-flight gear is sellable). None = legacy cap.
        self._gear_keep = gear_keep

    def _active_window_for_inventory(self, state: WorldState, game_data: GameData) -> bool:
        """True if some held item can be sold to a currently-active reachable merchant."""
        now = datetime.now(timezone.utc)
        for item_code, qty in state.inventory.items():
            if qty <= 0:
                continue
            for npc_code, _price in game_data.npcs_buying_item(item_code):
                if not game_data.is_event_npc(npc_code):
                    continue
                if event_npc_tradeable(npc_code, game_data, x=state.x, y=state.y,
                                       active_events=state.active_events, now=now):
                    return True
        return False

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if state.inventory_max == 0:
            return 0.0
        sellable = any(game_data.npcs_buying_item(code)
                       for code in state.inventory if state.inventory[code] > 0)
        if not sellable:
            return 0.0
        steps = worst_accumulation_steps(state, game_data, gear_keep=self._gear_keep)
        if steps >= SEVERE_STEPS:
            accum_value = DISCRETIONARY_CEIL
        elif steps > 0:
            accum_value = min(ACCUM_BASE + steps * ACCUM_STEP, DISCRETIONARY_CEIL)
        else:
            accum_value = 0.0
        if self.is_satisfied(state) and accum_value == 0.0:
            return 0.0
        used_fraction = state.inventory_used / state.inventory_max
        bank_locked_value = 0.0 if self._bank_accessible else used_fraction * 100.0
        window_value = SEIZE_WINDOW_VALUE if self._active_window_for_inventory(state, game_data) else 0.0
        return max(bank_locked_value, accum_value, window_value)

    def is_satisfied(self, state: WorldState) -> bool:
        return state.inventory_free >= MIN_FREE_SLOTS

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"inventory_free": MIN_FREE_SLOTS}

    def relevant_actions(self, actions: list[Action], state: WorldState, game_data: GameData) -> list[Action]:
        result: list[Action] = []
        for action in actions:
            if "recovery" in action.tags or (isinstance(action, NpcSellAction)
                                             and state.inventory.get(action.item_code, 0) > 0):
                result.append(action)
        for code, excess in sellable_accumulation(state, game_data,
                                                  gear_keep=self._gear_keep).items():
            # `sellable_accumulation` guarantees at least one buyer is reachable;
            # pick the highest-price buyer that actually has a location (a
            # higher-price buyer may be a dormant event merchant with no tile).
            for npc_code, _price in game_data.npcs_buying_item(code):
                loc = game_data.npc_location(npc_code)
                if loc is None:
                    continue
                act = NpcSellAction(npc_code=npc_code, item_code=code,
                                    quantity=excess, npc_location=loc)
                if act.is_applicable(state, game_data):
                    result.append(act)
                    break
        return result

    def __repr__(self) -> str:
        return "SellInventory"
