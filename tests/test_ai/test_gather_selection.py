"""select_gather_source: lex-argmin over (expected_gathers, distance, code)."""
from artifactsmmo_cli.ai.gather_selection import GatherCandidate, select_gather_source


def _c(code, rate, mn, mx, dist):
    return GatherCandidate(resource_code=code, rate=rate, min_quantity=mn, max_quantity=mx, distance=dist)


def test_picks_lower_expected_gathers_over_distance():
    # A: rate1/avg1 = 1 expected gather, far (dist 50). B: rate3/avg1 = 3, near (dist 1).
    # Fewer expected gathers wins despite distance.
    assert select_gather_source("copper_ore", [_c("A", 1, 1, 1, 50), _c("B", 3, 1, 1, 1)]) == "A"


def test_distance_breaks_expected_gathers_tie():
    # Equal expected gathers (both 2): nearer wins.
    assert select_gather_source("x", [_c("FAR", 2, 1, 1, 9), _c("NEAR", 2, 1, 1, 2)]) == "NEAR"


def test_code_breaks_distance_tie_deterministically():
    assert select_gather_source("x", [_c("b", 1, 1, 1, 5), _c("a", 1, 1, 1, 5)]) == "a"


def test_avg_quantity_reduces_expected_gathers():
    # rate 4 but yields 2-4 (avg 3) ⇒ expected 4/3 ≈ 1.33, beats rate 2 yield 1 (expected 2).
    assert select_gather_source("x", [_c("HIGHYIELD", 4, 2, 4, 9), _c("LOWYIELD", 2, 1, 1, 1)]) == "HIGHYIELD"


def test_single_candidate_returned():
    assert select_gather_source("x", [_c("only", 7, 1, 1, 3)]) == "only"


def test_empty_returns_none():
    assert select_gather_source("x", []) is None
