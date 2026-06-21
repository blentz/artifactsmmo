"""Unit coverage for the strategic_value efficiency-weighted scorer (#16).

The formal differential + mutation gate proves exact-integer agreement with the
Lean core; these tests cover the pure function in the main suite.
"""
from artifactsmmo_cli.ai.tiers.strategic_value import strategic_value_pure


def test_weighted_sum():
    """Each input scaled by its own weight, summed.
    1*1000 + 2*3 + 4*5 + 6*7 + 8*9 = 1000 + 6 + 20 + 42 + 72 = 1140."""
    assert strategic_value_pure(1, 2, 4, 6, 8, 1000, 3, 5, 7, 9) == 1140


def test_all_zero_is_zero():
    assert strategic_value_pure(0, 0, 0, 0, 0, 0, 0, 0, 0, 0) == 0


def test_pure_bag_value():
    """A 35-slot bag with weights ⟨1000,1,1,50,1⟩ scores 35*50 = 1750 (matches
    the Lean witness `pure_bag_scores_positive`)."""
    assert strategic_value_pure(0, 0, 0, 35, 0, 1000, 1, 1, 50, 1) == 1750


def test_combat_weight_dominates_efficiency():
    """One point of combat_raw (×1000) outscores a 35-slot bag (×1)."""
    bag = strategic_value_pure(0, 0, 0, 35, 0, 1000, 1, 1, 1, 1)
    combat = strategic_value_pure(1, 0, 0, 0, 0, 1000, 1, 1, 1, 1)
    assert combat > bag


def test_nonneg_under_nonneg_inputs():
    assert strategic_value_pure(3, 5, 7, 9, 11, 2, 4, 6, 8, 10) >= 0


def test_monotone_in_inventory_space():
    base = strategic_value_pure(0, 0, 0, 10, 0, 1000, 1, 1, 50, 1)
    more = strategic_value_pure(0, 0, 0, 20, 0, 1000, 1, 1, 50, 1)
    assert more > base
