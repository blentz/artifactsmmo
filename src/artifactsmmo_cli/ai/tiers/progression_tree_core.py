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
