"""Wave 2 of the synergy-weighting epic: the pure synergy core.

`synergy_pure(shared, total)` is the third modulating factor in
`weight = gain * falloff(focus) * synergy` (design spec §3). It is a scalar
twin of `falloff`: an affine map of a normalised ratio into `[S_MIN, 1]`,
exact `Fraction`, no float in the decision path. These tests pin the bounds,
the degenerate case, the assert-not-clamp contract, and — load-bearing — the
§3.5 invariant that synergy's dynamic range stays strictly inside `falloff`'s
so aging always dominates alignment.
"""

from fractions import Fraction

import pytest

from artifactsmmo_cli.ai.tiers.progression_tree_core import FOCUS_FLOOR, falloff
from artifactsmmo_cli.ai.tiers.synergy_core import S_MIN, synergy_pure


def test_synergy_core_bounds():
    """`S_MIN <= synergy <= 1` over a swept (shared, total) grid, and the two
    extremes are exactly S_MIN (no overlap) and 1 (full overlap)."""
    for total in range(1, 25):
        for shared in range(0, total + 1):
            s = synergy_pure(shared, total)
            assert S_MIN <= s <= Fraction(1)
    assert synergy_pure(0, 7) == S_MIN            # zero overlap -> floor
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


def test_synergy_range_inside_falloff():
    """The §3.5 anti-starvation invariant, as arithmetic over the REAL constants:
    synergy's dynamic range (S_MAX/S_MIN = 3) must stay strictly inside falloff's
    (FOCUS_1/FOCUS_FLOOR = 9), so aging structurally dominates alignment and a
    high-synergy stuck root still decays. Retuning either constant trips this."""
    s_max = synergy_pure(1, 1)                     # ceiling of the synergy curve
    focus_1 = falloff(0)                           # flat-top of the falloff curve
    assert s_max / S_MIN < focus_1 / FOCUS_FLOOR
