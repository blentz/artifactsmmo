"""select_monster_for_drop: lex-argmin over (expected_kills, distance, code)."""
from artifactsmmo_cli.ai.learned_drops import LearnedDrops
from artifactsmmo_cli.ai.monster_drop_selection import (
    MonsterDropCandidate,
    select_monster_for_drop,
)


def _c(code, rate, mn, mx, dist):
    """A candidate at the drop row's prior: `rate / mean quantity` kills a
    unit (`LearnedDrops.empty()`, ruling T16a)."""
    attempts = LearnedDrops.empty().attempts_per_unit(code, "x", rate, mn, mx, 0)
    return MonsterDropCandidate(monster_code=code, attempts=attempts, distance=dist)


def test_picks_lower_expected_kills_over_distance():
    # A: rate1/avg1 = 1 expected kill, far (dist 50). B: rate3/avg1 = 3, near (dist 1).
    # Fewer expected kills wins despite distance.
    assert select_monster_for_drop("egg", [_c("A", 1, 1, 1, 50), _c("B", 3, 1, 1, 1)]) == "A"


def test_distance_breaks_expected_kills_tie():
    # Equal expected kills (both 2): nearer wins.
    assert select_monster_for_drop("x", [_c("FAR", 2, 1, 1, 9), _c("NEAR", 2, 1, 1, 2)]) == "NEAR"


def test_code_breaks_distance_tie_deterministically():
    assert select_monster_for_drop("x", [_c("b", 1, 1, 1, 5), _c("a", 1, 1, 1, 5)]) == "a"


def test_avg_quantity_reduces_expected_kills():
    # rate 4 but yields 2-4 (avg 3) => expected 4/3 ~ 1.33, beats rate 2 yield 1 (expected 2).
    assert select_monster_for_drop("x", [_c("HIGHYIELD", 4, 2, 4, 9), _c("LOWYIELD", 2, 1, 1, 1)]) == "HIGHYIELD"


def test_single_candidate_returned():
    assert select_monster_for_drop("x", [_c("only", 7, 1, 1, 3)]) == "only"


def test_empty_returns_none():
    assert select_monster_for_drop("x", []) is None
