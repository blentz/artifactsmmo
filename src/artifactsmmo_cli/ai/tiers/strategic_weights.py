"""Derive strategic_value's per-stat weights from LEARNED gameplay data (#16
Phase 3b).

`strategic_value` (tiers/strategic_value.py) scores gear for cross-slot priority:
combat stats at the dominant SCALE weight, non-combat efficiency stats
(wisdom/prospecting/inventory_space/haste) at a per-stat rate. This module
computes those efficiency rates in a COMMON currency — cooldown-seconds saved —
so they are commensurate with each other, frequency-weighted by the observed
action mix.

Why learned, not static: the ArtifactsMMO API has NO fight-cooldown formula and
no char-level xp curve, so the typical action cooldowns AND how often each action
runs are read from the LearningStore (action_class_cost / action_class_fraction)
rather than assumed. Cold (no observations) → every efficiency rate is 0, so the
bot ranks gear on combat alone until it has learned enough — no invented rates.

Commensuration vs combat (the dominance decision, user 2026-06-21): combat and
cooldown-seconds are different dimensions, so combat dominance is STRUCTURAL, not
a shared unit — `strategic_value` caps the whole efficiency block at
EFFICIENCY_BUDGET (< one combat-raw point × SCALE), so efficiency orders gear only
among efficiency-bearing / empty slots and can never outrank a real combat
upgrade. This module returns that budget alongside the weights.
"""

from artifactsmmo_cli.ai.learning.projections import DEFAULT_FIGHT_CYCLES
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.tiers.strategic_value import STRATEGIC_SCALE
from artifactsmmo_cli.ai.world_state import WorldState

# Combat keeps the dominant weight (= SCALE); see strategic_value.
COMBAT_WEIGHT = STRATEGIC_SCALE

# The whole efficiency block is capped just below one combat-raw point (× SCALE),
# so any combat item (raw >= 1 → combat_part >= SCALE) outranks any all-efficiency
# item. Efficiency ordering happens strictly within this sub-budget.
EFFICIENCY_BUDGET = STRATEGIC_SCALE - 1

# Fixed-point scale converting cooldown-seconds-saved (fractional) to the integer
# weights the proved core consumes. Sized so a typical efficiency item lands well
# inside EFFICIENCY_BUDGET (the cap is the hard guarantee; this is resolution).
SECONDS_FP = 100

# openapi: wisdom/prospecting = "1% extra per 10 points" = 0.001 fraction per point.
_XP_DROP_RATE_PER_POINT = 0.001

# No invented cooldowns: the API exposes no static per-action cooldown formula,
# so an unlearned move/deposit cooldown contributes a rate of 0 (default 0.0)
# rather than a fabricated figure — the same discipline `haste` follows below.
# The action-mix fraction is ~0 cold anyway, and once deposits/moves actually
# occur their cooldowns are sampled, so this path is essentially unreachable.
_UNLEARNED_CD = 0.0

_FIGHT_CLASS = "FightAction"
_MOVE_CLASS = "MovementAction"
_DEPOSIT_CLASS = "DepositAllAction"


def strategic_weights(
    state: WorldState, history: LearningStore | None,
) -> tuple[tuple[int, int, int, int, int], int]:
    """Return ``((combat, wisdom, prospecting, inventory, haste), budget)``.

    Efficiency weights are ``round(seconds_saved_rate × SECONDS_FP)`` where each
    rate is frequency-weighted by the learned action mix:

      * wisdom / prospecting: ``0.001 × fight_cd × f_fight`` (a point helps on
        every FIGHT cycle — fewer fights to level / per drop);
      * inventory_space: ``(bank_roundtrip_cd / inventory_max) × f_trip`` per slot
        (a slot defers a fraction of a bank trip, on every TRIP cycle);
      * haste: 0 until the live probe measures its cooldown-reduction rate (no
        invented rate).

    With no history (or no observations) every fraction is 0 → efficiency weights
    are 0 and only combat drives gear priority. All weights are non-negative, so
    the proved `strategic_value_pure` nonneg/monotonicity contracts hold."""
    if history is None:
        return (COMBAT_WEIGHT, 0, 0, 0, 0), EFFICIENCY_BUDGET

    fight_cd = history.action_class_cost(_FIGHT_CLASS, default=DEFAULT_FIGHT_CYCLES)
    f_fight = history.action_class_fraction(_FIGHT_CLASS)
    move_cd = history.action_class_cost(_MOVE_CLASS, default=_UNLEARNED_CD)
    deposit_cd = history.action_class_cost(_DEPOSIT_CLASS, default=_UNLEARNED_CD)
    f_trip = history.action_class_fraction(_DEPOSIT_CLASS)

    xp_drop_rate = _XP_DROP_RATE_PER_POINT * fight_cd * f_fight
    roundtrip_cd = 2.0 * move_cd + deposit_cd
    inventory_max = state.inventory_max
    inventory_rate = (roundtrip_cd / inventory_max) * f_trip if inventory_max > 0 else 0.0

    weights = (
        COMBAT_WEIGHT,
        round(xp_drop_rate * SECONDS_FP),       # wisdom
        round(xp_drop_rate * SECONDS_FP),       # prospecting
        round(inventory_rate * SECONDS_FP),     # inventory_space
        0,                                       # haste — deferred to the probe
    )
    return weights, EFFICIENCY_BUDGET
