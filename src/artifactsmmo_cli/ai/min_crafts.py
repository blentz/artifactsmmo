"""Lower bound on CRAFT actions to obtain `qty` of `item` given `owned`.

One craft per craftable closure node that must be produced (not covered by held
copies). A raw leaf (no recipe) contributes 0 — it is gathered, not crafted.
Counting one craft per produced node is a sound LOWER bound on craft actions
irrespective of per-action craft batching. Mirrors min_gathers' fuel-bounded
greedy-consume so it extracts to Lean cleanly."""

from collections.abc import Mapping


def min_crafts(item: str, qty: int, recipes: Mapping[str, dict[str, int]],
               owned: dict[str, int]) -> int:
    state = _min_crafts(len(recipes) + 1, item, qty, recipes, (0, dict(owned)))
    return state[0]


def _min_crafts(fuel: int, item: str, qty: int,
                recipes: Mapping[str, dict[str, int]],
                state: tuple[int, dict[str, int]]) -> tuple[int, dict[str, int]]:
    if fuel <= 0:
        return state
    total = state[0]
    owned = state[1]
    held = owned.get(item, 0)
    used = min(held, qty)
    owned[item] = held - used
    remaining = qty - used
    if remaining <= 0:
        return (total, owned)
    recipe = recipes.get(item, {})
    if len(recipe) == 0:
        return (total, owned)  # raw leaf: gathered, not crafted
    # This craftable node must be produced: +1 craft, then recurse into inputs.
    state = (total + 1, owned)
    for material, per_unit in recipe.items():
        state = _min_crafts(fuel - 1, material, per_unit * remaining, recipes, state)
    return state
