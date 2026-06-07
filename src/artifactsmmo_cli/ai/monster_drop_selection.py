"""Expected-kills-optimal monster selection for a needed DROP. When a needed item
is dropped by more than one monster, pick the source minimizing the EXPECTED number
of kills to acquire one unit — `rate / avg_quantity` — tie-broken by nearest monster
then code (a total order ⇒ a unique, deterministic winner). Pure: no I/O. This is the
differential target proved in formal/Formal/MonsterDropSelection.lean over exact
rationals (Q). Mirrors gather_selection.py (kills replace gathers; monsters replace
resource nodes).
"""

from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class MonsterDropCandidate:
    monster_code: str
    rate: int          # 1-in-N drop rate (>= 1)
    min_quantity: int  # >= 1
    max_quantity: int  # >= min_quantity
    distance: int      # Manhattan distance to nearest monster tile (>= 0)


def _expected_kills(c: MonsterDropCandidate) -> Fraction:
    """Expected kills to acquire one unit: rate / average yield. Exact rational
    (never float) so the proof is about the real ordering, not a surrogate."""
    avg_quantity = Fraction(c.min_quantity + c.max_quantity, 2)
    return Fraction(c.rate) / avg_quantity


def _key(c: MonsterDropCandidate) -> tuple[Fraction, int, str]:
    return (_expected_kills(c), c.distance, c.monster_code)


def select_monster_for_drop(item: str, candidates: list[MonsterDropCandidate]) -> str | None:
    """Return the monster_code of the lex-argmin candidate, or None if empty.
    `item` is carried for the caller's grouping; the metric does not use it."""
    if not candidates:
        return None
    return min(candidates, key=_key).monster_code
