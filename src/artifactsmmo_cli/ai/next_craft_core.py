"""Deterministic next-craft-action generator.

Computes the single next action needed to make progress toward `qty` of a
target item, walking THE ONE OBTAIN MODEL (`ai/obtain_sources.Source`) instead
of hard-coding "no recipe -> gather" as the only non-craft route.

The bot executes only plan[0] each cycle; this pure function replaces an
expensive 52K-node A* re-run by reading directly from the recipe DAG (for
CRAFT descent) and the priority-ordered source map (for everything else) plus
current inventory.

`sources` is OPTIONAL and defaults to empty: with no sources supplied for any
item, the descent degrades EXACTLY to the original recipe-tree-only walk
(gather a recipe-less leaf, withdraw a banked short input, else craft) --
this is what keeps every pre-existing caller and test byte-identical. When a
priority-ordered `Source` list is supplied for an item, the FIRST applicable
source wins: WITHDRAW and RECYCLE (both "consume stock already owned") preempt
even a craft; CRAFT itself defers to the recipe-descent below (which may
still choose to withdraw/descend a short input); GATHER/BUY/DROP are taken
immediately since nothing above them in priority applied.

`NextAction.kind` stays a plain string (not the `SourceKind` enum) on
purpose: `SourceKind` is a bare `Enum`, not `str`-mixed, so
`SourceKind.GATHER == "gather"` is False -- storing the enum member itself
would silently break every pre-existing equality-based test. `code` carries
the source's own item/resource/npc/monster code (RECYCLE's destroyed item,
BUY's npc, DROP's monster); it is "" whenever the source's own code is
`item` itself (CRAFT, WITHDRAW, plain GATHER), matching the pre-existing
3-field NextAction constructions used throughout the test suite.
"""

from collections.abc import Mapping
from typing import Literal, NamedTuple

from artifactsmmo_cli.ai.obtain_sources import Source, SourceKind


class NextAction(NamedTuple):
    """The next single action needed to progress toward the target item.

    Attributes:
        item: The item to produce or gather.
        kind: ``"gather"``/``"craft"``/``"withdraw"`` (the original three) or
              ``"recycle"``/``"buy"``/``"drop"`` (from a widened `sources` map).
        qty:  How many of ``item`` are still needed (the current deficit).
        code: The source's own code (RECYCLE's destroyed item, BUY's npc,
              DROP's monster). "" when the source's own code is `item` itself.
    """

    item: str
    kind: Literal["gather", "craft", "withdraw", "recycle", "buy", "drop"]
    qty: int
    code: str = ""


def next_craft_target_pure(
    recipes: Mapping[str, dict[str, int]],
    owned: Mapping[str, int],
    bank: Mapping[str, int],
    target: str,
    qty: int,
    sources: Mapping[str, list[Source]] | None = None,
) -> NextAction | None:
    """Return the next action needed to produce ``qty`` of ``target``, or ``None``.

    Returns ``None`` when already satisfied (``owned[target] >= qty``).

    Walks the recipe DAG depth-first: at each item, the priority-ordered
    ``sources`` entry (if any) is consulted first; a CRAFT entry there defers
    to the same recipe-descent the pure recipe-tree walk always used, so a
    craftable item with all inputs on hand still crafts and a short input
    still recurses or withdraws exactly as before.

    Args:
        recipes: Maps each craftable item code to its per-craft input quantities,
                 e.g. ``{"copper_bar": {"copper_ore": 10}}``.  An item absent from
                 this mapping is treated as a raw resource.
        owned:   Current inventory counts (item code → quantity held).
        bank:    Current bank counts (item code -> quantity held).
        target:  The item code to work toward.
        qty:     How many of ``target`` are needed.
        sources: THE obtain model (`ai/obtain_sources.obtain_source_map`), a
                 priority-ordered list of `Source` per item. Defaults to
                 empty, which reduces this function to the original
                 recipe-tree-only walk.

    Returns:
        A :class:`NextAction` describing the immediate next step, or ``None`` if
        the target quantity is already satisfied.
    """
    if owned.get(target, 0) >= qty:
        return None
    return _next(recipes, sources or {}, owned, bank, target, qty, len(recipes) + 1)


