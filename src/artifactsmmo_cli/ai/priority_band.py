"""Clamp a learned priority bonus into a goal's discretionary band.

A discretionary goal's priority must never escape its [floor, ceiling] band;
since every discretionary band's ceiling sits below the survival floor, this
guarantees by construction that a learned bonus can never reorder a
discretionary goal above a survival goal.

EXACT-RATIONAL CORE. ``clamp_into_band`` operates over ``fractions.Fraction``
(exact rational arithmetic), matching the Lean ``clampIntoBand`` over ``Rat``
BIT-FOR-BIT. Callers pass any rational inputs (the live caller in
``grind_character_xp.py`` lifts ``char_xp * SCALAR_TO_PRIORITY_GAIN`` into a
Fraction and the constants ``30``/``45``); ``min``/``max``/``+`` on Fractions are
exact. The previous float-vs-Int "order-faithful abstraction" caveat is closed.
"""
from fractions import Fraction


def clamp_into_band(floor: Fraction, ceiling: Fraction, bonus: Fraction) -> Fraction:
    """Return ``floor + bonus`` clamped into ``[floor, ceiling]``.

    Result is always within ``[floor, ceiling]`` when ``floor <= ceiling``,
    regardless of bonus sign or magnitude. EXACT under ``Fraction`` arithmetic —
    matches the Lean ``clampIntoBand`` over ``Rat`` byte-for-byte.
    """
    return min(ceiling, max(floor, floor + bonus))
