"""DrainBankJunkGoal: withdraw over-cap junk out of the bank so it can be shed."""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.bank_drain import bank_drain_excess
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.world_state import WorldState

DRAIN_BANK_JUNK_VALUE = 15.0
"""Discretionary housekeeping value: below RECYCLE_SURPLUS (20) and
GATHER_MATERIALS (50) so it never preempts objective or material-recovery work,
above the WAIT last-resort. Fires only during idle, low-pressure cycles to pull
over-cap bank junk (sap, far-skill-gated byproducts) into the bag where the
DiscardOverstock guard sells-or-deletes it — clearing a stockpile that would
otherwise sit in the bank forever."""


class DrainBankJunkGoal(Goal):
    """Withdraw bank holdings the keep authority licenses for disposal.

    Targets the BANK copies above BOTH the worth-hoarding cap and the authority's
    OWNERSHIP cap (`keep_owned`) — so the last tool, the last combat weapon, the
    active profile's gear demand, the recipe demand, the task item and the currency
    all survive a drain that would otherwise feed them straight to the discard
    ladder. The withdrawn excess becomes inventory overstock, which the
    DiscardOverstock guard sheds on a later cycle. See
    `ai/bank_drain.bank_drain_excess` for why the BAG cap (`keep_in_bag`) does NOT
    bound a bank-side drain.
    """

    def __init__(self, game_data: GameData, ctx: SelectionContext,
                 bank_accessible: bool, initial_total: int | None = None) -> None:
        self._gd = game_data
        # The per-cycle SelectionContext the keep authority reads (gear_keep,
        # step_profile). It REPLACES the `protected_codes` frozenset — protection is
        # a QUANTITY the authority owns, not a code-set this goal carries
        # (item-protection-authority epic, Task 9).
        self._ctx = ctx
        self._accessible = bank_accessible
        # Construction-time drain snapshot: ANY reduction below it satisfies, so
        # ONE space-capped Withdraw is a complete 1-action plan and a deep pile
        # drains one bag-load per episode. See `is_satisfied` for why the
        # all-or-nothing form made this goal UNPLANNABLE — the SAME dead end
        # `RecycleSurplusGoal.initial_total` was added for on 2026-07-05. None
        # keeps the strict all-clear semantics.
        self._initial_total = initial_total

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if self.is_satisfied(state):
            return 0.0
        return DRAIN_BANK_JUNK_VALUE

    def is_satisfied(self, state: WorldState) -> bool:
        """Satisfied when nothing is licensed, or when the licensed total has
        FALLEN below the construction snapshot.

        WHY THE SNAPSHOT IS LOAD-BEARING (measured 2026-08-05, part 2 of the
        disposal-unification epic). The all-or-nothing form — "satisfied iff
        `bank_drain_excess` is empty" — is UNREACHABLE for any pile deeper than
        the bag: a withdraw moves copies bank->bag, so emptying the map means
        holding all of them at once, and the live bank held 2273 licensed copies
        against a 120-quantity bag. Offline probe against the committed bundle,
        7 codes / 1993 licensed copies: `nodes_explored=8, timed_out=False,
        plan_len=0` — a STRUCTURAL refusal, not a budget timeout. So the rung was
        starved twice over: ranked below the objective step (defect A) AND unable
        to produce a plan even if selected. Hoisting it without this would have
        materialized a COLLECT-band candidate that could never win."""
        excess = bank_drain_excess(state, self._gd, self._ctx)
        if not excess:
            return True
        return (self._initial_total is not None
                and sum(excess.values()) < self._initial_total)

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"bank_junk_drained": True}

    def relevant_actions(
        self, actions: list[Action], state: WorldState, game_data: GameData,
    ) -> list[Action]:
        """One WithdrawItemAction per over-cap bank code, sized to fit free space.

        The withdraw MINTS the items into the bag, so the quantity is capped at
        current free slots (server HTTP 497 / `WithdrawItemAction.is_applicable`).
        The remainder drains on a later idle cycle once the bag is shed.

        THE PER-CYCLE BOUND (part 2, 2026-08-05) is these two facts together:
        the QUANTITY is capped at `state.inventory_free`, and the snapshot in
        `is_satisfied` makes ONE such withdraw a complete plan. So a drain
        episode is exactly ONE action-bucket request, whatever the pile's depth.

        WHY THAT BOUND AND NOT A BIGGER ONE — it is read off the rate budget, not
        chosen by taste. Every withdraw is one request in the ACTION bucket, whose
        sustainable pace is `utils/rate_budget.WindowBudget.sustainable_interval`
        = max over the API's declared windows of `span / limit`, and `divided_by`
        splits that per-IP budget across `play --all` children. The rest of the
        ladder spends exactly one action request per cycle (one action, one
        cooldown), so a shed rung that emitted K withdraws per episode would cost
        K times what any other candidate costs and would burst the governor's
        sliding window. At K=1 the drain is rate-neutral. Depth is recovered by
        BATCHING the quantity instead: the live 2273-copy hoard clears in
        ~2273/111 = 21 withdraw episodes, not 2273 requests.
        """
        bank_loc = game_data.bank_location_or_none
        if bank_loc is None:
            return []
        excess = bank_drain_excess(state, game_data, self._ctx)
        result: list[Action] = []
        for code, excess_qty in excess.items():
            start = excess_qty if excess_qty < state.inventory_free else state.inventory_free
            for qty in range(start, 0, -1):
                action = WithdrawItemAction(code=code, quantity=qty,
                                            bank_location=bank_loc,
                                            accessible=self._accessible)
                if action.is_applicable(state, game_data):
                    result.append(action)
                    break
        return result

    def __repr__(self) -> str:
        return "DrainBankJunk"
