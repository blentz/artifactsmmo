"""Pure lower bound on the GatherActions a plan needs to obtain an item.

A gather mints exactly +1 of its drop (see
`actions.gather_apply_core.gather_apply_pure`), and a raw material can only be
obtained by gathering (or by withdrawing a held copy, accounted for via
`owned`). So crafting `qty` of `item` from scratch requires at least
`min_gathers` gather steps. Since the planner's returned plan length never
exceeds `max_depth` (proved in `formal/Formal/PlannerDepthBound.lean`), a target
whose `min_gathers` exceeds the goal's `max_depth` is provably unreachable — the
sound condition the UpgradeEquipment skip gate uses.

Kept pure (plain dicts, no GameData/WorldState) so the differential harness can
execute it against the Lean oracle. The recursion is FUEL-BOUNDED
(mechanical-extraction P3d): `_min_gathers` threads an explicit `fuel` that
`min_gathers` seeds with `len(recipes) + 1`, which an acyclic recipe graph can
never exhaust (every recursing frame expands a distinct craftable along its
path), so the bound is unreachable on real data — it exists so the extracted
Lean model (`formal/Formal/Extracted/MinGathers.lean`) recurses structurally on
a `Nat` fuel, exactly like the hand model `Formal.StepDispatch.minGathers`. A
cyclic recipe (uncraftable) now terminates with the whole remaining need
accounted as raw — conservatively LARGE, so the unreachability gate
(`min_gathers > max_depth` ⇒ skip) stays sound — instead of a RecursionError.
"""

from collections.abc import Mapping


def min_gathers(
    item: str,
    qty: int,
    recipes: Mapping[str, dict[str, int]],
    owned: dict[str, int],
) -> int:
    """Lower bound on gather actions to obtain `qty` of `item` given `owned`
    holdings. `recipes[code]` maps a craftable item to its `{material: per_unit}`
    recipe; an item absent from `recipes` (or with an empty recipe) is raw and
    must be gathered. `owned` is consumed greedily on a private copy — the
    caller's dict is never mutated."""
    state = _min_gathers(len(recipes) + 1, item, qty, recipes, (0, dict(owned)))
    return state[0]


def _min_gathers(
    fuel: int,
    item: str,
    qty: int,
    recipes: Mapping[str, dict[str, int]],
    state: tuple[int, dict[str, int]],
) -> tuple[int, dict[str, int]]:
    """Add the gathers for one `(item, qty)` node to the threaded
    `(total, owned)` state, crediting (and CONSUMING) held copies first — a
    unit credited under one parent is not available to a sibling branch.

    `fuel` bounds the recursion structurally (the Lean model's `Nat` fuel):
    unreachable on acyclic recipes given the `len(recipes) + 1` seed; a cyclic
    recipe terminates with the node's quantity accounted as raw work.
    """
    if fuel <= 0:
        return (state[0] + qty, state[1])
    total = state[0]
    owned = state[1]
    # Consume held copies of this exact item first.
    held = owned.get(item, 0)
    used = min(held, qty)
    owned[item] = held - used
    remaining = qty - used
    if remaining <= 0:
        return (total, owned)
    recipe = recipes.get(item, {})
    if len(recipe) == 0:
        # Raw material: each remaining unit is one gather.
        return (total + remaining, owned)
    # Craftable: recurse into each material at the per-unit quantity * remaining.
    state = (total, owned)
    for material, per_unit in recipe.items():
        state = _min_gathers(fuel - 1, material, per_unit * remaining, recipes, state)
    return state
