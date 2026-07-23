"""PURE cores of the progression-tree selector (spec 2026-07-06). No
GameData/WorldState — plain data only, mirrored by Formal/ProgressionTree.lean.

The tree replaces the flat scalar root ranking: trunk (L10..L50 milestones),
two branches (gear | xp) switched by band adequacy, tertiary untouched."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from types import MappingProxyType

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
    instead of recomputing from a global cycle index — see `interleave_due`,
    which is exactly the (cycle+1)-fold of this step from empty seats."""
    if not weighted:
        return None
    return max(
        weighted,
        key=lambda kw: (kw[1] / (seats.get(kw[0], 0) + 1), kw[1], kw[0]),
    )[0]


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

    This is the REFERENCE BATCH scheduler, defined as the fold of `dhondt_step`
    over an accumulating `seats` dict for `cycle+1` steps: seat-for-seat
    identical to recomputing the whole d'Hondt allocation from seat 0 (its
    former body), so it stays byte-for-byte behavior-identical for fixed
    weights. Live callers instead advance seats incrementally and take ONE
    `dhondt_step` per decision — the fold identity guarantees that reproduces
    this same schedule while costing O(candidates) rather than O(cycle)."""
    if not weighted:
        return None
    seats: dict[str, int] = {}
    winner = weighted[0][0]
    for _ in range(cycle + 1):
        step = dhondt_step(weighted, seats)
        assert step is not None  # weighted is non-empty here
        winner = step
        seats[winner] = seats.get(winner, 0) + 1
    return winner


@dataclass(frozen=True)
class GearCandidate:
    """One upgrade candidate for the gear branch. `gain` is the WEIGHTED
    value gain (potion-family weight already applied by the assembler)."""
    slot: str
    code: str
    gain: Fraction
    level: int


def _gear_pref_key(c: GearCandidate) -> tuple[Fraction, int, str, str]:
    """Canonical total order for gear candidates: biggest weighted gain, then
    higher item level (newer gear generation), then code and slot ascending as
    PURE disambiguators (insertion-order and hash-seed independent). The single
    source of truth for both `gear_target_pick`'s argmax and `focus_aging_order`'s
    tail sort. Mirrors Lean `Formal.ProgressionTree.better`."""
    return (-c.gain, -c.level, c.code, c.slot)


def gear_target_pick(candidates: list[GearCandidate]) -> GearCandidate | None:
    """Deterministic argmax over the canonical `_gear_pref_key` total order."""
    if not candidates:
        return None
    return min(candidates, key=_gear_pref_key)


_NO_SYNERGY: Mapping[tuple[str, str], Fraction] = MappingProxyType({})
"""The empty synergy map — 'no alignment signal'. A missing `(slot, code)` entry
reads as `Fraction(1)` (the §3.4 degenerate), so `_scaled_weights` with this
sentinel is byte-identical to the pre-synergy weight `gain * falloff`. Mirrors
`progression_tree._NO_FOCUS`/`_NO_SEATS`; the default for every synergy-aware
function so the whole plumbing lands inert before real values arrive (spec §3.8),
and the one-line kill switch if a live trace goes wrong."""


def _scaled_weights(candidates: list[GearCandidate],
                    focus: Mapping[tuple[str, str], int],
                    synergy: Mapping[tuple[str, str], Fraction] = _NO_SYNERGY
                    ) -> list[tuple[str, Fraction]]:
    """(slot-keyed weight) = base gain * falloff(focus level) * synergy per
    candidate — magnitude * staleness * purity (spec §3.2). Keyed by SLOT —
    unique per candidate (one gear candidate per slot), so two same-code
    candidates (e.g. iron_ring targeting ring1_slot AND ring2_slot) stay
    distinct; keying by code would collapse them. The caller maps the winning
    slot back to its GearCandidate. `synergy` looks up on the SAME `(slot, code)`
    key as `focus`; a missing entry is `Fraction(1)` (no signal), so the empty
    `_NO_SYNERGY` reproduces the pre-synergy `gain * falloff` exactly."""
    return [(c.slot, c.gain * falloff(focus.get((c.slot, c.code), 0))
             * synergy.get((c.slot, c.code), Fraction(1)))
            for c in candidates]


def focus_aging_pick(candidates: list[GearCandidate],
                     focus: Mapping[tuple[str, str], int],
                     seats: Mapping[str, int],
                     synergy: Mapping[tuple[str, str], Fraction] = _NO_SYNERGY
                     ) -> GearCandidate | None:
    """The gear root to pursue THIS cycle, with anti-starvation aging.

    While every candidate is still inside its flat farm window (focus <=
    FOCUS_FLAT) AND no candidate carries a synergy signal (every synergy
    multiplier is the `Fraction(1)` no-signal default), the result is
    bit-identical to the proven `gear_target_pick` argmax — no jitter for fresh
    roots. The synergy clause is load-bearing: weights can differ even when
    nothing is stale, so without it synergy would be silently inert for the
    first FOCUS_FLAT cycles of every root — exactly the window where it matters
    most (spec Phase 3). Once any candidate has been focused past the flat
    window OR a synergy signal is present, its selection weight decays (see
    `falloff`) / is scaled (see `synergy`) and the pick is the single
    `dhondt_step` over scaled gains GIVEN the seats handed
    out so far (the caller accumulates one seat per aged decision — see
    `GamePlayer._interleave_seats`), so a decayed stuck root hands cycles to
    reachable alternatives without ever being fully abandoned (FOCUS_FLOOR > 0).

    Seats are held on the caller (like the focus ledger) rather than recomputed
    from a global cycle index: for fixed weights, incrementally accumulated
    seats reproduce the old `interleave_due(scaled, cycle)` schedule seat-for-
    seat (the `dhondt_step`/`interleave_due` fold identity) at O(candidates)
    cost per decision."""
    if not candidates:
        return None
    if (all(focus.get((c.slot, c.code), 0) <= FOCUS_FLAT for c in candidates)
            and all(synergy.get((c.slot, c.code), Fraction(1)) == Fraction(1)
                    for c in candidates)):
        return gear_target_pick(candidates)
    winner_slot = dhondt_step(_scaled_weights(candidates, focus, synergy), seats)
    return next(c for c in candidates if c.slot == winner_slot)


def focus_aging_order(candidates: list[GearCandidate],
                      focus: Mapping[tuple[str, str], int],
                      seats: Mapping[str, int],
                      synergy: Mapping[tuple[str, str], Fraction] = _NO_SYNERGY
                      ) -> list[GearCandidate]:
    """Display/fallback order whose head is exactly `focus_aging_pick` and
    whose tail is the remaining candidates in the canonical argmax order
    (`gear_target_pick`'s total order). Keeps `decide_tree`'s
    `ordered[0] == pick` invariant intact under aging and synergy scaling."""
    if not candidates:
        return []
    pick = focus_aging_pick(candidates, focus, seats, synergy)
    assert pick is not None
    rest = sorted((c for c in candidates if c is not pick), key=_gear_pref_key)
    return [pick, *rest]
