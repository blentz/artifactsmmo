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
and Formal/Extracted/StrategicValue.lean (extracted), bridged in Bridges9.lean.
"""

from artifactsmmo_cli.ai.game_data import ItemStats

# Fixed-point scale for the efficiency weights. The documented per-point rates
# are sub-unit (openapi: wisdom/prospecting = "1% extra per 10 points" = 0.001
# benefit fraction per point), so we carry every weight in 1/STRATEGIC_SCALE
# units to stay inside the proved nonneg-INT core (mirrors the ×10000 fixed
# point used in predict_win's lifesteal arithmetic).
STRATEGIC_SCALE = 1000

# Combat stats keep weight 1 (= SCALE), the DOMINANT weight: the cross-slot gap
# fractions are ratios so the shared scale cancels, leaving combat-slot ordering
# identical to equip_value. Efficiency stats are sub-dominant.
_COMBAT_WEIGHT = STRATEGIC_SCALE

# wisdom / prospecting: openapi "1% extra per 10 points" → 0.001 fraction/pt →
# 0.001 × SCALE = 1 fixed-point unit. Down-weighted ~1000× vs combat, so XP/drop
# artifacts no longer rank like raw attack in cross-slot priority (#16).
_WISDOM_WEIGHT = round(0.001 * STRATEGIC_SCALE)
_PROSPECTING_WEIGHT = round(0.001 * STRATEGIC_SCALE)

# inventory_space + haste: DEFERRED (PLAN_acquisition_timing.md Phase 3b / the
# live haste probe). No commensurated cooldown-seconds-saved rate exists yet, so
# rather than INVENT one these retain weight PARITY with combat (= SCALE) — the
# same 1:1 treatment equip_value gives them, i.e. unchanged behaviour until the
# derived rates land. NOT a derived value; an explicit hold.
_INVENTORY_WEIGHT_DEFERRED = STRATEGIC_SCALE
_HASTE_WEIGHT_DEFERRED = STRATEGIC_SCALE

# (combat, wisdom, prospecting, inventory, haste) in fixed-point units.
DEFAULT_STRATEGIC_WEIGHTS: tuple[int, int, int, int, int] = (
    _COMBAT_WEIGHT, _WISDOM_WEIGHT, _PROSPECTING_WEIGHT,
    _INVENTORY_WEIGHT_DEFERRED, _HASTE_WEIGHT_DEFERRED,
)


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
    extracted def by the Bridges9 bridge.
    """
    return (
        combat_raw * combat_weight
        + wisdom * wisdom_weight
        + prospecting * prospecting_weight
        + inventory_space * inventory_weight
        + haste * haste_weight
    )


def strategic_value(
    stats: ItemStats,
    weights: tuple[int, int, int, int, int] = DEFAULT_STRATEGIC_WEIGHTS,
    efficiency_budget: int | None = None,
    horizon: tuple[int, int] | None = None,
) -> int:
    """Efficiency-weighted cross-slot value of an equippable — used ONLY by gear
    cross-slot priority (#14/#16, StrategyEngine._equip_gain), never the combat
    loadout pick (that stays on the proved `equip_value`).

    Hoists the ItemStats dict sums to the ints the extracted core takes:
    `combat_raw` is the genuine-combat signal (attack + resistance + hp_restore +
    hp_bonus + dmg + critical_strike + lifesteal + combat_buff) — exactly
    `equip_value`'s raw signal MINUS the four efficiency stats, which are weighted
    separately.

    value = combat_raw × combat_weight + EFFICIENCY, where EFFICIENCY is the
    weighted efficiency-stat sum optionally CAPPED at `efficiency_budget`. Combat
    and the efficiency rates are different dimensions (stat-points vs
    cooldown-seconds), so combat dominance is STRUCTURAL: with the budget set
    below one combat-raw point (× weight), any combat item outranks any
    all-efficiency item, and efficiency only orders gear among efficiency-bearing
    / empty slots (#16 sub-budget decision). `efficiency_budget=None` leaves the
    block uncapped (the plain weighted sum). The cap is policy in this wrapper;
    the proved core `strategic_value_pure` stays a pure weighted sum. Derived
    weights + budget come from `strategic_weights(state, history)`.

    `horizon=(num, den)` (#14 acquisition timing) scales the efficiency block by
    `num/den` — the fraction of the character's leveling still ahead,
    `(max_level − level) / max_level`. Efficiency benefits (saved cooldowns)
    accrue over the REMAINING climb, so they are worth most early and decay to 0
    at max level (the bot won't chase a rune at L49). Combat is NOT scaled — a
    weapon is needed regardless of horizon. Scaling only shrinks the (already
    capped) efficiency block, so combat dominance is preserved. `None` ⇒ factor 1.
    """
    attack = sum(stats.attack.values()) if stats.attack else 0
    resistance = sum(stats.resistance.values()) if stats.resistance else 0
    combat_raw = (attack + resistance + stats.hp_restore + stats.hp_bonus
                  + stats.dmg + stats.critical_strike + stats.lifesteal
                  + stats.combat_buff)
    combat_w, wisdom_w, prospecting_w, inventory_w, haste_w = weights
    combat_part = combat_raw * combat_w
    # Efficiency block via the proved core with combat zeroed out, then capped,
    # then horizon-scaled (#14). Cap-before-scale keeps the result ≤ budget.
    efficiency_part = strategic_value_pure(
        0, stats.wisdom, stats.prospecting, stats.inventory_space, stats.haste,
        0, wisdom_w, prospecting_w, inventory_w, haste_w,
    )
    if efficiency_budget is not None and efficiency_part > efficiency_budget:
        efficiency_part = efficiency_budget
    if horizon is not None:
        num, den = horizon
        efficiency_part = efficiency_part * num // den
    return combat_part + efficiency_part
