"""DrainBankJunkGoal: withdraw over-cap junk out of the bank so it can be shed."""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.bank_drain import bank_drain_excess
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

DRAIN_BANK_JUNK_VALUE = 15.0
"""Discretionary housekeeping value: below RECYCLE_SURPLUS (20) and
GATHER_MATERIALS (50) so it never preempts objective or material-recovery work,
above the WAIT last-resort. Fires only during idle, low-pressure cycles to pull
over-cap bank junk (sap, far-skill-gated byproducts) into the bag where the
DiscardOverstock guard sells-or-deletes it — clearing a stockpile that would
otherwise sit in the bank forever."""


class DrainBankJunkGoal(Goal):
    """Withdraw bank holdings held above their useful keep-cap.

    Targets non-objective codes whose bank quantity exceeds
    `useful_quantity_cap` (after crediting what inventory already holds toward
    the cap). The withdrawn excess becomes inventory overstock, which the
    existing DiscardOverstock guard sheds (sell if a buyer is active, else
    delete) on a later cycle. See `ai/bank_drain.bank_drain_excess`.
    """

    def __init__(self, game_data: GameData, protected_codes: frozenset[str],
                 bank_accessible: bool) -> None:
        self._gd = game_data
        self._protected = protected_codes
        self._accessible = bank_accessible

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if self.is_satisfied(state):
            return 0.0
        return DRAIN_BANK_JUNK_VALUE

    def is_satisfied(self, state: WorldState) -> bool:
        return not bank_drain_excess(state, self._gd, self._protected)

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
        excess = bank_drain_excess(state, game_data, self._protected)
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
