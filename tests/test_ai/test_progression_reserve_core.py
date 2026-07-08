from artifactsmmo_cli.ai.progression_reserve_core import (
    affordable,
    effective_floor,
    effective_floor_multi,
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


# --- effective_floor_multi (follow-up wave Task 4: joint gold affordability) --


def test_effective_floor_multi_generalizes_singleton():
    """`effective_floor_multi(reserved, [x])` must equal `effective_floor(reserved,
    x)` for every x — the multi form is a direct generalization, not a
    parallel reimplementation."""
    reserved = {"a": 30, "b": 50, "c": 10}
    for key in ("a", "b", "c", "z"):
        assert effective_floor_multi(reserved, [key]) == effective_floor(reserved, key)


def test_effective_floor_multi_dedups_every_admitted_item():
    """Buying BOTH "a" and "b" together dedups BOTH reservations from the
    total — not just one (the single-leaf `effective_floor` bug this task
    fixes: checking "a" and "b" independently each dedups only itself, so
    each leaf's check silently credits the OTHER leaf's reservation as
    still-protected room)."""
    reserved = {"a": 30, "b": 50, "c": 10}
    assert effective_floor_multi(reserved, {"a", "b"}) == 10       # 90 - 30 - 50
    assert effective_floor_multi(reserved, {"a", "b", "c"}) == 0   # fully dedupped
    assert effective_floor_multi(reserved, set()) == 90            # nothing bought -> full


def test_effective_floor_multi_never_negative():
    """A set covering the ENTIRE reserved map floors at exactly 0 (never
    negative): the summed deductions are a subset of `reserved`'s own values,
    so they can never exceed reserve_total."""
    reserved = {"a": 30, "b": 50}
    assert effective_floor_multi(reserved, {"a", "b", "unrelated"}) == 0


def test_effective_floor_multi_unreserved_items_contribute_nothing():
    reserved = {"a": 30, "b": 50}
    assert effective_floor_multi(reserved, {"x", "y"}) == 80  # full, none reserved
