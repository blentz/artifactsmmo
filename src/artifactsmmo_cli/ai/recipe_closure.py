"""Recipe-closure helper: the gather/craft action scope for producing items.

Walks an item's crafting recipe down to its gathered resources, returning the
set of resource codes to gather and the set of intermediate item codes to
craft. Goals use this to restrict the planner's branching factor to the actions
that can actually contribute to producing a target item, instead of every
gather/craft in the game.
"""

from collections.abc import Iterable

from artifactsmmo_cli.ai.game_data import GameData


def recipe_closure(game_data: GameData, roots: Iterable[str]) -> tuple[set[str], set[str]]:
    """Return (needed_resources, craftable_mats) for producing every item in roots.

    needed_resources: resource codes whose drop is some material in the closure.
    craftable_mats:    item codes in the closure that have a crafting recipe.
    """
    needed_resources: set[str] = set()
    craftable_mats: set[str] = set()
    visited: set[str] = set()

    def collect(material: str) -> None:
        if material in visited:
            return
        visited.add(material)
        for resource_code, drop_item in game_data.resource_drops.items():
            if drop_item == material:
                needed_resources.add(resource_code)
        recipe = game_data.crafting_recipe(material) or {}
        if recipe:
            craftable_mats.add(material)
            for sub_mat in recipe:
                collect(sub_mat)

    for root in roots:
        collect(root)
    return needed_resources, craftable_mats


def raw_material_units(game_data: GameData, item: str, visited: frozenset[str] | None = None) -> int:
    """Total raw-resource quantity gathered to craft one `item`, multiplying
    ingredient quantities down the recipe tree. A raw (gathered) or unknown item
    costs 1. Cyclic recipes terminate via the visited guard (revisit -> 1)."""
    visited = visited or frozenset()
    if item in visited:
        return 1
    recipe = game_data.crafting_recipe(item)
    if not recipe:
        return 1
    deeper = visited | {item}
    return sum(qty * raw_material_units(game_data, sub, deeper) for sub, qty in recipe.items())
