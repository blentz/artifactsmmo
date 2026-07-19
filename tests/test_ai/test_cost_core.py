"""Coverage tests for actions/cost_core.py pure helpers."""

from artifactsmmo_cli.ai.actions.cost_core import (
    OVERHEAL_CONSUMABLE_COST,
    REST_COST_MAX,
    distance_cost_pure,
    learned_cost_pure,
    qty_cost_pure,
    rest_cost_pure,
)
from artifactsmmo_cli.ai.actions.rest import RestAction
from tests.test_ai.fixtures import make_state


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


def test_rest_cost_pure_full_deficit_is_ten():
    # hp=0 → missing 100% → max(3, 100)/10 = 10.0 (matches the prior flat constant).
    assert rest_cost_pure(0, 100) == 10.0


def test_rest_cost_pure_full_hp_hits_min_floor():
    # hp==max_hp → missing 0% → max(3, 0)/10 = 0.3 (the 3s minimum cooldown).
    assert rest_cost_pure(100, 100) == 0.3


def test_rest_cost_pure_ten_percent_missing_is_one():
    # hp=90/100 → missing 10% → max(3, 10)/10 = 1.0.
    assert rest_cost_pure(90, 100) == 1.0


def test_rest_cost_pure_small_deficit_hits_min_floor():
    # hp=99/100 → missing 1% → max(3, 1)/10 = 0.3 (min-3s floor bites).
    assert rest_cost_pure(99, 100) == 0.3


def test_rest_cost_pure_ceils_partial_percent():
    # hp=95/200 → missing 105/200 = 52.5% → ceil = 53 → max(3, 53)/10 = 5.3.
    assert rest_cost_pure(95, 200) == 5.3


def test_rest_cost_pure_nonneg_and_deep_deficit():
    # hp=10/100 → missing 90% → max(3, 90)/10 = 9.0 (the re-anchored demo point).
    assert rest_cost_pure(10, 100) == 9.0
    assert rest_cost_pure(10, 100) >= 0.0


def test_rest_action_cost_delegates_to_rest_cost_pure():
    # RestAction.cost must return rest_cost_pure(state.hp, state.max_hp).
    state = make_state(hp=10, max_hp=100)
    assert RestAction().cost(state, None, None) == rest_cost_pure(10, 100) == 9.0


# ─── the overheal sentinel's domination invariant ────────────────────────────
# UseConsumableAction returns OVERHEAL_CONSUMABLE_COST when the only available
# consumable overshoots the deficit, so that the planner Rests rather than waste
# it. That is only correct while the sentinel strictly exceeds EVERY reachable
# Rest cost. Previously that reasoning lived in a comment, in a different file
# from the formula it constrained; these tests make it executable.

def test_rest_cost_max_is_the_supremum_of_rest_cost_pure():
    # missing <= max_hp, so pct_ceil <= 100 and the cost peaks at max(3,100)/10.
    # The peak is independent of max_hp, which is why a single constant suffices.
    assert REST_COST_MAX == 10.0
    for max_hp in (1, 2, 3, 7, 99, 100, 150, 1000):
        for hp in range(max_hp + 1):
            assert rest_cost_pure(hp, max_hp) <= REST_COST_MAX
    assert rest_cost_pure(0, 150) == REST_COST_MAX      # attained at a full deficit


def test_overheal_sentinel_strictly_dominates_every_rest_cost():
    for max_hp in (1, 2, 3, 7, 99, 100, 150, 1000):
        for hp in range(max_hp + 1):
            assert OVERHEAL_CONSUMABLE_COST > rest_cost_pure(hp, max_hp)


def test_overheal_sentinel_is_derived_not_hardcoded():
    # Pins the derivation itself: the sentinel is a multiple of the Rest maximum,
    # so rescaling the Rest cost unit carries the sentinel with it. The value must
    # stay 100.0 to keep the Lean mirror (ActionCostNonneg.consumableCostOverheal)
    # in lockstep.
    assert OVERHEAL_CONSUMABLE_COST == 10.0 * REST_COST_MAX == 100.0
