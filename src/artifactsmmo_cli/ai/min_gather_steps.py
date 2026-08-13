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
    initial_state: tuple[list[str], dict[str, int]] = ([], dict(owned))
    state = _min_gather_steps(len(recipes) + 1, item, qty, recipes, initial_state)
    return len(state[0])


def _min_gather_steps(fuel: int, item: str, qty: int,
                      recipes: Mapping[str, dict[str, int]],
                      state: tuple[list[str], dict[str, int]]) -> tuple[list[str], dict[str, int]]:
    if fuel <= 0:
        return (state[0] if item in state[0] else [*state[0], item], state[1])
    leaves = state[0]
    owned = state[1]
    held = owned.get(item, 0)
    used = min(held, qty)
    owned[item] = held - used
    remaining = qty - used
    if remaining <= 0:
        return (leaves, owned)
    recipe = recipes.get(item, {})
    if len(recipe) == 0:
        return (leaves if item in leaves else [*leaves, item], owned)
    state = (leaves, owned)
    for material, per_unit in recipe.items():
        state = _min_gather_steps(fuel - 1, material, per_unit * remaining,
                                  recipes, state)
    return state
