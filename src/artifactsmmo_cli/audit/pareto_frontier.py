"""The non-dominated set of measured activity bundles.

The season-9 objective is multi-variate: character XP is primary, but access to
it is gated behind skill XP, and skill XP is gated behind currencies whose
actions differ in efficiency. A scalar would need weights nobody has measured,
and inventing them is exactly the epicycle this audit exists to avoid. The
frontier needs no weights — it reports which bundles are not beaten outright,
and the design decision is made against that set.

Seconds are the shared denominator, not a fourth axis: every currency here is
already per second.
"""

from artifactsmmo_cli.audit.currency_rate_census import GoalRates


def _axes(rates: GoalRates) -> tuple[float, float, float]:
    return (rates.char_xp_per_second, rates.skill_xp_per_second, rates.gold_per_second)


def _dominates(a: GoalRates, b: GoalRates) -> bool:
    """True when `a` is at least as good as `b` on every currency and strictly
    better on at least one. Equality does not dominate, so two identical bundles
    both survive rather than one silently eliminating the other."""
    left, right = _axes(a), _axes(b)
    return all(x >= y for x, y in zip(left, right, strict=True)) and left != right


def frontier(rows: list[GoalRates]) -> list[GoalRates]:
    """The bundles no other bundle dominates, in the order given."""
    return [a for a in rows if not any(_dominates(b, a) for b in rows if b is not a)]
