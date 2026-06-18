"""Unit tests for the pure strategy-blend and decide-key cores.

These pin the property contracts the Lean proofs lock:
* `balancing` clamp bounds and the threshold identity (leader-current=2 ⇒ 1.0).
* `blend_weight` warm-up zero and the [0, 0.5] cap.
* `learned_blend` convex bound and warm-up identity.
* `goal_repr_of_guard` / `goal_repr_of_means` exhaustiveness across every
  enum variant.
"""
import pytest

from artifactsmmo_cli.ai.tiers.decide_key import (
    decide_key,
    goal_repr_of_guard,
    goal_repr_of_means,
)
from artifactsmmo_cli.ai.tiers.guards import GuardKind
from artifactsmmo_cli.ai.tiers.means import MeansKind
from artifactsmmo_cli.ai.tiers.strategy_blend import (
    BALANCE_MAX,
    BALANCE_MIN,
    LEARN_SAMPLE_FULL,
    LEARN_W_MAX,
    balancing,
    blend_weight,
    learned_blend,
)


class TestBalancing:
    def test_threshold_identity(self) -> None:
        """At leader - current = BALANCE_THRESHOLD (= 2), multiplier = 1.0."""
        assert balancing(leader=5, current=3) == 1.0
        assert balancing(leader=10, current=8) == 1.0

    def test_above_threshold_amplifies(self) -> None:
        # leader - current = 4, raw = 1 + 0.25 * (4 - 2) = 1.5
        assert balancing(leader=5, current=1) == pytest.approx(1.5)

    def test_clamp_upper(self) -> None:
        """Arbitrarily large gap clamps at BALANCE_MAX (2.0)."""
        assert balancing(leader=100, current=0) == BALANCE_MAX

    def test_clamp_lower(self) -> None:
        """leader = current ⇒ raw = 0.5, clamped at BALANCE_MIN (0.5)."""
        assert balancing(leader=3, current=3) == BALANCE_MIN

    def test_leader_below_current_clamps(self) -> None:
        """leader < current ⇒ raw < 0.5 ⇒ clamp at floor."""
        assert balancing(leader=0, current=10) == BALANCE_MIN


class TestBlendWeight:
    def test_zero_samples_is_zero(self) -> None:
        assert blend_weight(0) == 0.0

    def test_negative_samples_is_zero(self) -> None:
        """Defensive: a corrupted negative sample_count still returns 0."""
        assert blend_weight(-3) == 0.0

    def test_ramp(self) -> None:
        # half-way: 10 / 20 = 0.5 ⇒ w = 0.5 * 0.5 = 0.25
        assert blend_weight(10) == pytest.approx(0.25)

    def test_full_caps(self) -> None:
        assert blend_weight(LEARN_SAMPLE_FULL) == LEARN_W_MAX
        assert blend_weight(LEARN_SAMPLE_FULL * 100) == LEARN_W_MAX


class TestLearnedBlend:
    def test_w_zero_is_identity(self) -> None:
        assert learned_blend(value=0.42, normalized=0.99, w=0.0) == 0.42

    def test_w_one_is_normalized(self) -> None:
        assert learned_blend(value=0.42, normalized=0.99, w=1.0) == 0.99

    def test_convex_bound(self) -> None:
        v, n = 0.3, 0.8
        for w_int in range(0, 11):
            w = w_int / 10.0
            out = learned_blend(v, n, w)
            assert min(v, n) - 1e-12 <= out <= max(v, n) + 1e-12

    def test_monotone_in_normalized(self) -> None:
        """Given w > 0, raising normalized never decreases the blend."""
        for w_int in range(1, 6):
            w = w_int / 10.0
            assert learned_blend(0.3, 0.2, w) <= learned_blend(0.3, 0.7, w)


class TestDecideKey:
    def test_tuple_shape(self) -> None:
        assert decide_key(-0.9, 5, -3, "X") == (-0.9, 5, -3, "X")

    def test_sort_order_final_then_effort_then_protection_then_repr(self) -> None:
        items = [
            (-0.5, 3, 0, "B"),
            (-0.9, 5, 0, "A"),
            (-0.5, 2, 0, "Z"),
            (-0.5, 3, 0, "A"),
            (-0.5, 3, -9, "Y"),  # same (final, effort) as the -0.5/3 group; protection wins
        ]
        items.sort(key=lambda t: decide_key(*t))
        # -0.9 wins; then ties at -0.5 break by effort, then by protection
        # (more-negative negProtect = higher gear value first), then by repr.
        assert items[0] == (-0.9, 5, 0, "A")
        assert items[1] == (-0.5, 2, 0, "Z")
        assert items[2] == (-0.5, 3, -9, "Y")
        assert items[3] == (-0.5, 3, 0, "A")
        assert items[4] == (-0.5, 3, 0, "B")


class TestDispatcherExhaustiveness:
    @pytest.mark.parametrize("kind", list(GuardKind))
    def test_every_guard_has_nonempty_repr(self, kind: GuardKind) -> None:
        r = goal_repr_of_guard(kind)
        assert isinstance(r, str) and r

    @pytest.mark.parametrize("kind", list(MeansKind))
    def test_every_means_has_nonempty_repr(self, kind: MeansKind) -> None:
        r = goal_repr_of_means(kind)
        assert isinstance(r, str) and r
