"""Pure cores of the progression-tree selector (spec 2026-07-06).

Mirrored by Formal/ProgressionTree.lean; the PROGRESSION_TREE_MUTATIONS
group binds these tests to the source."""

from fractions import Fraction

from artifactsmmo_cli.ai.tiers.progression_tree_core import (
    FOCUS_FLAT,
    FOCUS_FLOOR,
    FOCUS_SPAN,
    POTION_TYPE_WEIGHTS,
    Branch,
    GearCandidate,
    branch_pick_pure,
    falloff,
    gear_target_pick,
    interleave_due,
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


class TestBranchPick:
    def test_truth_table(self):
        # gear iff (not adequate) and (target exists) — all four cases:
        assert branch_pick_pure(False, True) is Branch.GEAR
        assert branch_pick_pure(False, False) is Branch.XP
        assert branch_pick_pure(True, True) is Branch.XP
        assert branch_pick_pure(True, False) is Branch.XP


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


class TestGearTargetPick:
    def test_empty_is_none(self):
        assert gear_target_pick([]) is None

    def test_biggest_gain_wins(self):
        a = GearCandidate(slot="weapon_slot", code="iron_sword", gain=Fraction(30), level=10)
        b = GearCandidate(slot="boots_slot", code="iron_boots", gain=Fraction(5), level=10)
        assert gear_target_pick([a, b]) == a
        assert gear_target_pick([b, a]) == a  # insertion-order independent

    def test_gain_tie_higher_level_wins(self):
        a = GearCandidate(slot="ring1_slot", code="old_ring", gain=Fraction(4), level=5)
        b = GearCandidate(slot="ring1_slot", code="new_ring", gain=Fraction(4), level=15)
        assert gear_target_pick([a, b]) == b
        assert gear_target_pick([b, a]) == b

    def test_full_tie_falls_to_code_then_slot(self):
        # Semantically identical candidates: code is a PURE disambiguator
        # (picker-tie precedent — canonical total order, not hash roulette).
        a = GearCandidate(slot="ring1_slot", code="aaa_ring", gain=Fraction(4), level=5)
        b = GearCandidate(slot="ring1_slot", code="bbb_ring", gain=Fraction(4), level=5)
        assert gear_target_pick([a, b]) == a
        assert gear_target_pick([b, a]) == a
        c = GearCandidate(slot="ring2_slot", code="aaa_ring", gain=Fraction(4), level=5)
        assert gear_target_pick([c, a]) == a
        assert gear_target_pick([a, c]) == a


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


def test_interleave_empty_is_none():
    assert interleave_due([], 0) is None


def test_interleave_single_key_always_that_key():
    for c in range(0, 20):
        assert interleave_due([("a", Fraction(3))], c) == "a"


def test_interleave_equal_weights_alternate():
    w = [("a", Fraction(1)), ("b", Fraction(1))]
    got = [interleave_due(w, c) for c in range(6)]
    # 1:1 split, deterministic
    assert got.count("a") == 3 and got.count("b") == 3
    assert got == [interleave_due(w, c) for c in range(6)]  # reproducible


def test_interleave_proportional_over_window():
    # weight 3:1 -> "a" gets ~3x the cycles of "b" over a full window
    w = [("a", Fraction(3)), ("b", Fraction(1))]
    got = [interleave_due(w, c) for c in range(4)]
    assert got.count("a") == 3 and got.count("b") == 1


def test_interleave_dominant_weight_gets_every_cycle_when_others_tiny():
    # 1000:1 -> "b" is due at most once per 1001 cycles; the first cycles are all "a"
    w = [("a", Fraction(1000)), ("b", Fraction(1))]
    assert all(interleave_due(w, c) == "a" for c in range(8))


def test_interleave_is_pure_function_of_cycle():
    w = [("a", Fraction(5)), ("b", Fraction(2)), ("c", Fraction(1))]
    assert [interleave_due(w, c) for c in range(20)] == [interleave_due(w, c) for c in range(20)]


def test_interleave_is_order_independent():
    # the schedule depends only on the SET of (key, weight) pairs, not list order
    fwd = [("a", Fraction(5)), ("b", Fraction(2)), ("c", Fraction(1))]
    rev = list(reversed(fwd))
    for c in range(60):
        assert interleave_due(fwd, c) == interleave_due(rev, c)
