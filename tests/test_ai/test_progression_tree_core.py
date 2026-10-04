"""Pure cores of the progression-tree selector (spec 2026-07-06).

Mirrored by Formal/ProgressionTree.lean; the PROGRESSION_TREE_MUTATIONS
group binds these tests to the source.

WAVE 3b: the resolution walk replaced the scored ranking, and with it the whole
gear-argmax/aging family (`branch_pick_pure`, `gear_target_pick`,
`_gear_pref_key`, `_scaled_pref_key`, `_scaled_weights`, `focus_aging_pick`,
`focus_aging_order`, `interleave_due`, `_NO_SYNERGY`/`_NO_ACHIEVABILITY`/
`_NO_ROLE`) left the module — see the re-derived deletion list §4/§5. What
remains here is what `ai/decisions/root.py` actually calls: `milestone_pure`,
`potion_type_weight`, and the `GearCandidate` record
`tiers/progression_tree.py` still assembles. Phase 4-2b-ii deleted `falloff`,
`run_falloff` and `dhondt_step`: the intention's cycle budget and one-turn yield
replaced the aging they scheduled."""

from dataclasses import fields
from fractions import Fraction

from artifactsmmo_cli.ai.tiers.progression_tree_core import (
    POTION_TYPE_WEIGHTS,
    GearCandidate,
    milestone_pure,
    potion_type_weight,
)


class TestMilestone:
    def test_next_band_boundary(self):
        assert milestone_pure(1) == 10
        assert milestone_pure(9) == 10
        assert milestone_pure(10) == 20
        assert milestone_pure(11) == 20
        assert milestone_pure(39) == 40
        assert milestone_pure(49) == 50

    def test_capped_at_fifty(self):
        assert milestone_pure(50) == 50
        assert milestone_pure(55) == 50

    def test_strictly_above_level_below_cap(self):
        for level in range(1, 50):
            m = milestone_pure(level)
            assert level < m <= 50


class TestPotionWeights:
    def test_health_is_maximal(self):
        assert all(POTION_TYPE_WEIGHTS["hp_restore"] >= w
                   for w in POTION_TYPE_WEIGHTS.values())

    def test_lookup_and_unknown(self):
        assert potion_type_weight("hp_restore") == Fraction(1)
        assert potion_type_weight("charm_of_unmodeled") == Fraction(0)

    def test_all_weights_exact_nonnegative(self):
        for w in POTION_TYPE_WEIGHTS.values():
            assert isinstance(w, Fraction) and w >= 0


def test_modulating_weights_absent_from_gear_candidate_identity():
    """A modulating weight is never candidate identity — it must not enter
    GearCandidate's fields or its repr (the currency-grind lesson: a moving
    value inside identity resets sticky keying). Structurally excluded."""
    names = {f.name for f in fields(GearCandidate)}
    assert names == {"slot", "code", "gain", "level"}
    # two candidates equal but for a weighting context have identical repr
    a = GearCandidate(slot="s", code="c", gain=Fraction(5), level=1)
    b = GearCandidate(slot="s", code="c", gain=Fraction(5), level=1)
    assert repr(a) == repr(b)


