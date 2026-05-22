from artifactsmmo_cli.ai.tiers.objective import ObjectiveGap
from artifactsmmo_cli.ai.tiers.personality import BalancedPersonality, weighted_remaining


def _gap(cl=0.0, sk=0.0, gr=0.0) -> ObjectiveGap:
    return ObjectiveGap(char_level_gap=0, skill_gaps={}, gear_gaps={},
                        char_level_fraction=cl, skills_fraction=sk, gear_fraction=gr)


def test_balanced_weights_all_one():
    p = BalancedPersonality()
    for c in ("char_level", "skills", "gear"):
        assert p.category_weight(c) == 1.0


def test_balanced_unknown_category_is_one():
    assert BalancedPersonality().category_weight("mystery") == 1.0


def test_weighted_remaining_zero_when_complete():
    assert weighted_remaining(_gap(), BalancedPersonality()) == 0.0


def test_weighted_remaining_sums_fractions_under_balanced():
    g = _gap(cl=0.2, sk=0.5, gr=0.1)
    assert weighted_remaining(g, BalancedPersonality()) == 0.8


def test_weighted_remaining_grows_with_gaps():
    p = BalancedPersonality()
    assert weighted_remaining(_gap(cl=0.1), p) < weighted_remaining(_gap(cl=0.9), p)
