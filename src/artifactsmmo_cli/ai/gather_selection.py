"""Yield-rate-optimal gather-source selection. When a needed item is the primary
drop of more than one resource, pick the source minimizing the EXPECTED number of
gathers to acquire one unit — `rate / avg_quantity` — tie-broken by nearest node
then code (a total order ⇒ a unique, deterministic winner). Pure: no I/O. This is
the differential target proved in formal/Formal/GatherSelection.lean over exact rationals (Q).
"""

from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class GatherCandidate:
    resource_code: str
    rate: int          # 1-in-N drop rate (>= 1)
    min_quantity: int  # >= 1
    max_quantity: int  # >= min_quantity
    distance: int      # Manhattan distance to nearest node (>= 0)


def expected_gathers(rate: int, min_quantity: int, max_quantity: int) -> Fraction:
    """Expected gathers to acquire one unit of a drop row: rate / average yield.
    Exact rational (never float) so the proof is about the real ordering, not a
    surrogate. Public because every price of a gather (`GatherAction.cost`, the
    acquisition walk's GATHER route) charges THIS figure per unit: a planner
    gather credits one unit, and a 1-in-20 secondary drop takes 20 real gathers
    to deliver it."""
    avg_quantity = Fraction(min_quantity + max_quantity, 2)
    return Fraction(rate) / avg_quantity


def _expected_gathers(c: GatherCandidate) -> Fraction:
    return expected_gathers(c.rate, c.min_quantity, c.max_quantity)


def _key(c: GatherCandidate) -> tuple[Fraction, int, str]:
    return (_expected_gathers(c), c.distance, c.resource_code)


def select_gather_source(item: str, candidates: list[GatherCandidate]) -> str | None:
    """Return the resource_code of the lex-argmin candidate, or None if empty.
    `item` is carried for the caller's grouping; the metric does not use it."""
    if not candidates:
        return None
    return min(candidates, key=_key).resource_code


def rank_gather_sources(candidates: list[GatherCandidate]) -> list[str]:
    """Every candidate's resource_code, best first, by the same total order
    `select_gather_source` minimises: its head IS that function's answer. The
    one walk takes an item's gather routes in this order (Phase 2c-2b)."""
    return [c.resource_code for c in sorted(candidates, key=_key)]
