import itertools

from artifactsmmo_cli.ai.potion_baseline import potion_baseline_pure


def _b(level):  # (5 -> 5) to (45 -> 100)
    return potion_baseline_pure(level, 5, 5, 45, 100)


def test_flat_low_through_low_level():
    assert _b(1) == 5
    assert _b(5) == 5


def test_full_at_and_above_high_level():
    assert _b(45) == 100
    assert _b(50) == 100


def test_linear_ramp_between():
    # 5 + floor(95*(level-5)/40)
    assert _b(6) == 7      # 5 + floor(95/40)=5+2
    assert _b(10) == 16    # 5 + floor(95*5/40)=5+11
    assert _b(20) == 40    # 5 + floor(95*15/40)=5+35
    assert _b(30) == 64    # 5 + floor(95*25/40)=5+59
    assert _b(40) == 88    # 5 + floor(95*35/40)=5+83


def test_monotone_non_decreasing():
    vals = [_b(level) for level in range(1, 51)]
    assert all(a <= b for a, b in itertools.pairwise(vals))
