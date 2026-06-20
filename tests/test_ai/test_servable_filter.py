"""Servable-filter: keep only roots whose actionable step is plannable now.

Pure-core tests for keep_servable + a decide()-level test that a top-scored root
with an UNSERVABLE step is demoted so chosen_root is a root the bot can actually
work on (the feather_coat mismatch fix, trace 2026-06-20).
"""

from artifactsmmo_cli.ai.tiers.meta_goal import MetaGoal
from artifactsmmo_cli.ai.tiers.servable_filter import keep_servable
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_tiers_strategy import TestStickyCommitment, _eng


class TestKeepServable:
    def test_keeps_only_servable_when_some_servable(self):
        assert keep_servable(["a", "b", "c"], [False, True, False]) == ["b"]

    def test_keeps_all_when_none_servable(self):
        # Graceful fallback: no servable root -> keep everyone (arbiter still walks).
        assert keep_servable(["a", "b"], [False, False]) == ["a", "b"]

    def test_keeps_all_when_all_servable(self):
        assert keep_servable(["a", "b"], [True, True]) == ["a", "b"]

    def test_empty(self):
        assert keep_servable([], []) == []

    def test_length_mismatch_raises(self):
        import pytest
        with pytest.raises(ValueError, match="equal length"):
            keep_servable(["a"], [True, False])


class TestDecideServableFilter:
    """decide() demotes a top-scored root whose step is unservable."""

    def test_unservable_top_root_is_demoted(self):
        gd = TestStickyCommitment()._two_root_gd()
        eng = _eng(gd)
        state = make_state(level=5)
        baseline = eng.decide(state, gd)
        top_repr = repr(baseline.chosen_root)
        # Build a step_servable that marks the natural top root UNSERVABLE and
        # everything else servable.
        def servable(root: MetaGoal, _step: MetaGoal) -> bool:
            return repr(root) != top_repr
        filtered = eng.decide(state, gd, step_servable=servable)
        assert repr(filtered.chosen_root) != top_repr, (
            "top root with unservable step must be demoted")

    def test_all_unservable_keeps_natural_top(self):
        gd = TestStickyCommitment()._two_root_gd()
        eng = _eng(gd)
        state = make_state(level=5)
        baseline = eng.decide(state, gd)
        # Nothing servable -> graceful fallback to the natural ranking.
        filtered = eng.decide(state, gd, step_servable=lambda r, s: False)
        assert repr(filtered.chosen_root) == repr(baseline.chosen_root)

    def test_none_predicate_is_unfiltered(self):
        gd = TestStickyCommitment()._two_root_gd()
        eng = _eng(gd)
        state = make_state(level=5)
        assert repr(eng.decide(state, gd, step_servable=None).chosen_root) == repr(
            eng.decide(state, gd).chosen_root)
