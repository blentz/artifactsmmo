"""Pure core of GatherMaterials' currency-affordability fast-fail.

Extracted for the differential test (`formal/diff/test_currency_afford_diff.py`)
against the kernel-proved `Formal.CurrencyAffordFastFail.isPlannable`, whose
`fastfail_sound` theorem proves: when this returns False, NO plan in the goal's
action set raises the leaf's owned count to `needed` — because the only
acquisition is an NpcBuy that is inapplicable while unaffordable, and the goal's
actions cannot earn the currency (no task-completion in GatherMaterials'
relevant_actions). So pruning discards no satisfiable plan and the GOAP search is
spared the budget-exhausting node burn.
"""


def currency_afford_plannable_pure(target_in_closure: bool, affordable: bool,
                                   owned: int, needed: int) -> bool:
    """True ⇒ worth planning; False ⇒ fast-fail. Mirrors
    `Formal.CurrencyAffordFastFail.isPlannable`:
    `!targetInClosure || affordable || needed ≤ owned`."""
    return (not target_in_closure) or affordable or owned >= needed
