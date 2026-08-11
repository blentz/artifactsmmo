# GE cancel race + request-budget pricing

Two defects found in the 2026-08-10 five-character trace review
(`play-trace-{C3P0,HAL,Lor,R2D2,Robby}-20260810-08*.jsonl`, 2609 cycles over
10.6 hours) and fixed together, because both are consequences of the same fact:
**the binding constraint on a `play --all` fleet is the per-IP request budget,
not the action cooldown.**

## What the traces measured

Cycles per hour, per character, per hour-since-start:

| character | per-hour cycles | wall clock blocked |
|---|---|---|
| C3P0 | 52, 50, 54, 51, 53, 52, 51, 55, 48, 54 | 32% |
| HAL | 50, 51, 53, 50, 54, 50, 49, 47, 53, 52 | 49% |
| Lor | 52, 51, 54, 51, 52, 53, 49, 48, 51, 55 | 32% |
| R2D2 | 40, 38, 38, 50, 51, 49, 54, 51, 51, 55 | 29% |
| Robby | 43, 41, 43, 43, 42, 44, 43, 43, 30, 43 | 0% |

The ceiling is flat and hard: every character sits at its share of the hourly
action bucket. Mean wall-clock per action was ~69s for all five, against a mean
cooldown of 11.5s (HAL) to 65.2s (Robby). Robby — the only character whose
cooldowns are near the budget pace — never blocked at all; the four that spend
cheap actions burned their hour's allowance in 25-35 minutes and then idled.

Because the burn is a burst, `RateGovernor`'s sliding window releases in a
burst exactly 3600s later, so every stall ends at the same wall-clock minute
(:24:30, one hour after process start). That looks like a fixed window and is
not one.

## Defect 1 — the GE cancel race

Grand Exchange orders are ACCOUNT-scoped: `/my/grandexchange/orders` returns the
same list to every child, so all five age the same order past
`ge_order_config.TTL_CYCLES` and all five plan the same cancel. One wins; the
rest get `HTTP 404: Order not found`.

Measured: 6 of 20 distinct order ids were attacked by two or more characters,
costing 8 wasted requests. One id was attacked by three:

```
6a79f5c481a11b38d8228e9c  HAL 404 | R2D2 ok | Robby 404
```

Eight requests is small in absolute terms and large against a budget that pays
out ~52 per character per hour.

### Fix

A new coordination row, `GeOrderClaim`, in the shape `BankStockClaim` already
established for the account-shared bank:

* `CoordinationStore.claim_ge_order(order_id, now)` — written immediately
  BEFORE the cancel request, so a sibling deriving its own targets in the
  meantime sees it. Accumulates per order id rather than replacing wholesale,
  because `cancel_targets` can report several ids at once and they are worked
  one per cycle.
* `CoordinationStore.sibling_order_claims(now)` — the fourth deliberately
  unfiltered cross-character read; returns a `frozenset` because the only
  question asked is membership.
* `CoordinationStore.release_ge_orders()` — called when the cancel provably did
  not happen, so a claim never hides an order that is still open.
* `cancel_selection.cancel_targets(..., sibling_claims)` skips claimed ids
  BEFORE evaluating any trigger, so a claimed BUY is not credited against the
  gold shortfall either — the sibling is freeing that escrow, not us.

`GE_ORDER_CLAIM_TTL_SECONDS = 60`, shared with `BANK_CLAIM_TTL_SECONDS` and
sized against the same settlement window (one cycle at the observed 15-25s
cadence, covered twice over).

NOT a lock. Nothing blocks on it and the HTTP 404 backstop is unchanged, so a
missed claim simply reproduces today's behaviour.

### Liveness

`CancelOrdersGoal` underwrites the guarantee that no posted order's capital is
locked forever, paired in Lean with `EscrowConservation.sell_escrow_freed`
(which proves only that an escape EXISTS; that it is TAKEN is discharged in
Python by the TTL trigger). Hiding an order weakens that half, so the claim is
TTL-bounded: the guarantee moves from "a stale order is cancelled on the next
cycle" to "within one claim TTL of it", never to "never". The cancel-target set
still provably shrinks toward empty.

