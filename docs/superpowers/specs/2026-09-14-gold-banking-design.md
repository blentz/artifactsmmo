# Gold banking: the half of the bank nobody built

`[DESIGN 2026-09-14]`

## 1. The finding

Gold is per-character. `openapi.json` says so three different ways:

| schema | description |
|---|---|
| `CharacterSchema.gold` | "The numbers of gold on this character" |
| `BankSchema.gold` | "Quantity of gold in your bank" |
| `AccountLeaderboardSchema.gold` | "Gold in the account" |

The pocket is per-character; the bank is the account-wide pool. **Nothing in the
fleet has ever moved gold from the first to the second.** Measured against
`learning.db` — 184,010 cycles, five characters:

| | |
|---|---|
| `DepositGoldAction` executions, ever | **0** |
| `WithdrawGoldAction` executions, ever | 2 |
| pocket gold, live 2026-09-14 16:34 | Lor 28,016 · R2D2 23,429 · HAL 6,978 · C3P0 3,532 · Robby 1,672 |

Lor is carrying seventeen times what Robby is, on one account, and neither can
reach the other's coin.

The liveness census already declares the action dormant, with a reason:

```
| `DepositGoldAction` | action | 0 | dormant | conditional: gold is banked by DepositAll, not as a separate step |
```

**That reason is false.** `DepositAllAction.execute` calls `deposit_item` and
nothing else; it has never touched gold. The census exists precisely because "a
reason nobody rechecks is a green light with an out-of-date argument behind it",
and this is one.

## 2. Why it never fired

Two independent causes, either of which alone is sufficient.

**No goal wants gold in the bank.** `factory.py:381` emits
`DepositGoldAction` at four fixed quantities:

```python
for q in (50, 100, 500, 1000):
    actions.append(DepositGoldAction(quantity=q, bank_location=bank, accessible=bank_accessible))
```

Nothing scores a state with banked gold above one without, so the planner has no
reason to pick any of them.

**The one bank goal filters it out.** `DepositInventoryGoal.relevant_actions`
admits `"deposit"`-tagged actions only. `DepositGoldAction.tags` is
`frozenset({"bank"})`. It is not in the candidate set even when the character is
standing at the bank about to deposit.

And a third, which is what shapes the design: `DepositInventoryGoal` is
space-driven end to end. `value` ramps on `_used_fraction`, `is_satisfied` is
"nothing left to bank", `desired_state` returns `{"inventory_used": ...}`. **A
sibling gold action could never be planned by it** — A* stops the moment
`inventory_used` reaches target, and a gold deposit does not move
`inventory_used`. Adding the tag would not be enough.

## 3. Withdraw, and what banking breaks

`GatherMaterialsGoal.relevant_actions` (`gathering.py:613`) admits one
deficit-sized `WithdrawGold` when pocket gold cannot cover a plan's gold-priced
leaves — the GAP-3 ferry, added 2026-07-08 for a real admit/emit break:

> `is_plannable`'s affordability (`analyze_currency_leaves`) credits pocket +
> KNOWN bank gold [while] `NpcBuyAction`'s gold gate reads POCKET gold only.

That is correct, live, and covers one goal. Withdraw is not the problem.

**Bank expansion is, and not the way it first appears.** `means.py:452` and
`ExpandBankGoal.value` both call the same `expansion_fires`, deliberately, so
"the two cannot re-type it differently":

```python
# bank_expansion_timing.py:93
return pocket_gold >= cost and should_expand_bank(
    used, capacity, account_gold, cost, reserve, trigger_num, trigger_den)
```

Both pass `state.gold` as the pocket. **There is no admit/emit split here** —
reading only the account-scoped half of this two-part gate and calling it the
whole gate was an error in an earlier draft of this document, corrected here
rather than deleted, because the wrong conclusion it produced (add a ferry to
`ExpandBankGoal.relevant_actions`) is the obvious fix and the next reader will
reach for it too.

That ferry would be **dead code**. `expansion_fires` requires `pocket_gold >=
cost` at BOTH gates, so a pocket-short character's goal returns `0.0` and
`relevant_actions` is never consulted. Nothing would ever ask for the gold back.

The real risk is STARVATION. Bank a character down to its slack, let
`next_expansion_cost` grow past that, and the expansion silently never fires —
no error, no rung, no plan. A bank that cannot expand is the livelock fixed on
2026-09-13.

And nothing currently protects that gold. `reserved_targets` reserves the
cheapest unmet **item** purchase — gear, boss, crafting-unlock codes.
`ExpandBankGoal.value` states the gap itself: "A bank expansion is never a
reserved gear code."

