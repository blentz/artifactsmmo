"""How far to commit toward a sibling's material demand in one goal.

Replaces the bare `banked + 1` "replenish-one-replan" idiom. A supply commitment
target recomputed on every acquisition churns its goal's repr, which is part of
its identity, resetting sticky-commit keying each cycle. Measured case: two
characters produced 456 units against an ask of 60, with the commitment target
churning across `x50 -> x10 -> x60 -> x61 -> x40 -> x37 -> x59 -> x41 -> x81 ->
x116 -> x100 -> x97 -> x129` on every cycle as the `banked + demand` rule
recomputed the target against a republished demand.

The milestone ladder keeps both properties. The target is an ABSOLUTE multiple of
`SUPPLY_BATCH`, so it does not move while the character works through a batch,
and it is never more than `banked + demand`, so no commitment exceeds what was
asked.
"""

from artifactsmmo_cli.ai.thresholds import SUPPLY_BATCH


def supply_batch_target_pure(banked: int, demand: int) -> int:
    """Total units of the supply this goal should commit to producing.

    Returns the next batch milestone strictly above `banked`, clamped to `banked + demand`.
    Equal to `banked` when there is nothing to supply (`demand <= 0`).

    Always strictly greater than `banked` while `demand > 0`, so the goal can
    never be trivially satisfied and spin.
    """
    if demand <= 0:
        return banked
    # Next multiple of the batch strictly above `banked`: ceil((banked + 1) / batch).
    batches = -(-(banked + 1) // SUPPLY_BATCH)
    return min(banked + demand, batches * SUPPLY_BATCH)
