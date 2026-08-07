"""Acceptance suite for the unified progression objective `J`.

The four scenarios in `docs/spec_unified_objective/WITNESSES.md` are harvested
verbatim as `TestW001`; the rest pin the remaining clauses. Every test names the
clause it enforces, so a failure says which part of the contract broke.
"""

import pytest

from artifactsmmo_cli.ai.tiers.progression_choice import (
    TARGET_LEVEL,
    ProgressionCandidate,
    candidate_band,
    choose,
    objective_j,
    rank_candidates,
    sort_key,
)


def _c(identity: str, cost: int, level: int = TARGET_LEVEL, cycles: int = 0,
       failed: bool = False) -> ProgressionCandidate:
    return ProgressionCandidate(identity=identity, acquire_cost=cost,
                                reachable_level=level, cycles_to_fifty=cycles,
                                failed=failed)


def _order(cands: list[ProgressionCandidate]) -> list[str]:
    return [c.identity for c in rank_candidates(cands)]


class TestW001:
    """W-001 — the withdrawal of S-009, as four executable facts.

    S-009 would have pinned every positive-cost gear behind the XP trunk, because
    S-014 collapses the finite band's level field to the constant 50 and S-009
    compared levels within that band. Scenario 1 is the case it broke; 2 and 3 are
    the cases it was written to cover, which `J` and S-006 already force without
    it.
    """

    def test_1_paying_gear_beats_the_trunk(self):
        """The case S-009 would have broken. Gear costs 40 actions and saves 600
        cycles; J = 340 against the trunk's 900, so it must win (S-005)."""
        trunk = _c("trunk_xp", cost=0, cycles=900)
        gear = _c("iron_sword", cost=40, cycles=300)
        assert _order([trunk, gear]) == ["iron_sword", "trunk_xp"]
        assert choose([trunk, gear]).identity == "iron_sword"

    def test_2_worthless_gear_loses_to_the_trunk_by_J_alone(self):
        """No trunk guard is consulted: identical outcomes, so the gear's cost is
        pure loss and J decides (900 vs 940)."""
        trunk = _c("trunk_xp", cost=0, cycles=900)
        gear = _c("dead_gear", cost=40, cycles=900)
        assert choose([trunk, gear]).identity == "trunk_xp"
        assert objective_j(trunk) == 900
        assert objective_j(gear) == 940

    def test_3_worthless_gear_loses_in_the_unreachable_band_too(self):
        """Same reachable level, so S-006's second key — acquisition cost —
        prefers the trunk's zero over the gear's 40."""
        trunk = _c("trunk_xp", cost=0, level=17)
        gear = _c("dead_gear", cost=40, level=17)
        assert choose([trunk, gear]).identity == "trunk_xp"

    def test_4_ceiling_raising_gear_wins_in_the_unreachable_band(self):
        """S-006's FIRST key is furthest progress, so a higher reachable level
        wins whatever the costs — this is the R2D2 case that motivated `J`."""
        trunk = _c("trunk_xp", cost=0, level=17)
        gear = _c("greater_wooden_staff", cost=40, level=25)
        assert choose([trunk, gear]).identity == "greater_wooden_staff"


class TestBands:
    def test_band_is_decided_by_the_level_field_alone(self):
        """S-014. No infinity sentinel exists, so no second encoding can disagree
        with the level field."""
        assert candidate_band(_c("a", 0, level=TARGET_LEVEL)) == 0
        assert candidate_band(_c("b", 0, level=TARGET_LEVEL - 1)) == 1
        assert candidate_band(_c("c", 0, level=TARGET_LEVEL, failed=True)) == 2
        # a FAILED candidate is FAILED whatever its level claims
        assert candidate_band(_c("d", 0, level=3, failed=True)) == 2

    def test_finite_beats_unreachable_beats_failed(self):
        """S-006 ('a candidate with finite J ranks better than every unreachable
        one') and S-012 ('FAILED ranks below every candidate whose outcome is
        not FAILED')."""
        failed = _c("failed", cost=0, failed=True)
        unreachable = _c("unreach", cost=0, level=17)
        finite = _c("finite", cost=999, cycles=999)
        assert _order([failed, unreachable, finite]) == ["finite", "unreach", "failed"]

    def test_failed_never_chosen_while_a_usable_candidate_exists(self):
        """S-012, stated as the choice rather than the order. The FAILED
        candidate is free and the usable one is ruinously expensive; FAILED still
        loses."""
        failed = _c("failed", cost=0, failed=True)
        usable = _c("usable", cost=10**6, cycles=10**6)
        assert choose([failed, usable]).identity == "usable"

    def test_all_failed_still_returns_a_choice(self):
        """S-001 totality: FAILED-only input is non-empty, so the core must still
        choose. S-012 only forbids choosing FAILED when something usable exists."""
        chosen = choose([_c("f1", 0, failed=True), _c("f2", 0, failed=True)])
        assert chosen is not None and chosen.identity == "f1"

    def test_cycles_field_is_not_read_for_an_unreachable_candidate(self):
        """S-014 says the cycles figure carries no meaning below level 50. Two
        candidates identical but for an absurd cycles value must rank identically,
        so a void field cannot leak into the order."""
        a = _c("a", cost=5, level=17, cycles=0)
        b = _c("b", cost=5, level=17, cycles=-10**9)
        assert sort_key(a)[:1] == sort_key(b)[:1]
        assert sort_key(a) == sort_key(b)


