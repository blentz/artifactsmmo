"""Pure core of the acquisition-leaf attainability decision.

Extracted so the formal differential test (`formal/diff/test_leaf_attainable_diff.py`)
can exercise the exact decision against the kernel-proved Lean model
`Formal.LeafAttainable.leafAttainable` (`formal/Formal/LeafAttainable.lean`).

A recipe-closure LEAF (an item with no recipe of its own, bottoming out the
craft walk) is attainable iff at least one acquisition source applies. The
`task_earnable` disjunct is the C1 addition: an item awarded by completing tasks
(e.g. `tasks_coin`) is obtainable via the always-available task loop, which in
turn funds task-currency purchases (jasper_crystal @ tasks_trader -> satchel).
"""


def leaf_attainable_pure(gatherable: bool, known_spawn_drop: bool,
                         task_earnable: bool,
                         buyable_with_attainable_currency: bool) -> bool:
    """True ⇒ the leaf can be acquired by some known means; False ⇒ dead leaf.

    Mirrors `Formal.LeafAttainable.leafAttainable`:
    `gatherable || knownSpawnDrop || taskEarnable || buyableWithAttainableCurrency`.
    """
    return (gatherable or known_spawn_drop or task_earnable
            or buyable_with_attainable_currency)
