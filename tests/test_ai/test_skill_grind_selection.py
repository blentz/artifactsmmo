"""Unit tests for the pure skill_grind_selection core."""

from artifactsmmo_cli.ai.tiers.skill_grind_selection import (
    GrindCandidate,
    skill_grind_selection_pure,
)


def _c(code, skill="weaponcrafting", level=1, missing=0, obtainable=True):
    return GrindCandidate(code=code, craft_skill=skill, craft_level=level,
                          mats_missing=missing, obtainable=obtainable)


def test_craft_level_breaks_tie_on_equal_missing():
    # equal mats_missing -> higher craft_level wins (more XP).
    cands = [_c("dagger", level=1, missing=0), _c("staff", level=3, missing=0)]
    assert skill_grind_selection_pure("weaponcrafting", 5, cands) == "staff"


def test_fewest_missing_wins_over_higher_level():
    cands = [_c("dagger", level=1, missing=0), _c("staff", level=3, missing=2)]
    assert skill_grind_selection_pure("weaponcrafting", 5, cands) == "dagger"


def test_filters_cross_skill_in_level_and_unobtainable():
    cands = [
        _c("gear_item", skill="gearcrafting", level=1, missing=0),   # cross-skill
        _c("too_high", level=9, missing=0),                          # above level
        _c("unobtain", level=1, missing=0, obtainable=False),        # not obtainable
        _c("good", level=1, missing=0),
    ]
    assert skill_grind_selection_pure("weaponcrafting", 5, cands) == "good"


def test_empty_when_none_feasible():
    cands = [_c("gear", skill="gearcrafting"), _c("hi", level=9)]
    assert skill_grind_selection_pure("weaponcrafting", 5, cands) == ""


def test_full_tie_keeps_first_seen():
    # equal mats_missing AND equal craft_level -> keep the first-seen incumbent
    # (deterministic, no string tie-break). Exercises the `return False` leaf.
    cands = [_c("first", level=2, missing=1), _c("second", level=2, missing=1)]
    assert skill_grind_selection_pure("weaponcrafting", 5, cands) == "first"