## Defect 2 — actions priced in cooldown seconds

`Action.cost` prices an action at the seconds its cooldown takes, and the
planner's `g` accumulates those seconds. That is the true price only while the
cooldown is what the bot waits on. On a fleet it is not: an action whose
cooldown is cheaper than the budget pace does not happen any sooner for being
cheap — it still costs one request out of a fixed hourly supply. Pricing it at
its cooldown makes a plan of many cheap actions look better than a plan of few
dear ones, which is backwards in exactly the regime the traces measured.

### Fix

The planner's edge cost becomes `max(action.cost(...), action_floor_seconds)`,
where the floor is the action bucket's `WindowBudget.sustainable_interval()` —
live `/my/rates` data divided by the number of concurrent children, never a
constant. It defaults to `0.0`, so every single-character run and every caller
that never wires a `RateGovernor` sees the pre-change planner exactly.

A LOWER BOUND, NOT A FLAT RATE. `max` keeps every action dearer than the floor
at its own price, so distance does not become free. Where the floor binds for
both alternatives the comparison degenerates to "fewer actions wins", which is
the correct objective in that regime.

### Why the floor goes on the edge and not inside `Action.cost`

Two independent constraints, both load-bearing:

* **Consistency.** `PlannerAdmissibility.lean` documents `h ≡ 0`, but that
  comment is stale: `goals/progression.py` and `goals/gathering.py` both return
  `LevelSkill(...).cost(...)` as their heuristic, and `skillGrind_h_consistent`
  is a TIGHT equality. Raising only the EDGE keeps `h s ≤ cost s s' + h s'` on
  the slack side and leaves admissibility strictly safer (`trueRemaining` rises
  while `h` does not). Raising only the HEURISTIC would break consistency and
  make closed-set pruning discard cheaper routes.
* **The published cost formulas.** `formal/diff/test_action_cost_nonneg_diff.py`
  pins ~20 EXACT equalities on live `Action.cost(...)`, and `ActionCostNonneg`
  carries two UPPER bounds on Rest (`restCost_le_restCostMax`,
  `restCost_lt_consumableCostOverheal`) that keep the overheal sentinel
  dominant over every possible Rest. A floor inside the pure cost cores would
  falsify all of them.

Non-negativity — the seal on the optimality proof — is preserved trivially:
`max(x, y) ≥ x ≥ 0`.

### What was deliberately NOT changed

`objective_j` and `acquisition_cost_core` are denominated in ACTIONS, and both
modules carry explicit warnings that anything which is not an action count must
be converted before entering. `sustainable_interval` is a duration. It is at
home in the planner's `g` (seconds) and NOT in J, so it was kept out. Nothing
in `formal/` would have caught a leak across that boundary.

## Adjacent defect found, NOT fixed

`cost_core.rest_cost_pure` returns the real rest cooldown **divided by 10**, and
its docstring declares "cost unit = 10s". Every other cost in the codebase is in
SECONDS: `learned_cost_pure` returns the median `actual_cooldown_seconds`
unscaled, `FightAction`'s static fallback is `10.0 + dist`, and `planner.py`'s
own contract comment says the heuristic estimates "remaining plan cost
(seconds)". Rest is therefore priced at one tenth of its true time cost relative
to any learned action — a full-HP rest really costs ~100s and is priced 10.0,
while a fight that really costs 20s is priced 20.0.

This is consistent with what the traces show: Robby spent 215 actions on Rest
against 216 on Fight, and C3P0 162 against 320.

It was left alone because it is out of the scope asked for and its blast radius
is documented as large — the rest time-value is what gates the potion economy
and the defensive-gear channel, and `restCostMax` / `OVERHEAL_CONSUMABLE_COST`
are derived from it and mirrored in Lean, so moving it moves two proven upper
bounds and the overheal sentinel with it. The request-budget floor masks it
whenever the budget binds (Rest is floored like everything else) but not on a
single-character run.
