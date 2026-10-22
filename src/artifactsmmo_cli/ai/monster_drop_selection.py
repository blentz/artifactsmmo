"""Expected-kills-optimal monster selection for a needed DROP. When a needed item
is dropped by more than one monster, pick the source minimizing the EXPECTED number
of kills to acquire one unit — the learned drop model's attempts per unit
(`LearnedDrops.attempts_per_unit`: `1 / (chance × mean quantity)`, spec
2026-10-18 §2.8, ruling T16a) — tie-broken by nearest monster then code (a total
order ⇒ a unique, deterministic winner). Pure: no I/O. This is the differential
target proved in formal/Formal/MonsterDropSelection.lean over exact rationals (Q).
Mirrors gather_selection.py (kills replace gathers; monsters replace resource
nodes); the key is the same wins-per-unit factor the acquisition walk's DROP route
prices (`acquisition_cost._drop_actions`).
"""

from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class MonsterDropCandidate:
    monster_code: str
    attempts: Fraction  # expected kills per unit (> 0)
    distance: int       # Manhattan distance to nearest monster tile (>= 0)


def _key(c: MonsterDropCandidate) -> tuple[Fraction, int, str]:
    return (c.attempts, c.distance, c.monster_code)


def select_monster_for_drop(item: str, candidates: list[MonsterDropCandidate]) -> str | None:
    """Return the monster_code of the lex-argmin candidate, or None if empty.
    `item` is carried for the caller's grouping; the metric does not use it."""
    if not candidates:
        return None
    return min(candidates, key=_key).monster_code
