"""Differential: the real Python `sort_key` ≡ the proved Lean
`Extracted.ProgressionChoice.sort_key` over random candidates.

The whole order rests on this one function, so pinning it pointwise pins the
ranking: `rank_candidates` is `sorted(..., key=sort_key)` and `sorted` is a
standard-library total sort, deterministic and stable.

The generator is deliberately NOT uniform. A candidate reaches the interesting
branches only if it is non-FAILED and its level lands near the target, so
`reachable_level` is drawn tightly around `TARGET_LEVEL` and `failed` is drawn
4:1 against. Uniform sampling would have spent almost every example in the
FAILED band, where the key is a constant and nothing can diverge — the same
dilution that let two ordering mutants survive a 400-example sweep on
`skill_grind_selection` (2026-08-06). Values well outside the band still appear,
via the wide arm below.
"""
from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.tiers.progression_choice import (
    TARGET_LEVEL,
    ProgressionCandidate,
    sort_key,
)
from formal.diff.oracle_client import run_oracle

# Tight around the band boundary, where every branch is reachable.
_level = st.one_of(
    st.integers(min_value=TARGET_LEVEL - 4, max_value=TARGET_LEVEL + 2),
    st.integers(min_value=-5, max_value=120),
)
_cost = st.integers(min_value=0, max_value=5000)
_cycles = st.integers(min_value=-5000, max_value=5000)
_failed = st.sampled_from([False] * 4 + [True])


def _lean(c: ProgressionCandidate) -> tuple[int, int, int]:
    out = run_oracle("progression_choice",
                     [[c.acquire_cost, c.reachable_level, c.cycles_to_fifty,
                       1 if c.failed else 0]])[0]
    return (out["band"], out["primary"], out["secondary"])


@settings(max_examples=500, deadline=None)
@given(cost=_cost, level=_level, cycles=_cycles, failed=_failed)
def test_python_sort_key_matches_lean(cost, level, cycles, failed):
    c = ProgressionCandidate(identity="c", acquire_cost=cost,
                             reachable_level=level, cycles_to_fifty=cycles,
                             failed=failed)
    assert sort_key(c) == _lean(c), (cost, level, cycles, failed)


def test_band_boundary_is_exact_on_both_sides():
    """The band boundary decides which figures are even read, so it is pinned
    exactly rather than sampled: level 49 is unreachable, 50 is finite."""
    for level, expect_band in ((TARGET_LEVEL - 1, 1), (TARGET_LEVEL, 0),
                               (TARGET_LEVEL + 1, 0)):
        c = ProgressionCandidate("c", 7, level, 11, False)
        assert sort_key(c)[0] == expect_band
        assert sort_key(c) == _lean(c)


def test_failed_key_is_constant_on_both_sides():
    """S-012 gives FAILED no internal order, so wildly different fields must
    still produce one identical key — on both sides."""
    a = ProgressionCandidate("a", 0, 50, 0, True)
    b = ProgressionCandidate("b", 4999, -5, -5000, True)
    assert sort_key(a) == sort_key(b)
    assert sort_key(a) == _lean(a)
    assert sort_key(b) == _lean(b)


def test_unreachable_ignores_the_void_cycles_field_on_both_sides():
    """S-014's void field, executed. Two unreachable candidates differing ONLY in
    cycles-to-50 must key identically — the property the Lean contract pins."""
    a = ProgressionCandidate("a", 12, 17, 0, False)
    b = ProgressionCandidate("b", 12, 17, 999_999, False)
    assert sort_key(a) == sort_key(b)
    assert sort_key(a) == _lean(a)
    assert sort_key(b) == _lean(b)
