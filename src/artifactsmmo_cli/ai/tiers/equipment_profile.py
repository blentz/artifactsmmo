"""Equipment profiles: named weight presets for the strategic_value scorer
(spec docs/superpowers/specs/2026-07-08-equipment-profiles-design.md).

A profile is a weight vector over strategic_value's five inputs
(combat_raw, wisdom, prospecting, inventory_space, haste) in
1/STRATEGIC_SCALE fixed-point units. COMBAT zeroes the efficiency stats so
gear ranks by combat content alone (fixing the flat-parity bug where a
prospecting artifact outranked a weapon). UTILITY keeps the combat FLOOR
(combat still dominates shared slots structurally) and gives the four
efficiency stats their own nonzero weights so efficiency-slot gear
(rings/artifacts/utility) gets ordered and pursued.

Phase 1: presets only, unwired. The UTILITY efficiency weights are the
live-tunable knob (spec Phase 5); the values here are the conservative
start, NOT the DEFAULT_STRATEGIC_WEIGHTS deferred parity (which weights
inventory_space as strongly as combat)."""

from enum import Enum

from artifactsmmo_cli.ai.game_data import ItemStats
from artifactsmmo_cli.ai.tiers.strategic_value import STRATEGIC_SCALE, strategic_value


class ProfileKind(Enum):
    COMBAT = "combat"
    UTILITY = "utility"


# wisdom/prospecting: openapi "1% per 10 points" -> 0.001 * SCALE = 1 unit
# (same derived rate strategic_value uses). inventory_space/haste: no
# commensurated rate exists yet, so a conservative small weight (1 unit),
# NOT the SCALE-parity deferral — profiles must not weight a bag like a
# weapon. All four tunable in Phase 5.
_EFF = 1

PROFILE_WEIGHTS: dict[ProfileKind, tuple[int, int, int, int, int]] = {
    #                    (combat,          wisdom, prospecting, inventory, haste)
    ProfileKind.COMBAT: (STRATEGIC_SCALE, 0, 0, 0, 0),
    ProfileKind.UTILITY: (STRATEGIC_SCALE, _EFF, _EFF, _EFF, _EFF),
}


def profile_weights(kind: ProfileKind) -> tuple[int, int, int, int, int]:
    """The strategic_value weight tuple for `kind`. Direct index: an
    unmapped kind is a programming error, not a runtime default."""
    return PROFILE_WEIGHTS[kind]


def score_for_profile(stats: ItemStats, kind: ProfileKind) -> int:
    """Profile-aware strategic value of an equippable — the scorer the tree's
    gear branch consumes (Phase 3). COMBAT ranks by combat content only;
    UTILITY gives efficiency stats their weight over the combat floor."""
    return strategic_value(stats, profile_weights(kind))
