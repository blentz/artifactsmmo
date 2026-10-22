"""The learned drop chance (spec 2026-10-18 §2.8): a Beta posterior on the API
rate, a fleet-wide prospecting multiplier `1 + k·P`, and the fit of `k`."""

from fractions import Fraction

import pytest

from artifactsmmo_cli.ai.drop_chance_core import (
    chance_at,
    fit_k,
    posterior_chance,
    prospecting_multiplier,
    units_per_attempt,
)


def test_the_prior_is_one_hit_in_the_api_rate() -> None:
    assert posterior_chance(300, 0, 0) == Fraction(1, 300)


def test_observations_update_the_prior() -> None:
    """Live 2026-10-19: 383 gathers at `trout_spot` for 2 `small_pearls`."""
    assert posterior_chance(300, 383, 2) == Fraction(3, 683)


@pytest.mark.parametrize(("api_rate", "attempts", "hits"),
                         [(0, 10, 1), (300, 1, 2), (300, 1, -1)])
def test_an_impossible_observation_raises(api_rate: int, attempts: int, hits: int) -> None:
    with pytest.raises(ValueError, match="posterior_chance out of range"):
        posterior_chance(api_rate, attempts, hits)


def test_the_multiplier_is_one_plus_k_times_prospecting() -> None:
    assert prospecting_multiplier(Fraction(1, 5), 10) == 3
    assert prospecting_multiplier(Fraction(0), 40) == 1


def test_the_multiplier_never_falls_below_one() -> None:
    assert prospecting_multiplier(Fraction(-1), 5) == 1
    assert prospecting_multiplier(Fraction(1, 5), -10) == 1


def test_the_chance_is_the_posterior_times_the_multiplier() -> None:
    assert chance_at(300, 0, 0, Fraction(1, 5), 10) == Fraction(1, 100)
    assert chance_at(300, 383, 2, Fraction(0), 0) == Fraction(3, 683)


def test_the_chance_never_exceeds_one() -> None:
    assert chance_at(1, 0, 0, Fraction(1, 5), 10) == 1
    assert chance_at(2, 5, 5, Fraction(3), 100) == 1


def test_no_samples_fit_no_prospecting_effect() -> None:
    assert fit_k([]) == 0


def test_k_is_the_attempt_weighted_least_squares_slope() -> None:
    """Observed over API rate `r`: 3 at P 10 (1 hit in 100 at rate 300) and 2 at
    P 20 (1 in 50 at rate 100). Weighted by attempts, `k = (100·10·2 + 50·20·1)
    / (100·10² + 50·20²) = 1/10`; unweighted it would read 2/25. A sample at
    P 0 adds nothing."""
    samples = [(300, 10, 100, 1), (100, 20, 50, 1), (300, 0, 383, 2)]
    assert fit_k(samples) == Fraction(1, 10)


def test_a_sample_without_attempts_is_no_observation() -> None:
    assert fit_k([(300, 10, 100, 1), (300, 40, 0, 0)]) == Fraction(1, 5)
    assert fit_k([(300, 10, 0, 0)]) == 0


def test_a_slope_below_zero_is_clamped() -> None:
    assert fit_k([(300, 10, 300, 0)]) == 0


def test_no_positive_prospecting_fits_nothing() -> None:
    """At P −5, 0 hits in 300 at rate 300 fit a slope of 1/5 through the
    origin; with no positive prospecting there is no bonus to learn."""
    assert fit_k([(300, -5, 300, 0)]) == 0
    assert fit_k([(300, 0, 300, 3)]) == 0


@pytest.mark.parametrize("sample", [(0, 10, 100, 1), (300, 10, 1, 2), (300, 10, 1, -1)])
def test_an_impossible_sample_raises(sample: tuple[int, int, int, int]) -> None:
    with pytest.raises(ValueError, match="fit_k sample out of range"):
        fit_k([sample])


def test_a_unit_is_the_chance_times_the_mean_quantity() -> None:
    """Ruling T16a: an attempt yields `chance × (min + max) / 2` units. A drop
    of 1 to 3 at 1 in 8 under the prior is `(1/8) · 2`; of 2 to 4, `(1/8) · 3`."""
    assert units_per_attempt(8, 1, 3, 0, 0, Fraction(0), 0) == Fraction(1, 4)
    assert units_per_attempt(8, 2, 4, 0, 0, Fraction(0), 0) == Fraction(3, 8)


def test_a_unit_reads_the_observations_and_the_prospecting() -> None:
    """The live pearls (383 attempts, 2 hits) make a unit 3/683; a learned
    slope of 1/10 at prospecting 10 doubles it."""
    assert units_per_attempt(300, 1, 1, 383, 2, Fraction(0), 0) == Fraction(3, 683)
    assert units_per_attempt(300, 1, 1, 383, 2, Fraction(1, 10), 10) == Fraction(6, 683)
