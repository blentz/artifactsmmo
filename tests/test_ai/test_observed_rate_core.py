"""A measured XP rate belongs to the level it was measured at.

The defect these pin, measured live on 2026-08-09: `cheapest_path_to_level` reused
one learned rate at every rung of a 38-level walk, which deleted the game's
published grey-mob rule (0 XP ten or more levels above a monster) from every
projection that had any observation at all. C3P0 projected reaching level 50 by
farming a LEVEL 4 slime at a flat 7.0 XP per cycle from rung 12 to rung 49.
"""

import pytest

from artifactsmmo_cli.ai.learning.observed_rate_core import rescale_observed_xp


class TestRescaleObservedXp:
    def test_same_level_is_the_identity(self):
        """Restating a rate for the level it was already measured at must not
        move it. If this ever drifts, every projection silently re-scales itself
        for no reason."""
        assert rescale_observed_xp(7.0, 7, 7) == 7.0

    def test_the_grey_boundary_zeroes_the_rate(self):
        """THE HEADLINE CASE, with C3P0's real numbers. `green_slime` is level 4
        and awarded 7 XP at character level 12, where the 100 samples averaging
        7.0/cycle were taken. The published rule puts its award at 0 from level 14
        up. The measured rate must not survive that boundary."""
        assert rescale_observed_xp(7.0, 7, 0) == 0.0

    def test_a_partial_penalty_scales_proportionally(self):
        """Between the boundaries the award merely shrinks, and so must the rate.
        Half the XP per kill is half the XP per cycle — the ratio is dimensionless,
        so the result stays whole-loop XP per executed action."""
        assert rescale_observed_xp(7.0, 10, 5) == 3.5

    def test_a_rate_measured_low_scales_UP_toward_a_richer_monster(self):
        """The correction is not a one-way dampener. A rate measured while the
        character was under-levelled for a monster is an UNDER-estimate at a
        higher rung, and restating it must raise it. A version that only ever
        reduced would be a different (and wrong) function that these boundary
        cases alone would not distinguish."""
        assert rescale_observed_xp(2.0, 5, 20) == 8.0

    @pytest.mark.parametrize("rate", [0.0, -0.5, -11.1])
    def test_a_non_positive_measured_rate_is_declined(self, rate):
        """-11.1 is R2D2's real `red_slime` rate over 100 samples. A negative XP
        rate should not be representable at all, but while it is, it is not
        evidence of a positive one and must not be laundered into a small
        positive by a scaling factor greater than one."""
        assert rescale_observed_xp(rate, 10, 20) == 0.0

    @pytest.mark.parametrize("observed_award", [0, -3])
    def test_an_incoherent_observation_is_declined(self, observed_award):
        """A positive rate recorded where the formula says the monster awarded
        NOTHING. The two disagree, there is no ratio to take, and the direction of
        safety here is the opposite of the acquisition bound's: this figure feeds
        how FAR a candidate is projected to get, and the objective prefers
        candidates that get further, so over-promising captures the decision."""
        assert rescale_observed_xp(7.0, observed_award, 20) == 0.0

    def test_zero_target_award_needs_no_special_case(self):
        """Pins the deliberate ABSENCE of a branch. `xp_at_target_level == 0` is
        the grey rule itself and the ordinary arithmetic already returns 0.0; a
        guard for it would be a second encoding of the same fact, free to drift
        from the first. Distinct from the two declines above, which return 0.0
        for a reason the arithmetic could NOT have produced."""
        assert rescale_observed_xp(7.0, 7, 0) == 0.0
        assert rescale_observed_xp(0.001, 1000000, 0) == 0.0
