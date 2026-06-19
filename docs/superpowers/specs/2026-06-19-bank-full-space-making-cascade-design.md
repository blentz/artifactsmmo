# Bank-full space-making cascade — design

Date: 2026-06-19
Related: [[project_inventory_livelock_fix]], [[project_zombie_commitment_livelock]],
[[project_recycle_surplus]], [[project_craft_relief_intermediates_only]]

## Problem

When the bag is full AND the bank cannot accept items (bank full or
unreachable), the bot has no valid way to make space by depositing — yet
`DEPOSIT_FULL` still fires (it never checks bank room). It tries to deposit into
a bank that can't take the item, makes no progress, and stalls. Observed live:
Robby hoarded 17 copper_helmets and parked on a full bag.

This is also the root of the pre-existing `formal/diff/test_ladder_fires_diff.py::
test_ladder_fires_matches_production` failure: production `select_bank_deposits`
last-resort-banks a hard_critical item, firing `DEPOSIT_FULL=True`, while the
Lean model disagrees — both sides ignore bank capacity, so the deposit path is
modeled as always-available when it isn't.

When depositing is impossible, the bot must make space by, in priority order:
**craft → recycle → sell → discard**, preserving the most value at each step and
never destroying objective materials.

## Goal

Add a bank-full relief cascade so that, under bag pressure when the bank has no
room, the bot crafts/recycles/sells/discards (in that order) instead of
fruitlessly trying to deposit. Fix `DEPOSIT_FULL` to stop firing when the bank
cannot take items (resolving the livelock and the `ladder_fires` residual at its
root).

## Trigger predicate

```
bank_has_room(state, game_data) :=
    state.bank_accessible
    AND game_data.bank_capacity is not None
    AND len(state.bank_items or {}) < game_data.bank_capacity
```

`bank_capacity is None` means "capacity unknown" (NOT full) — distinct from the
existing `bank_capacity == 0` convention used as a divide-guard in `BANK_EXPAND`.
The cascade activates under bag pressure when `not bank_has_room`. When the bank
HAS room, the bot deposits (and may still craft-relieve as today) — but it no
longer recycles/sells/discards for relief (those are reserved for bank-full).

## The space-pressure response

Under bag pressure the bot makes space ONE of two ways, mutually exclusive on
bank room:

- **bank_has_room → DEPOSIT.** Depositing is recoverable and loses nothing, so
  it is always preferred when the bank can take items. No crafting / recycling /
  selling / discarding for relief.
- **¬bank_has_room → CASCADE: craft → recycle → sell → discard.** Each rung
  reuses an existing goal and respects the active-profile keep-set, so no rung
  destroys objective materials.

**Discard is NOT a bag-full response.** It never fires merely because the bag is
full — it fires only when `¬bank_has_room`, as the LAST cascade rung, and only
for **truly worthless** items (no craft use, no recycle path, no NPC sale).
Selling overstock for gold is the SELL rung's job, one tier above discard.

| Tier | Guard | Goal (reused) | Fires (bag pressure) when |
|------|-------|---------------|----------------------------|
| 1 craft | `CRAFT_RELIEF` (exists, unchanged) | `CraftReliefGoal` + sole-output extension | a craft-relief candidate exists |
| 2 recycle | `RECYCLE_RELIEF` (NEW, `¬bank_has_room`) | `RecycleSurplusGoal` | a recyclable surplus exists |
| 3 sell | `SELL_RELIEF` (NEW, `¬bank_has_room`) | `SellInventoryGoal` | an NPC-sellable (tradeable + buyer) item exists |
| 4 discard | `DISCARD_CRITICAL` / `DISCARD_HIGH` (exist, **+ `¬bank_has_room` gate**) | `DiscardOverstockGoal`, **delete-only path** | last: a truly-worthless overstock item remains |

Tier 1 craft (`CRAFT_RELIEF`) is bank-agnostic and stays as today (fires at fill
≥ 0.70 with a candidate — the existing craft-before-deposit). It therefore also
serves the bank-full case as the top cascade rung. Tiers 2–4 are
`¬bank_has_room`-gated.

### Guard ordering

New `GUARD_ORDER` (guards.py:75):

```
HP_CRITICAL, REST_FOR_COMBAT, BANK_UNLOCK, REACH_UNLOCK_LEVEL,
CRAFT_RELIEF,                       # bank-agnostic, fill ≥ 0.70 (unchanged)
RECYCLE_RELIEF, SELL_RELIEF,        # NEW, ¬bank_has_room
DEPOSIT_FULL,                       # now bank_has_room-gated
DISCARD_CRITICAL, DISCARD_HIGH,     # now ¬bank_has_room-gated, delete-only, worthless
GEAR_REVIEW
```

`DEPOSIT_FULL` (bank_has_room) and `RECYCLE_RELIEF`/`SELL_RELIEF`/`DISCARD_*`
(¬bank_has_room) are mutually exclusive on the bank-room predicate, so their
relative order is immaterial; the listing reads craft → recycle → sell →
deposit-or-discard. Behavior:
- **bank_has_room** → CRAFT_RELIEF (if candidate) then DEPOSIT_FULL (≥0.90).
  RECYCLE/SELL/DISCARD gated OFF — no relief-discard with bank room.
- **¬bank_has_room** → CRAFT_RELIEF → RECYCLE_RELIEF → SELL_RELIEF → (DEPOSIT off)
  → DISCARD_CRITICAL/HIGH (delete worthless). Discard genuinely last.

**Behavior change (intended):** the existing `DISCARD_CRITICAL`/`DISCARD_HIGH`
guards gain a `¬bank_has_room` gate, so they no longer fire on bag-fullness alone
when the bank has room (the bot deposits instead). This is the explicit
requirement "we don't need to discard before bank full."

