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
execute it against the Lean oracle.
"""


def min_gathers(
    item: str,
    qty: int,
    recipes: dict[str, dict[str, int]],
    owned: dict[str, int],
) -> int:
    """Lower bound on gather actions to obtain `qty` of `item` given `owned`
    holdings. `recipes[code]` maps a craftable item to its `{material: per_unit}`
    recipe; an item absent from `recipes` (or with an empty recipe) is raw and
    must be gathered. `owned` is consumed greedily on a private copy — the
    caller's dict is never mutated."""
    return _min_gathers(item, qty, recipes, dict(owned))


def _min_gathers(
    item: str,
    qty: int,
    recipes: dict[str, dict[str, int]],
    owned: dict[str, int],
) -> int:
    # Consume held copies of this exact item first.
    have = owned.get(item, 0)
    used = min(have, qty)
    owned[item] = have - used
    remaining = qty - used
    if remaining <= 0:
        return 0
    recipe = recipes.get(item) or {}
    if not recipe:
        # Raw material: each remaining unit is one gather.
        return remaining
    # Craftable: recurse into each material at the per-unit quantity * remaining.
    total = 0
    for material, per_unit in recipe.items():
        total += _min_gathers(material, per_unit * remaining, recipes, owned)
    return total
