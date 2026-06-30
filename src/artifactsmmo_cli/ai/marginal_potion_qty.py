"""Win-rate-scaled potion quantity for marginal-fight provisioning.

The harder the fight, the more health potions to stack into a utility slot: 0 when
the monster is not marginal (observed win-rate at/above the threshold, or too few
samples), 1 just below the threshold, scaling up to a full stack at the full-stack
win-rate, then clamped to the full stack down to the combat veto floor. The
equipped count never exceeds what the bot holds.

Win-rate is an integer permille (success_rate * 1000) so the decision is float-free
and mirrors `formal/Formal/MarginalPotionQty.lean` bit-for-bit over Nat. The
float->permille conversion lives in the goal glue (strategy_driver), not here.
"""


def marginal_potion_qty_pure(
    samples: int,
    win_permille: int,
    min_samples: int,
    threshold_permille: int,
    full_stack_permille: int,
    max_stack: int,
    utility_slot_filled: bool,
    held_heal_qty: int,
) -> int:
    if utility_slot_filled or held_heal_qty <= 0:
        return 0
    if samples < min_samples or win_permille >= threshold_permille:
        return 0
    if win_permille <= full_stack_permille:
        desired = max_stack
    else:
        # fraction = (threshold - win) / (threshold - full), rises as win falls.
        # desired = ceil(fraction * max_stack), floored at 1. Integer ceil:
        # (a + b - 1) // b for a, b > 0.
        numerator = (threshold_permille - win_permille) * max_stack
        denominator = threshold_permille - full_stack_permille
        desired = max(1, (numerator + denominator - 1) // denominator)
    return min(desired, held_heal_qty)