## 4. Design

### 4.1 One pure core

`ai/gold_surplus_core.py` — no I/O, property-testable, mutable in isolation:

```python
GOLD_CHUNK = 10_000

def bankable_gold(pocket: int, reserve: int, chunk: int = GOLD_CHUNK) -> int:
    """Whole `chunk` units of pocket gold above `reserve`. 0 when short."""
    return max(0, (pocket - reserve) // chunk) * chunk
```

`reserve` is `progression_reserve(state, game_data)` — already documented as
"Total gold reserved for near-term progression", already floored at
`_MIN_SAFETY_FLOOR = 100`, already the authority every gold sink consults. **No
second notion of near-term demand is introduced.** The last time two gold
thresholds disagreed, `reserve_floor` returned 75,745 against 30,532 of account
gold and refused every purchase on all five characters, including the purchase
it was reserving for.

`reserve` is the caller's keep, which §4.3 widens to
`max(progression_reserve(...), expansion_hold(...))`. `bankable_gold` itself
knows nothing about either — it takes one number, which is what keeps it
property-testable.

Worked example — Lor, bank under 70% full, reserve 3,000:

```
pocket  28,016
reserve  3,000
surplus 25,016
deposit 20,000   (2 x 10k)
keeps    8,016   <- slack
```

**The kept remainder is the hysteresis, and it is the point.** The withdraw
ferry must drain a full 10,000 of slack before another chunk is eligible, so
deposit and withdraw cannot trade the same coin. A rule that banked everything
above the reserve would let the ferry pull gold straight back the next cycle —
the `Withdraw`↔`DepositAll` oscillation this codebase has already shipped once.

Stated as the invariant the tests assert:

```
pocket - bankable_gold(pocket, reserve) >= reserve     for all pocket, reserve
```

### 4.2 Gold rides the bank trip

`DepositAllAction` becomes the bank trip rather than the item-deposit trip. This
makes the census's existing claim true instead of false.

- `_gold_deposit(state)` → `bankable_gold(state.gold, keep)` where `keep` is the
  §4.3 combination `max(progression_reserve(...), expansion_hold(...))`, returning
  `0` when `game_data is None` — the same no-data rule `_deposits` already
  follows. No defaulting: no game data means no banking.
- `apply` subtracts from `gold`, adds to `bank_gold`. `apply` and `execute` must
  keep telling the same story; that file's comments defend this invariant twice
  already.
- `execute` issues one `action_deposit_gold` **after** the item batches, with
  `wait_out_cooldown` before it, and only when a chunk is due. One extra request,
  only when gold actually moves.

`is_applicable` is **unchanged** — still items-only. Gold rides a trip that items
justify; it never causes one.

This is what keeps the change cheap. `value`, `is_satisfied` and `desired_state`
are untouched, so both Lean theorems over this goal still bind:
`depositInventoryValue` (the exact ramp formula) and
`MeansFiring._fires_depositFull_implies_depositInventory_positive` (the guard).
Lean models `depositAllCost` and the action-set enumeration, neither of which
`apply`'s gold semantics reaches. `formal/diff/test_apply_baseline_diff.py`
checks `BASELINE_FIELDS`, the combat-stat set — gold is not among them.

**No Lean change. No new MeansKind. No new GuardKind. No new ladder rung.**

### 4.3 The expansion hold

The fix is on the DEPOSIT side, not the withdraw side: never bank gold an
imminent expansion needs.

```python
def expansion_hold(state, game_data) -> int:
    """`next_expansion_cost` while an expansion is in play, else 0."""
```

"In play" is bank fill at or above `_SATISFIED_FILL` (0.70) — the constant
`ExpandBankGoal` already uses to mean exactly that. The keep becomes:

```python
keep = max(progression_reserve(state, game_data), expansion_hold(state, game_data))
```

```
fill <70%   keep = progression_reserve        -> gold pools freely
fill >=70%  keep = max(reserve, next_cost)    -> price held back
fill >=75%  expansion_fires: pocket can pay   -> buys
```

`TRIGGER_FILL_NUM/DEN` is **75/100**, not the 95/100 that `expand_bank.py`'s
comment claims — a stale comment, corrected as part of this work.
`_SATISFIED_FILL`'s own note ("Held five points under the trigger") confirms 75.

The 70%-to-75% band is the runway. It is narrow, and it does not need to be
wide: the hold stays on for as long as fill is at or above 70%, so a pocket that
cannot yet cover the cost keeps accumulating until it can, and the expansion
then fires. **Self-correcting, not deadlocking** — it can be slow, never stuck.
Holding unconditionally would pin a rising four-figure sum in every pocket
forever, which is most of what pooling was for; holding only at the trigger
risks arriving there with the gold already banked and no way to get it back.

