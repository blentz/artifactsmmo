"""Dispatcher-exhaustiveness round-trip for `decide_key.py`.

Every `GuardKind` / `MeansKind` variant must map to a non-empty repr —
the Python read-back of the Lean total-`match` guarantee in
`formal/Formal/DecideKey.lean` (`goalReprOfGuard` / `goalReprOfMeans`).
A new enum variant added without a table entry raises `KeyError` here.
"""
import pytest

from artifactsmmo_cli.ai.tiers.decide_key import (
    _MEANS_REPR,
    goal_repr_of_guard,
    goal_repr_of_means,
)
from artifactsmmo_cli.ai.tiers.guards import GuardKind
from artifactsmmo_cli.ai.tiers.means import (
    COLLECT_REWARD_ORDER,
    DISCRETIONARY_ORDER,
    MeansKind,
)


class TestDispatcherExhaustiveness:
    @pytest.mark.parametrize("kind", list(GuardKind))
    def test_every_guard_has_nonempty_repr(self, kind: GuardKind) -> None:
        r = goal_repr_of_guard(kind)
        assert isinstance(r, str) and r

    @pytest.mark.parametrize("kind", list(MeansKind))
    def test_every_means_has_nonempty_repr(self, kind: MeansKind) -> None:
        r = goal_repr_of_means(kind)
        assert isinstance(r, str) and r


def test_currency_turnin_is_the_last_enum_variant() -> None:
    """2026-08-16, fleet-currency-turn-in Task 6: CURRENCY_TURNIN is appended
    LAST, after SUPPLY_BANK (which held this spot from 2026-08-01 until now) —
    enum identity must stay stable for the DecideKey oracle, so new variants
    only ever append."""
    assert list(MeansKind)[-1] is MeansKind.CURRENCY_TURNIN


def test_supply_bank_has_a_dispatch_repr() -> None:
    assert _MEANS_REPR[MeansKind.SUPPLY_BANK] == "SupplyBank"


def test_currency_turnin_has_a_dispatch_repr() -> None:
    assert _MEANS_REPR[MeansKind.CURRENCY_TURNIN] == "CurrencyTurnIn"


def test_currency_turnin_is_last_in_the_collect_reward_band() -> None:
    """2026-08-16 Task 6: CURRENCY_TURNIN is slotted into COLLECT_REWARD_ORDER
    immediately after SUPPLY_BANK — same band, same reasoning (see
    tiers/means.py's comment on both): ABOVE the objective step so a resolved
    fleet election is not left to rot behind whatever gear `J` is chasing, and
    LAST among the collect-reward rungs so it never parks a pending reward
    claim or a >=85%-full bag behind it."""
    assert MeansKind.CURRENCY_TURNIN not in DISCRETIONARY_ORDER
    assert (COLLECT_REWARD_ORDER.index(MeansKind.SUPPLY_BANK)
            < COLLECT_REWARD_ORDER.index(MeansKind.CURRENCY_TURNIN))
    # 2026-08-19 (S-051): ACCEPT_TASK joined this band and took the last slot.
    # The property that matters is unchanged and is asserted directly — the
    # turn-in still sits behind nothing open-ended. A one-action draw is not
    # something a resolved election can rot behind, and putting the accept
    # BEFORE the turn-in did preempt it (caught by test_turn_in_scenario).
    assert COLLECT_REWARD_ORDER[-1] is MeansKind.ACCEPT_TASK
    assert (COLLECT_REWARD_ORDER.index(MeansKind.CURRENCY_TURNIN)
            < COLLECT_REWARD_ORDER.index(MeansKind.ACCEPT_TASK))
    for cheap in (MeansKind.CLAIM_PENDING, MeansKind.COMPLETE_TASK,
                  MeansKind.SELL_PRESSURED, MeansKind.LOW_YIELD_CANCEL,
                  MeansKind.TASK_CANCEL):
        assert (COLLECT_REWARD_ORDER.index(cheap)
                < COLLECT_REWARD_ORDER.index(MeansKind.CURRENCY_TURNIN))
