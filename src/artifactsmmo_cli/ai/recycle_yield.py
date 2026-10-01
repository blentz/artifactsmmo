"""What one recycled unit is expected to return, per material.

The server returns a FIXED total per unit recycled, drawn at random from the
recipe's material units (measured over 902 live recycles, 2026-10-01: 2 per unit
at recipe sums 6-8, 3 at 12-15, 4 at 16; one `iron_dagger` returned two feathers
and no iron_bar). The total is learned per item (`LearningStore.
fleet_recycle_totals`); the split is a random selection, so material `m` is
expected `total * q_m / sum(q)` per unit. The planner credits the whole part of
that expectation: a share below one unit is no supply it can count on.
"""

from collections.abc import Mapping


def recycle_unit_yield(recipe: Mapping[str, int], total: int) -> dict[str, int]:
    """Expected whole units of each recipe material one recycled unit returns,
    for a learned per-unit `total`."""
    weight = sum(recipe.values())
    return {material: total * qty // weight for material, qty in recipe.items()}
