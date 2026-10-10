"""Pure core: the best consumable loadout's pick
(`docs/PLAN_consumable_utility.md` increment 4; proved model
`formal/Formal/BestLoadout.lean`, differential
`formal/diff/test_best_loadout_diff.py`).

The candidates arrive in the reader's enumeration order (no potions, each single
potion, each pair, in the catalogue order of the API item list), each scored
`(XP per second, consumable units one fight uses)`. The pick is the highest
rate; on the same rate the fewer units (fewer consumables bought or drawn for
the same XP per second); on a full tie the EARLIER candidate — the fold
replaces its choice only on a candidate that strictly beats it, so no spelling
order ever decides (`Formal.BestLoadout.pick_optimal`: no candidate beats the
pick)."""

from collections.abc import Sequence
from fractions import Fraction


def beats(a: tuple[Fraction, int], b: tuple[Fraction, int]) -> bool:
    """`a` has a higher rate, or the same rate on fewer units."""
    return a[0] > b[0] or (a[0] == b[0] and a[1] < b[1])


def pick_best(candidates: Sequence[tuple[Fraction, int]]) -> int | None:
    """Index of the best `(rate, units)` candidate; None with no candidates."""
    best: int | None = None
    for index, candidate in enumerate(candidates):
        if best is None or beats(candidate, candidates[best]):
            best = index
    return best
