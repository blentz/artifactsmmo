"""Pure core: how many accept→complete task cycles fund a currency target.

Extracted so the formal differential test (`formal/diff/test_currency_funding_diff.py`)
can exercise it against the kernel-proved Lean
`Formal.Liveness.CurrencyFunding.fundingCycles`, whose `fundingCycles_sufficient`
theorem proves these many cycles (each adding ≥ the floor ≥ 1 coin) REACH the
target — so `ReachCurrencyGoal.max_depth` (∝ this count) admits a complete plan and
the GOAP search does not time out. `funding_remaining_descends` proves termination
(the remaining-coins measure strictly drops each cycle).
"""


def funding_cycles_pure(on_hand: int, target: int, per_task_floor: int) -> int:
    """Cycles to raise `on_hand` to `target`, each cycle yielding at least
    `per_task_floor` (≥1) coins: 0 if already funded, else ceil((target-on_hand)/floor).
    Caller guarantees `per_task_floor >= 1` (it is `min_task_coin_reward()`)."""
    if on_hand >= target:
        return 0
    deficit = target - on_hand
    return (deficit + per_task_floor - 1) // per_task_floor