def _next(
    recipes: Mapping[str, dict[str, int]],
    sources: Mapping[str, list[Source]],
    owned: Mapping[str, int],
    bank: Mapping[str, int],
    item: str,
    need: int,
    fuel: int,
) -> NextAction:
    """Recurse into the obtain model / recipe DAG to find the deepest actionable step.

    Args:
        recipes: Same as :func:`next_craft_target_pure`.
        sources: Same as :func:`next_craft_target_pure` (already defaulted to {}).
        owned:   Same as :func:`next_craft_target_pure`.
        bank:    Same as :func:`next_craft_target_pure`.
        item:    Current item being evaluated.
        need:    Total quantity of ``item`` required.
        fuel:    Recursion budget; equal to ``len(recipes) + 1`` at the top level.
                 Acyclic recipe data guarantees this is never exhausted; the guard
                 exists only to keep the function total.

    Returns:
        The next :class:`NextAction` toward satisfying ``need`` of ``item``.
    """
    deficit = need - owned.get(item, 0)
    # THE obtain model, priority order (WITHDRAW, RECYCLE, CRAFT, GATHER, BUY,
    # DROP): take the FIRST applicable source. WITHDRAW/RECYCLE both consume
    # stock already owned, so they preempt even a craft. CRAFT breaks out to
    # the recipe descent below (never falling through to the lower-priority
    # GATHER/BUY/DROP entries that may follow it in the list) because the
    # descent itself decides craft-now vs. descend-into-short-input, which is
    # exactly the pre-existing behaviour this widened walk must reproduce.
    for src in sources.get(item, ()):
        if src.kind is SourceKind.CRAFT:
            break
        return _step_for(src, item, deficit, bank)
    recipe = recipes.get(item)
    if recipe is None:
        return NextAction(item, "gather", deficit)  # raw resource → gather the shortfall
    if fuel <= 0:  # pragma: no cover
        # Acyclic recipe data guarantees this branch is unreachable via the public
        # next_craft_target_pure API: fuel is seeded at len(recipes)+1 and each
        # recursive call marks a DISTINCT item (the DFS can visit at most
        # len(recipes) items before hitting a raw leaf with no recipe).  The guard
        # exists only to keep the function total for hypothetically cyclic inputs.
        return NextAction(item, "gather", deficit)
    # To craft `deficit` more of `item`, each input is needed `per * deficit`.
    for inp, per in recipe.items():
        required = per * deficit
        if owned.get(inp, 0) < required:
            # First short input. If it is in the bank, withdraw what's there
            # (capped at the shortfall) rather than re-gathering/re-crafting it;
            # otherwise descend to make it. Mirrors Lean `nextHelper` withdraw arm.
            if bank.get(inp, 0) == 0:
                return _next(recipes, sources, owned, bank, inp, required, fuel - 1)
            return NextAction(inp, "withdraw", min(bank.get(inp, 0), required - owned.get(inp, 0)))
    return NextAction(item, "craft", deficit)  # all inputs on hand → craft


def _step_for(src: Source, item: str, deficit: int, bank: Mapping[str, int]) -> NextAction:
    """Translate a non-CRAFT `Source` into the immediate next step for `item`.

    WITHDRAW is capped at the bank's shortfall, mirroring the pre-existing
    bank-withdraw branch exactly. RECYCLE/GATHER/BUY/DROP each ask for the
    full deficit in one step; RECYCLE's source-item consumption is applied
    later by `craft_plan_driver_core._apply_state` (it needs `yield_per`,
    which a `NextAction` does not carry). `code` names the source's own
    item/resource/npc/monster code, left "" when identical to `item`
    (WITHDRAW's own bank item, or a plain 1:1 GATHER of the item itself).
    """
    code = "" if src.code == item else src.code
    if src.kind is SourceKind.WITHDRAW:
        return NextAction(item, "withdraw", min(bank.get(src.code, 0), deficit), code)
    return NextAction(item, src.kind.value, deficit, code)
