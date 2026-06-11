"""Unit tests for the P3c exact-Fraction cycles_for_progress core.

Deterministic pins for every branch of the exact core (the Hypothesis
differential suite in formal/diff covers the same ground statistically
against the Lean oracle; these are the fast, always-on unit pins)."""

from fractions import Fraction

from artifactsmmo_cli.ai.learning.cycles_for_progress_core import (
    CycleRow,
    _median_exact,
    cycles_for_progress_exact,
    cycles_for_progress_pure,
)


def _rows(chrono: list[CycleRow]) -> list[CycleRow]:
    """Chronological -> newest-first (the LearningStore convention)."""
    return list(reversed(chrono))


class TestExactCore:
    def test_empty_rows_return_none(self):
        assert cycles_for_progress_exact([], 1) is None
        assert cycles_for_progress_pure([], 1) is None

    def test_below_warmup_returns_none(self):
        rows = _rows([
            CycleRow(0, 0, None),
            CycleRow(1, 1, None),
        ])
        assert cycles_for_progress_exact(rows, 5) is None
        assert cycles_for_progress_pure(rows, 5) is None

    def test_odd_interval_count_returns_middle_element(self):
        # Three satisfy readings 2, 5, 9 -> median is the middle int, 5.
        rows = _rows([
            CycleRow(0, None, 2),
            CycleRow(1, None, 9),
            CycleRow(2, None, 5),
        ])
        exact = cycles_for_progress_exact(rows, 1)
        assert exact == Fraction(5)
        # Float boundary: numerically equal float (formerly an int return).
        assert cycles_for_progress_pure(rows, 1) == 5.0

    def test_even_interval_count_returns_exact_midpoint(self):
        # Readings 2 and 3 -> exact midpoint 5/2; the wrapper rounds once.
        rows = _rows([
            CycleRow(0, None, 2),
            CycleRow(1, None, 3),
        ])
        assert cycles_for_progress_exact(rows, 1) == Fraction(5, 2)
        assert cycles_for_progress_pure(rows, 1) == 2.5

    def test_strict_increase_intervals(self):
        # Progress bumps at cycles 1, 4, 6: intervals 4-1=3 and 6-4=2.
        rows = _rows([
            CycleRow(0, 0, None),
            CycleRow(1, 1, None),
            CycleRow(2, 1, None),   # flat: tp <= prev branch
            CycleRow(3, 1, None),
            CycleRow(4, 2, None),
            CycleRow(5, 2, None),
            CycleRow(6, 3, None),
        ])
        assert cycles_for_progress_exact(rows, 2) == Fraction(5, 2)

    def test_none_reading_resets_strict_detector(self):
        """The P3c fidelity semantics (kernel-pinned in
        Formal/CyclesForProgress.lean): a None task_progress reading resets
        the detector, so `0, None, 5, 7` contributes NO strict interval and
        the lone satisfy reading is the whole median."""
        rows = _rows([
            CycleRow(0, 0, None),
            CycleRow(1, None, None),
            CycleRow(2, 5, None),
            CycleRow(3, 7, 9),
        ])
        assert cycles_for_progress_exact(rows, 1) == Fraction(9)

    def test_non_positive_satisfy_reading_is_skipped(self):
        # cycles_to_satisfy == 0 fails the `> 0` gate: no interval at all.
        rows = _rows([
            CycleRow(0, None, 0),
            CycleRow(1, None, 0),
        ])
        assert cycles_for_progress_exact(rows, 1) is None

    def test_dual_signal_single_cycle(self):
        # The verdict-(b) case: the final row bumps progress AND satisfies.
        rows = _rows([
            CycleRow(0, 0, None),
            CycleRow(1, 2, None),
            CycleRow(2, 4, 3),
        ])
        # strict interval [2-1=1] ++ satisfy [3] -> median (1+3)/2 = 2.
        assert cycles_for_progress_exact(rows, 2) == Fraction(2)

    def test_wrapper_is_float_of_exact(self):
        rows = _rows([
            CycleRow(0, None, 3),
            CycleRow(1, None, 4),
        ])
        exact = cycles_for_progress_exact(rows, 1)
        assert exact is not None
        wrapper = cycles_for_progress_pure(rows, 1)
        assert wrapper == float(exact) == 3.5


class TestMedianExact:
    def test_odd(self):
        assert _median_exact([9, 1, 5]) == Fraction(5)

    def test_even_midpoint_stays_exact(self):
        assert _median_exact([1, 2]) == Fraction(3, 2)

    def test_singleton(self):
        assert _median_exact([7]) == Fraction(7)
