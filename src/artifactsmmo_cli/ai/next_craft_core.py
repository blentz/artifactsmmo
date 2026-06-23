"""Deterministic next-craft-action generator.

Computes the single next action (gather or craft) needed to make progress toward
`qty` of a target item, walking the recipe DAG without running a full GOAP search.

The bot executes only plan[0] each cycle; this pure function replaces an expensive
52K-node A* re-run by reading directly from the recipe DAG and current inventory.
"""

from collections.abc import Mapping
from typing import Literal, NamedTuple


class NextAction(NamedTuple):
    """The next single action needed to progress toward the target item.

    Attributes:
        item: The item to produce or gather.
        kind: ``"gather"`` for raw resources (no recipe), ``"craft"`` for craftable items.
        qty:  How many of ``item`` are still needed (the current deficit).
    """

    item: str
    kind: Literal["gather", "craft"]
    qty: int


def next_craft_target_pure(
    recipes: Mapping[str, dict[str, int]],
    owned: Mapping[str, int],
    target: str,
    qty: int,
) -> NextAction | None:
    """Return the next action needed to produce ``qty`` of ``target``, or ``None``.

    Returns ``None`` when already satisfied (``owned[target] >= qty``).

    Walks the recipe DAG depth-first: finds the deepest still-short item that is
    actionable right now — either a raw resource (no recipe) to ``"gather"``, or a
    craftable item whose inputs are all already on hand to ``"craft"``.

    Args:
        recipes: Maps each craftable item code to its per-craft input quantities,
                 e.g. ``{"copper_bar": {"copper_ore": 10}}``.  An item absent from
                 this mapping is treated as a raw resource.
        owned:   Current inventory counts (item code → quantity held).
        target:  The item code to work toward.
        qty:     How many of ``target`` are needed.

    Returns:
        A :class:`NextAction` describing the immediate next step, or ``None`` if
        the target quantity is already satisfied.
    """
    if owned.get(target, 0) >= qty:
        return None
    return _next(recipes, owned, target, qty, len(recipes) + 1)


def _next(
    recipes: Mapping[str, dict[str, int]],
    owned: Mapping[str, int],
    item: str,
    need: int,
    fuel: int,
) -> NextAction:
    """Recurse into the recipe DAG to find the deepest actionable step.

    Args:
        recipes: Same as :func:`next_craft_target_pure`.
        owned:   Same as :func:`next_craft_target_pure`.
        item:    Current item being evaluated.
        need:    Total quantity of ``item`` required.
        fuel:    Recursion budget; equal to ``len(recipes) + 1`` at the top level.
                 Acyclic recipe data guarantees this is never exhausted; the guard
                 exists only to keep the function total.

    Returns:
        The next :class:`NextAction` toward satisfying ``need`` of ``item``.
    """
    deficit = need - owned.get(item, 0)
    recipe = recipes.get(item)
    if recipe is None:
        return NextAction(item, "gather", deficit)  # raw resource → gather the shortfall
    if fuel <= 0:
        # Acyclic recipe data guarantees this branch is unreachable; total-function guard.
        return NextAction(item, "gather", deficit)
    # To craft `deficit` more of `item`, each input is needed `per * deficit`.
    for inp, per in recipe.items():
        required = per * deficit
        if owned.get(inp, 0) < required:
            return _next(recipes, owned, inp, required, fuel - 1)  # make input first
    return NextAction(item, "craft", deficit)  # all inputs on hand → craft
