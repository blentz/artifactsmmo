"""Pure lower bound on the GATHER ACTIONS a plan needs to obtain an item.

The twin of `min_crafts`, and the batch-aware replacement for
`ceil_gathers(min_gathers(...))` inside `min_plan_length`.

`min_gathers` counts raw UNITS, which was a sound lower bound on ACTIONS only
while one gather minted exactly one unit. `GatherAction` now carries a
`quantity`, so a single action mints the whole deficit of one material and a
real plan can be SHORTER than the unit count — at which point the unit count is
no longer a lower bound at all, and `is_plannable` (which consumes
`min_plan_length`) starts rejecting reachable goals.

One batched gather serves one raw material's entire demand, so the sound bound
is the number of DISTINCT raw leaves that must be gathered — exactly mirroring
`min_crafts`, which counts one craft per produced node irrespective of craft
batching.

`min_gathers` is deliberately left alone: `craft_vs_buy` and `gather_step_target`
consume it as a count of real API actions (units), which batching does not
change.

Kept pure (plain dicts, no GameData/WorldState) so the differential harness can
execute it against the Lean oracle. The recursion is FUEL-BOUNDED exactly as
`min_gathers`/`min_crafts` are: a cyclic recipe terminates instead of raising
RecursionError.
"""

from collections.abc import Mapping


def min_gather_steps(item: str, qty: int, recipes: Mapping[str, dict[str, int]],
                     owned: dict[str, int]) -> int:
    """Lower bound on batched gather ACTIONS to obtain `qty` of `item`.

    `recipes[code]` maps a craftable to its `{material: per_unit}` recipe; an
    item absent from `recipes` (or with an empty recipe) is raw. `owned` is
    consumed greedily on a private copy — the caller's dict is never mutated.
    """
    state = _min_gather_steps(len(recipes) + 1, item, qty, recipes,
                              ([], dict(owned)))
    return len(state[0])


def _min_gather_steps(fuel: int, item: str, qty: int,
                      recipes: Mapping[str, dict[str, int]],
                      state: tuple[list[str], dict[str, int]]) -> tuple[list[str], dict[str, int]]:
    """Collect the raw leaves whose demand is not covered by `owned`.

    A leaf reached from two branches is recorded once: one batched action
    covers the summed demand, so it is one step.
    """
    if fuel <= 0:
        leaves, owned = state
        if item not in leaves:
            leaves = [*leaves, item]
        return (leaves, owned)
    leaves, owned = state
    held = owned.get(item, 0)
    used = min(held, qty)
    owned[item] = held - used
    remaining = qty - used
    if remaining <= 0:
        return (leaves, owned)
    recipe = recipes.get(item, {})
    if len(recipe) == 0:
        if item not in leaves:
            leaves = [*leaves, item]
        return (leaves, owned)
    state = (leaves, owned)
    for material, per_unit in recipe.items():
        state = _min_gather_steps(fuel - 1, material, per_unit * remaining,
                                  recipes, state)
    return state
