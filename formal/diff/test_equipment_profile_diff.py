"""Differential lockstep: Python profile_for <-> Lean profileFor.

Skill-level roots — the only former utility-axis pursuit — were retired in epic
P3 (under-skill gear grinds planner-natively via the LevelSkill action, not a
tree-level skill root), so `profile_for` is now a constant COMBAT for every root
and adequacy. The mirror stays: the harness imports the REAL profile_for from
src and checks it agrees with Lean profileFor over the remaining root kinds."""

import pytest

from artifactsmmo_cli.ai.tiers.equipment_profile import ProfileKind, profile_for
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachCharLevel

_XP = ReachCharLevel(level=20)
_GEAR = ObtainItem(code="fire_bow", quantity=1, slot="weapon_slot")

# (root, band_adequate) -> expected, matching Lean profileFor exactly: COMBAT
# for every root and adequacy (utility axis retired in P3).
_CASES = [
    (_XP, True, ProfileKind.COMBAT),
    (_GEAR, True, ProfileKind.COMBAT),
    (_XP, False, ProfileKind.COMBAT),
    (_GEAR, False, ProfileKind.COMBAT),
]


@pytest.mark.parametrize("root, adequate, expected", _CASES)
def test_profile_for_matches_lean(root, adequate, expected):
    assert profile_for(root, adequate) is expected
