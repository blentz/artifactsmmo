"""Expected-attempts-optimal gather-source selection. When a needed item is a
drop of more than one resource, pick the source minimizing the EXPECTED number
of gathers to acquire one unit — the learned drop model's attempts per unit
(`LearnedDrops.attempts_per_unit`: `1 / (chance × mean quantity)`, spec
2026-10-18 §2.8, ruling T16a) — tie-broken by nearest node then code (a total
order ⇒ a unique, deterministic winner). Pure: no I/O. This is the differential
target proved in formal/Formal/GatherSelection.lean over exact rationals (Q).

The key is the SAME figure the planner's gather charges (`GatherAction.gathers`)
and the acquisition walk's GATHER route prices (`acquisition_cost._gather_actions`),
so the source a picker keeps is the one both producers price.
"""

from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class GatherCandidate:
    resource_code: str
    attempts: Fraction  # expected gathers per unit (> 0)
    distance: int       # Manhattan distance to nearest node (>= 0)


def _key(c: GatherCandidate) -> tuple[Fraction, int, str]:
    return (c.attempts, c.distance, c.resource_code)


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
