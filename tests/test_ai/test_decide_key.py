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


def test_the_retired_fleet_rungs_are_no_means() -> None:
    """Phase 5-2c-iv: SUPPLY_BANK and CURRENCY_TURNIN left the ladder for the
    fleet objective (`ReachFleetOutcome`), so neither value names a means and
    no dispatch repr remains for them."""
    values = {kind.value for kind in MeansKind}
    assert "supply_bank" not in values and "currency_turnin" not in values
    assert set(_MEANS_REPR) == set(MeansKind)
    assert set(COLLECT_REWARD_ORDER) | set(DISCRETIONARY_ORDER) <= set(MeansKind)
