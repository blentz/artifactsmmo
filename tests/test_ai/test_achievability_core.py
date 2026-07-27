from fractions import Fraction

from artifactsmmo_cli.ai.tiers.achievability_core import (
    A_MIN,
    EFFORT_SCALE,
    achievability_pure,
)
from artifactsmmo_cli.ai.tiers.synergy_core import S_MIN


def test_the_cheapest_candidate_is_unpenalised():
    assert achievability_pure(effort=18, min_effort=18) == Fraction(1)


def test_a_far_costlier_candidate_approaches_the_floor():
    a = achievability_pure(effort=10_000, min_effort=18)
    assert A_MIN < a < Fraction(3, 5)


def test_never_below_the_floor():
    assert achievability_pure(effort=10**9, min_effort=0) >= A_MIN


def test_never_above_one():
    assert achievability_pure(effort=0, min_effort=99) <= Fraction(1)


def test_antitone_in_effort():
    """More effort scores no higher — the defining property."""
    prev = Fraction(2)
    for effort in range(0, 2000, 71):
        cur = achievability_pure(effort, min_effort=5)
        assert cur <= prev
        prev = cur


def test_the_floor_is_strictly_positive():
    """d'Hondt must still award a seat eventually (minWeight_pos)."""
    assert A_MIN > 0


def test_the_range_sits_inside_synergy():
    """Hierarchy: falloff 9:1 > synergy 3:1 > achievability 2:1."""
    assert Fraction(1) / A_MIN < Fraction(1) / S_MIN


def test_a_free_candidate_does_not_collapse_the_others():
    """THE REGRESSION THE SCALE CONSTANT EXISTS FOR (live 2026-07-27).

    Effort is unbounded BELOW: a utility potion costs ~0 unmet units and appears
    in most real decisions. With a scale of 1, that dragged `min_effort` to 0 and
    pulled every other candidate onto the floor TOGETHER — the spread collapsed
    to 1.03:1, which could not overcome the 1.19:1 gain gap this factor exists to
    overcome, so raw gain took the ordering back and the 1000-ticket trophy
    returned to the top. Seen in Robby's trace: cycle 0 picked adventurer_pants,
    cycle 2 gained a potion candidate and reverted.

    The scale keeps the two apart even when the reference is 0.
    """
    near = achievability_pure(effort=32, min_effort=0)     # craftable
    far = achievability_pure(effort=1000, min_effort=0)    # 1000-ticket chain
    assert near / far >= Fraction(119, 100), "spread cannot overturn the gain gap"
    assert 21020 * near > 25050 * far, "raw gain would still win"


def test_the_scale_is_what_separates_them():
    """Falsifiability for the constant itself: at a scale of 1 — the value that
    shipped and self-disabled — the SAME two candidates collapse together and
    raw gain wins. If this ever stops failing, the constant has stopped mattering
    and the test above is passing for some other reason."""
    def at_scale(effort: int, min_effort: int, scale: int) -> Fraction:
        return A_MIN + (Fraction(1) - A_MIN) * Fraction(min_effort + scale, effort + scale)

    near_1, far_1 = at_scale(32, 0, 1), at_scale(1000, 0, 1)
    assert 21020 * near_1 < 25050 * far_1, "scale 1 should collapse, it is the bug"

    near_k, far_k = at_scale(32, 0, EFFORT_SCALE), at_scale(1000, 0, EFFORT_SCALE)
    assert 21020 * near_k > 25050 * far_k
