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
    # Among equally-wanted, every rate ties (the credit zeroes them all), so the
    # final RAW acquire_steps tie-break decides. Same answer, different reason.
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


def test_craft_level_buys_its_way_past_a_cheaper_chain_only_by_paying_for_it():
    # A higher craft_level DOES outrank a cheaper chain now -- but only when
    # its rate (craft_level per effective step) is at least as high as the
    # cheaper chain's, not merely "more": at an exact rate tie the craft_level
    # tie-break still favors the higher level even if its raw acquire_steps is
    # larger, which "pays more" would not cover. This test replaced
    # `test_craft_level_is_only_a_tie_break_under_cost` on 2026-08-14: that test
    # passed under both orderings while asserting the opposite of what the code
    # does, which is worse than failing.
    # 5/51 = 0.098 loses to 1/7 = 0.143 -- the level does NOT buy its way past.
    loses = [_c("cheap_low", level=1, steps=7), _c("dear_high", level=5, steps=51)]
    assert skill_grind_selection_pure("weaponcrafting", 15, loses) == "cheap_low"
    # 5/20 = 0.250 beats 1/7 = 0.143 -- same level gap, cheaper enough to win.
    wins = [_c("cheap_low", level=1, steps=7), _c("dear_high", level=5, steps=20)]
    assert skill_grind_selection_pure("weaponcrafting", 15, wins) == "dear_high"
    # equal cost -> the higher level wins on the RATE itself (5*7 = 35 against
    # 1*7 = 7), NOT on the craft_level tie-break: that clause is reachable only
    # when the rates tie, as in test_craft_level_breaks_tie_on_equal_missing
    # above. Corrected 2026-08-15; the assertion is unchanged.
    tied = [_c("low", level=1, steps=7), _c("high", level=5, steps=7)]
    assert skill_grind_selection_pure("weaponcrafting", 15, tied) == "high"


def test_a_costlier_chain_wins_when_it_pays_proportionally_more_xp():
    """THE 2026-08-14 SYMPTOM. Live Lor, weaponcrafting 8: apprentice_gloves
    priced 13 actions at craft level 1 (rate 0.077) and sticky_dagger priced 59
    at craft level 5 (rate 0.085). Cheapest-chain picked the gloves, and the
    grind sat at weaponcrafting 8 for 757 cycles crafting a level-1 rung.

    This test and
    `test_craft_level_buys_its_way_past_a_cheaper_chain_only_by_paying_for_it`
    (added by this same change) are the two tests in the file that distinguish
    the two orderings. All 14 pre-existing tests pass identically under both --
    this key was silently wrong for months because nothing in the suite could
    tell the difference. Verified by working all 14 through both orderings by
    hand while planning this change.
    """
    cands = [_c("apprentice_gloves", level=1, steps=13),
             _c("sticky_dagger", level=5, steps=59)]
    assert skill_grind_selection_pure("weaponcrafting", 8, cands) == "sticky_dagger"


def test_a_wanted_rung_wins_on_rate_because_its_chain_is_owed_anyway():
    """A wanted rung's chain is work the objective owes regardless of the
    grind, so the grind's MARGINAL cost for it is zero -- it wins the rate
    comparison rather than winning by lexicographic fiat. 500 steps against 2
    is the shape that would look absurd under raw cost and is correct under
    marginal cost."""
    cands = [_c("throwaway", level=5, steps=2, wanted=False),
             _c("committed_weapon", level=1, steps=500, wanted=True)]
    assert skill_grind_selection_pure("weaponcrafting", 8, cands) == "committed_weapon"


def test_raw_cost_still_separates_two_rungs_the_objective_both_wants():
    """The credit zeroes effective steps for EVERY wanted rung, so they all tie
    on rate. Two rungs both owed are not equally near -- the cheaper is reached
    sooner -- so RAW acquire_steps is the final tie-break. Without it this falls
    through to insertion order, which is arbitrary."""
    cands = [_c("owed_far", level=3, steps=40, wanted=True),
             _c("owed_near", level=3, steps=4, wanted=True)]
    assert skill_grind_selection_pure("weaponcrafting", 8, cands) == "owed_near"


def test_a_free_throwaway_does_not_tie_its_way_past_a_wanted_keeper():
    """Both credit to zero effective steps, so the RATE comparison ties at
    zero. Without `wanted` as the first tie-break under the rate, the incumbent
    survives on insertion order -- which is the June 2026
    apprentice_gloves-over-copper_dagger inversion returning through the back
    door."""
    cands = [_c("free_throwaway", level=1, steps=0, wanted=False),
             _c("copper_dagger", level=1, steps=2, wanted=True)]
    assert skill_grind_selection_pure("weaponcrafting", 8, cands) == "copper_dagger"


def test_out_of_level_candidates_cannot_change_the_selection():
    """THE THEOREM `build_selectable_grind_candidates`' in-level hoist rests on.

    That function stopped pricing out-of-level rungs (69 in-skill craftables
    down to 10 for live R2D2 at weaponcrafting 9, and each skipped rung is a
    full route walk plus a full recursive obtainability walk — the producer's own
    47.0s of a 67.3s from-scratch `greater_wooden_staff` search, under a
    `LevelSkill.is_applicable` that was 48.2s of it; profile 2026-08-13). That hoist
    is only sound because THIS core discards the same rows itself, before
    `_beats` ever ranks them. So: appending an out-of-level candidate that would
    win every ranking key outright — wanted, zero-cost, highest level — must
    leave the answer untouched. If this core ever ranked such a row, the hoist
    upstream would silently change which rung the grind picks.
    """
    in_level = [_c("copper_dagger", level=1, steps=7)]
    would_win = _c("iron_dagger", level=10, steps=0, wanted=True)
    assert skill_grind_selection_pure("weaponcrafting", 3, in_level) == "copper_dagger"
    assert skill_grind_selection_pure(
        "weaponcrafting", 3, [*in_level, would_win]) == "copper_dagger"
    # And with NOTHING in level, an out-of-level row must not rescue the answer.
    assert skill_grind_selection_pure("weaponcrafting", 3, [would_win]) == ""
