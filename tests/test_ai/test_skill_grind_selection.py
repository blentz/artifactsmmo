"""Unit tests for the pure skill_grind_selection core."""

from artifactsmmo_cli.ai.tiers.skill_grind_selection import (
    GrindCandidate,
    skill_grind_selection_pure,
)


def _c(code, skill="weaponcrafting", level=1, steps=0, obtainable=True, wanted=False,
       xp_positive=True):
    return GrindCandidate(code=code, craft_skill=skill, craft_level=level,
                          acquire_steps=steps, obtainable=obtainable, wanted=wanted,
                          xp_positive=xp_positive)


def test_wanted_beats_cheaper_throwaway():
    # The reported case: a WANTED keeper (copper_dagger, needs 2 mats) must beat a
    # throwaway (apprentice_gloves, 0 mats on hand). Wanted is the primary key.
    cands = [
        _c("apprentice_gloves", level=1, steps=0, wanted=False),
        _c("copper_dagger", level=1, steps=2, wanted=True),
    ]
    assert skill_grind_selection_pure("weaponcrafting", 5, cands) == "copper_dagger"


def test_wanted_first_regardless_of_candidate_order():
    # Same as above but wanted listed first — still wins (order-independent).
    cands = [
        _c("copper_dagger", level=1, steps=2, wanted=True),
        _c("apprentice_gloves", level=1, steps=0, wanted=False),
    ]
    assert skill_grind_selection_pure("weaponcrafting", 5, cands) == "copper_dagger"


def test_among_wanted_fewest_missing_still_wins():
    # Wanted is primary; among equally-wanted, the old (fewest-missing, level) key
    # still applies.
    cands = [
        _c("wanted_expensive", level=1, steps=5, wanted=True),
        _c("wanted_cheap", level=1, steps=1, wanted=True),
        _c("unwanted_free", level=1, steps=0, wanted=False),
    ]
    assert skill_grind_selection_pure("weaponcrafting", 5, cands) == "wanted_cheap"


def test_craft_level_breaks_tie_on_equal_missing():
    # equal acquire_steps -> higher craft_level wins (more XP).
    cands = [_c("dagger", level=1, steps=0), _c("staff", level=3, steps=0)]
    assert skill_grind_selection_pure("weaponcrafting", 5, cands) == "staff"


def test_fewest_missing_wins_over_higher_level():
    cands = [_c("dagger", level=1, steps=0), _c("staff", level=3, steps=2)]
    assert skill_grind_selection_pure("weaponcrafting", 5, cands) == "dagger"


def test_filters_cross_skill_in_level_and_unobtainable():
    cands = [
        _c("gear_item", skill="gearcrafting", level=1, steps=0),   # cross-skill
        _c("too_high", level=9, steps=0),                          # above level
        _c("unobtain", level=1, steps=0, obtainable=False),        # not obtainable
        _c("good", level=1, steps=0),
    ]
    assert skill_grind_selection_pure("weaponcrafting", 5, cands) == "good"


def test_empty_when_none_feasible():
    cands = [_c("gear", skill="gearcrafting"), _c("hi", level=9)]
    assert skill_grind_selection_pure("weaponcrafting", 5, cands) == ""


def test_full_tie_keeps_first_seen():
    # equal acquire_steps AND equal craft_level -> keep the first-seen incumbent
    # (deterministic, no string tie-break). Exercises the `return False` leaf.
    cands = [_c("first", level=2, steps=1), _c("second", level=2, steps=1)]
    assert skill_grind_selection_pure("weaponcrafting", 5, cands) == "first"


def test_zero_xp_rung_loses_to_costlier_paying_rung():
    # THE 2026-08-05 LIVELOCK in miniature. The grey rung has its materials
    # already in hand (steps=0), which wins EVERY ranking key it takes part
    # in — so only a filter can stop it. Robby ground the ash_plank equivalent
    # for 288 cycles at zero woodcutting xp.
    cands = [
        _c("ash_plank", level=1, steps=0, xp_positive=False),
        _c("spruce_plank", level=10, steps=6, xp_positive=True),
    ]
    assert skill_grind_selection_pure("weaponcrafting", 15, cands) == "spruce_plank"


def test_empty_when_every_in_level_rung_is_grey():
    # No paying rung at all -> "" rather than "pick the grey one anyway". The
    # empty result is what lets next_grind_goal fall through to the gather
    # fallback instead of committing the cycle to a zero-xp craft.
    cands = [
        _c("ash_plank", level=1, steps=0, xp_positive=False),
        _c("copper_dagger", level=2, steps=0, xp_positive=False, wanted=True),
    ]
    assert skill_grind_selection_pure("weaponcrafting", 15, cands) == ""


def test_grey_filter_outranks_the_wanted_preference():
    # `wanted` is the FIRST ranking key, so a wanted-but-grey rung would win the
    # ordering outright. The filter runs before ranking, so it does not.
    cands = [
        _c("wanted_but_grey", level=1, steps=0, wanted=True, xp_positive=False),
        _c("plain_but_paying", level=10, steps=5, wanted=False, xp_positive=True),
    ]
    assert skill_grind_selection_pure("weaponcrafting", 15, cands) == "plain_but_paying"


def test_deep_chain_loses_to_a_shallow_one_with_more_recipe_entries():
    # THE 2026-08-06 REWORK, in the unit the key now measures. Live R2D2 at
    # weaponcrafting 5: sticky_sword listed FEWER recipe entries (5 copper_bar)
    # than apprentice_gloves (6 feather) and so won the old `mats_missing` key —
    # but those 5 bars are 50 copper_ore gathers, so the real costs are 51
    # actions against 7. Counting ACTIONS instead of recipe slots inverts it,
    # which is the whole point of the change.
    cands = [
        _c("sticky_sword", level=5, steps=51),
        _c("apprentice_gloves", level=1, steps=7),
    ]
    assert skill_grind_selection_pure("weaponcrafting", 5, cands) == "apprentice_gloves"


def test_craft_level_is_only_a_tie_break_under_cost():
    # A higher craft_level is preferred ONLY when the chains cost the same.
    # It must never buy its way past a genuinely cheaper chain — that ordering
    # is what let a 51-action rung outrank a 7-action one for months.
    same = [_c("cheap_low", level=1, steps=7), _c("dear_high", level=5, steps=51)]
    assert skill_grind_selection_pure("weaponcrafting", 15, same) == "cheap_low"
    tied = [_c("low", level=1, steps=7), _c("high", level=5, steps=7)]
    assert skill_grind_selection_pure("weaponcrafting", 15, tied) == "high"
