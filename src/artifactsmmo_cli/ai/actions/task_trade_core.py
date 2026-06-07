"""Pure core for `TaskTradeAction.is_applicable` / `.apply` held↔progress bookkeeping.

This module isolates the minimal inventory-coupled transition that
`TaskTradeAction` performs at the taskmaster: the API `taskTrade` action
submits `quantity` held copies of the task item and advances `task_progress`
by `quantity`, consuming exactly those `quantity` held copies.

The Lean module `formal/Formal/Liveness/ItemsTaskRun.lean` proves the
inventory-COUPLED termination model where the per-unit `trade` REQUIRES a held
item and CONSUMES exactly one to advance progress by one
(`held -= 1 ∧ progress += 1`, only while `0 < held ∧ progress < total`). The
faithful correspondence to the live multi-unit action is:

  the live `apply` over the REACHABLE trading domain — the states where the
  planner actually fires TaskTrade: `held >= quantity` (the action guard) AND
  `progress < total` (the `PursueTaskGoal.is_satisfied` stop guard) — equals
  `quantity`-fold application of the proven per-unit `ItemsTaskRun.trade`.

`task_trade_step(held, progress, total, quantity)` is the real production
transition on the (held, progress) projection: it returns
`(held - quantity, progress + quantity)`. The `total` parameter is part of the
reachable-domain contract (`progress < total`) but does NOT itself gate the
live transition — the live action advances unconditionally once fired; the
goal's `progress >= total` stop is what halts trading. Modeling BOTH guards in
`task_trade_applicable` makes the reachable domain explicit and honest.

`TaskTradeAction.is_applicable` / `.apply` delegate to these cores; behavior is
identical (the slot-pop bookkeeping for the dict representation lives in
`apply`, which calls `task_trade_step` for the held/progress numbers).
"""


def task_trade_applicable(held: int, quantity: int, progress: int, total: int) -> bool:
    """True iff a TaskTrade of `quantity` is in the reachable trading domain.

    Combines the live action guard (`held >= quantity`, with `quantity >= 1`)
    and the goal stop guard (`progress < total`). This is the genuinely
    reachable precondition under which the live planner ever fires TaskTrade:
    `is_applicable` enforces `held >= quantity`, and `PursueTaskGoal` only keeps
    pursuing while `progress < total`. Mirrors `quantity`-fold fireability of
    the proven per-unit `ItemsTaskRun.trade`.
    """
    if quantity < 1:
        return False
    if held < quantity:
        return False
    return progress < total


def task_trade_step(held: int, progress: int, quantity: int) -> tuple[int, int]:
    """The real production transition on the (held, progress) projection.

    Returns `(held - quantity, progress + quantity)` — consume `quantity` held
    task items, advance progress by `quantity`. This is exactly the held/
    progress arithmetic `TaskTradeAction.apply` performs (the dict slot-pop in
    `apply` is the same `held - quantity` count, popped to absent when it
    reaches zero). Over the reachable trading domain it equals `quantity`-fold
    `ItemsTaskRun.trade`.
    """
    return (held - quantity, progress + quantity)
