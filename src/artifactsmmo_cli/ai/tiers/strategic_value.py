"""Strategic value: efficiency-weighted item score for cross-slot objective priority.

Separate from the proved COMBAT scorer `equip_value` (tiers/equip_value.py),
which sums every stat 1:1 and ranks within-slot combat loadout. `equip_value`
is consumed by 10 modules and is deliberately left untouched (#16 plan,
PLAN_acquisition_timing.md). `strategic_value` instead re-weights the
non-combat EFFICIENCY stats (wisdom, prospecting, inventory_space, haste) by a
per-stat efficiency rate so a bag's compounding value isn't scored like raw
attack, while combat stats keep a single shared weight so combat-slot ordering
is preserved. It feeds ObjectiveGap cross-slot priority + #14 acquisition timing
ONLY — never the combat loadout pick.

The per-stat WEIGHTS are derived (openapi rates for wisdom/prospecting; a
gather/craft-cadence proxy for inventory_space; an empirical probe for haste —
PLAN_acquisition_timing.md Phase 1) and supplied by the impure layer that owns
game_data; this module is the pure, total, nonneg-int weighted sum the objective
proofs are parametric over. Mirrored in Formal/StrategicValue.lean (hand model)
and Formal/Extracted/StrategicValue.lean (extracted), bridged in Bridges8.lean.
"""


def strategic_value_pure(
    combat_raw: int,
    wisdom: int,
    prospecting: int,
    inventory_space: int,
    haste: int,
    combat_weight: int,
    wisdom_weight: int,
    prospecting_weight: int,
    inventory_weight: int,
    haste_weight: int,
) -> int:
    """PURE CORE (extracted): the nonneg-weighted strategic sum — each of the
    five inputs (combat_raw, wisdom, prospecting, inventory_space, haste) scaled
    by its own weight and added together.

    `combat_raw` is the already-summed genuine-combat signal (attack +
    resistance + hp_restore + hp_bonus + dmg + critical_strike + lifesteal +
    combat_buff) carrying ONE shared `combat_weight`, so the combat ordering
    `equip_value` produces is preserved when combat_weight dominates the
    efficiency weights. The four efficiency stats each carry their own derived
    rate weight. Every summand is exact integer arithmetic, matching the Lean
    `Formal.StrategicValue.strategicValue` model directly.

    For nonneg stats and nonneg weights the result is nonneg (the ObjectiveGap
    gap bounds need this) and monotone non-decreasing in every stat — proved
    over all inputs in Formal/StrategicValue.lean and transferred onto this
    extracted def by the Bridges8 bridge.
    """
    return (
        combat_raw * combat_weight
        + wisdom * wisdom_weight
        + prospecting * prospecting_weight
        + inventory_space * inventory_weight
        + haste * haste_weight
    )
