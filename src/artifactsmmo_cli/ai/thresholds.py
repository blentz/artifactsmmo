"""Single source of truth for the HP-critical preempt threshold and the
inventory space-pressure ladder.

Stdlib-only leaf: imports nothing from the decision layers (goals/, tiers/) so
any module can depend on it without an import cycle — the very reason these
constants used to be re-typed in several places. Consolidating them here removes
that silent-drift risk (DRY backlog Group A, findings #2 and #3).

The pressure ladder is strictly ascending: CRAFT_RELIEF < HIGH < DEPOSIT_FULL <
CRITICAL. A proven liveness invariant (Formal.Liveness.MeansFiring) relies on
HIGH < DEPOSIT_FULL; keeping the rungs in one ascending block makes an inverting
edit obvious. The Lean model carries its OWN copies of these values; the
PRESSURE_HIGH num/den pair is additionally mirrored into Lean by mechanical
extraction (scripts/extract_lean.py -> Formal/Extracted/Thresholds.lean) so the
proven overstock core and this source cannot diverge.
"""

# HP-critical preempt threshold (hp / max_hp). Below this the HP-critical guard
# preempts every other means and RestoreHPGoal returns its ceiling value. Set to
# 0.75 (was 0.25) so the bot rests to full before fighting: low-HP fight starts
# were the avoidable-loss source that tripped the combat veto (see spec
# 2026-06-30). _is_winnable (player.py) projects HP to max before the winnability
# check, so the 2026-06-06 "parked at 76/130" deadlock does not recur.
CRITICAL_HP_FRACTION = 0.75

# Inventory space-pressure ladder, as exact integer rationals (num/den). The
# proven overstock core cross-multiplies these ints (float-free at the boundary).
# NOTE: each must be a single-name int-literal assignment — the Lean extractor
# (scripts/extract_lean.py) recognizes only that form for the mirrored pair.
CRAFT_RELIEF_NUM = 14
CRAFT_RELIEF_DEN = 20
PRESSURE_HIGH_NUM = 17
PRESSURE_HIGH_DEN = 20
DEPOSIT_FULL_NUM = 18
DEPOSIT_FULL_DEN = 20
PRESSURE_CRITICAL_NUM = 19
PRESSURE_CRITICAL_DEN = 20

# Float views (human-facing); equal the legacy re-typed literals exactly:
# 0.70 / 0.85 / 0.90 / 0.95.
CRAFT_RELIEF_FRACTION = CRAFT_RELIEF_NUM / CRAFT_RELIEF_DEN
PRESSURE_HIGH_FRACTION = PRESSURE_HIGH_NUM / PRESSURE_HIGH_DEN
DEPOSIT_FULL_FRACTION = DEPOSIT_FULL_NUM / DEPOSIT_FULL_DEN
PRESSURE_CRITICAL_FRACTION = PRESSURE_CRITICAL_NUM / PRESSURE_CRITICAL_DEN

# Marginal-fight potion provisioning (spec 2026-06-30).
UTILITY_SLOT_MAX_STACK = 100       # openapi.json EquipSchema.quantity.maximum

# Level-scaled potion stocking (spec 2026-06-30-potion-supply). Baseline ramps
# linearly from (level 5 -> 5 potions) to (level 45 -> 100 potions).
POTION_LOW_LEVEL = 5
POTION_LOW_QTY = 5
POTION_HIGH_LEVEL = 45
POTION_HIGH_QTY = 100             # == UTILITY_SLOT_MAX_STACK
POTION_GATHER_BATCH = 5           # gather/craft this many when gathering is required
