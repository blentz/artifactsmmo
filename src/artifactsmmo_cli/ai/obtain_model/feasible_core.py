"""The pure feasibility fixpoint behind `ObtainModel.feasible`, mirrored by
`formal/Formal/ObtainModelFeasible.lean::feasible`.

"Can I get at least one unit of X from here?" An item is feasible if it is
held, or if some READY route to it has every input feasible. Cycles are
resolved as infeasible (least fixpoint): an item cannot be the reason it
is obtainable.

Kernel-checked properties of the Lean mirror:
- soundness: every feasible item has a finite derivation from holdings through
  ready routes;
- completeness: every such derivable item in the closure is found;
- monotonicity: holding more never makes an item infeasible.

Existence only: quantities (how many units, how much gold) are not modelled
here, the same question the models this replaces asked.
"""

from collections.abc import Collection, Mapping, Sequence


def feasible_items(closure: Sequence[str], held: Collection[str],
                   ready_inputs: Mapping[str, Sequence[Sequence[str]]]) -> frozenset[str]:
    """The least set containing every held item of `closure` and every item
    with a ready route whose inputs are all in the set.

    `closure` must contain every input of every route listed in
    `ready_inputs` for its items (the caller builds it that way).
    `ready_inputs[item]` is one input list per ready route to `item`; a route
    with no inputs (a withdraw, a gather, a drop) makes the item feasible on
    its own."""
    feasible = {item for item in closure if item in held}
    changed = True
    while changed:
        changed = False
        for item in closure:
            if item in feasible:
                continue
            if any(all(x in feasible for x in inputs) for inputs in ready_inputs.get(item, ())):
                feasible.add(item)
                changed = True
    return frozenset(feasible)
