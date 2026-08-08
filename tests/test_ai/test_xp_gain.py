"""XP actually gained across a level-up.

`new_xp - prev_xp` reports the cycles that earned the MOST as large losses,
because the server resets xp into the new level. Live 2026-08-07: 30 of 22333
character rows negative, every one a level-up.
"""

from artifactsmmo_cli.ai.learning.xp_gain import xp_gained


class TestSameLevel:
    def test_plain_difference_is_exact(self):
        assert xp_gained(5, 100, 500, 5, 130) == 30

    def test_no_gain_reads_zero(self):
        assert xp_gained(5, 100, 500, 5, 100) == 0

    def test_max_xp_is_not_consulted(self):
        """While the level holds, the threshold is irrelevant — so a caller with
        no threshold to hand still gets an exact answer."""
        assert xp_gained(5, 100, 0, 5, 130) == 30


class TestOneLevelUp:
    def test_counts_the_remainder_plus_the_carryover(self):
        """C3P0's real 10->11 crossing, which was recorded as -2097."""
        assert xp_gained(10, 2097, 2100, 11, 0) == 3

    def test_a_big_hit_that_overflows_the_level(self):
        assert xp_gained(6, 934, 950, 7, 9) == 25

    def test_landing_exactly_on_the_threshold(self):
        assert xp_gained(3, 90, 100, 4, 0) == 10

    def test_result_is_never_negative_for_a_real_crossing(self):
        """The property the naive difference violated: crossing a level cannot
        lose xp. `prev_xp <= prev_max_xp` and `new_xp >= 0` on any real reading,
        so the sum is non-negative by construction."""
        for prev_xp in range(0, 101, 10):
            for new_xp in range(0, 51, 10):
                assert xp_gained(4, prev_xp, 100, 5, new_xp) >= 0


class TestUnresolvable:
    def test_two_levels_at_once_is_unknown(self):
        """Resolving it needs the max_xp of every level crossed, and the API only
        reports the CURRENT level's threshold. Never observed in 22333 cycles."""
        assert xp_gained(4, 50, 100, 6, 10) is None

    def test_a_level_going_down_is_unknown(self):
        """Not something the server does, so the observation pair is untrustworthy
        rather than a negative gain."""
        assert xp_gained(6, 50, 100, 5, 10) is None

    def test_none_is_unknown_and_not_zero(self):
        """The distinction the caller stores: 'could not tell' must stay separate
        from 'earned nothing', or an unmeasurable cycle silently drags the mean
        down exactly like the negative it replaced."""
        unresolvable = xp_gained(4, 50, 100, 6, 10)
        no_gain = xp_gained(5, 100, 500, 5, 100)
        assert unresolvable is None
        assert no_gain == 0
        assert unresolvable != no_gain
