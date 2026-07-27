from fractions import Fraction

from artifactsmmo_cli.ai.tiers.achievability_core import A_MIN, achievability_pure
from artifactsmmo_cli.ai.tiers.synergy_core import S_MIN


def test_the_cheapest_candidate_is_unpenalised():
    assert achievability_pure(effort=18, min_effort=18) == Fraction(1)


def test_effort_is_relative_not_absolute():
    """Self-scaling: only the RATIO matters, so no absolute effort constant."""
    assert achievability_pure(9, 4) == achievability_pure(19, 9)


def test_a_far_costlier_candidate_approaches_the_floor():
    a = achievability_pure(effort=1000, min_effort=18)
    assert A_MIN < a < Fraction(3, 5)


def test_never_below_the_floor():
    assert achievability_pure(effort=10**9, min_effort=0) >= A_MIN


def test_never_above_one():
    assert achievability_pure(effort=0, min_effort=99) <= Fraction(1)


def test_antitone_in_effort():
    """More effort scores no higher — the defining property."""
    prev = Fraction(2)
    for effort in range(0, 200, 7):
        cur = achievability_pure(effort, min_effort=5)
        assert cur <= prev
        prev = cur


def test_the_floor_is_strictly_positive():
    """d'Hondt must still award a seat eventually (minWeight_pos)."""
    assert A_MIN > 0


def test_the_range_sits_inside_synergy():
    """Hierarchy: falloff 9:1 > synergy 3:1 > achievability 2:1."""
    assert Fraction(1) / A_MIN < Fraction(1) / S_MIN