class TestOrdering:
    def test_finite_band_orders_by_J(self):
        """S-005."""
        cands = [_c("mid", 10, cycles=100), _c("best", 5, cycles=20),
                 _c("worst", 200, cycles=200)]
        assert _order(cands) == ["best", "mid", "worst"]

    def test_unreachable_band_prefers_furthest_progress_then_cost(self):
        """S-006, both keys. Level dominates; cost only separates equal levels."""
        cands = [_c("l17_cheap", 1, level=17), _c("l25_dear", 500, level=25),
                 _c("l17_free", 0, level=17)]
        assert _order(cands) == ["l25_dear", "l17_free", "l17_cheap"]

    def test_acquisition_cost_not_cycles_breaks_the_unreachable_tie(self):
        """S-006's stated reason: cycles-to-50 is void below level 50, so ranking
        on it would compare two meaningless numbers. The candidate with the WORSE
        cycles figure but lower cost must still win."""
        cheap_bad_cycles = _c("cheap", cost=1, level=17, cycles=10**6)
        dear_good_cycles = _c("dear", cost=99, level=17, cycles=0)
        assert _order([dear_good_cycles, cheap_bad_cycles]) == ["cheap", "dear"]

    def test_ranking_is_a_permutation_of_the_input(self):
        """S-007: every candidate returned, none omitted, duplicated or invented."""
        cands = [_c("a", 3, cycles=1), _c("b", 0, failed=True),
                 _c("c", 1, level=20), _c("d", 7, cycles=2)]
        ranked = rank_candidates(cands)
        assert len(ranked) == len(cands)
        assert sorted(c.identity for c in ranked) == ["a", "b", "c", "d"]

    def test_first_element_is_the_chosen_candidate(self):
        """S-007's last sentence, on a non-empty input."""
        cands = [_c("x", 50, cycles=50), _c("y", 1, cycles=1)]
        assert rank_candidates(cands)[0] is choose(cands)


class TestTieBreak:
    def test_ties_keep_input_order_not_identity_text(self):
        """S-008: deterministic, and explicitly NOT by comparing identities as
        text. Reversing the input reverses the tied pair — which a name-sorting
        implementation could not do."""
        a, b = _c("zzz", 5, cycles=5), _c("aaa", 5, cycles=5)
        assert _order([a, b]) == ["zzz", "aaa"]
        assert _order([b, a]) == ["aaa", "zzz"]

    def test_repeated_calls_agree(self):
        """S-001/S-008 determinism: same input, same order, every call."""
        cands = [_c("a", 5, cycles=5), _c("b", 5, cycles=5), _c("c", 1, cycles=9)]
        first = _order(cands)
        assert all(_order(cands) == first for _ in range(5))

    def test_core_does_not_mutate_its_argument(self):
        """S-001: mutates none of its arguments."""
        cands = [_c("a", 9, cycles=9), _c("b", 1, cycles=1)]
        before = list(cands)
        rank_candidates(cands)
        choose(cands)
        assert cands == before


class TestEmpty:
    def test_empty_sequence_yields_empty_ranking_and_no_choice(self):
        """S-015."""
        assert rank_candidates([]) == []
        assert choose([]) is None

    def test_singleton_is_chosen_whatever_its_band(self):
        """S-001 totality across all three bands."""
        for c in (_c("f", 0, cycles=1), _c("u", 0, level=2),
                  _c("x", 0, failed=True)):
            assert choose([c]) is c


class TestExactness:
    def test_comparison_is_exact_at_a_one_cycle_difference(self):
        """S-013: no significance threshold — two J values differing at all are
        ordered by that difference, however small."""
        a = _c("a", cost=10**9, cycles=0)
        b = _c("b", cost=10**9 - 1, cycles=0)
        assert choose([a, b]).identity == "b"

    def test_J_is_integer_addition_in_one_unit(self):
        """S-004 + S-010: the two terms are added directly, no conversion."""
        c = _c("c", cost=40, cycles=300)
        assert objective_j(c) == 340
        assert isinstance(objective_j(c), int)


@pytest.mark.parametrize("level", [0, 1, TARGET_LEVEL - 1, TARGET_LEVEL, TARGET_LEVEL + 1])
def test_sort_key_is_a_tuple_of_ints_at_every_level(level: int):
    """S-013: the key the order rests on is exact integers, never floats, for
    every level a projection can report — including above the cap."""
    key = sort_key(_c("c", 3, level=level, cycles=7))
    assert len(key) == 3
    assert all(isinstance(k, int) and not isinstance(k, bool) for k in key)
