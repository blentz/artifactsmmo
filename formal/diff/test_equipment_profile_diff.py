"""Differential lockstep: Python profile_for <-> Lean profileFor.

Skill-level roots — the only former utility-axis pursuit — were retired in epic
P3 (an under-skill gear's skill gate is a sub-task the walk opens by a grind,
not a tree-level skill root), so `profile_for` is now a constant COMBAT for every
root. The mirror stays: the harness imports the REAL profile_for from
src and checks it agrees with Lean profileFor over the remaining root kinds."""

import pytest

from artifactsmmo_cli.ai.tiers.equipment_profile import ProfileKind, profile_for
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachCharLevel

_XP = ReachCharLevel(level=20)
_GEAR = ObtainItem(code="fire_bow", quantity=1, slot="weapon_slot")

# root -> expected, matching Lean profileFor exactly: COMBAT for every root
# (utility axis retired in P3).
_CASES = [
    (_XP, ProfileKind.COMBAT),
    (_GEAR, ProfileKind.COMBAT),
]


@pytest.mark.parametrize("root, expected", _CASES)
def test_profile_for_matches_lean(root, expected):
    assert profile_for(root) is expected
