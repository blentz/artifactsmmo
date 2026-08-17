import pytest

from artifactsmmo_cli.ai.supply_batch_target import supply_batch_target_pure
from artifactsmmo_cli.ai.thresholds import SUPPLY_BATCH


def test_nothing_demanded_targets_what_is_already_banked():
    assert supply_batch_target_pure(banked=17, demand=0) == 17


def test_a_small_demand_is_capped_at_what_was_asked():
    # Never produce more than the ask, even though the batch would reach 20.
    assert supply_batch_target_pure(banked=17, demand=1) == 18


def test_a_large_demand_advances_one_batch_at_a_time():
    assert supply_batch_target_pure(banked=0, demand=60) == SUPPLY_BATCH
    assert supply_batch_target_pure(banked=7, demand=60) == SUPPLY_BATCH


def test_the_target_does_not_move_while_working_through_a_batch():
    """The defect this exists to prevent: a target recomputed each cycle churns
    the goal's repr, which is part of its identity."""
    targets = {supply_batch_target_pure(banked=b, demand=60 - b) for b in range(0, SUPPLY_BATCH)}
    assert targets == {SUPPLY_BATCH}


def test_crossing_a_batch_boundary_advances_exactly_one_batch():
    assert supply_batch_target_pure(banked=SUPPLY_BATCH, demand=60) == 2 * SUPPLY_BATCH


@pytest.mark.parametrize("banked", [0, 3, 10, 57])
def test_the_target_always_exceeds_what_is_banked_while_demand_remains(banked):
    assert supply_batch_target_pure(banked, demand=5) > banked
