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
from artifactsmmo_cli.ai.tiers.means import DISCRETIONARY_ORDER, MeansKind


class TestDispatcherExhaustiveness:
    @pytest.mark.parametrize("kind", list(GuardKind))
    def test_every_guard_has_nonempty_repr(self, kind: GuardKind) -> None:
        r = goal_repr_of_guard(kind)
        assert isinstance(r, str) and r

    @pytest.mark.parametrize("kind", list(MeansKind))
    def test_every_means_has_nonempty_repr(self, kind: MeansKind) -> None:
        r = goal_repr_of_means(kind)
        assert isinstance(r, str) and r


def test_supply_bank_is_the_last_enum_variant() -> None:
    assert list(MeansKind)[-1] is MeansKind.SUPPLY_BANK


def test_supply_bank_has_a_dispatch_repr() -> None:
    assert _MEANS_REPR[MeansKind.SUPPLY_BANK] == "SupplyBank"


def test_supply_bank_sits_between_consumables_and_idle_selling() -> None:
    order = list(DISCRETIONARY_ORDER)
    assert (order.index(MeansKind.MAINTAIN_CONSUMABLES)
            < order.index(MeansKind.SUPPLY_BANK)
            < order.index(MeansKind.SELL_IDLE))
