"""PURE cores of the progression-tree selector (spec 2026-07-06). No
GameData/WorldState — plain data only, mirrored by Formal/ProgressionTree.lean.

The tree replaced the flat scalar root ranking: trunk (L10..L50 milestones),
two branches (gear | xp) switched by band adequacy, tertiary untouched.

WAVE 3a/3b: the boolean branch pivot is GONE. `resolve_root`'s five-node walk
(`ai/decisions/root.py`) chooses between gear and xp by RESOLUTION, not by a
`band_adequate` switch, so `Branch`, `branch_pick_pure` and the whole
gear-argmax/aging family left this module. What remains is what that walk
calls: `milestone_pure` (the trunk), `potion_type_weight`, and the
`GearCandidate` record. Phase 4-2b-ii deleted the focus-aging fall-off and the
d'Hondt interleave: the intention's cycle budget and the one-turn yield
(`ai/intention_progress.py`, `GamePlayer._track_intention`) replace them."""

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


@dataclass(frozen=True)
class GearCandidate:
    """One gear upgrade candidate. `gain` is the WEIGHTED value gain
    (potion-family weight already applied by the assembler)."""
    slot: str
    code: str
    gain: Fraction
    level: int
