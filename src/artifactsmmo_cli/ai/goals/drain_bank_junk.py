"""DrainBankJunkGoal: withdraw over-cap junk out of the bank so it can be shed."""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.bank_drain import DrainSnapshot, bank_drain_excess, owned_total
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.inventory_keep import bankable, destroyable
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.shed_actions import shed_actions
from artifactsmmo_cli.ai.thresholds import DEPOSIT_FULL_FRACTION
from artifactsmmo_cli.ai.tiers.guards import used_fraction
from artifactsmmo_cli.ai.world_state import WorldState

DRAIN_BANK_JUNK_VALUE = 15.0
"""Discretionary housekeeping value: below RECYCLE_SURPLUS (20) and
GATHER_MATERIALS (50) so it never preempts objective or material-recovery work,
above the WAIT last-resort. Fires only during idle, low-pressure cycles to pull
over-cap bank junk (sap, far-skill-gated byproducts) out of the bank and shed
it in the same plan — clearing a stockpile that would otherwise sit in the
bank forever."""


class DrainBankJunkGoal(Goal):
    """Withdraw bank holdings the keep authority licenses for disposal, and
    dispose of them in the same plan.

    Targets the BANK copies above BOTH the worth-hoarding cap and the authority's
    OWNERSHIP cap (`keep_owned`) — so the last tool, the last combat weapon, the
    active profile's gear demand, the recipe demand, the task item and the currency
    all survive. See `ai/bank_drain.bank_drain_excess` for why the BAG cap
    (`keep_in_bag`) does NOT bound a bank-side drain.

    ONE PLAN, WITHDRAW THEN SHED (2026-09-30). The drain used to stop at the
    withdraw and leave the junk to the DiscardOverstock guard, which acts only
    under bag pressure. Below it the junk sat, the next episode withdrew more,
    and at DEPOSIT_FULL the deposit guard banked it all again: live R2D2 and HAL
    lapped `Withdraw ×4 → DepositAll` every ~25 s. Now the plan sheds what it
    withdraws through the same routing the discard guard uses (`shed_actions`),
    the withdraw is sized to keep the bag below the deposit guard's fraction,
    and the episode counts only a disposal as done (the OWNED total falls; a
    withdraw merely moves copies).
    """

    def __init__(self, game_data: GameData, ctx: SelectionContext,
                 bank_accessible: bool, snapshot: DrainSnapshot) -> None:
        self._gd = game_data
        # The per-cycle SelectionContext the keep authority reads (gear_keep,
        # step_profile). It REPLACES the `protected_codes` frozenset — protection is
        # a QUANTITY the authority owns, not a code-set this goal carries
        # (item-protection-authority epic, Task 9).
        self._ctx = ctx
        self._accessible = bank_accessible
        # Construction-time snapshot: ANY disposal satisfies, so one withdraw
        # and its shed are a complete plan and a deep pile drains one episode
        # at a time. See `is_satisfied`.
        self._snapshot = snapshot

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if self.is_satisfied(state):
            return 0.0
        return DRAIN_BANK_JUNK_VALUE

    def is_satisfied(self, state: WorldState) -> bool:
        """Satisfied when the character owns FEWER copies of the snapshot's
        licensed codes than it did (something was sold, recycled or deleted),
        or when it licensed nothing. The bank-side excess alone cannot end the
        episode: withdrawing the whole licensed pile empties it with every copy
        still owned.

        WHY A SNAPSHOT (measured 2026-08-05). The all-or-nothing form — "satisfied
        iff `bank_drain_excess` is empty" — is UNREACHABLE for any pile deeper
        than the bag (2273 licensed copies against a 120-quantity bag), so the
        goal could never plan. WHY THE OWNED TOTAL (2026-09-30): the bank-side
        total fell on the withdraw alone, so the plan ended with the junk in the
        bag, where nothing shed it before the deposit guard banked it again."""
        return (not self._snapshot.codes
                or owned_total(state, self._snapshot.codes) < self._snapshot.owned)

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"bank_junk_drained": True}

    def relevant_actions(
        self, actions: list[Action], state: WorldState, game_data: GameData,
    ) -> list[Action]:
        """Per over-cap bank code, one WithdrawItemAction and the actions that
        shed what the bag may then shed (`shed_actions` for the discard
        guard's licence, `min(bankable, destroyable)`, evaluated on the state
        after the withdraw).

        The withdraw MINTS the items into the bag, so its quantity is the largest
        that is applicable (free space, server HTTP 497) AND leaves the bag below
        `DEPOSIT_FULL_FRACTION` (`guards.used_fraction`), so the deposit guard
        does not bank the junk before its shed runs. The remainder drains on a
        later episode.

        THE PER-EPISODE BOUND (part 2, 2026-08-05): ONE withdraw per episode,
        batched by quantity, keeps the drain rate-neutral against the per-IP
        action budget (`utils/rate_budget.WindowBudget.sustainable_interval`);
        the shed is the one request that makes the episode count.
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
                if not action.is_applicable(state, game_data):
                    continue
                after = action.apply(state, game_data)
                if used_fraction(after) >= DEPOSIT_FULL_FRACTION:
                    continue
                result.append(action)
                # What the bag may shed once the withdraw lands: the discard
                # guard's own licence, `min(bankable, destroyable)`, read after
                # it. So neither authority is crossed: no copy the bag keeps (a
                # heal) and none the character must own is shed, whether it is
                # a withdrawn copy or one already held.
                shed = min(bankable(code, after, game_data, self._ctx),
                           destroyable(code, after, game_data, self._ctx))
                if shed > 0:
                    result.extend(shed_actions(code, shed, after, game_data, self._ctx,
                                               self._accessible))
                break
        return result

    def __repr__(self) -> str:
        return "DrainBankJunk"
