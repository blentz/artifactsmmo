"""Pure core: the chance a drop lands, learned from observed drops (spec
2026-10-18 §2.8).

There is no server-side drop-rate oracle. The API's `rate` (one in `rate`
attempts) is a prior, and the fleet's observed attempts and hits update it:

    posterior_chance = (1 + hits) / (api_rate + attempts)

the Beta posterior mean with the weight of one observed hit in `api_rate`
attempts. Prospecting raises a drop's chance by one fleet-wide multiplier
`1 + k·P`, floored at 1, with `k` fitted (`fit_k`) on every observed attempt and
a prior of `k = 0`: no prospecting bonus is assumed until the data shows one.

    chance_at = min(1, posterior_chance × prospecting_multiplier)
    units_per_attempt = chance_at × (min_quantity + max_quantity) / 2

Proved in `Formal.DropChance` (the posterior is in (0, 1], a hit never lowers
it, the multiplier is monotone in P for k ≥ 0, the chance never exceeds 1, the
fitted k is never negative) and diffed by `formal/diff/test_drop_chance_diff.py`.
"""

from collections.abc import Sequence
from fractions import Fraction


def posterior_chance(api_rate: int, attempts: int, hits: int) -> Fraction:
    """`(1 + hits) / (api_rate + attempts)`: the prior of one hit in `api_rate`
    attempts, then the observations."""
    if api_rate < 1 or not 0 <= hits <= attempts:
        raise ValueError(f"posterior_chance out of range: api_rate {api_rate}, "
                         f"attempts {attempts}, hits {hits}")
    return Fraction(1 + hits, api_rate + attempts)


def prospecting_multiplier(k: Fraction, prospecting: int) -> Fraction:
    """`1 + k·P`, floored at 1: prospecting never lowers a drop's chance."""
    return max(Fraction(1), 1 + k * prospecting)


def chance_at(api_rate: int, attempts: int, hits: int, k: Fraction,
              prospecting: int) -> Fraction:
    """The chance per attempt at `prospecting`, capped at 1."""
    return min(Fraction(1), posterior_chance(api_rate, attempts, hits)
               * prospecting_multiplier(k, prospecting))


def units_per_attempt(api_rate: int, min_quantity: int, max_quantity: int,
                      attempts: int, hits: int, k: Fraction, prospecting: int) -> Fraction:
    """Units of a drop one attempt yields, expected: `chance_at` times the
    drop's mean quantity `(min + max) / 2`. With nothing observed
    (`attempts = hits = 0`, `k = 0`) it is the API prior alone, `1/api_rate`
    of the mean. The ONE drop model every consumer prices and ranks a drop
    by (ruling T16a): the planner's gather, the acquisition walk and every
    source picker take `1 /` this as their expected attempts per unit."""
    return (chance_at(api_rate, attempts, hits, k, prospecting)
            * Fraction(min_quantity + max_quantity, 2))


def fit_k(samples: Sequence[tuple[int, int, int, int]]) -> Fraction:
    """The prospecting slope `k ≥ 0` fitted to `(api_rate, prospecting,
    attempts, hits)` samples, one per (source, item, prospecting).

    Each sample's ratio is its observed rate over the API base rate,
    `r = (hits / attempts) · api_rate` (1 when the API rate is exact), and
    `r − 1 = k·P` is fitted through the origin by least squares weighted by
    attempts: `k = Σ w·P·(r − 1) / Σ w·P²`. A sample without attempts observes
    nothing and is dropped. With no sample at a positive prospecting there is
    no bonus to learn: 0. A slope below 0 is clamped to 0."""
    for api_rate, prospecting, attempts, hits in samples:
        if api_rate < 1 or not 0 <= hits <= attempts:
            raise ValueError(f"fit_k sample out of range: api_rate {api_rate}, "
                             f"prospecting {prospecting}, attempts {attempts}, hits {hits}")
    kept = [sample for sample in samples if sample[2] > 0]
    if not any(prospecting > 0 for _, prospecting, _, _ in kept):
        return Fraction(0)
    num = sum((attempts * prospecting * (Fraction(hits, attempts) * api_rate - 1)
               for api_rate, prospecting, attempts, hits in kept), Fraction(0))
    den = sum((Fraction(attempts * prospecting * prospecting)
               for _, prospecting, attempts, _ in kept), Fraction(0))
    return max(Fraction(0), num / den)
