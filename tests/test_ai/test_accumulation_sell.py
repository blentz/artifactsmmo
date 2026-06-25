from artifactsmmo_cli.ai.accumulation_sell import (
    ACCUM_MULT, SEVERE_STEPS, accumulation_excess, accumulation_steps,
)


def test_steps_is_floor_log2_ratio():
    assert accumulation_steps(14, 1) == 3   # 2^3=8<=14<16
    assert accumulation_steps(11, 2) == 2   # 11/2=5.5 -> 2^2=4*2=8<=11<16
    assert accumulation_steps(32, 1) == 5   # exactly SEVERE
    assert accumulation_steps(1000, 1) == 9


def test_steps_zero_below_eff_cap_and_cap_zero_uses_one():
    assert accumulation_steps(0, 5) == 0
    assert accumulation_steps(3, 0) == 1    # eff_cap 1: 2^1=2<=3<4


def test_excess_sells_down_to_true_cap_past_gate():
    assert accumulation_excess(14, 1) == 13   # keep 1
    assert accumulation_excess(14, 0) == 14   # dominated -> sell all
    assert accumulation_excess(11, 2) == 9    # keep 2


def test_excess_zero_below_ratio_gate():
    assert accumulation_excess(4, 1) == 0     # 4 < 5*1
    assert accumulation_excess(9, 2) == 0     # 9 < 5*2=10
    assert accumulation_excess(10, 2) == 8    # 10 >= 10 -> keep 2


def test_constants():
    assert ACCUM_MULT == 5
    assert SEVERE_STEPS == 5
