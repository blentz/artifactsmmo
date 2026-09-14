"""DepositAllAction: move to bank and deposit all bankable inventory items."""

import dataclasses
from dataclasses import dataclass, field
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_deposit_bank_item_my_name_action_bank_deposit_item_post import (
    sync as deposit_item,
)
from artifactsmmo_api_client.models.simple_item_schema import SimpleItemSchema

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.cooldown_wait import wait_out_cooldown
from artifactsmmo_cli.ai.actions.cost_core import qty_cost_pure
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.bank_room import bank_has_room
from artifactsmmo_cli.ai.bank_selection import select_bank_deposits
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT, SelectionContext
from artifactsmmo_cli.ai.world_state import WorldState

DEPOSIT_BATCH_MAX = 20
"""Codes the server accepts in one deposit request.

`openapi.json`, `/my/{name}/action/bank/deposit/item` request body:
`min_items: 1, max_items: 20`. Exceeding it is a 422 the planner cannot see
coming, so the trip is split rather than sent whole.
"""


@dataclass
class DepositAllAction(Action):
    """Move to bank and deposit every SURPLUS copy in the bag.

    "All" is per-copy, not per-code: `select_bank_deposits` returns the quantity
    of each held code that exceeds its `keep_in_bag` cap, so a stack can be
    PARTIALLY banked (17 of 18 copper_axe — the working tool stays)."""

    tags: ClassVar[frozenset[str]] = frozenset({"bank", "deposit"})

    bank_location: tuple[int, int] = field(default=(0, 0), repr=False)
    accessible: bool = True  # False when bank is gated behind an unmet achievement (HTTP 496)
    game_data: GameData | None = field(default=None, repr=False)
    # The selection context the deposit quantities are computed under — its
    # `step_profile` is the active goal's material demand (the GOAL_MATERIALS keep
    # reason). DepositInventoryGoal threads its own ctx in via relevant_actions;
    # run-5 trace 2026-06-11 23:05 (cycle 10) showed the goal planning with the
    # profile while the executed action ignored it — banking all 59 ash_wood the
    # active wooden_shield grind needed (14 withdraw cycles to recover).
    ctx: SelectionContext = field(default=NO_PROFILE_CONTEXT, repr=False)
    #: One-entry `(state, deposits)` memo for `_deposits`; see there. Excluded
    #: from `repr`/`eq` so an action carrying a warm memo still compares equal to
    #: a cold one — the planner dedups actions by value.
    _last_deposits: "tuple[WorldState, list[tuple[str, int]]] | None" = field(
        default=None, repr=False, compare=False)

    def _deposits(self, state: WorldState) -> list[tuple[str, int]]:
        """Surplus copies to bank this trip (per-code quantity, sell-value
        ordered), or [] when no game_data is available (no banking without data).

        MEMOISED ON THE STATE OBJECT ITSELF, for the immediately repeated call.
        The planner asks `is_applicable(state)` and then `apply(state)` with the
        SAME state object, and both need this list, so every expanded node paid
        for it twice. Profiled on C3P0's skill-gap search: 10,846 calls for 5,423
        nodes, 11.7s of a 15.0s budget, the whole of it `select_bank_deposits` ->
        `bankable` -> `reason_quantity` (1.48M calls).

        IDENTITY, NOT VALUE. The key is `is`, so this cannot answer for a
        different state that merely looks equal — and it needs no hash of a
        115-item bag, which is what makes it cheaper than the call it replaces.
        One entry: the pattern being exploited is an immediate repeat, and
        holding more states alive would trade a search's worth of memory for
        nothing. Correct even if the planner stops repeating — it would simply
        never hit."""
        if self.game_data is None:
            return []
        cached = self._last_deposits
        if cached is not None and cached[0] is state:
            return cached[1]
        out = select_bank_deposits(state, self.game_data, self.ctx)
        out = self._acceptable(state, out)
        self._last_deposits = (state, out)
        return out

    def _acceptable(self, state: WorldState,
                    deposits: list[tuple[str, int]]) -> list[tuple[str, int]]:
        """`deposits` minus the codes a FULL bank cannot take — those needing a
        new slot it does not have.

        Room is a PER-CODE question. A deposit into a stack the bank already
        carries merges into that slot and a full bank still accepts it; only a
        code the bank does not hold needs a slot of its own. Filtering the list
        every caller reads keeps `is_applicable`, `apply` and `execute` telling
        the same story — gating only `is_applicable` would leave `apply`
        projecting a deposit `execute` cannot make.

        UNKNOWN IS NOT FULL, which is why `bank_has_room` cannot answer alone:
        it folds `bank_items is None` (bank not read this cycle) and
        `bank_capacity == 0` (capacity not read) into the same False as a
        genuinely full bank. Treating those as full would refuse every deposit
        before the first bank visit, so knownness is established first and the
        shared predicate then answers the room question itself.

        Live Robby 2026-09-12: 50 codes in 50 slots, six held codes, none of
        them banked. Every deposit 462'd and the skill-grind sub-plan re-emitted
        `DepositAll` at its head for 181 consecutive cycles."""
        capacity = self.game_data.bank_capacity if self.game_data is not None else 0
        known = state.bank_items is not None and capacity > 0
        if not known or bank_has_room(self.accessible, state.bank_items, capacity):
            return deposits
        banked = state.bank_items or {}
        return [(code, qty) for code, qty in deposits if code in banked]

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        return self.accessible and bool(self._deposits(state))

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        dest = self.bank_location
        new_inventory = dict(state.inventory)
        new_bank = dict(state.bank_items or {})
        for code, qty in self._deposits(state):
            new_bank[code] = new_bank.get(code, 0) + qty
            # PARTIAL deposit: only the surplus above `keep_in_bag` leaves the bag,
            # so the kept copies (the working tool, the task's own inputs, the heal
            # stock) must survive `apply`. Popping the whole stack — what this did
            # while deposits were whole-stack — would make the PLANNED state a lie
            # about what execution does, and the planner would think a protected
            # copy had been banked.
            remaining = new_inventory.get(code, 0) - qty
            if remaining > 0:
                new_inventory[code] = remaining
            else:
                new_inventory.pop(code, None)
        return dataclasses.replace(
            state,
            x=dest[0],
            y=dest[1],
            inventory=new_inventory,
            cooldown_expires=None,
            bank_items=new_bank,
        )

    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        dest = self.bank_location
        dist = abs(dest[0] - state.x) + abs(dest[1] - state.y)
        return qty_cost_pure(0.0, len(state.inventory), dist, 2.0)

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        if (state.x, state.y) != self.bank_location:
            state = MoveAction(x=self.bank_location[0], y=self.bank_location[1]).execute(state, client)
        last_state = state
        deposits = self._deposits(state)
        # ONE REQUEST PER BATCH, NOT PER CODE. The endpoint takes a list body,
        # and every accepted deposit — whatever its width — starts exactly one
        # server cooldown. Sending each code on its own put the second call
        # inside the first call's cooldown: live Robby 2026-09-13, a 2.07%
        # `error:cooldown` rate over 1404 executions (18x FightAction's), every
        # failure a PARTIAL deposit with the items already gone from the bag and
        # ~1.5s of cooldown left to run. Batching also cuts a 21-code trip from
        # 21 requests to 2, against a per-IP request budget that is the fleet's
        # binding constraint.
        for start in range(0, len(deposits), DEPOSIT_BATCH_MAX):
            batch = deposits[start:start + DEPOSIT_BATCH_MAX]
            if start:
                # Only BETWEEN batches. The cooldown the final batch sets is the
                # player loop's to sleep out, and waiting on it here would bill
                # the same cooldown twice.
                wait_out_cooldown(last_state)
            body = [SimpleItemSchema(code=code, quantity=qty) for code, qty in batch]
            result = deposit_item(client=client, name=state.character, body=body)
            # A REJECTION IS NOT A SKIP. Every documented non-200 comes back as
            # an `ErrorResponseSchema`, which carries no `.data` — so the old
            # `hasattr(result, "data")` guard swallowed each one and returned
            # the UNCHANGED state as a success, with no cooldown. Live Robby
            # 2026-09-12 spent 8.3 hours re-deriving the identical plan that way
            # against a full bank (462), reporting `ok` on all 181 cycles.
            result = Action._raise_for_error(result, "DepositAll")
            last_state = WorldState.from_character_schema(
                result.data.character,
                bank_items=last_state.bank_items,
                bank_gold=last_state.bank_gold,
                pending_items=last_state.pending_items,
                active_events=last_state.active_events,
            )
        return last_state

    def __repr__(self) -> str:
        return "DepositAll"
