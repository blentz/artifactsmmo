"""PURE core of the fleet's shared skill climb (spec 2026-10-18 §2.5). No
GameData/WorldState: plain data only, mirrored by Formal/FleetClimb.lean.

A crafting skill climb is paid ONCE, by one character, and serves every fleet
piece gated by that skill. Two pieces of that live here:

  * `amortized_climb_seconds`: the climb's remaining cost divided across the
    fleet units it unlocks. The unit is whatever `remaining` is in; the caller
    (`acquisition_cost._sibling_craft_option`) passes grind CYCLES, which are
    planner actions (`skill_grind_cost_core`).
  * `climber`: who climbs. The character with the least remaining climb, ties
    by the least other committed work, then the fleet's own order (the
    account's `GET /my/characters` order). Never a name or `repr` order.
"""

from collections.abc import Mapping, Sequence
from fractions import Fraction


def amortized_climb_seconds(remaining: Fraction, units: int) -> Fraction:
    """The share of a `remaining` climb each of the `units` fleet units it
    unlocks pays. At least one unit (the one being priced) always shares the
    climb, so `units < 1` is a caller bug and is refused."""
    if units < 1:
        raise ValueError(f"a climb is shared by at least one unit, got {units}")
    return remaining / units


def climber(remaining_by_character: Mapping[str, Fraction],
            committed_by_character: Mapping[str, int],
            order: Sequence[str]) -> str:
    """The character that climbs: the argmin of `(remaining, committed)` over
    `remaining_by_character`, the first in `order` on a full tie.

    `order` is the fleet order, and every candidate must be in it: a character
    outside the fleet has no place in the tie order (`ValueError`), as in
    `consumable_floor_core.share`. Every candidate must carry a committed
    count (`KeyError` otherwise): a missing count is a caller bug, never 0."""
    outside = [name for name in remaining_by_character if name not in order]
    if outside:
        raise ValueError(f"climb candidates outside the fleet order: {outside}")
    candidates = [name for name in order if name in remaining_by_character]
    if not candidates:
        raise ValueError("no character can climb: the fleet is empty")
    # `min` keeps the first of equal keys, and `candidates` is in fleet order.
    return min(candidates,
               key=lambda name: (remaining_by_character[name], committed_by_character[name]))
