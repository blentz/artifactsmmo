from artifactsmmo_cli.ai.progression_reserve_core import (
    affordable,
    effective_floor,
    reserve_total,
)


def test_reserve_total_sums_costs():
    assert reserve_total({"a": 30, "b": 50}) == 80
    assert reserve_total({}) == 0


def test_effective_floor_deducts_the_bought_reserved_item():
    reserved = {"a": 30, "b": 50}
    assert effective_floor(reserved, "a") == 50   # 80 - 30
    assert effective_floor(reserved, "b") == 30    # 80 - 50


def test_effective_floor_full_for_nonreserved_or_none():
    reserved = {"a": 30, "b": 50}
    assert effective_floor(reserved, "z") == 80     # not reserved -> full
    assert effective_floor(reserved, None) == 80    # discretionary -> full


def test_affordable_reserved_item_not_blocked_by_itself():
    reserved = {"a": 30, "b": 50}
    # gold 60, buying reserved "a" at price 30: floor 50, need gold >= 30+50=80 -> NO
    assert affordable(60, 30, reserved, "a") is False
    # gold 80: 80 >= 80 -> YES (a's own 30 deducted, only b's 50 protected)
    assert affordable(80, 30, reserved, "a") is True


def test_affordable_discretionary_protects_full_floor():
    reserved = {"a": 30, "b": 50}
    # buying non-reserved "z" price 10: need gold >= 10 + 80 = 90
    assert affordable(89, 10, reserved, "z") is False
    assert affordable(90, 10, reserved, "z") is True
