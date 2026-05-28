"""Coverage of the pure low-yield-cancel boundary.

These tests pin down the exact semantics modelled in Lean
(`formal/Formal/LowYieldCancel.lean`):

  * no-task / no-sample short-circuits,
  * zero-fast-path INTENTIONALLY bypasses the confidence gate (single alt
    sample, near-zero confidence — verified against the production design
    documented in `TestGHCharXpFastCancel`),
  * margin gate with the production constants 0.5 / 1.5.
"""
from artifactsmmo_cli.ai.learning.low_yield_boundary import low_yield_fires_pure


class TestNoTask:
    def test_no_task_never_fires(self) -> None:
        # Even with all other gates clearly passed, no task ⇒ no fire.
        assert (
            low_yield_fires_pure(
                has_task=False,
                current_xp=1.0,
                alt_xp=100.0,
                confidence=1.0,
                farm_samples=10,
                alt_samples=10,
            )
            is False
        )


class TestSampleGate:
    def test_zero_farm_samples_never_fires(self) -> None:
        assert (
            low_yield_fires_pure(
                has_task=True,
                current_xp=0.0,
                alt_xp=100.0,
                confidence=1.0,
                farm_samples=0,
                alt_samples=10,
            )
            is False
        )

    def test_zero_alt_samples_never_fires(self) -> None:
        assert (
            low_yield_fires_pure(
                has_task=True,
                current_xp=0.0,
                alt_xp=100.0,
                confidence=1.0,
                farm_samples=10,
                alt_samples=0,
            )
            is False
        )


class TestZeroFastPath:
    """Pinning the INTENDED bypass behaviour (Robby gudgeon scenario)."""

    def test_zero_current_with_positive_alt_fires_even_at_low_confidence(self) -> None:
        # Single alt sample, confidence below the 0.5 gate — still fires because
        # current_xp == 0 makes zero unimprovable. This is INTENDED.
        assert (
            low_yield_fires_pure(
                has_task=True,
                current_xp=0.0,
                alt_xp=0.01,
                confidence=0.0,
                farm_samples=1,
                alt_samples=1,
            )
            is True
        )

    def test_zero_current_zero_alt_low_confidence_does_not_fire(self) -> None:
        # Fast-path needs alt_xp > 0; margin gate needs confidence ≥ 0.5. Neither holds.
        assert (
            low_yield_fires_pure(
                has_task=True,
                current_xp=0.0,
                alt_xp=0.0,
                confidence=0.0,
                farm_samples=5,
                alt_samples=5,
            )
            is False
        )

    def test_zero_current_zero_alt_high_confidence_fires_trivially(self) -> None:
        # Production reality: fast-path skipped (alt_xp not > 0), but the margin
        # check `0 ≥ 0 * 1.5` holds trivially under confidence ≥ 0.5. This is
        # an edge of the proved spec, not a bug — both rates equal zero so
        # cancellation is meaningless either way (no info, but spec-compliant).
        assert (
            low_yield_fires_pure(
                has_task=True,
                current_xp=0.0,
                alt_xp=0.0,
                confidence=1.0,
                farm_samples=5,
                alt_samples=5,
            )
            is True
        )


class TestMarginGate:
    def test_below_confidence_threshold_does_not_fire(self) -> None:
        # Current > 0 so zero-fast-path doesn't trigger. confidence < 0.5 blocks.
        assert (
            low_yield_fires_pure(
                has_task=True,
                current_xp=1.0,
                alt_xp=100.0,
                confidence=0.49,
                farm_samples=10,
                alt_samples=10,
            )
            is False
        )

    def test_at_confidence_boundary_fires_when_margin_met(self) -> None:
        # confidence == 0.5 is at the gate (>=) — should fire.
        assert (
            low_yield_fires_pure(
                has_task=True,
                current_xp=1.0,
                alt_xp=1.5,
                confidence=0.5,
                farm_samples=10,
                alt_samples=10,
            )
            is True
        )

    def test_below_margin_does_not_fire(self) -> None:
        assert (
            low_yield_fires_pure(
                has_task=True,
                current_xp=1.0,
                alt_xp=1.49,
                confidence=1.0,
                farm_samples=10,
                alt_samples=10,
            )
            is False
        )

    def test_at_margin_boundary_fires(self) -> None:
        assert (
            low_yield_fires_pure(
                has_task=True,
                current_xp=2.0,
                alt_xp=3.0,
                confidence=1.0,
                farm_samples=10,
                alt_samples=10,
            )
            is True
        )

    def test_custom_margin_and_threshold_respected(self) -> None:
        # margin=2.0, min_confidence=0.8 — 1.99 < 2.0 ⇒ no fire even with high confidence.
        assert (
            low_yield_fires_pure(
                has_task=True,
                current_xp=1.0,
                alt_xp=1.99,
                confidence=1.0,
                farm_samples=10,
                alt_samples=10,
                margin=2.0,
                min_confidence=0.8,
            )
            is False
        )
