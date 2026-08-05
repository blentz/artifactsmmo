"""SellInventoryGoal: sell the copies the keep authority licenses, for gold and space."""

from datetime import datetime, timezone

from artifactsmmo_cli.ai.accumulation_sell import (
    SEVERE_STEPS,
    bank_sellable_surplus,
    sell_targets,
    worst_accumulation_steps,
    worst_bank_accumulation_steps,
)
from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.npc_sell import NpcSellAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
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
                 bank_accessible: bool = True, relief: bool = False,
                 state: WorldState | None = None) -> None:
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
        # BANK-ARM SNAPSHOT (part 2, 2026-08-05). `state=` arms the bank-side arm
        # AND bounds it in one move: the codes the bank licenses for sale right
        # now, and how many copies of them the character OWNS (bag + bank). A
        # `Withdraw` leaves that number untouched and a `NpcSell` strictly lowers
        # it, so the SHORTEST progressing plan is exactly one `Withdraw` + one
        # `NpcSell` — see `is_satisfied` for the bound and its derivation.
        #
        # `None` (every pre-existing call site, incl. the SELL_RELIEF guard)
        # keeps the BAG-ONLY behaviour byte-for-byte: an unsnapshotted bank arm
        # would have no termination bound, which is the `RecycleSurplusGoal.
        # initial_total=None` contract exactly.
        self._snapshot_codes: frozenset[str] = frozenset()
        self._initial_owned: int | None = None
        if state is not None:
            self._snapshot_codes = frozenset(
                bank_sellable_surplus(state, game_data, ctx))
            self._initial_owned = self._owned_snapshot_total(state)

    def _owned_snapshot_total(self, state: WorldState) -> int:
        """Copies of the snapshot's codes the character OWNS — bag PLUS bank.

        The progress metric for the bank arm, chosen because a `Withdraw` moves a
        copy between the two halves and so leaves the SUM exactly unchanged,
        while a sale destroys ownership and lowers it. A metric over the bank
        alone would call a bare `Withdraw` progress and the goal would stop one
        action short of the sale it exists for."""
        bank = state.bank_items or {}
        return sum(state.inventory.get(code, 0) + bank.get(code, 0)
                   for code in self._snapshot_codes)

    def _bank_arm_actions(self, state: WorldState,
                          game_data: GameData) -> list[Action]:
        """The two legs the bank arm needs per licensed code: a space-capped
        `Withdraw`, and the `NpcSell` that becomes applicable once it lands.

        Neither is applicable in the initial state (the bag holds none of the
        code) — the PLANNER orders them, exactly as the recycle-source census's
        BANKED cell has it stage `Withdraw` before `Recycle`. `sell_targets`
        cannot reach these copies at all: it iterates `state.inventory`, so a
        surplus held ENTIRELY in the bank was invisible to the sell route.

        NO WITHDRAW WITHOUT A SALE, and the sale's own precondition is what says
        so. `accumulation_sell._is_sellable` only asks whether a buyer has a TILE;
        `NpcSellAction.is_applicable` also demands the merchant be TRADEABLE NOW
        (`event_npc_tradeable`), and several bulk piles — sap, gudgeon on the
        committed bundle — are priced only by dormant event merchants. Offering a
        bare withdraw there would be the DRAIN rung wearing a sell hat: it would
        mint junk into the bag with no sale to follow, on a rung the arbiter
        hoists ABOVE the objective step. So the pair is offered only when the sale
        is applicable in the state the withdraw ACTUALLY produces.

        Empty whenever the goal was built without a `state=` snapshot, or the
        bank is inaccessible / has no tile — the arm has no bound and no first
        leg in those worlds."""
        bank_loc = game_data.bank_location_or_none
        if self._initial_owned is None or bank_loc is None or not self._bank_accessible:
            return []
        result: list[Action] = []
        for code, licensed in bank_sellable_surplus(state, game_data, self._ctx).items():
            # The withdraw MINTS copies into the bag (HTTP 497), so the quantity
            # is capped at the free space — the SAME per-episode quantity bound
            # `DrainBankJunkGoal.relevant_actions` derives from the rate budget.
            start = licensed if licensed < state.inventory_free else state.inventory_free
            for qty in range(start, 0, -1):
                withdraw = WithdrawItemAction(code=code, quantity=qty,
                                              bank_location=bank_loc,
                                              accessible=self._bank_accessible)
                if not withdraw.is_applicable(state, game_data):
                    continue
                sale = self._sale_after(code, qty,
                                        withdraw.apply(state, game_data), game_data)
                if sale is None:
                    break
                result.append(withdraw)
                result.append(sale)
                break
        return result

    def _sale_after(self, code: str, quantity: int, landed: WorldState,
                    game_data: GameData) -> NpcSellAction | None:
        """The batch sale of `quantity` copies of `code` that is APPLICABLE in
        `landed` — the state the paired withdraw produces.

        Buyers are walked in price order until one yields an applicable action,
        exactly as `_sell_actions` does for the bag: the highest-price buyer may
        be a dormant event merchant. `None` means no buyer can take these copies
        this cycle, and the arm declines to withdraw them at all."""
        for npc_code, _price in game_data.npcs_buying_item(code):
            loc = game_data.npc_location(npc_code)
            if loc is None:
                continue
            sale = NpcSellAction(npc_code=npc_code, item_code=code,
                                 quantity=quantity, npc_location=loc)
            if sale.is_applicable(landed, game_data):
                return sale
        return None

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
        # The BANK arm is counted here too: a hoard held entirely in the bank has
        # nothing in `state.inventory` to answer this question, so the bag-only
        # test scored the live 703-sap pile at 0.0 — value() would have told a
        # false story about the very rung the bank arm exists to feed.
        sellable = (any(game_data.npcs_buying_item(code)
                        for code in state.inventory if state.inventory[code] > 0)
                    or bool(bank_sellable_surplus(state, game_data, self._ctx)))
        if not sellable:
            return 0.0
        if self.is_satisfied(state):
            return 0.0
        steps = max(worst_accumulation_steps(state, game_data, self._ctx),
                    worst_bank_accumulation_steps(state, game_data, self._ctx))
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
        satisfied and no-op a fired SELL_RELIEF guard.

        THE BANK ARM IS SNAPSHOT-BOUNDED (part 2, 2026-08-05). Spending the bank's
        WHOLE licence is unreachable for a deep pile — the copies have to pass
        through a 120-quantity bag, and the live bank held 2273 of them — which is
        the same all-or-nothing dead end that made `DrainBankJunkGoal` return
        plan_len=0 with `nodes_explored=8`. So once the bag licence is spent, the
        goal is satisfied by ANY fall in OWNED copies of the snapshot's codes.

        THE BOUND THAT FALLS OUT, AND ITS DERIVATION. A `Withdraw` does not move
        that number, a `NpcSell` does, so the cheapest satisfying plan is exactly
        ONE `Withdraw` + ONE `NpcSell`: two ACTION-bucket requests per sell
        episode, whatever the pile's depth. That is read off the rate budget, not
        picked by taste — the per-IP action budget
        (`utils/rate_budget.WindowBudget.sustainable_interval`, `divided_by` the
        number of `play --all` children) is this bot's binding constraint, and
        every other rung on the ladder spends one request per cycle. An episode of
        K withdraw+sell pairs would cost K times what any other candidate costs
        and burst the governor's sliding window. Depth is recovered by BATCHING
        the quantity (one sale of 120, not 120 sales of one), so the live
        2273-copy hoard sheds in ~21 episodes rather than 2273 requests."""
        if self._sell_actions(state, self._gd):
            return False
        if not self._bank_arm_actions(state, self._gd):
            return True
        return (self._initial_owned is not None
                and self._owned_snapshot_total(state) < self._initial_owned)

    @property
    def max_depth(self) -> int:
        return MAX_SELL_DEPTH

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"sellable_surplus_sold": True}

    def relevant_actions(self, actions: list[Action], state: WorldState,
                         game_data: GameData) -> list[Action]:
        """ONLY the authority-licensed sells, plus the bank arm's staged
        withdraw+sell pairs. The pre-built factory NpcSell set (`actions`) is
        deliberately NOT admitted: it carries one quantity=1 sale per (npc, item)
        pair with no protection at all, and it is what let a bank-locked full bag
        sell the task's own item, the heal stock or the last tool to buy itself
        five free slots."""
        return self._sell_actions(state, game_data) + self._bank_arm_actions(state, game_data)

    def __repr__(self) -> str:
        return "SellInventory"
