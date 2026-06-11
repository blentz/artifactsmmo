from fractions import Fraction

from artifactsmmo_cli.ai.tiers.objective import ObjectiveGap
from artifactsmmo_cli.ai.tiers.personality import BalancedPersonality, weighted_remaining

# P4a: ObjectiveGap fractions and personality weights are exact Fractions;
# the weighted scalar is exact — equalities below are exact, no approx.
_ZERO = Fraction(0)


def _gap(cl=_ZERO, sk=_ZERO, gr=_ZERO) -> ObjectiveGap:
    return ObjectiveGap(char_level_gap=0, skill_gaps={}, gear_gaps={},
                        char_level_fraction=cl, skills_fraction=sk, gear_fraction=gr)


def test_balanced_weights_all_one():
    p = BalancedPersonality()
    for c in ("char_level", "skills", "gear"):
        assert p.category_weight(c) == Fraction(1)


def test_balanced_unknown_category_is_one():
    assert BalancedPersonality().category_weight("mystery") == Fraction(1)


def test_weighted_remaining_zero_when_complete():
    assert weighted_remaining(_gap(), BalancedPersonality()) == 0


def test_weighted_remaining_sums_fractions_under_balanced():
    g = _gap(cl=Fraction(1, 5), sk=Fraction(1, 2), gr=Fraction(1, 10))
    # Exact rational sum — the float-era pytest.approx tolerance is gone (P4a).
    assert weighted_remaining(g, BalancedPersonality()) == Fraction(4, 5)


def test_weighted_remaining_grows_with_gaps():
    p = BalancedPersonality()
    assert weighted_remaining(_gap(cl=Fraction(1, 10)), p) < weighted_remaining(_gap(cl=Fraction(9, 10)), p)
