"""Clamp a learned priority bonus into a goal's discretionary band.

A discretionary goal's priority must never escape its [floor, ceiling] band;
since every discretionary band's ceiling sits below the survival floor, this
guarantees by construction that a learned bonus can never reorder a
discretionary goal above a survival goal.
"""


def clamp_into_band(floor: float, ceiling: float, bonus: float) -> float:
    """Return floor+bonus clamped into [floor, ceiling].

    Result is always within [floor, ceiling] when floor <= ceiling, regardless
    of bonus sign or magnitude.
    """
    return min(ceiling, max(floor, floor + bonus))
