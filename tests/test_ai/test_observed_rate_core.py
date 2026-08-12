"""A measured XP rate belongs to the level it was measured at.

The defect these pin, measured live on 2026-08-09: `cheapest_path_to_level` reused
one learned rate at every rung of a 38-level walk, which deleted the game's
published grey-mob rule (0 XP ten or more levels above a monster) from every
projection that had any observation at all. C3P0 projected reaching level 50 by
farming a LEVEL 4 slime at a flat 7.0 XP per cycle from rung 12 to rung 49.
"""

import pytest

from artifactsmmo_cli.ai.learning.observed_rate_core import (
    rescale_observed_xp,
    sample_level,
)
from artifactsmmo_cli.ai.monster_catalog import MonsterCatalog


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


class TestSampleLevel:
    """Which single level a multi-level measurement is restated FROM.

    Found by the spec's own ratification pass, not by a failing run: the clause
    said "the rounded mean" and the code said `round(...)`, which is half-to-EVEN.
    A half-integer mean straddling the grey step therefore decided, on parity
    alone, between a finite restated rate and a zero one -- and a zero one can stop
    the walk. The tiebreak now goes the way the module resolves everything else.
    """

    def test_no_recorded_level_is_absent_rather_than_a_guess(self):
        """Distinct from every numeric answer: S-018 makes an unlevelled
        measurement ABSENT, which falls back to the published prediction, NOT a
        rate restated to zero."""
        assert sample_level([]) is None

    def test_a_single_level_is_itself(self):
        assert sample_level([16]) == 16

    @pytest.mark.parametrize(
        ("levels", "expected"),
        [([16, 17], 16), ([17, 18], 17), ([16, 16, 17, 17], 16)],
    )
    def test_a_tie_resolves_DOWNWARD(self, levels, expected):
        """The whole point. A lower sample level carries a HIGHER published award
        there, hence a SMALLER restated rate -- the direction that does not
        manufacture reach. `[17, 18]` is the case Python's half-to-even would send
        UP, so this pins a real difference and not just a restatement of `round`."""
        assert sample_level(levels) == expected

    def test_the_half_to_even_disagreement_is_real(self):
        """Pins that the two rules genuinely differ, so the choice above is load
        bearing rather than a no-op rename. If this ever passes vacuously the
        tiebreak test above is testing nothing."""
        assert round(35 / 2) == 18
        assert sample_level([17, 18]) == 17

    @pytest.mark.parametrize(
        ("levels", "expected"),
        [([16, 16, 17], 16), ([16, 17, 17], 17), ([10, 20, 31], 20)],
    )
    def test_a_non_tie_rounds_to_the_nearest(self, levels, expected):
        """Away from the tie the rule is ordinary nearest-rounding, so the
        tiebreak is not smuggling in a floor."""
        assert sample_level(levels) == expected

    def test_no_binary_float_can_move_a_tie(self):
        """Computed in integers. A mean of 0.1-style thirds is exactly the shape
        that makes a float comparison land on the wrong side of a half."""
        assert sample_level([1] * 3 + [2] * 3) == 1
        assert sample_level([49, 50]) == 49

    @pytest.mark.parametrize("bogus", [0, -3])
    def test_a_level_below_one_is_not_a_level(self, bogus):
        """Characters start at 1, so the API cannot issue a smaller level. A zero
        is the ABSENCE of a reading, not a reading of zero, and it is dropped like
        a missing one -- otherwise it drags the mean toward a value the published
        award is not even defined at."""
        assert sample_level([bogus, 20, 20]) == 20

    def test_only_bogus_levels_is_the_same_as_none(self):
        """The degenerate arm. Not zero, not an error: ABSENT, so S-008's fallback
        to the published prediction applies and the walk continues."""
        assert sample_level([0]) is None
        assert sample_level([0, 0, -1]) is None

    def test_a_zero_would_otherwise_be_undefined_not_merely_wrong(self):
        """Why this is excluded rather than clamped. The published award divides
        the monster's level by the character's, so at a sample level of zero there
        is no award to compare -- neither positive nor non-positive, which is the
        one gap both of the restatement's degenerate rules claim."""
        assert sample_level([0, 1]) == 1


class TestPublishedPenaltyBand:
    """The band the published prose never assigns, ratified 2026-08-11 as FULL.

    The game documents three cases -- at or below the monster's level 100%, five or
    more above 70%, ten or more above 0% -- and never says what a gap of 1..4 does.
    That is the ORDINARY case, not a corner: a climbing character out-levels most of
    its candidate pool by one to four, so the argmax that picks a rung's monster had
    no defined reward across most of its own pool.
    """

    @staticmethod
    def _award(gap):
        catalog = MonsterCatalog(levels={"m": 20}, hp={"m": 200}, types={"m": "normal"})
        return catalog.xp_per_kill("m", 20 + gap, wisdom=0)

    @pytest.mark.parametrize("gap", [1, 2, 3, 4])
    def test_a_gap_of_one_to_four_keeps_the_full_penalty_band(self, gap):
        """Lower-bounded steps: the 70% band begins AT five, so everything below it
        is still full. The award still falls across 1..4 because the formula's base
        term divides by the character's level -- what must NOT change is the PENALTY,
        so the drop is gradual rather than the 30% cliff the other reading gives."""
        at_gap = self._award(gap)
        at_five = self._award(5)
        assert at_gap > at_five, (gap, at_gap, at_five)

    def test_the_seventy_percent_band_really_does_start_at_five(self):
        """Pins that the band above is not vacuous: gap 4 to gap 5 is where the
        penalty actually bites, and it is a cliff, not a slope."""
        drop_inside = self._award(3) - self._award(4)
        cliff = self._award(4) - self._award(5)
        assert cliff > drop_inside * 2, (drop_inside, cliff)

    def test_ten_levels_above_awards_nothing(self):
        assert self._award(10) == 0
        assert self._award(9) > 0


class TestPublishedFormulaFactors:
    """`wisdom_bonus` and `monster_multiplier`, checked against the published docs
    on 2026-08-11 rather than inferred.

    Both were factors the spec quoted and never defined, and the misreading is not
    subtle: `wisdom_bonus` read as "the bonus conferred" rather than "the factor" is
    ZERO for a zero-wisdom character, which zeroes every award and turns an ordinary
    climb into an unreachable target. The published scale is +0.1% per point, i.e.
    `1 + wisdom * 0.001` -- a THOUSANDTH, where an adversary's own recommendation
    said a hundredth.
    """

    @staticmethod
    def _cat(mtype="normal"):
        return MonsterCatalog(levels={"m": 20}, hp={"m": 200}, types={"m": mtype})

    def test_zero_wisdom_is_the_identity_not_zero(self):
        assert self._cat().xp_per_kill("m", 20, wisdom=0) > 0

    def test_wisdom_scales_by_a_thousandth_per_point(self):
        """1000 wisdom doubles the award (1 + 1000*0.001 = 2.0). Under the
        hundredth reading it would be 11x, so this separates the two outright."""
        base = self._cat().xp_per_kill("m", 20, wisdom=0)
        assert self._cat().xp_per_kill("m", 20, wisdom=1000) == pytest.approx(
            2 * base, abs=1)

    @pytest.mark.parametrize(("mtype", "factor"), [("normal", 1.0), ("elite", 1.4),
                                                   ("boss", 2.0)])
    def test_the_published_monster_type_multipliers(self, mtype, factor):
        base = self._cat("normal").xp_per_kill("m", 20, wisdom=0)
        assert self._cat(mtype).xp_per_kill("m", 20, wisdom=0) == pytest.approx(
            factor * base, abs=1)
