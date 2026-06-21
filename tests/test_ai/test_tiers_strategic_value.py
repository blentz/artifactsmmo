"""Unit coverage for the strategic_value efficiency-weighted scorer (#16).

The formal differential + mutation gate proves exact-integer agreement with the
Lean core; these tests cover the pure function in the main suite.
"""
from artifactsmmo_cli.ai.game_data import ItemStats
from artifactsmmo_cli.ai.tiers.strategic_value import (
    DEFAULT_STRATEGIC_WEIGHTS,
    STRATEGIC_SCALE,
    strategic_value,
    strategic_value_pure,
)


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


# ---- wrapper (ItemStats → strategic_value) ----

def test_wrapper_combat_raw_excludes_efficiency_stats():
    """combat_raw = attack+resistance+hp_restore+hp_bonus+dmg+crit+lifesteal+
    combat_buff (equip_value's raw MINUS the four efficiency stats), ×SCALE.
    A pure-combat weapon (attack 30) → 30 × 1000 = 30000."""
    s = ItemStats(code="iron_sword", level=2, type_="weapon", attack={"earth": 30})
    assert strategic_value(s) == 30 * STRATEGIC_SCALE


def test_wrapper_combat_raw_sums_every_combat_field():
    """Every combat field contributes to combat_raw (so a dropped term is caught):
    attack(2+3) + resistance(4) + hp_restore(5) + hp_bonus(6) + dmg(7) + crit(8)
    + lifesteal(9) + combat_buff(10) = 54 → 54 × 1000 = 54000. Efficiency stats
    (wisdom/prospecting/inventory/haste) are NOT in combat_raw."""
    s = ItemStats(
        code="kitchen_sink", level=1, type_="weapon",
        attack={"fire": 2, "air": 3}, resistance={"earth": 4}, hp_restore=5,
        hp_bonus=6, dmg=7, critical_strike=8, lifesteal=9, combat_buff=10,
    )
    assert strategic_value(s) == 54 * STRATEGIC_SCALE


def test_wrapper_efficiency_stats_downweighted():
    """wisdom/prospecting carry weight 1 (openapi 0.001×SCALE); inventory/haste
    DEFERRED at parity (=SCALE). An artifact (wisdom 25, prospecting 25) →
    25*1 + 25*1 = 50; a bag (inventory_space 35) → 35*1000 = 35000."""
    artifact = ItemStats(code="guide", level=1, type_="artifact", wisdom=25, prospecting=25)
    assert strategic_value(artifact) == 50
    bag = ItemStats(code="bag", level=1, type_="bag", inventory_space=35)
    assert strategic_value(bag) == 35 * STRATEGIC_SCALE


def test_wrapper_default_weights_shape():
    """Documented fixed-point weights: combat/inventory/haste at SCALE, wisdom/
    prospecting at the 0.001 rate."""
    assert DEFAULT_STRATEGIC_WEIGHTS == (1000, 1, 1, 1000, 1000)


def test_wrapper_accepts_custom_weights():
    """Phase 3b supplies derived inventory/haste weights via the weights arg."""
    bag = ItemStats(code="bag", level=1, type_="bag", inventory_space=10)
    assert strategic_value(bag, (1000, 1, 1, 7, 1000)) == 70


def test_efficiency_budget_caps_efficiency_block_below_combat():
    """#16 sub-budget: the efficiency block is capped at efficiency_budget so a
    combat item always outranks an all-efficiency item. A 100-slot bag at weight
    50 = 5000 efficiency, capped to budget 999."""
    bag = ItemStats(code="bag", level=1, type_="bag", inventory_space=100)
    capped = strategic_value(bag, (1000, 1, 1, 50, 0), efficiency_budget=999)
    assert capped == 999  # combat_part 0 + min(999, 5000)
    # A single combat-raw point outranks the capped bag.
    weapon = ItemStats(code="w", level=1, type_="weapon", attack={"earth": 1})
    assert strategic_value(weapon, (1000, 1, 1, 50, 0), efficiency_budget=999) == 1000


def test_efficiency_budget_none_is_uncapped():
    """No budget → plain weighted sum (backward-compatible)."""
    bag = ItemStats(code="bag", level=1, type_="bag", inventory_space=100)
    assert strategic_value(bag, (1000, 1, 1, 50, 0)) == 5000


def test_efficiency_under_budget_passes_through():
    """Below the cap the efficiency block is unchanged (combat 0 + 5*50=250)."""
    bag = ItemStats(code="bag", level=1, type_="bag", inventory_space=5)
    assert strategic_value(bag, (1000, 1, 1, 50, 0), efficiency_budget=999) == 250


# ---- #14 horizon factor ----

def test_horizon_scales_efficiency_only_not_combat():
    """horizon (num,den) scales the efficiency block by num/den; combat untouched.
    weapon attack 10 (combat 10000) + bag-ish efficiency: a mixed item with
    inventory 10 (weight 50 → eff 500) at horizon 1/2 → eff 250, combat stays."""
    item = ItemStats(code="m", level=1, type_="body_armor",
                     resistance={"earth": 10}, inventory_space=10)
    # combat_raw 10 → 10000; efficiency 10*50=500; horizon 1/2 → 250.
    assert strategic_value(item, (1000, 1, 1, 50, 0), horizon=(1, 2)) == 10000 + 250


def test_horizon_zero_at_max_level_kills_efficiency():
    """At max level the horizon numerator is 0 → efficiency contributes nothing."""
    bag = ItemStats(code="bag", level=1, type_="bag", inventory_space=35)
    assert strategic_value(bag, (1000, 1, 1, 50, 0), horizon=(0, 50)) == 0


def test_horizon_full_early_is_unscaled():
    """Full horizon (50/50) leaves the efficiency block unchanged."""
    bag = ItemStats(code="bag", level=1, type_="bag", inventory_space=35)
    full = strategic_value(bag, (1000, 1, 1, 50, 0), horizon=(50, 50))
    none = strategic_value(bag, (1000, 1, 1, 50, 0))
    assert full == none == 35 * 50


def test_horizon_preserves_combat_dominance():
    """Horizon only shrinks the (capped) efficiency block, so a combat item still
    outranks an all-efficiency item at any horizon."""
    bag = ItemStats(code="bag", level=1, type_="bag", inventory_space=100)
    weapon = ItemStats(code="w", level=1, type_="weapon", attack={"earth": 1})
    capped_bag = strategic_value(bag, (1000, 1, 1, 50, 0), efficiency_budget=999, horizon=(49, 50))
    one_combat = strategic_value(weapon, (1000, 1, 1, 50, 0), efficiency_budget=999, horizon=(49, 50))
    assert capped_bag < one_combat == 1000
