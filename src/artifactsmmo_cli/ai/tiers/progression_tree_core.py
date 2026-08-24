"""PURE cores of the progression-tree selector (spec 2026-07-06). No
GameData/WorldState — plain data only, mirrored by Formal/ProgressionTree.lean.

The tree replaced the flat scalar root ranking: trunk (L10..L50 milestones),
two branches (gear | xp) switched by band adequacy, tertiary untouched.

WAVE 3a/3b: the boolean branch pivot is GONE. `resolve_root`'s five-node walk
(`ai/decisions/root.py`) chooses between gear and xp by RESOLUTION, not by a
`band_adequate` switch, so `Branch`, `branch_pick_pure` and the whole
gear-argmax/aging family left this module. What remains is what that walk
calls: `milestone_pure` (the trunk), `potion_type_weight`, the focus-aging
constants with `falloff`, `dhondt_step`, and the `GearCandidate` record."""

from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction

TRUNK_CAP = 50
BAND = 10


def milestone_pure(level: int) -> int:
    """Next trunk milestone: min(50, (level // 10 + 1) * 10). Strictly above
    `level` until the cap; the L50 capstone is the fixed point."""
    return min(TRUNK_CAP, (level // BAND + 1) * BAND)


POTION_TYPE_WEIGHTS: dict[str, Fraction] = {
    "hp_restore": Fraction(1),
    "boost": Fraction(1, 4),
    "resist": Fraction(1, 4),
    "antipoison": Fraction(1, 4),
}
"""Per-effect-family consumable weights — the ONLY tuning surface for
potions in the gear branch (user decision 2026-07-06: health maximized now,
other families dialed later). Applied as a multiplier on the candidate's
value gain before the gear branch ranks it."""


def potion_type_weight(family: str) -> Fraction:
    """Table lookup. An UNKNOWN family weighs 0: an unmodeled consumable
    must never outrank modeled gear — the family universe is closed by the
    table, and extending it is a deliberate tuning act, not a default."""
    return POTION_TYPE_WEIGHTS.get(family, Fraction(0))


FOCUS_FLAT = 10
"""Iterations a freshly-focused root farms at FULL weight before decay begins.
While every candidate is at or below this level the resolution walk takes its
flat-window fast path — `WhichSlotIsFurthestBehind._aged_head`
(`ai/decisions/root.py`) returns the plain head instead of a `dhondt_step`, so
a fresh root sees no interleave jitter."""

FOCUS_SPAN = 100
"""Iterations over which a focused root's weight decays from 1 to FOCUS_FLOOR.
Decay runs on focus levels (FOCUS_FLAT, FOCUS_FLAT + FOCUS_SPAN]."""

FOCUS_FLOOR = Fraction(1, 9)
"""Minimum weight multiplier (> 0): a stuck drop root is NEVER fully abandoned,
so if its drop finally lands it resumes. Tuning surface — calibrated live
(Task 11) against the real Robby trace ratio (wolf_ears gain 18100 : iron_ring
gain 2000, ~9.05:1): at this floor the asymptotic split once a stuck root is
fully decayed (focus >= FOCUS_FLAT + FOCUS_SPAN) is ~50/50 (18100/9 = 2011
vs 2000), matching the design intent's near-even hand-off. The literal "50%
share by iteration 60" anchor is unreachable for a ratio this large under the
pinned convex (quadratic ease-in) curve with FOCUS_SPAN=100 -- the curve is
provably still >= 0.75 at the span midpoint regardless of floor -- so the
~50/50 split lands at the floor (iteration ~110) instead; see
task-11-report.md."""


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


def dhondt_step(weighted: list[tuple[str, Fraction]],
                seats: Mapping[str, int]) -> str | None:
    """One seat of the d'Hondt / highest-averages apportionment: the key
    maximizing `w_i / (seats_i + 1)` GIVEN the seats already handed out.

    This is the single-step PRIMITIVE the scheduler is built from — O(len
    (weighted)), no loop over a cycle index. The winning quotient ties break by
    higher weight then key string (`(quotient, weight, key)` via `max`), a
    canonical, list-order-independent total order, so the winner depends only on
    the SET of (key, weight) pairs and the seat counts, never on input ordering.
    An unseated key defaults to 0 seats (`seats.get(k, 0)`) — the closed
    universe: a key absent from `seats` is fresh. `None` only for an empty list.

    Callers accumulate seats incrementally across decisions (one bump for the
    returned key), giving an O(candidates)-per-decision proportional schedule
    instead of recomputing the whole apportionment from a global cycle index.
    The live caller is `WhichSlotIsFurthestBehind._aged_head`
    (`ai/decisions/root.py`), whose seat ledger is `GamePlayer._interleave_seats`;
    the no-starvation bound on the resulting schedule is
    `Formal.Liveness.InterleaveNoStarvation.interleaveDue_reaches`."""
    if not weighted:
        return None
    return max(
        weighted,
        key=lambda kw: (kw[1] / (seats.get(kw[0], 0) + 1), kw[1], kw[0]),
    )[0]


@dataclass(frozen=True)
class GearCandidate:
    """One gear upgrade candidate. `gain` is the WEIGHTED value gain
    (potion-family weight already applied by the assembler)."""
    slot: str
    code: str
    gain: Fraction
    level: int
