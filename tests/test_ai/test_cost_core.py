"""Coverage tests for actions/cost_core.py pure helpers."""

from artifactsmmo_cli.ai.actions.cost_core import (
    distance_cost_pure,
    learned_cost_pure,
    qty_cost_pure,
)


def test_distance_cost_pure_sums_base_and_distance():
    assert distance_cost_pure(5.0, 3) == 8.0


def test_distance_cost_pure_zero_distance():
    assert distance_cost_pure(7.0, 0) == 7.0


def test_qty_cost_pure_scales_per_unit():
    # base=2, qty=5, dist=1, per_unit=0.5 → 2 + 0.5*5 + 1 = 5.5
    assert qty_cost_pure(2.0, 5, 1, 0.5) == 5.5


def test_qty_cost_pure_qty_one():
    assert qty_cost_pure(2.0, 1, 0, 0.5) == 2.5


def test_learned_cost_pure_no_history_uses_static():
    assert learned_cost_pure(10.0, 0.0, 0.0, has_history=False) == 10.0


def test_learned_cost_pure_confident_history_uses_learned():
    # confident_threshold=0.95 default; rate>=0.95 → learned wins.
    assert learned_cost_pure(10.0, 7.0, 0.96, has_history=True) == 7.0


def test_learned_cost_pure_low_confidence_scales_by_rate_floor():
    # rate < 0.95 → learned / max(rate, 0.1).
    # static=10, learned=3, rate=0.05 → 3 / 0.1 = 30.
    assert learned_cost_pure(10.0, 3.0, 0.05, has_history=True) == 30.0
