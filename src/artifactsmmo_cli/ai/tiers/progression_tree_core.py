"""PURE cores of the progression-tree selector (spec 2026-07-06). No
GameData/WorldState — plain data only, mirrored by Formal/ProgressionTree.lean.

The tree replaces the flat scalar root ranking: trunk (L10..L50 milestones),
two branches (gear | xp) switched by band adequacy, tertiary untouched."""

from dataclasses import dataclass
from enum import Enum
from fractions import Fraction

TRUNK_CAP = 50
BAND = 10


class Branch(Enum):
    GEAR = "gear"
    XP = "xp"


def milestone_pure(level: int) -> int:
    """Next trunk milestone: min(50, (level // 10 + 1) * 10). Strictly above
    `level` until the cap; the L50 capstone is the fixed point."""
    return min(TRUNK_CAP, (level // BAND + 1) * BAND)


def branch_pick_pure(band_adequate: bool, gear_target_exists: bool) -> Branch:
    """Gear-first until the band's loadout is adequate; then xp to the next
    milestone. One boolean pivot — no scalar competition (the design's core
    bet). Gear also yields when it has no reachable target (nothing to do)."""
    if not band_adequate and gear_target_exists:
        return Branch.GEAR
    return Branch.XP


POTION_TYPE_WEIGHTS: dict[str, Fraction] = {
    "hp_restore": Fraction(1),
    "boost": Fraction(1, 4),
    "resist": Fraction(1, 4),
    "antipoison": Fraction(1, 4),
}
"""Per-effect-family consumable weights — the ONLY tuning surface for
potions in the gear branch (user decision 2026-07-06: health maximized now,
other families dialed later). Applied as a multiplier on the candidate's
value gain before gear_target_pick."""


def potion_type_weight(family: str) -> Fraction:
    """Table lookup. An UNKNOWN family weighs 0: an unmodeled consumable
    must never outrank modeled gear — the family universe is closed by the
    table, and extending it is a deliberate tuning act, not a default."""
    return POTION_TYPE_WEIGHTS.get(family, Fraction(0))


FOCUS_FLAT = 10
"""Iterations a freshly-focused root farms at FULL weight before decay begins.
Below this the aging pick is bit-identical to the plain `gear_target_pick`
argmax (see `focus_aging_pick`)."""

FOCUS_SPAN = 100
"""Iterations over which a focused root's weight decays from 1 to FOCUS_FLOOR.
Decay runs on focus levels (FOCUS_FLAT, FOCUS_FLAT + FOCUS_SPAN]."""

FOCUS_FLOOR = Fraction(1, 8)
"""Minimum weight multiplier (> 0): a stuck drop root is NEVER fully abandoned,
so if its drop finally lands it resumes. Tuning surface — calibrated live
(Task 11)."""


def falloff(focus_level: int) -> Fraction:
    """Selection-weight multiplier for a root that has been the committed focus
    for `focus_level` iterations.

    Flat at 1 through FOCUS_FLAT (farm window), convex (quadratic ease-in)
    decay to FOCUS_FLOOR across the next FOCUS_SPAN iterations, then held at
    FOCUS_FLOOR. Convex so the hand-off is gentle early (keep farming) and
    steepens later. Exact `Fraction` — no float in the decision path. The
    constants are the ONLY tuning surface; the shape (flat -> convex -> floor)
    is pinned by the tests."""
    if focus_level <= FOCUS_FLAT:
        return Fraction(1)
    if focus_level >= FOCUS_FLAT + FOCUS_SPAN:
        return FOCUS_FLOOR
    t = Fraction(focus_level - FOCUS_FLAT, FOCUS_SPAN)
    return Fraction(1) - (Fraction(1) - FOCUS_FLOOR) * t * t


def interleave_due(weighted: list[tuple[str, Fraction]], cycle: int) -> str | None:
    """Deterministic proportional scheduler (d'Hondt / highest-averages).

    Returns the key that receives the (cycle+1)-th seat when seats are handed
    out one at a time, each to the key maximizing `w_i / (seats_i + 1)`. The
    method is house-monotone (no Alabama paradox), so each added seat goes to
    exactly one key; over any window each key wins about `w_i / total` of the
    seats, and every strictly-positive-weight key wins a seat within
    `total / w_i` cycles (the no-starvation bound). The winning quotient ties
    break by higher weight then key string — a canonical, list-order-independent
    total order — so the schedule depends only on the SET of (key, weight) pairs
    and the cycle, never on input ordering. Pure function of (weighted, cycle):
    no persisted accumulator, no RNG, no wall-clock. `None` only for an empty
    list.

    A naive `max(pool, key=(weight, key))` over a per-key "due" set is WRONG
    (it collapses to one winner every cycle — fails the equal-weight 1:1 and
    3:1 cases), and `cycle % len` rotation is list-order-dependent; d'Hondt is
    the correct order-independent proportional method."""
    if not weighted:
        return None
    seats: dict[str, int] = {key: 0 for key, _ in weighted}
    winner = weighted[0][0]
    for _ in range(cycle + 1):
        winner = max(
            weighted,
            key=lambda kw: (kw[1] / (seats[kw[0]] + 1), kw[1], kw[0]),
        )[0]
        seats[winner] += 1
    return winner


@dataclass(frozen=True)
class GearCandidate:
    """One upgrade candidate for the gear branch. `gain` is the WEIGHTED
    value gain (potion-family weight already applied by the assembler)."""
    slot: str
    code: str
    gain: Fraction
    level: int


def gear_target_pick(candidates: list[GearCandidate]) -> GearCandidate | None:
    """Deterministic argmax: biggest weighted gain, then higher item level
    (newer gear generation), then code and slot as PURE disambiguators
    (canonical total order — insertion-order and hash-seed independent)."""
    if not candidates:
        return None
    return min(candidates, key=lambda c: (-c.gain, -c.level, c.code, c.slot))