### Sell vs discard — no double-handling, worthless-only discard

`DiscardOverstockGoal` today sells-before-deletes. Under the cascade the SELL rung
(`SellInventoryGoal`) owns NPC selling; the DISCARD rung is restricted to the
**delete-only** path AND to items that are **truly worthless** — zero NPC
sell-value, no recycle path, not a craft input on hand. Because SELL_RELIEF
(higher) already consumes every sellable item, by the time DISCARD fires only
worthless items remain; the worthless filter is belt-and-suspenders so a
profile-overstocked-but-sellable item is never deleted.

### Craft-tier extension (sole-output materials)

Extend `craft_relief_candidates` (craft_relief.py) with candidates where an
on-hand material is a recipe input for **exactly one** craftable output, that
output is craftable ≥1 now, and the existing net-relief gate (`_net_relief_per_
craft > 0`) holds. Example: `copper_ore → copper_bar` is `copper_ore`'s only
craft output, so crafting it is deterministic and zero-regret. The existing
goal-chain-intermediate candidates are retained. The recycle→bars→re-craft loop
the user described emerges from per-cycle re-evaluation (no special state).

## Reuse map

Reused as-is: `CraftReliefGoal`, `RecycleSurplusGoal`, `SellInventoryGoal`,
`NpcSellAction`, `DiscardOverstockGoal` (delete path), `recyclable_surplus`,
`_sell_value`/`npcs_buying_item`, `active_profile` keep-set, `_last_resort_
deposit`'s victim-ranking heuristic (for the delete-only victim choice if needed).

Net-new: (a) `bank_has_room` predicate; (b) `RECYCLE_RELIEF` + `SELL_RELIEF`
GuardKinds with `¬bank_has_room`-gated fire predicates and `map_guard` branches
(recycle → `RecycleSurplusGoal`, sell → `SellInventoryGoal`); (c) the
`bank_has_room` conjunct on `DEPOSIT_FULL`; (d) the `¬bank_has_room` gate on
`DISCARD_CRITICAL`/`DISCARD_HIGH` plus the delete-only + worthless-only
restriction on the discard goal; (e) the sole-output craft extension to
`craft_relief_candidates`; (f) the matching Lean ladder defs + differential
bindings. `CRAFT_RELIEF` is UNCHANGED (bank-agnostic, already tier-1).

## Formal scope (kernel-proven ladder — lockstep required)

The guard/means ladder is proven and pinned. Changes land across all layers:

- **Lean** (`formal/Formal/Liveness/ProductionLadder.lean`, possibly
  `BankSelection.lean`): add `bankHasRoom` to the Lean `State` (from
  `bankAccessible`, `bankCapacity`, `bankItemsCount`); `depositFullFires` +=
  `bankHasRoom`; `discardCriticalFires`/`discardHighFires` += `¬bankHasRoom`; new
  `recycleReliefFires`, `sellReliefFires` predicates (each `¬bankHasRoom ∧
  candidate-nonempty`); update `allInLadderOrder` to the new order
  (`craftRelief, recycleRelief, sellRelief, depositFull, discardCritical,
  discardHigh`); re-prove the ladder liveness/safety theorems under it.
- **Differential** (`formal/diff/test_ladder_fires_diff.py`): add `recycleRelief`/
  `sellRelief` to `LadderMeans` + `ASSERTED_SLOTS`; thread `bankHasRoom` and the
  candidate-nonempty signals through the oracle arg array; re-pin the
  `depositFull`/`discardCritical`/`discardHigh` slots now that they read
  `bankHasRoom`; add boundary witnesses (bank-full vs bank-has-room). This
  resolves the `ladder_fires` residual: DEPOSIT_FULL no longer fires on the
  bank-full scenario, both sides agree.
- **Mutation**: refresh `mutate.py` anchors after the guard edits; no surviving
  mutants.
- **Craft extension**: `craft_relief_candidates` is a DRIVEN/passthrough oracle
  signal (slot 27), so extending it stays diff-consistent automatically; it
  needs its own production correctness tests, not a new Lean predicate.

Implementation runs through the formal-development workflow (Lean + differential
+ mutation lockstep), NOT plain TDD.

## Testing / success criteria

- 100% coverage; unit tests for `bank_has_room`, each new guard fire predicate,
  the `map_guard` branches, the sole-output craft extension, the delete-only +
  worthless-only discard restriction, AND a regression test that `DISCARD_*` does
  NOT fire when `bank_has_room` (the intended behavior change).
- A bank-full integration scenario: bag full + bank full → asserts the cascade
  picks craft, then (no craft) recycle, then (no recycle) sell, then (only a
  worthless item left) discard.
- A bank-has-room scenario: bag full + bank has room → deposits; recycle/sell/
  discard stay quiet.
- `test_ladder_fires_diff` GREEN (residual resolved); new slots pinned with
  boundary witnesses.
- `gate.sh`: no NEW failures, BankSelection/ladder slot green.
  ⚠️ `gate.sh` is currently red on OTHER pre-existing baseline defects too; this
  work clears the bank-full/ladder slot, not necessarily the entire gate.

## Non-goals / YAGNI

- No new unified opportunity-cost scorer — the priority cascade (craft > recycle
  > sell > discard) encodes the opportunity-cost ordering; each tier keeps its
  existing selection logic.
- When the bank HAS room, deposit stays preferred and `CRAFT_RELIEF` is
  unchanged; the ONLY bank-has-room behavior change is that relief
  recycle/sell/discard no longer fire (deposit handles it).
- No "craft anything on hand" — craft is limited to goal-chain intermediates +
  sole-output materials (deterministic, zero-regret).
- Bank-capacity expansion (`BANK_EXPAND`) is unchanged.
