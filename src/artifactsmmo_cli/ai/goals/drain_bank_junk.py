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
                 bank_accessible: bool) -> None:
        self._gd = game_data
        # The per-cycle SelectionContext the keep authority reads (gear_keep,
        # step_profile). It REPLACES the `protected_codes` frozenset — protection is
        # a QUANTITY the authority owns, not a code-set this goal carries
        # (item-protection-authority epic, Task 9).
        self._ctx = ctx
        self._accessible = bank_accessible

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if self.is_satisfied(state):
            return 0.0
        return DRAIN_BANK_JUNK_VALUE

    def is_satisfied(self, state: WorldState) -> bool:
        return not bank_drain_excess(state, self._gd, self._ctx)

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"bank_junk_drained": True}

    def relevant_actions(
        self, actions: list[Action], state: WorldState, game_data: GameData,
    ) -> list[Action]:
        """One WithdrawItemAction per over-cap bank code, sized to fit free space.

        The withdraw MINTS the items into the bag, so the quantity is capped at
        current free slots (server HTTP 497 / `WithdrawItemAction.is_applicable`).
        The remainder drains on a later idle cycle once the bag is shed.
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
