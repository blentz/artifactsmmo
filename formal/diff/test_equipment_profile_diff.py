"""Differential lockstep: Python profile_for <-> Lean profileFor (the 6
category x adequacy cases). Binds the real src selector.

Mirrors Formal/EquipmentProfile.lean's truth table exactly: the plan-gate
combat floor forces COMBAT whenever the band is inadequate; once adequate a
utility objective (ReachSkillLevel) selects UTILITY, and every other root
(ReachCharLevel xp grind, ObtainItem gear) stays COMBAT. The harness imports
the REAL profile_for from src -- it never reimplements the selector."""

import pytest

from artifactsmmo_cli.ai.tiers.equipment_profile import ProfileKind, profile_for
from artifactsmmo_cli.ai.tiers.meta_goal import (
    ObtainItem,
    ReachCharLevel,
    ReachSkillLevel,
)

_SKILL = ReachSkillLevel(skill="weaponcrafting", level=10)
_XP = ReachCharLevel(level=20)
_GEAR = ObtainItem(code="fire_bow", quantity=1, slot="weapon_slot")

# (root, band_adequate) -> expected, matching Lean profileFor exactly.
_CASES = [
    (_SKILL, True, ProfileKind.UTILITY),
    (_XP, True, ProfileKind.COMBAT),
    (_GEAR, True, ProfileKind.COMBAT),
    (_SKILL, False, ProfileKind.COMBAT),
    (_XP, False, ProfileKind.COMBAT),
    (_GEAR, False, ProfileKind.COMBAT),
]


@pytest.mark.parametrize("root, adequate, expected", _CASES)
def test_profile_for_matches_lean(root, adequate, expected):
    assert profile_for(root, adequate) is expected
