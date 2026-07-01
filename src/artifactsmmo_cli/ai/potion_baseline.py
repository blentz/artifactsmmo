"""Level-scaled potion baseline: how many potions to keep on-hand at a given level.
Flat `low_qty` through `low_level`, full `high_qty` at/above `high_level`, linear ramp
(floor) between. Float-free; mirrored bit-for-bit by formal/Formal/PotionBaseline.lean."""


def potion_baseline_pure(
    level: int, low_level: int, low_qty: int, high_level: int, high_qty: int,
) -> int:
    if level <= low_level:
        return low_qty
    if level >= high_level:
        return high_qty
    # linear interpolation, floored: low_qty + (high_qty-low_qty)*(level-low_level)//(high_level-low_level)
    return low_qty + (high_qty - low_qty) * (level - low_level) // (high_level - low_level)
