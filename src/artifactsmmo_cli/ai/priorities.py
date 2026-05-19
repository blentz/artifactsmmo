"""Single source of truth for goal priorities. Higher = more urgent.

Read top-to-bottom: every goal's relative position is documented here.
Changing any value here changes every goal that uses it. To shift a single
goal's position, change ITS constant — don't redefine the constant inline.

Hard rules (asserted by tests in test_priorities.py):
  - HP_CRITICAL must beat every other constant in this file.
  - Survival/prereq constants (HP_CRITICAL, UNLOCK_*, DEPOSIT_FULL) must
    sit above tactical pursuits (FARM_*, UPGRADE_*).
  - GATHER_MATERIALS > FARM_ITEMS_BASE so an in-flight upgrade-material
    chain interrupts the current task loop.
"""

# === Survival floor — top of the ladder ===

HP_CRITICAL = 110.0
"""When state.hp_percent < RestoreHPGoal.CRITICAL_HP_FRACTION. Beats every
other goal so the bot heals/consumes before continuing combat."""

# === Hard prerequisites — gates that, unmet, make other goals unsatisfiable ===

BANK_UNLOCK = 90.0
"""UnlockBankGoal when bank requires a fight Robby can actually attempt."""

COMPLETE_TASK = 90.0
"""CompleteTaskGoal when a fully-progressed task is held — turn it in for reward."""

REACH_UNLOCK_LEVEL = 85.0
"""ReachUnlockLevelGoal: drive char XP grinding to satisfy a learned blocker
within MAX_ACHIEVABLE_GAP levels."""

# === Inventory pressure ===

DEPOSIT_FULL = 80.0
"""DepositInventoryGoal ceiling (at 100% used). Ramps from 0 at
DepositInventoryGoal._RAMP_START (50%)."""

DISCARD_OVERSTOCK_BASE = 40.0
"""DiscardOverstockGoal baseline when overstock present but bag not full.
Sits below GATHER_MATERIALS (50) — overstock is non-urgent during normal
gather/craft chains."""

DISCARD_OVERSTOCK_HIGH_PRESSURE = 55.0
"""DiscardOverstockGoal when inventory_used > HIGH_PRESSURE_FRACTION (0.85).
Above GATHER_MATERIALS so the bot preempts gather to free slots before
the bag fills and Gather actions start failing."""

DISCARD_OVERSTOCK_CRITICAL = 85.0
"""DiscardOverstockGoal when inventory_used > CRITICAL_PRESSURE_FRACTION (0.95).
Above DEPOSIT_FULL (80) and tactical pursuits but below COMPLETE_TASK and
BANK_UNLOCK so hard prerequisites still win. Bag this full and any Gather
will fail; clear excess immediately."""

# === Strategic decisions (data-driven) ===

LOW_YIELD_CANCEL = 70.0
"""LowYieldCancelGoal when projection shows alternatives clearly pay more."""

LEVEL_SKILL = 55.0
"""LevelSkillGoal when an upgrade is gated on +N (≤ MAX_SKILL_GAP) skill levels."""

# === Tactical pursuits ===

GATHER_MATERIALS = 50.0
"""GatherMaterialsGoal: gather/craft until target_item's recipe is satisfied.
Fixed high priority so material chains finish before the loop reverts to farming."""

UPGRADE_EQUIPMENT_RELEVANT_TOOL = 50.0
"""UpgradeEquipmentGoal value when the chosen upgrade has a positive
skill_effect for the active task's gather skill (e.g. better axe during
ash_plank task → woodcutting)."""

UPGRADE_EQUIPMENT_INVENTORY_READY = 60.0
"""UpgradeEquipmentGoal priority when an upgrade is sitting in inventory
ready to equip in one action — preempts gathering so we don't grind
unnecessary materials."""

FARM_ITEMS_BASE = 35.0
"""FarmItemsGoal base (per-cycle items-task delivery). Outranks FarmMonster
cold-start so an active items task dominates monster grinding."""

UPGRADE_EQUIPMENT_BASE = 35.0
"""UpgradeEquipmentGoal base when no relevant-tool match."""

FARM_MONSTER_BASE = 30.0
"""FarmMonsterGoal base (per-cycle character-XP grinding)."""

GRIND_CHARACTER_XP_FLOOR = 30.0
"""GrindCharacterXPGoal lower bound (cold-start with no observed monster yield)."""

GRIND_CHARACTER_XP_CEILING = 45.0
"""GrindCharacterXPGoal upper bound (after dynamic bonus). Caps below
LEVEL_SKILL so skill-driven progression wins over generic XP grind."""

# === Long-tail / opportunistic ===

TASK_EXCHANGE = 22.0
"""TaskExchangeGoal when enough tasks_coin to spend a full batch."""

ACCEPT_TASK = 20.0
"""AcceptTaskGoal when no task held."""

TASK_CANCEL_TOO_HARD = 12.0
"""TaskCancelGoal (the combat-driven variant; LowYieldCancelGoal is the
data-driven counterpart at LOW_YIELD_CANCEL=70)."""
