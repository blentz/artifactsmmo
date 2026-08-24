"""Pure cores of the progression-tree selector (spec 2026-07-06).

Mirrored by Formal/ProgressionTree.lean; the PROGRESSION_TREE_MUTATIONS
group binds these tests to the source."""

from dataclasses import fields
from fractions import Fraction

from artifactsmmo_cli.ai.tiers.progression_tree_core import (
    _NO_ACHIEVABILITY,
    _NO_ROLE,
    _NO_SYNERGY,
    FOCUS_FLAT,
    FOCUS_FLOOR,
    FOCUS_SPAN,
    POTION_TYPE_WEIGHTS,
    Branch,
    GearCandidate,
    _gear_pref_key,
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
from artifactsmmo_cli.ai.tiers.synergy_core import S_MIN


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


def test_aging_order_tail_uses_scaled_weights_not_raw_gain():
    """THE 2026-07-27 REGRESSION (live). The tail is the fallback list the
    arbiter walks when the head cannot be served, so sorting it by RAW gain
    preserved exactly the ordering the head's own factors rejected: behind an
    achievability-demoted head sat lich_race_trophy (25050) ahead of
    adventurer_pants (15019), one position down.

    Live gains and achievability values, Robby L21.
    """
    trophy = _gc("artifact2_slot", "lich_race_trophy", 25050)
    ring = _gc("ring2_slot", "life_ring", 21020)
    pants = _gc("leg_armor_slot", "adventurer_pants", 15019)
    cands = [trophy, ring, pants]
    achievability = {
        ("artifact2_slot", "lich_race_trophy"): Fraction(553, 1000),
        ("ring2_slot", "life_ring"): Fraction(786, 1000),
        ("leg_armor_slot", "adventurer_pants"): Fraction(1),
    }
    order = focus_aging_order(cands, {}, {}, _NO_SYNERGY, achievability)

    assert [c.code for c in order] == ["life_ring", "adventurer_pants", "lich_race_trophy"]
    # Raw gain would have ordered the tail trophy-first; the head is the same
    # either way, so ONLY the tail distinguishes the two.
    assert sorted((c for c in cands if c is not order[0]),
                  key=_gear_pref_key)[0] is trophy


def test_aging_order_tail_is_unchanged_when_every_factor_is_inert():
    """The scaled key must reduce to `_gear_pref_key` exactly with no signals,
    so the weighted tail is not a behaviour change for unweighted callers."""
    cands = [_gc("ring2_slot", "iron_ring", 2000), _gc("helmet_slot", "wolf_ears", 18100),
             _gc("boots_slot", "iron_boots", 9000)]
    order = focus_aging_order(cands, {}, {})
    assert order == [order[0], *sorted((c for c in cands if c is not order[0]),
                                       key=_gear_pref_key)]


# --- Wave 3a: synergy plumbing (spec 2026-07-19 §3, Phase 3) ---
# weight = gain * falloff(focus) * synergy. Wave 3a wires the third factor with
# the empty _NO_SYNERGY default so the whole tree is byte-identical until Wave 3b
# supplies real values. These tests pin (a) that inertness and (b) the FAST-PATH
# TRAP fix: the argmax short-circuit must respect a synergy signal even when
# nothing is stale.


def test_no_synergy_map_is_inert():
    """With _NO_SYNERGY (the default), the weight is exactly the pre-synergy
    `gain * falloff(focus)` — the third factor collapses to Fraction(1). Any
    drift here means the plumbing is not inert."""
    cands = [_gc("helmet_slot", "wolf_ears", 18100),
             _gc("ring2_slot", "iron_ring", 2000)]
    focus = {("helmet_slot", "wolf_ears"): FOCUS_FLAT + FOCUS_SPAN}  # decayed
    expected = [(c.slot, c.gain * falloff(focus.get((c.slot, c.code), 0)))
                for c in cands]
    assert _scaled_weights(cands, focus, _NO_SYNERGY) == expected
    assert _scaled_weights(cands, focus) == expected                  # default
    # order/pick unchanged too
    seats: dict[str, int] = {}
    assert (focus_aging_order(cands, focus, seats, _NO_SYNERGY)
            == focus_aging_order(cands, focus, seats))


def test_synergy_scales_the_weight():
    """A synergy multiplier < 1 suppresses a candidate's weight proportionally
    (purity factor). `synergy_pure`'s floor S_MIN gives a 3x suppression."""
    cands = [_gc("helmet_slot", "big", 9)]
    synergy = {("helmet_slot", "big"): S_MIN}
    assert _scaled_weights(cands, {}, synergy) == [("helmet_slot", 9 * S_MIN)]


def test_fast_path_respects_synergy():
    """THE PHASE-3 TRAP. Every candidate is inside the flat window (nothing
    stale), so the old guard would take the argmax fast-path and ignore synergy
    entirely — silently inert for the first FOCUS_FLAT cycles. The fix falls
    back to argmax only when there is ALSO no synergy signal, so a suppressed
    high-gain candidate loses to an aligned lower-gain one."""
    a = _gc("helmet_slot", "big", 10)      # higher gain, but zero-overlap
    b = _gc("ring1_slot", "small", 5)      # lower gain, fully aligned
    cands = [a, b]
    synergy = {("helmet_slot", "big"): S_MIN}   # big suppressed to 10/3 < 5
    # No synergy: the fast-path argmax picks the higher gain (big).
    assert focus_aging_pick(cands, {}, {}) is a
    # With synergy: the guard sees a signal, drops to dhondt over scaled
    # weights, and the aligned candidate wins despite lower raw gain.
    assert focus_aging_pick(cands, {}, {}, synergy) is b
    assert focus_aging_order(cands, {}, {}, synergy)[0] is b


def test_synergy_absent_from_gear_candidate_identity():
    """Synergy is a modulating weight, never candidate identity — it must not
    enter GearCandidate's fields or its repr (the currency-grind lesson: a
    moving value inside identity resets sticky keying). Structurally excluded."""
    names = {f.name for f in fields(GearCandidate)}
    assert "synergy" not in names
    # two candidates equal but for a synergy context have identical repr
    assert repr(_gc("s", "c", 5)) == repr(_gc("s", "c", 5))


# --- Task 4 (achievability factor): wiring into the weight ---


def test_achievability_scales_the_weight():
    """A distant candidate with the bigger gain loses to a close smaller one."""
    far = GearCandidate(slot="artifact3_slot", code="trophy", gain=Fraction(25050), level=20)
    near = GearCandidate(slot="ring1_slot", code="life_ring", gain=Fraction(21020), level=15)
    ach = {("artifact3_slot", "trophy"): Fraction(509, 1000),
           ("ring1_slot", "life_ring"): Fraction(788, 1000)}
    weights = dict(_scaled_weights([far, near], {}, _NO_SYNERGY, ach))
    assert weights["ring1_slot"] > weights["artifact3_slot"]


def test_empty_achievability_reproduces_the_old_weights():
    """The inert default must be bit-identical to pre-achievability behaviour."""
    c = GearCandidate(slot="ring1_slot", code="life_ring", gain=Fraction(21020), level=15)
    assert (_scaled_weights([c], {}, _NO_SYNERGY, _NO_ACHIEVABILITY)
            == _scaled_weights([c], {}, _NO_SYNERGY))


def test_achievability_breaks_the_flat_window_short_circuit():
    """THE TRAP: while every root is fresh, focus_aging_pick returns the plain
    argmax. Without extending that condition, achievability is inert for the
    first FOCUS_FLAT cycles — exactly the window a fresh gear decision lives in.
    Same bug synergy's docstring records."""
    far = GearCandidate(slot="artifact3_slot", code="trophy", gain=Fraction(25050), level=20)
    near = GearCandidate(slot="ring1_slot", code="life_ring", gain=Fraction(21020), level=15)
    ach = {("artifact3_slot", "trophy"): Fraction(1, 2)}
    pick = focus_aging_pick([far, near], {}, {}, _NO_SYNERGY, ach)
    assert pick.code == "life_ring", "flat-window fast path ignored achievability"


def test_tie_break_flips_under_achievability_dhondt_vs_argmax():
    """Task 4 review finding (Important 4): achievability escaping the
    fast path swaps which TIE-BREAK RULE governs a genuine tie between two
    same-code, same-gain candidates in different slots — exactly the live
    DUPLICATE_SLOT_TYPE shape (e.g. `copper_ring` filling ring1_slot AND
    ring2_slot).

    `gear_target_pick`'s canonical order (`_gear_pref_key` = `(-gain,
    -level, code, slot)`, via `min`) breaks a tie by ASCENDING slot: ring1
    wins. `dhondt_step`'s `(quotient, weight, key)` via `max` breaks the
    SAME tie by DESCENDING key: ring2 wins (both candidates are keyed by
    `c.slot` in `_scaled_weights`, so `key` here IS the slot string).

    Before this task, EVERY synergy-off caller — `decide_tree`'s own
    default, unit tests, the offline `plan` path — always took the argmax
    fast path, so this reversal could never surface (synergy already
    bypassed the fast path in production, but only for `enable_synergy=
    True` callers). A non-1 achievability value now bypasses the fast path
    unconditionally (achievability has no opt-in flag), so a synergy-off
    caller can hit this reversal too. Pinned here so it is documented
    behaviour, not an incidental surprise: the two candidates carry the
    SAME achievability (as same-code duplicates naturally would, sharing an
    identical requirement multiset and therefore identical `_effort_for`),
    so this isolates the tie-break RULE swap from any magnitude change."""
    a = GearCandidate(slot="ring1_slot", code="copper_ring", gain=Fraction(100), level=1)
    b = GearCandidate(slot="ring2_slot", code="copper_ring", gain=Fraction(100), level=1)
    cands = [a, b]
    # No achievability signal: fast path taken, ascending-slot tiebreak (ring1).
    assert gear_target_pick(cands) is a
    assert focus_aging_pick(cands, {}, {}) is a
    # Achievability escapes the fast path. Both candidates carry the SAME
    # non-1 value (a real duplicate-slot item's multiset is identical for
    # both slots), so this is purely a tie-break-rule swap, not a magnitude
    # change.
    ach = {("ring1_slot", "copper_ring"): Fraction(3, 4),
           ("ring2_slot", "copper_ring"): Fraction(3, 4)}
    winner = focus_aging_pick(cands, {}, {}, _NO_SYNERGY, ach)
    assert winner is b, (
        "dhondt_step's tie-break favors the HIGHER slot key, reversing "
        "gear_target_pick's LOWER-slot tiebreak")


# --- Task 13 (role factor): wiring into the weight, inert by default ---
#
# `ai/role_alignment.py` held the two multipliers this section threads through
# `_scaled_weights`' `role` parameter. Wave 3b deleted that module (re-derived
# deletion list §3 row 9: its sole importer was `progression_tree._role_map`,
# itself uncalled), so the two values are stated here as the literals they
# were: ALIGNED = 1 (no signal, or on-role) and MISALIGNED = 1/2 (damped, never
# zeroed). The `role` parameter itself is unchanged and is what these pin.

_ALIGNED = Fraction(1)
_MISALIGNED = Fraction(1, 2)


def test_role_scales_the_weight():
    """A misaligned candidate with the bigger gain loses to an aligned smaller
    one — same shape as the achievability weight-scaling test above."""
    off_role = GearCandidate(slot="artifact3_slot", code="trophy", gain=Fraction(25050), level=20)
    on_role = GearCandidate(slot="ring1_slot", code="life_ring", gain=Fraction(21020), level=15)
    role = {("artifact3_slot", "trophy"): _MISALIGNED}
    weights = dict(_scaled_weights([off_role, on_role], {}, role=role))
    assert weights["ring1_slot"] > weights["artifact3_slot"]


def test_empty_role_reproduces_the_old_weights():
    """The inert default must be bit-identical to pre-role behaviour."""
    c = GearCandidate(slot="ring1_slot", code="life_ring", gain=Fraction(21020), level=15)
    assert (_scaled_weights([c], {}, _NO_SYNERGY, _NO_ACHIEVABILITY, _NO_ROLE)
            == _scaled_weights([c], {}, _NO_SYNERGY, _NO_ACHIEVABILITY))


def test_role_breaks_the_flat_window_short_circuit():
    """THE TRAP: while every root is fresh, focus_aging_pick returns the plain
    argmax. Without extending that condition, role is inert for the first
    FOCUS_FLAT cycles — exactly the window a fresh gear decision lives in.
    Same bug synergy's and achievability's docstrings record."""
    off_role = GearCandidate(slot="artifact3_slot", code="trophy", gain=Fraction(25050), level=20)
    on_role = GearCandidate(slot="ring1_slot", code="life_ring", gain=Fraction(21020), level=15)
    role = {("artifact3_slot", "trophy"): _MISALIGNED}
    pick = focus_aging_pick([off_role, on_role], {}, {}, role=role)
    assert pick is not None
    assert pick.code == "life_ring", "flat-window fast path ignored role"


# Relocated from `tests/test_ai/test_role_alignment.py`, which wave 3b deleted
# with its subject (`ai/role_alignment.py`, re-derived deletion list §3 row 9).
# These two do NOT test that module: their subject is the `role` PARAMETER of
# `_scaled_weights` / `focus_aging_pick` / `focus_aging_order`, which survives.
# They are kept because `test_empty_role_reproduces_the_old_weights` above is
# deliberately weaker — it compares the default against `_NO_ROLE` itself, so a
# `_NO_ROLE` poisoned with a real entry would still satisfy it. The pair below
# compares against an INDEPENDENTLY constructed empty mapping, and then proves
# that comparison can detect a difference at all.


def _role_gear_candidates() -> list[GearCandidate]:
    return [
        GearCandidate(slot="weapon_slot", code="iron_sword", gain=Fraction(100), level=10),
        GearCandidate(slot="ring1_slot", code="iron_ring", gain=Fraction(50), level=8),
        GearCandidate(slot="ring2_slot", code="iron_ring", gain=Fraction(50), level=8),
    ]


def test_default_role_is_inert() -> None:
    """The inert-landing proof.

    Comparing the default call against `role=_NO_ROLE` explicitly would be
    VACUOUS: `_NO_ROLE` IS the default, so both sides invoke the identical
    object no matter what that object holds — a `_NO_ROLE` poisoned with a
    real `(slot, code)` entry would still make the two sides equal to each
    other (review finding, Task 13). Comparing against an INDEPENDENTLY
    constructed empty mapping instead means this test actually depends on
    `_NO_ROLE` being empty: if the default sentinel were ever poisoned, the
    poisoned default (left side) would diverge from the genuinely empty map
    (right side) and this test would fail."""
    cands = _role_gear_candidates()
    focus: dict = {}
    seats: dict = {}
    truly_empty: dict[tuple[str, str], Fraction] = {}
    assert (_scaled_weights(cands, focus)
            == _scaled_weights(cands, focus, role=truly_empty))
    assert (focus_aging_pick(cands, focus, seats)
            is focus_aging_pick(cands, focus, seats, role=truly_empty))
    assert (focus_aging_order(cands, focus, seats)
            == focus_aging_order(cands, focus, seats, role=truly_empty))


def test_nonempty_role_map_changes_weight_pick_and_order() -> None:
    """Sanity check for the comparison methodology `test_default_role_is_inert`
    relies on: a role map that actually penalizes a candidate MUST change the
    weight, the pick, AND the order — demonstrating the comparison is capable
    of detecting a difference at all. Without this, a byte-identical assertion
    is evidence of nothing (review finding, Task 13)."""
    off_role = GearCandidate(slot="artifact3_slot", code="trophy", gain=Fraction(25050), level=20)
    on_role = GearCandidate(slot="ring1_slot", code="life_ring", gain=Fraction(21020), level=15)
    cands = [off_role, on_role]
    focus: dict = {}
    seats: dict = {}
    role = {("artifact3_slot", "trophy"): _MISALIGNED}

    default_weights = dict(_scaled_weights(cands, focus))
    penalized_weights = dict(_scaled_weights(cands, focus, role=role))
    assert penalized_weights["artifact3_slot"] != default_weights["artifact3_slot"]
    assert penalized_weights["artifact3_slot"] == default_weights["artifact3_slot"] * _MISALIGNED
    assert penalized_weights["ring1_slot"] == default_weights["ring1_slot"]

    default_pick = focus_aging_pick(cands, focus, seats)
    penalized_pick = focus_aging_pick(cands, focus, seats, role=role)
    assert default_pick is not None and penalized_pick is not None
    assert default_pick.code == "trophy"
    assert penalized_pick.code == "life_ring"

    default_order = [c.code for c in focus_aging_order(cands, focus, seats)]
    penalized_order = [c.code for c in focus_aging_order(cands, focus, seats, role=role)]
    assert default_order == ["trophy", "life_ring"]
    assert penalized_order == ["life_ring", "trophy"]
    assert default_order != penalized_order
