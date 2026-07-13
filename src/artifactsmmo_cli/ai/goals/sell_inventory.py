"""SellInventoryGoal: sell the copies the keep authority licenses, for gold and space."""

from datetime import datetime, timezone

from artifactsmmo_cli.ai.accumulation_sell import (
    SEVERE_STEPS,
    sell_targets,
    worst_accumulation_steps,
)
from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.npc_sell import NpcSellAction
from artifactsmmo_cli.ai.event_availability import event_npc_tradeable
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.selection_context import SelectionContext
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
hoard (`steps >= SEVERE_STEPS`, i.e. held >= 32x the keep) goes straight to
`DISCRETIONARY_CEIL` so it sheds first among housekeeping; a moderate hoard
ramps `min(ACCUM_BASE + steps*ACCUM_STEP, DISCRETIONARY_CEIL)`."""

MAX_SELL_DEPTH = 64
"""One batch NpcSell per licensed code clears the whole surplus, so the plan can
be as long as the bag has sellable stacks. The default depth (15) would cut a
20-stack bag's plan off at plan_len=0 and the goal would silently lose to a
lower-priority alternative (the `DiscardOverstockGoal` lesson)."""


class SellInventoryGoal(Goal):
    """Sell inventory to an NPC — for gold, and for the space a locked or full
    bank cannot give.

    WHAT MAY BE SOLD IS THE KEEP AUTHORITY'S ANSWER, not this goal's
    (item-protection-authority epic, Task 8): `ai/accumulation_sell.sell_targets`
    licenses `min(bankable, destroyable)` copies of each sellable code, so the
    equipped copy, the active profile's gear demand, the recipe demand, the task's
    own item, the heal stock, the currency and — through the in-bag half of the
    `min` — the last WORKING tool / COMBAT weapon all survive the sale. The goal
    used to plan against a SPACE target (`inventory_free >= MIN_FREE_SLOTS`) with
    the whole factory NpcSell set as its action pool, which let it sell ANY held
    item, protection be damned; and, being QUANTITY-blind to slots, it reported
    itself SATISFIED in a 19/20-slot bag with a roomy quantity cap, so a fired
    SELL_RELIEF guard was a no-op (census cell `active_task owned/liveness/
    slot_full`). Satisfaction is now the authority's licence being spent."""

    def __init__(self, game_data: GameData, ctx: SelectionContext,
                 bank_accessible: bool = True, relief: bool = False) -> None:
        self._gd = game_data
        # The per-cycle SelectionContext the keep authority reads (gear_keep,
        # step_profile). It REPLACES the `gear_keep` ctor param, which reached
        # `useful_quantity_cap` — whose zero cap for an un-profiled equippable is
        # what offered all 18 copper_axe, the working tool included.
        self._ctx = ctx
        self._bank_accessible = bank_accessible
        # The bank cannot take the surplus (mapped from GuardKind.SELL_RELIEF,
        # whose predicate IS `not bank_has_room`): the ratio gate exists to prefer
        # BANKING to an irreversible sale, so with no bank route it has no object
        # and the whole licensed surplus is offered — the bank-full cascade's SELL
        # rung, between RECYCLE_RELIEF and the destructive DISCARD guards.
        self._relief = relief

    def _sell_actions(self, state: WorldState, game_data: GameData) -> list[Action]:
        """One batch NpcSellAction per licensed code, at a buyer that can actually
        take it now.

        `sell_targets` guarantees at least one buyer is REACHABLE; the highest-price
        buyer may still be a dormant event merchant (no tile, or a shut spawn
        window), so the buyers are walked in price order until one yields an
        APPLICABLE action. Building the actions is also what makes `is_satisfied`
        honest: it is satisfied exactly when this list is empty, so every plan the
        goal admits terminates (each action removes its own code from the list and
        removes nothing else)."""
        result: list[Action] = []
        for code, quantity in sell_targets(state, game_data, self._ctx,
                                           relief=self._relief).items():
            for npc_code, _price in game_data.npcs_buying_item(code):
                loc = game_data.npc_location(npc_code)
                if loc is None:
                    continue
                act = NpcSellAction(npc_code=npc_code, item_code=code,
                                    quantity=quantity, npc_location=loc)
                if act.is_applicable(state, game_data):
                    result.append(act)
                    break
        return result

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
        if self.is_satisfied(state):
            return 0.0
        steps = worst_accumulation_steps(state, game_data, self._ctx)
        if steps >= SEVERE_STEPS:
            accum_value = DISCRETIONARY_CEIL
        elif steps > 0:
            accum_value = min(ACCUM_BASE + steps * ACCUM_STEP, DISCRETIONARY_CEIL)
        else:
            accum_value = 0.0
        used_fraction = state.inventory_used / state.inventory_max
        bank_locked_value = 0.0 if self._bank_accessible else used_fraction * 100.0
        window_value = SEIZE_WINDOW_VALUE if self._active_window_for_inventory(state, game_data) else 0.0
        return max(bank_locked_value, accum_value, window_value)

    def is_satisfied(self, state: WorldState) -> bool:
        """Satisfied once the authority's licence is spent — nothing left that may
        be sold AND can be sold now. NOT a space fraction: the keep caps may
        themselves fill the bag, and a bag that is slot-full but quantity-roomy
        (19/20 stacks in a 116-item cap — the live shape) would report itself
        satisfied and no-op a fired SELL_RELIEF guard."""
        return not self._sell_actions(state, self._gd)

    @property
    def max_depth(self) -> int:
        return MAX_SELL_DEPTH

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"sellable_surplus_sold": True}

    def relevant_actions(self, actions: list[Action], state: WorldState,
                         game_data: GameData) -> list[Action]:
        """ONLY the authority-licensed sells. The pre-built factory NpcSell set
        (`actions`) is deliberately NOT admitted: it carries one quantity=1 sale
        per (npc, item) pair with no protection at all, and it is what let a
        bank-locked full bag sell the task's own item, the heal stock or the last
        tool to buy itself five free slots."""
        return self._sell_actions(state, game_data)

    def __repr__(self) -> str:
        return "SellInventory"
