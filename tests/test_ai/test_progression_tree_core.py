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
    _scaled_weights,
    branch_pick_pure,
    dhondt_step,
    falloff,
    focus_aging_order,
    focus_aging_pick,
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


def _gc(slot, code, gain, level=1):
    return GearCandidate(slot=slot, code=code, gain=Fraction(gain), level=level)


def test_aging_pick_empty_focus_equals_argmax():
    cands = [_gc("helmet_slot", "wolf_ears", 18100), _gc("ring2_slot", "iron_ring", 2000)]
    # Unaged fast-path: the seats argument is not consulted; vary it to prove so.
    for c in range(50):
        assert focus_aging_pick(cands, {}, {"helmet_slot": c}) == gear_target_pick(cands)


def test_aging_pick_below_flat_window_equals_argmax():
    cands = [_gc("helmet_slot", "wolf_ears", 18100), _gc("ring2_slot", "iron_ring", 2000)]
    focus = {("helmet_slot", "wolf_ears"): FOCUS_FLAT}  # exactly at flat edge
    for c in range(50):
        assert focus_aging_pick(cands, focus, {"helmet_slot": c}) == gear_target_pick(cands)


def test_aging_pick_decayed_top_yields_some_cycles_to_alt():
    cands = [_gc("helmet_slot", "wolf_ears", 18100), _gc("ring2_slot", "iron_ring", 2000)]
    # push the stuck root deep into decay so its scaled gain approaches the alt
    focus = {("helmet_slot", "wolf_ears"): FOCUS_FLAT + FOCUS_SPAN}  # weight = FOCUS_FLOOR
    seats: dict[str, int] = {}
    picks = set()
    for _ in range(40):
        pick = focus_aging_pick(cands, focus, seats)
        picks.add(pick.code)
        seats[pick.slot] = seats.get(pick.slot, 0) + 1  # accumulate one seat
    assert "iron_ring" in picks   # ring2 is no longer starved
    assert "wolf_ears" in picks   # floor keeps the drop root alive


def test_aging_pick_incremental_seats_match_batch_interleave_schedule():
    """FIXED weights: the incremental-seats pick sequence reproduces the batch
    `interleave_due(scaled, cycle)` schedule seat-for-seat — the
    `dhondt_step`/`interleave_due` fold identity, so behavior is preserved for
    fixed weights (the whole point of the perf refactor)."""
    cands = [_gc("helmet_slot", "wolf_ears", 18100), _gc("ring2_slot", "iron_ring", 2000)]
    focus = {("helmet_slot", "wolf_ears"): FOCUS_FLAT + FOCUS_SPAN}
    scaled = _scaled_weights(cands, focus)
    seats: dict[str, int] = {}
    for c in range(60):
        pick = focus_aging_pick(cands, focus, seats)
        assert pick.slot == interleave_due(scaled, c)
        seats[pick.slot] = seats.get(pick.slot, 0) + 1


def test_aging_order_head_equals_pick():
    cands = [_gc("helmet_slot", "wolf_ears", 18100), _gc("ring2_slot", "iron_ring", 2000)]
    focus = {("helmet_slot", "wolf_ears"): FOCUS_FLAT + FOCUS_SPAN}
    seats: dict[str, int] = {}
    for _ in range(20):
        assert focus_aging_order(cands, focus, seats)[0] == focus_aging_pick(cands, focus, seats)
        seats[focus_aging_pick(cands, focus, seats).slot] = \
            seats.get(focus_aging_pick(cands, focus, seats).slot, 0) + 1


def test_aging_order_is_permutation_of_input():
    cands = [_gc("helmet_slot", "wolf_ears", 18100), _gc("ring2_slot", "iron_ring", 2000)]
    focus = {("helmet_slot", "wolf_ears"): 50}
    out = focus_aging_order(cands, focus, {"helmet_slot": 3})
    assert sorted(out, key=lambda c: c.code) == sorted(cands, key=lambda c: c.code)


def test_aging_pick_empty_candidates_is_none():
    assert focus_aging_pick([], {}, {}) is None
    assert focus_aging_order([], {}, {}) == []
