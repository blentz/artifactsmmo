"""Strategic value: the ONE gear ruler read for ACQUISITION priority.

`equip_value` (tiers/equip_value.py) = `gear_value(stats, Rank)` answers "which
piece is better". `strategic_value` answers the different, ECONOMIC question:
what is worth spending gold and cycles ACQUIRING, under a leveling horizon.
It does NOT compute a second score. It takes the ruler's own two terms —
`gear_components(stats, Rank)` = (COMBAT, EFFICIENCY) — and re-weights them, so
the two layers can never reach contradictory verdicts about the same item.

* COMBAT is the ruler's combat term verbatim (monster-relative defense +
  offense at the canonical adversary, plus the in-fight flat stats). It used to
  be a flat 8-stat sum `combat_raw` defined alongside the ruler; that sum
  weighted a resistance PERCENTAGE 1:1 against an HP amount, and it is gone.
* EFFICIENCY is the four time-buying stats (wisdom, prospecting,
  inventory_space, haste) — the SAME four the ruler isolates in
  `armor_score_efficiency` — re-weighted per stat, because a bag's compounding
  value should not be priced like raw attack, and optionally CAPPED.

Because the ruler's combat term takes no utility stat as an input at all
(`armor_score_combat_pure` has no such parameter), utility enters this score
exactly once, through the efficiency block.

The per-stat efficiency WEIGHTS are derived (openapi rates for
wisdom/prospecting; a gather/craft-cadence proxy for inventory_space; an
empirical probe for haste — PLAN_acquisition_timing.md Phase 1) and supplied by
the impure layer that owns game_data; `strategic_value_pure` is the pure, total,
nonneg-int weighted sum the objective proofs are parametric over. Mirrored in
Formal/StrategicValue.lean (hand model) and Formal/Extracted/StrategicValue.lean
(extracted), bridged in Bridges9.lean.
"""

from artifactsmmo_cli.ai.game_data import ItemStats
from artifactsmmo_cli.ai.gear_value import gear_components
from artifactsmmo_cli.ai.gear_value_core import Rank

# Fixed-point scale for the efficiency weights. The documented per-point rates
# are sub-unit (openapi: wisdom/prospecting = "1% extra per 10 points" = 0.001
# benefit fraction per point), so we carry every weight in 1/STRATEGIC_SCALE
# units to stay inside the proved nonneg-INT core (mirrors the ×10000 fixed
# point used in predict_win's lifesteal arithmetic).
#
# It doubles as the LEXICOGRAPHIC RADIX: paired with an efficiency block bounded
# to `|block| <= (SCALE - 1) // 2`, weighting combat by SCALE makes the score an
# order-embedding of the pair (combat, efficiency) ordered lexicographically.
# See `pursuit_value` for the derivation and the dominance property it buys.
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


def _combat_of_stats(stats: ItemStats) -> int:
    """strategic_value's combat input: the ONE gear ruler's own COMBAT term at
    the Rank purpose (`ai/gear_value.gear_components`).

    It MUST be the ruler's own term and not a scalar computed here, or the
    economics layer becomes a second ruler that can disagree with the picker
    about the same slot — the livelock class documented in
    `equipment/slot_occupancy.py`. Taking `[0]` of the ruler's partition is
    what makes that impossible by construction rather than by re-tuning."""
    return gear_components(stats, Rank)[0]


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

    `combat_raw` is the caller's already-computed combat scalar — in production
    the ONE gear ruler's own combat term (`gear_components(stats, Rank)[0]`),
    hoisted here by the `strategic_value` wrapper — carrying ONE shared
    `combat_weight`, so the combat ordering `equip_value` produces is preserved
    exactly when combat_weight dominates the efficiency weights. The four
    efficiency stats each carry their own derived rate weight. The core stays
    parametric in the scalar: it is the WEIGHTED SUM that is proved here, not
    any particular combat formula.
    Every summand is exact integer arithmetic, matching the Lean
    `Formal.StrategicValue.strategicValue` model directly.

    For nonneg stats and nonneg weights the result is nonneg and monotone
    non-decreasing in every stat — proved
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
    """ACQUISITION value of an equippable (#14/#16) — never the combat loadout
    pick (that stays on `equip_value`, the same ruler read un-re-weighted).

    value = COMBAT × combat_weight + EFFICIENCY, where COMBAT is
    `gear_components(stats, Rank)[0]` — the ONE ruler's own combat term — and
    EFFICIENCY is the weighted sum of the four time-buying stats the ruler
    isolates, optionally BOUNDED to `[-efficiency_budget, +efficiency_budget]`.

    Combat dominance is STRUCTURAL, by an order-embedding rather than by the
    numbers happening to work out. With `2 * efficiency_budget < combat_weight`
    the map `(c, e) ↦ c * combat_weight + clamp(e)` is strictly monotone in `c`:
    two items whose combat terms differ by even ONE unit cannot be reordered by
    any efficiency stats whatsoever, because the whole efficiency range spans
    less than one combat unit. Efficiency still totally ORDERS items whose
    combat terms tie — utility slots keep their ranking. `efficiency_budget=None`
    leaves the block unbounded (the plain weighted sum, no dominance claim).
    The bound is policy in this wrapper; the proved core `strategic_value_pure`
    stays a pure weighted sum. Derived weights + budget come from
    `strategic_weights(state, history)`.

    The bound is SYMMETRIC because efficiency stats can be NEGATIVE in the live
    catalog (obsidian_battleaxe / mesh_armor carry `inventory_space` −25 / −10).
    A one-sided cap would leave the block's SPAN unbounded below, and a span
    wider than `combat_weight` breaks the embedding. Flooring at 0 instead would
    have bounded it at the cost of making every inventory penalty invisible.

    `horizon=(num, den)` (#14 acquisition timing) scales the efficiency block by
    `num/den` — the fraction of the character's leveling still ahead,
    `(max_level − level) / max_level`. Efficiency benefits (saved cooldowns)
    accrue over the REMAINING climb, so they are worth most early and decay to 0
    at max level (the bot won't chase a rune at L49). Combat is NOT scaled — a
    weapon is needed regardless of horizon. Scaling only shrinks |efficiency|
    (`num <= den`), so it can only strengthen dominance. `None` ⇒ factor 1.
    """
    combat = _combat_of_stats(stats)
    combat_w, wisdom_w, prospecting_w, inventory_w, haste_w = weights
    combat_part = combat * combat_w
    # Efficiency block via the proved core with combat zeroed out, then bounded,
    # then horizon-scaled (#14). Bound-before-scale keeps the result in range.
    efficiency_part = strategic_value_pure(
        0, stats.wisdom, stats.prospecting, stats.inventory_space, stats.haste,
        0, wisdom_w, prospecting_w, inventory_w, haste_w,
    )
    if efficiency_budget is not None:
        if efficiency_part > efficiency_budget:
            efficiency_part = efficiency_budget
        if efficiency_part < -efficiency_budget:
            efficiency_part = -efficiency_budget
    if horizon is not None:
        num, den = horizon
        efficiency_part = efficiency_part * num // den
    return combat_part + efficiency_part
