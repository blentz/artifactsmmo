"""Pure cores of the progression-tree selector (spec 2026-07-06).

Mirrored by Formal/ProgressionTree.lean; the PROGRESSION_TREE_MUTATIONS
group binds these tests to the source.

WAVE 3b: the resolution walk replaced the scored ranking, and with it the whole
gear-argmax/aging family (`branch_pick_pure`, `gear_target_pick`,
`_gear_pref_key`, `_scaled_pref_key`, `_scaled_weights`, `focus_aging_pick`,
`focus_aging_order`, `interleave_due`, `_NO_SYNERGY`/`_NO_ACHIEVABILITY`/
`_NO_ROLE`) left the module — see the re-derived deletion list §4/§5. What
remains here is what `ai/decisions/root.py` actually calls: `milestone_pure`,
`potion_type_weight`, `FOCUS_FLAT`, `falloff`, `dhondt_step`, and the
`GearCandidate` record `tiers/progression_tree.py` still assembles."""

from dataclasses import fields
from fractions import Fraction

from artifactsmmo_cli.ai.tiers.progression_tree_core import (
    FOCUS_FLAT,
    FOCUS_FLOOR,
    FOCUS_SPAN,
    POTION_TYPE_WEIGHTS,
    GearCandidate,
    dhondt_step,
    falloff,
    milestone_pure,
    potion_type_weight,
)


class TestMilestone:
    def test_next_band_boundary(self):
        assert milestone_pure(1) == 10
        assert milestone_pure(9) == 10
        assert milestone_pure(10) == 20
        assert milestone_pure(11) == 20
        assert milestone_pure(39) == 40
        assert milestone_pure(49) == 50

    def test_capped_at_fifty(self):
        assert milestone_pure(50) == 50
        assert milestone_pure(55) == 50

    def test_strictly_above_level_below_cap(self):
        for level in range(1, 50):
            m = milestone_pure(level)
            assert level < m <= 50


class TestPotionWeights:
    def test_health_is_maximal(self):
        assert all(POTION_TYPE_WEIGHTS["hp_restore"] >= w
                   for w in POTION_TYPE_WEIGHTS.values())

    def test_lookup_and_unknown(self):
        assert potion_type_weight("hp_restore") == Fraction(1)
        assert potion_type_weight("charm_of_unmodeled") == Fraction(0)

    def test_all_weights_exact_nonnegative(self):
        for w in POTION_TYPE_WEIGHTS.values():
            assert isinstance(w, Fraction) and w >= 0


def test_falloff_flat_full_weight_through_flat_window():
    for level in range(0, FOCUS_FLAT + 1):
        assert falloff(level) == Fraction(1)


def test_falloff_reaches_floor_at_and_after_span_end():
    end = FOCUS_FLAT + FOCUS_SPAN
    assert falloff(end) == FOCUS_FLOOR
    assert falloff(end + 50) == FOCUS_FLOOR


def test_falloff_monotone_non_increasing():
    prev = falloff(0)
    for level in range(1, FOCUS_FLAT + FOCUS_SPAN + 20):
        cur = falloff(level)
        assert cur <= prev
        prev = cur


def test_falloff_strictly_decreases_inside_decay_window():
    a = falloff(FOCUS_FLAT + 1)
    b = falloff(FOCUS_FLAT + FOCUS_SPAN - 1)
    assert b < a < Fraction(1)


def test_falloff_floor_is_positive():
    assert FOCUS_FLOOR > 0


def test_dhondt_step_empty_is_none():
    assert dhondt_step([], {}) is None


def test_dhondt_step_single_key():
    assert dhondt_step([("a", Fraction(3))], {}) == "a"
    assert dhondt_step([("a", Fraction(3))], {"a": 99}) == "a"


def test_dhondt_step_no_seats_picks_max_quotient():
    # seats={}: every quotient is w/1, so the heaviest weight wins.
    w = [("a", Fraction(1)), ("b", Fraction(3)), ("c", Fraction(2))]
    assert dhondt_step(w, {}) == "b"


def test_dhondt_step_seats_can_flip_the_winner():
    # heavy key already seated enough that its quotient drops below the light
    # key's: 3/(3+1)=3/4 < 1/(0+1)=1 -> the light key wins this seat.
    w = [("a", Fraction(1)), ("b", Fraction(3))]
    assert dhondt_step(w, {}) == "b"           # unseated: heavy wins
    assert dhondt_step(w, {"b": 3}) == "a"     # heavy saturated: light flips in


def test_dhondt_step_is_order_independent():
    fwd = [("a", Fraction(5)), ("b", Fraction(2)), ("c", Fraction(1))]
    rev = list(reversed(fwd))
    for seats in ({}, {"a": 4}, {"a": 2, "b": 1}, {"c": 3}):
        assert dhondt_step(fwd, seats) == dhondt_step(rev, seats)


def test_dhondt_step_full_tie_breaks_on_the_HIGHER_key():
    """Split out of the wave-3a `test_tie_break_flips_under_achievability_
    dhondt_vs_argmax`, which pinned this against `gear_target_pick`'s opposite
    convention. That comparand is gone; the `dhondt_step` half is not, and it is
    the half the live `WhichSlotIsFurthestBehind._aged_head` depends on.

    `max` over `(quotient, weight, key)` breaks an exact tie by DESCENDING key
    string, so of two identically-weighted, identically-seated slots the LATER
    slot name wins — the live `ring1_slot`/`ring2_slot` duplicate-slot shape.
    Order-independent, so both list orders give the same answer."""
    w = [("ring1_slot", Fraction(100)), ("ring2_slot", Fraction(100))]
    assert dhondt_step(w, {}) == "ring2_slot"
    assert dhondt_step(list(reversed(w)), {}) == "ring2_slot"
    # ...and it really is the KEY doing the work: seat the higher key once and
    # the tie is no longer a tie, so the lower key takes this seat.
    assert dhondt_step(w, {"ring2_slot": 1}) == "ring1_slot"


def test_modulating_weights_absent_from_gear_candidate_identity():
    """A modulating weight is never candidate identity — it must not enter
    GearCandidate's fields or its repr (the currency-grind lesson: a moving
    value inside identity resets sticky keying). Structurally excluded."""
    names = {f.name for f in fields(GearCandidate)}
    assert names == {"slot", "code", "gain", "level"}
    # two candidates equal but for a weighting context have identical repr
    a = GearCandidate(slot="s", code="c", gain=Fraction(5), level=1)
    b = GearCandidate(slot="s", code="c", gain=Fraction(5), level=1)
    assert repr(a) == repr(b)
