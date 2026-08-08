"""Cycles to raise a skill to a gate — the price of a prerequisite.

The unit is CYCLES, which are actions: `skill_xp_per_cycle` is measured per
executed cycle, so an xp deficit divided by it yields actions with no seconds
anywhere on the path. That is what lets this term be ADDED to an acquisition
cost at all, and every case below is stated in those terms.
"""

from artifactsmmo_cli.ai.skill_grind_cost_core import skill_grind_cycles


def test_a_met_gate_costs_nothing() -> None:
    """Zero when the skill already clears the gate, so a caller can add this
    term UNCONDITIONALLY and have it vanish exactly when the skill is not a
    gate. A caller forced to branch on 'is this gated?' would be a second place
    the gate is decided, and the two could disagree."""
    assert skill_grind_cycles(10, 0, 500, 10, 25.0) == 0
    assert skill_grind_cycles(12, 0, 500, 10, 25.0) == 0


def test_one_level_costs_the_remaining_xp_over_the_rate() -> None:
    """400 xp still owed at 25 xp/cycle is 16 cycles."""
    assert skill_grind_cycles(9, 100, 500, 10, 25.0) == 16


def test_progress_into_the_current_level_is_credited() -> None:
    """Half way up costs half as much. The bound tracks WORK REMAINING, not a
    static per-level price — the same property that makes a purchase cheap when
    the currency is already held."""
    fresh = skill_grind_cycles(9, 0, 500, 10, 25.0)
    halfway = skill_grind_cycles(9, 250, 500, 10, 25.0)
    assert fresh == 20
    assert halfway == 10


def test_further_levels_each_cost_a_full_level() -> None:
    """The API exposes no per-level xp curve, so levels beyond the next are
    assumed to cost what the current one does — the same assumption
    `cheapest_path_to_level` makes for character levels and records as a known
    limit. It UNDER-estimates on a rising curve, which is the safe direction for
    a lower bound whose consumers prune with it."""
    # 5 -> 10 with a full level owed: 5 levels x 500 xp / 25 = 100 cycles.
    assert skill_grind_cycles(5, 0, 500, 10, 25.0) == 100


def test_a_faster_grind_costs_fewer_cycles() -> None:
    """Monotone in the observed rate. A character that has learned a better
    grind for a skill prices its gates lower, which is the whole reason the rate
    is observed rather than assumed."""
    slow = skill_grind_cycles(5, 0, 500, 10, 10.0)
    fast = skill_grind_cycles(5, 0, 500, 10, 50.0)
    assert slow > fast


def test_a_higher_gate_costs_more() -> None:
    """Monotone in the gate. A bound that were not would let the walk prefer a
    deeper tier, which is the `acquire_steps` defect class this project has hit
    three times."""
    assert (skill_grind_cycles(5, 0, 500, 20, 25.0)
            > skill_grind_cycles(5, 0, 500, 10, 25.0))


def test_a_partial_cycle_still_costs_a_whole_action() -> None:
    """Rounded UP. One xp short of the gate is still a cycle the character has
    to spend, and the objective is exact integers (S-013)."""
    assert skill_grind_cycles(9, 499, 500, 10, 25.0) == 1
    assert skill_grind_cycles(9, 400, 500, 10, 30.0) == 4   # 100/30 = 3.33 -> 4


def test_xp_beyond_the_level_requirement_does_not_go_negative() -> None:
    """A skill sitting on more xp than its level requires (the level-up has
    landed in state but the level field has not yet caught up) contributes 0 to
    the current level rather than a NEGATIVE deficit that would discount the
    levels above it.

    This is the same shape as the `delta_xp` defect fixed in `25cf28da`, where a
    naive difference across a level boundary produced negative xp for 30 of
    22,333 rows. A subtraction that can go negative across a boundary is worth
    guarding wherever it appears."""
    assert skill_grind_cycles(9, 600, 500, 10, 25.0) == 0
    # ...and the levels ABOVE the current one still cost full price.
    assert skill_grind_cycles(9, 600, 500, 11, 25.0) == 20
