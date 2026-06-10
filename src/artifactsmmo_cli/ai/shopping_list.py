# shopping_list

"""Bank-aware recipe shopping list: the true remaining acquisition work.

Recurses an item's crafting recipe to base materials, compiling the NET quantity
of every item (target + intermediates + base materials) that must still be
acquired AFTER crediting what the character already holds (inventory + bank,
passed as `owned`). Holdings are credited at EVERY recipe level, and stock at any
level SHORT-CIRCUITS the subtree below it: a banked intermediate (e.g. a
`copper_bar`) is withdrawn rather than re-crafted from `copper_ore`, so the ore
subtree is never expanded.

The net list is the lever the planner uses to PRUNE its action space (see
`UpgradeEquipmentGoal`/`GatherMaterialsGoal.relevant_actions`): a chain material
whose net is 0 is fully bank-covered, so only its `WithdrawItemAction` is offered
to the planner — never the `GatherAction`/deep sub-craft that would explode the
GOAP search. A material with a positive net keeps its gather/craft action for the
deficit only. Because the net never drops a REACHABLE material to 0 unless the
bank+inventory genuinely cover it, the pruning preserves planner admissibility
(it removes only redundant gather paths, never the sole path to a needed item).

Generalizes the `_BANKED_REGATHER_PENALTY` cost heuristic
(gathering.py) into a principled, proof-friendly pure core — the dominance and
reconstruction properties are mirrored in
`formal/Formal/ShoppingList.lean`.

Kept pure (plain dicts, no GameData/WorldState) so the differential harness can
execute it against the Lean oracle, exactly like `min_gathers`. The recursion is
FUEL-BOUNDED (mechanical-extraction P2): `_expand` threads an explicit `fuel`
that `shopping_list` seeds with `len(recipes) + 1`, which an acyclic recipe
graph can never exhaust (every expansion path visits distinct craftables), so
the bound is unreachable on real data — it exists so the extracted Lean model
(`formal/Formal/Extracted/ShoppingList.lean`) recurses structurally on a `Nat`
fuel, exactly like the hand model `Formal.ShoppingList.rawReq`.
"""

from collections.abc import Mapping


def shopping_list(
    item: str,
    qty: int,
    recipes: Mapping[str, dict[str, int]],
    owned: dict[str, int],
) -> dict[str, int]:
    """Net acquisition quantity per item code to obtain `qty` of `item`, crediting
    `owned` (inventory + bank) at every recipe level.

    `recipes[code]` maps a craftable item to its `{material: per_unit}` recipe; an
    item absent from `recipes` (or with an empty recipe) is raw. `owned` is
    consumed greedily on a private copy — the caller's dict is never mutated.

    Returns a dict mapping EVERY item visited in the closure to its net deficit
    (0 when fully covered by holdings). A net of 0 means "withdraw, don't acquire";
    a positive net is the remaining gather/craft work for that item.
    """
    net: dict[str, int] = {}
    state = _expand(len(recipes) + 1, item, qty, recipes, (dict(owned), net))
    return state[1]


def _expand(
    fuel: int,
    item: str,
    qty: int,
    recipes: Mapping[str, dict[str, int]],
    state: tuple[dict[str, int], dict[str, int]],
) -> tuple[dict[str, int], dict[str, int]]:
    """Expand one node of the recipe tree over the `(owned, net)` state pair.

    `fuel` bounds the recursion structurally (the Lean model's `Nat` fuel):
    unreachable on acyclic recipes given the `len(recipes) + 1` seed, and a
    cyclic recipe terminates with a truncated net instead of overflowing the
    stack.
    """
    if fuel <= 0:
        return state
    owned = state[0]
    net = state[1]
    # Credit held copies of this exact item first (inventory + bank).
    held = owned.get(item, 0)
    used = min(held, qty)
    owned[item] = held - used
    deficit = qty - used
    # Record the net for this item (0 when fully covered). Record even a 0 so the
    # caller sees the full closure and can offer the withdraw for covered items.
    net[item] = net.get(item, 0) + deficit
    if deficit <= 0:
        # Fully covered by holdings: SHORT-CIRCUIT — do not expand the subtree.
        # The banked copies are withdrawn, so no sub-material work is needed.
        return (owned, net)
    recipe = recipes.get(item, {})
    if len(recipe) == 0:
        # Raw material: the deficit is gathered directly, nothing below.
        return (owned, net)
    # Craftable with a deficit: recurse into each material for the deficit only.
    state = (owned, net)
    for material, per_unit in recipe.items():
        state = _expand(fuel - 1, material, per_unit * deficit, recipes, state)
    return state


def fully_covered_materials(
    item: str,
    qty: int,
    recipes: Mapping[str, dict[str, int]],
    owned: dict[str, int],
) -> set[str]:
    """Item codes in the recipe closure of `qty`×`item` whose NET deficit is 0 —
    i.e. fully covered by `owned` (inventory + bank). These are the materials the
    planner may WITHDRAW instead of gather/craft; the planner prunes the gather
    (and deep sub-craft) for each so the GOAP search can't explode into the
    bank-covered subtree. A material with ANY positive net is NOT returned (its
    gather/craft stays — never prune the only path to a real deficit), preserving
    planner admissibility."""
    net = shopping_list(item, qty, recipes, owned)
    return {code for code, deficit in net.items() if deficit <= 0}