**This touches no proven expansion logic** — not `should_expand_bank`, not
`expansion_fires`, not `BANK_EXPANSION_TIMING_MUTATIONS`, not the Lean
`shouldExpandBank_floor_preserves`. It is additive to the new pure core.

### 4.4 The TUI

`bank_gold` does not exist on the TUI side of the process boundary.
`CycleSnapshot` carries `gold` and `bank_items` and no bank gold, so the three
render sites are not omitting the number — they have nothing to omit.

`CycleSnapshot` gains `bank_gold: int | None = None`, beside `bank_items`.
Defaulting to `None` keeps already-serialized snapshots valid, the compatibility
rule `path_blocked` and the region field already rely on. One construction site,
`player.py:2785`, feeds it from `self.state.bank_gold`.

| file:line | now | after |
|---|---|---|
| `status_pane.py:164` | `Gold  8016` | `Gold (carried)  8,016` |
| `character_screen.py:24` | `Gold  8016` | `Gold (carried)  8,016` |
| `item_tables.py:34` | `Bank  47 items` | `Bank  47 items · 20,000 gold` |

The per-character panes stay about the character; the account-wide figure goes in
the one place that is account-wide. **Unknown renders as `—`, never `0`** — a
synced bank whose gold is unknown is a new case, distinct from the existing
`"Bank — waiting for sync…"` placeholder for an unsynced bank.

Thousands separators are added to these gold figures only, not swept across the
TUI.

## 5. Testing

| what | why it is the test that matters |
|---|---|
| `bankable_gold` below / at / above one chunk | the arithmetic lives in one place, so it is tested in one place |
| `pocket - bankable_gold(...) >= reserve`, all inputs | the property, not a case |
| reserve above pocket banks nothing | the saving-for-something-expensive state |
| bank a chunk, run the GAP-3 ferry, assert next `bankable_gold == 0` | the oscillation, asserted as an invariant rather than observed after the fact |
| `apply` moves `gold` and `bank_gold` together | `apply`/`execute` parity |
| `execute` issues the gold call after the item batches, only when due | request budget is the fleet's binding constraint |
| no gold call when `game_data is None` | "Use only API data or fail" |
| `expansion_hold` is 0 below 70% fill and `next_expansion_cost` at or above it | the boundary the whole hold turns on |
| banking never drops the pocket below `next_expansion_cost` at >=70% fill | the starvation this exists to prevent, as an invariant |
| a >=70%-fill character still reaches `expansion_fires` True after banking | **through a real planner run** — the end-to-end claim, not the arithmetic |
| three TUI sites, synced and unsynced | `test_status_pane.py`, `test_character_screen.py`, `test_item_tables.py` all exist |

Mutation guards on the two numbers that degrade silently: `GOLD_CHUNK`, and the
`>= reserve` boundary (`//` rounding up, `max(0, …)` dropped).

**Process note.** The pre-commit hook runs `tests/test_ai/` only, so all three
TUI changes are invisible to it. The full suite and `formal/gate.sh` are the gate
for this work.

`DepositGoldAction`'s `DORMANT` reason is reworded to describe the mechanism that
will actually exist: gold is banked inside `DepositAllAction.execute`, not as a
separate planner step. The action stays dormant, and the claim becomes checkable
against code.

## 6. Known limitation

**Gold moves only when an item deposit is already due** (bag at or above 85%). A
character that earns gold without filling its bag never banks it.

This follows directly from attaching the deposit to the existing bank trip
rather than giving it a rung of its own, and it is the right first cut: it costs
no ladder change and no proof work. The fix is a gold term on
`DepositInventoryGoal.value` — which is where the Lean mirror starts mattering.

**DEFERRED BY DECISION (2026-09-14), not overlooked.** The limitation is
accepted for this increment and gets its own design in a later session. Lor is
the case that will force it: 28,016 in pocket, and if it earns gold without
filling its bag, nothing here moves that gold.

## 7. Out of scope

Three other pocket-gold consumers have the same latent admit/emit split and are
**not** fixed here, because none is reachable-and-broken the way bank expansion
is:

- `ge_post_buy.py:51` — `GePostBuyOrderAction`
- `transition.py:87` — `TransitionAction`
- `ge_fill_sell.py` — `GeFillSellAction` admits on `can_spend` (ACCOUNT-scoped)
  and debits the pocket: the GAP-3 shape exactly, and the likeliest real one

Each should get a ferry in its owning goal, ideally behind a census that proves
no admit/emit split remains. Separate work.
