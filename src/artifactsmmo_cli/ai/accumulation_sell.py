# accumulation_sell

"""Ratio-driven, space-pressure-independent sell-down of accumulated multiples.

Pure integer-exact core (no float, so it mirrors the Lean `AccumulationSell`
def byte-for-byte under the differential gate). An item is over-accumulated when
its held quantity is a large multiple of its keep-cap (`useful_quantity_cap`);
the bot sheds the surplus down to the cap by selling, with urgency rising
geometrically (one step per doubling of the ratio).
"""


ACCUM_MULT = 5
"""Fire the accumulation sell when `held >= ACCUM_MULT * max(cap, 1)`."""

SEVERE_STEPS = 5
"""`accumulation_steps >= SEVERE_STEPS` (held >= cap*32) escalates the sell above
the progression band (see `tiers/means.py` SELL_PRESSURED)."""


def accumulation_steps(held: int, cap: int) -> int:
    """Geometric severity: the largest `k >= 0` with `eff_cap * 2**k <= held`
    (= floor(log2(held / eff_cap))), `eff_cap = max(cap, 1)`. 0 when held is
    below `eff_cap`. Integer-exact doubling — no float."""
    eff_cap = cap if cap > 1 else 1
    if held < eff_cap:
        return 0
    k = 0
    bound = eff_cap
    while bound * 2 <= held:
        bound = bound * 2
        k = k + 1
    return k


def accumulation_excess(held: int, cap: int) -> int:
    """`held - max(cap, 0)` when `held >= ACCUM_MULT * max(cap, 1)`, else 0.
    The RATIO gate uses `eff_cap = max(cap, 1)`; the amount kept is the TRUE cap,
    so a dominated item (cap 0) past the gate sells down to 0, a kept item
    (cap 1) sells down to 1."""
    eff_cap = cap if cap > 1 else 1
    if held < ACCUM_MULT * eff_cap:
        return 0
    keep = cap if cap > 0 else 0
    return held - keep
