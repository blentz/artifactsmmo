"""Wave 2 of the synergy-weighting epic: the pure synergy core.

`synergy_pure(shared, total)` is an affine map of a normalised overlap ratio
into `[S_MIN, 1]`, exact `Fraction`, no float in the decision path (design spec
§3), read by the taskmaster choice and the means-worth gate. These tests pin
the bounds, the degenerate case and the assert-not-clamp contract.
"""

from fractions import Fraction

import pytest

from artifactsmmo_cli.ai.tiers.synergy_core import (
    S_MIN,
    TOP_QUANTILE,
    expected_pool_synergy,
    synergy_pure,
)


def test_synergy_core_bounds():
    """`S_MIN <= synergy <= 1` over a swept (shared, total) grid, and the two
    extremes are exactly S_MIN (no overlap) and 1 (full overlap)."""
    for total in range(1, 25):
        for shared in range(0, total + 1):
            s = synergy_pure(shared, total)
            assert S_MIN <= s <= Fraction(1)
    assert synergy_pure(0, 7) == S_MIN            # zero overlap -> floor
    # The floor's VALUE, not only its name: `Formal/Synergy.lean`'s `sMin` is
    # `mkRat 1 3`, and `means_worth` thresholds at it.
    assert Fraction(1, 3) == S_MIN
    assert synergy_pure(7, 7) == Fraction(1)      # full overlap -> ceiling


def test_synergy_total_zero():
    """`synergy(s, 0) == 1` for all s: a candidate that needs nothing is
    maximally aligned (§3.4), not a division by zero. Proven, not commented."""
    for shared in range(0, 10):
        assert synergy_pure(shared, 0) == Fraction(1)
    assert synergy_pure(0, -3) == Fraction(1)     # total <= 0 guard, not just == 0


def test_synergy_asserts_shared_gt_total():
    """`shared > total` is impossible by construction (an intersection cannot
    exceed the set it is drawn from). The core ASSERTS rather than clamping: a
    violation means the assembly layer is wrong and must fail loudly (§3, Phase 2)."""
    with pytest.raises(AssertionError):
        synergy_pure(8, 7)


# --- Wave 4: reroll-aware pool synergy for taskmaster choice (spec §4.3) ---


def test_pool_synergy_single_is_that_value():
    assert expected_pool_synergy([Fraction(2, 5)]) == Fraction(2, 5)


def test_pool_synergy_is_mean_of_top_third():
    """k = ceil(n * 1/3); the mean is over the k HIGHEST synergies. Nine tasks →
    top three."""
    pool = [Fraction(i, 10) for i in range(1, 10)]   # 0.1 .. 0.9, n=9
    # top 3 = 0.9, 0.8, 0.7 -> mean 0.8
    assert expected_pool_synergy(pool) == Fraction(8, 10)


def test_pool_synergy_k_is_at_least_one():
    """A two-task pool still takes ceil(2/3)=1 — the single best draw, never
    zero (an empty slice would divide by zero)."""
    assert expected_pool_synergy([Fraction(1, 3), Fraction(1)]) == Fraction(1)


def test_pool_synergy_ceil_rounds_the_slice_up():
    """k rounds UP: four tasks take ceil(4/3)=2 (the top two), not floor=1. Pins
    ceil against a floor mutant."""
    pool = [Fraction(1, 10), Fraction(2, 10), Fraction(3, 10), Fraction(4, 10)]
    # top 2 = 0.4, 0.3 -> mean 0.35 (floor would give just 0.4)
    assert expected_pool_synergy(pool) == Fraction(35, 100)


def test_pool_synergy_is_reroll_aware():
    """The whole point: a master with one strong draw and many useless ones is
    valued by its GOOD draws (a bad draw is a cheap cancel), so its expected
    synergy beats the washed-out plain mean."""
    pool = [Fraction(1)] + [S_MIN] * 8               # one great, eight floor
    plain_mean = sum(pool, Fraction(0)) / len(pool)
    assert expected_pool_synergy(pool) > plain_mean


def test_pool_synergy_is_exact_fraction():
    result = expected_pool_synergy([Fraction(1, 3), Fraction(1, 7), Fraction(1)])
    assert isinstance(result, Fraction)              # no float in the decision path


def test_pool_synergy_empty_asserts():
    """An empty pool has no expected synergy — the impure caller must exclude a
    master with no tasks BEFORE calling, so this asserts rather than inventing a
    value."""
    with pytest.raises(AssertionError):
        expected_pool_synergy([])


def test_top_quantile_is_one_third():
    assert Fraction(1, 3) == TOP_QUANTILE
