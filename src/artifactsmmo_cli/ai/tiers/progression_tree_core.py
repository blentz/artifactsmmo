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
    table, and extending it is a deliberate tuning act, not a default.

    This function and `POTION_TYPE_WEIGHTS` have no production caller today,
    and are RETAINED deliberately (user decision, wave 3b). Wave 3a stopped
    `decide_tree` reading utility-slot candidates and wave 3b deleted
    `_utility_candidates` / `objective_candidates`, which were the only
    readers. Three things keep them: the Lean mirror `potionWeight` and its
    two theorems are kept alongside, so deleting this half would leave a
    proof over nothing; waves 4 and 6 both put potions back on the decision
    surface; and the closed-universe contract above is the tuning decision
    itself, which is expensive to rediscover and cheap to hold.

    The claim in the first sentence is CHECKED, not asserted:
    `scripts/gen_reachability_claims.py` resolves it to this function and
    fails the gate the day something starts calling it while this note still
    says nothing does."""
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

INTERLEAVE_RUN = FOCUS_FLAT
"""Cycles a key HOLDS the interleave before it is charged a d'Hondt seat.

THE INTERLEAVE ALLOCATES IN RUNS, NOT IN SINGLE CYCLES, and this constant is
the whole of that. `dhondt_step` is a pure argmax of `w/(seats+1)`: between seat
bumps its inputs do not move, so the same key keeps winning. Charging a seat on
every aged cycle therefore drops the winner's quotient every cycle and makes the
argmax alternate — proportional apportionment at one-cycle granularity, which is
MAXIMAL interleaving and exactly the wrong granularity for work that costs
travel to start.

Measured on the fleet run ending 2026-08-27: `aged_pick` was true in 99% of
cycles and 100% of root flips rode it. Lor changed root in 97% of 1,998 cycles
and walked 4,680 tiles across 18 DISTINCT ones — pacing between the same few
nodes for roughly half of a rate-limited run. Simulated over the same
apportionment past the decay band, charging once per run takes flips from 100%
to 9% with a median run of 10 cycles, and the seat RATIOS are unchanged (5:5:3
against 49:49:32).

It is `FOCUS_FLAT` deliberately, not a new number: that is already "the farm
window", the span a FRESH root is allowed before aging starts, so a root that
has aged gets turns of the same size it originally got for free.

WHAT THIS DOES NOT CHANGE: proportionality (each key still earns one seat per
`INTERLEAVE_RUN` cycles of its OWN work) and therefore not the anti-starvation
bound either — `Formal.ProgressionTree.interleaveDue_reaches` is stated over
SEAT ALLOCATIONS, so the bound in seats is untouched and the bound in cycles
scales by this constant. `test_ring2_starvation_repro.py` drives the real engine
and still elects every candidate.

RESIDUAL, stated so it is not mistaken for a full fix: inside the decay band
(`FOCUS_FLAT < focus <= FOCUS_FLAT + FOCUS_SPAN`) the winner's weight moves every
cycle as `falloff` decays it, so runs stay short there — simulated 78% flips.
That band is the deliberate hand-off ramp, each key crosses it once, and the
live fleet sat far past it (focus 393-1157). Fixing the band too would need real
hold state rather than a cadence."""

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


def run_falloff(focus_level: int) -> Fraction:
    """`falloff` sampled at RUN boundaries — the decay band's half of the
    interleave-thrash fix.

    THE SEAT CADENCE ALONE DOES NOT HOLD THE BAND. `INTERLEAVE_RUN` stops the
    d'Hondt quotient moving every cycle, which is enough once a candidate's
    weight has settled at `FOCUS_FLOOR`. Inside the decay band
    (`FOCUS_FLAT < focus <= FOCUS_FLAT + FOCUS_SPAN`) the WEIGHT itself still
    shrank every cycle, so the argmax could flip with no seat charged at all —
    simulated 81% of transitions, median run 1, exactly the thrash the cadence
    was meant to end. Sampling the curve once per run makes the weight constant
    across a run, and the winner then holds for the same reason it does past the
    band: nothing the argmax reads has moved. Simulated in-band: 81% -> 10%
    flips, median run 1 -> 10, all candidates still elected. Past the band it is
    identical to `falloff` by construction, so nothing there regresses.

    THE CURVE IS NOT TOUCHED, only where it is READ. `falloff` keeps its proved
    Lean mirror (`falloff_flat`, `falloff_le_one`, `falloff_ge_floor`,
    `falloff_floor_after`, `falloff_antitone`) and every property survives a
    monotone non-decreasing argument transform: the staircase is still antitone,
    still starts at 1, still reaches the floor at the same level. It is
    conservative in one direction — holding the run's STARTING weight means
    never quoting a weight the smooth curve had not already reached.

    Not merged into `falloff` itself because that function is the mirrored
    definition; a caller that wants the continuous curve must still get it."""
    return falloff(focus_level - focus_level % INTERLEAVE_RUN)


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
    `Formal.ProgressionTree.interleaveDue_reaches` — that is the NAMESPACE it
    is declared under; the file it lives in is
    `formal/Formal/Liveness/InterleaveNoStarvation.lean`, because the summation
    argument needs the Mathlib-permitted liveness tier."""
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
