"""Differential test: the real Python `strategic_value_pure` (efficiency-weighted
cross-slot scorer, #16) must agree EXACTLY with the proved Lean core
`Extracted.StrategicValue.strategic_value_pure` over random nonneg inputs, and
the proved nonneg + monotonicity contracts must hold on the Python side.

Exact-integer agreement is the soundness bridge: it pins the Python arithmetic
to the same def the Bridges9 nonneg/monotone theorems are proved about, so a
dropped term, flipped operator, or swapped weight diverges from the oracle and
is caught (the teeth behind the mutation gate).
"""
from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.tiers.strategic_value import strategic_value_pure
from formal.diff.oracle_client import run_oracle

# Nonneg domains (stats and weights are nonneg in production — combat raw is a
# sum of nonneg stats; weights are nonneg derived rates).
_stat = st.integers(min_value=0, max_value=500)
_weight = st.integers(min_value=0, max_value=2000)


@settings(max_examples=400)
@given(
    combat_raw=_stat, wisdom=_stat, prospecting=_stat, inventory_space=_stat, haste=_stat,
    combat_w=_weight, wisdom_w=_weight, prospecting_w=_weight, inventory_w=_weight, haste_w=_weight,
)
def test_strategic_value_matches_lean(
    combat_raw, wisdom, prospecting, inventory_space, haste,
    combat_w, wisdom_w, prospecting_w, inventory_w, haste_w,
):
    args = [combat_raw, wisdom, prospecting, inventory_space, haste,
            combat_w, wisdom_w, prospecting_w, inventory_w, haste_w]
    py = strategic_value_pure(*args)
    lean = run_oracle("strategic_value", [args])[0]
    assert py == lean["value"]
    # Proved contract: nonneg stats + nonneg weights ⇒ nonneg score.
    assert py >= 0


@settings(max_examples=200)
@given(
    combat_raw=_stat, wisdom=_stat, prospecting=_stat, inventory_space=_stat, haste=_stat,
    combat_w=_weight, wisdom_w=_weight, prospecting_w=_weight, inventory_w=_weight, haste_w=_weight,
    bump=st.integers(min_value=0, max_value=500),
    which=st.integers(min_value=0, max_value=4),
)
def test_strategic_value_monotone_in_each_stat(
    combat_raw, wisdom, prospecting, inventory_space, haste,
    combat_w, wisdom_w, prospecting_w, inventory_w, haste_w,
    bump, which,
):
    """Increasing ANY stat (nonneg weights) never lowers the score — mirrors the
    five `strategicValue_mono_*` theorems."""
    stats = [combat_raw, wisdom, prospecting, inventory_space, haste]
    weights = [combat_w, wisdom_w, prospecting_w, inventory_w, haste_w]
    base = strategic_value_pure(*stats, *weights)
    bumped_stats = list(stats)
    bumped_stats[which] += bump
    bumped = strategic_value_pure(*bumped_stats, *weights)
    assert bumped >= base


def test_pure_bag_witness_matches_lean_theorem():
    """Regression-pin the Lean witness `pure_bag_scores_positive`: a 35-slot bag
    with weights ⟨1000,1,1,50,1⟩ scores 1750."""
    args = [0, 0, 0, 35, 0, 1000, 1, 1, 50, 1]
    assert strategic_value_pure(*args) == 1750
    assert run_oracle("strategic_value", [args])[0]["value"] == 1750


def test_combat_weight_dominates_efficiency():
    """Regression-pin `combat_weight_dominates_efficiency`: one point of combat_raw
    (×1000) outscores a 35-slot bag (×1) — combat ordering is preserved."""
    bag = strategic_value_pure(0, 0, 0, 35, 0, 1000, 1, 1, 1, 1)
    combat = strategic_value_pure(1, 0, 0, 0, 0, 1000, 1, 1, 1, 1)
    assert combat > bag
