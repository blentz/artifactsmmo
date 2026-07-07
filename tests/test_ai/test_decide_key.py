"""Dispatcher-exhaustiveness round-trip for `decide_key.py`.

Every `GuardKind` / `MeansKind` variant must map to a non-empty repr —
the Python read-back of the Lean total-`match` guarantee in
`formal/Formal/DecideKey.lean` (`goalReprOfGuard` / `goalReprOfMeans`).
A new enum variant added without a table entry raises `KeyError` here.
"""
import pytest

from artifactsmmo_cli.ai.tiers.decide_key import (
    goal_repr_of_guard,
    goal_repr_of_means,
)
from artifactsmmo_cli.ai.tiers.guards import GuardKind
from artifactsmmo_cli.ai.tiers.means import MeansKind


class TestDispatcherExhaustiveness:
    @pytest.mark.parametrize("kind", list(GuardKind))
    def test_every_guard_has_nonempty_repr(self, kind: GuardKind) -> None:
        r = goal_repr_of_guard(kind)
        assert isinstance(r, str) and r

    @pytest.mark.parametrize("kind", list(MeansKind))
    def test_every_means_has_nonempty_repr(self, kind: MeansKind) -> None:
        r = goal_repr_of_means(kind)
        assert isinstance(r, str) and r
