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
HAS room, behavior is unchanged (deposit as today).

## Four-tier cascade

Implemented as guard-tier fire predicates, each gated on `not bank_has_room` so
normal (bank-has-room) behavior is untouched. Every tier reuses an existing goal
and respects the active-profile keep-set, so no tier ever destroys objective
materials.

| Tier | Guard | Goal (reused) | Fires (bank full + bag pressure) when |
|------|-------|---------------|----------------------------------------|
| 1 craft | `CRAFT_RELIEF_BANKFULL` (NEW guard, `¬bank_has_room`) | `CraftReliefGoal` + sole-output extension | a craft-relief candidate exists |
| 2 recycle | `RECYCLE_RELIEF` (NEW guard, `¬bank_has_room`) | `RecycleSurplusGoal` | a recyclable surplus exists |
| 3 sell | `SELL_RELIEF` (NEW guard, `¬bank_has_room`) | `SellInventoryGoal` | an NPC-sellable (tradeable + buyer) item exists |
| 4 discard | `DISCARD_CRITICAL` / `DISCARD_HIGH` (exist, fall-through) | `DiscardOverstockGoal`, **delete-only path** | last resort (sellables already consumed by tier 3) |

### Guard ordering

**Constraint:** under `not bank_has_room`, discard must be genuinely LAST
(craft > recycle > sell > discard). But the existing bank-has-room order
deliberately places `DISCARD_CRITICAL` (0.95) ABOVE `CRAFT_RELIEF` (0.70) — dump
junk before crafting at near-full. We must not change the bank-has-room ordering
(it is proven and out of scope).

**Resolution:** the bank-full cascade is a contiguous block of `¬bank_has_room`-
gated guards placed at the TOP of the space-pressure region, above
`DISCARD_CRITICAL`. The craft rung of the cascade is a NEW `¬bank_has_room`-gated
guard `CRAFT_RELIEF_BANKFULL` (same `CraftReliefGoal` + sole-output candidates as
the existing `CRAFT_RELIEF`, just gated on bank-full and positioned above
discard). The existing `CRAFT_RELIEF` stays where it is for the bank-has-room
case. New `GUARD_ORDER` (guards.py:75):

```
HP_CRITICAL, REST_FOR_COMBAT, BANK_UNLOCK, REACH_UNLOCK_LEVEL,
CRAFT_RELIEF_BANKFULL, RECYCLE_RELIEF, SELL_RELIEF,   # bank-full cascade (¬bank_has_room)
DISCARD_CRITICAL, CRAFT_RELIEF, DEPOSIT_FULL, DISCARD_HIGH,   # existing region (DEPOSIT_FULL now bank_has_room-gated)
GEAR_REVIEW
```

Behavior:
- **bank_has_room** → the three bank-full guards are gated OFF; the existing
  region (`DISCARD_CRITICAL, CRAFT_RELIEF, DEPOSIT_FULL, DISCARD_HIGH`) runs
  exactly as today. No proven behavior changes.
- **¬bank_has_room** → cascade fires top-down: craft → recycle → sell; if none
  have a candidate, fall through to `DISCARD_CRITICAL` (delete) then `DISCARD_
  HIGH` (delete); `DEPOSIT_FULL` never fires (gated off). Discard is genuinely
  last.

(Alternative considered and rejected: gate `DISCARD_CRITICAL`/`DISCARD_HIGH` on
"no craft/recycle/sell candidate" — rejected as guard-coupling that's harder to
model formally than a clean contiguous ordered block.)

### Sell vs discard — no double-handling

`DiscardOverstockGoal` today sells-before-deletes. To avoid the SELL and DISCARD
tiers both selling: the SELL tier owns NPC selling (`SellInventoryGoal`); the
DISCARD tier is restricted to the **delete-only** path (true last resort, fires
only when nothing is craftable, recyclable, or sellable). Concretely, under
bank-full pressure the discard guard's goal deletes; selling is the SELL tier's
job one rung above.

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

Net-new: (a) `bank_has_room` predicate; (b) `CRAFT_RELIEF_BANKFULL` +
`RECYCLE_RELIEF` + `SELL_RELIEF` GuardKinds with `¬bank_has_room`-gated fire
predicates and `map_guard` branches (craft maps to the same `CraftReliefGoal`,
recycle to `RecycleSurplusGoal`, sell to `SellInventoryGoal`); (c) the
`bank_has_room` conjunct on `DEPOSIT_FULL`; (d) the sole-output craft extension
to `craft_relief_candidates`; (e) the delete-only restriction on the discard goal
under bank-full; (f) the matching Lean ladder defs + differential bindings.

## Formal scope (kernel-proven ladder — lockstep required)

The guard/means ladder is proven and pinned. Changes land across all layers:

- **Lean** (`formal/Formal/Liveness/ProductionLadder.lean`, possibly
  `BankSelection.lean`): add `bankHasRoom` to the Lean `State` (from
  `bankAccessible`, `bankCapacity`, `bankItemsCount`); `depositFullFires` +=
  `bankHasRoom`; new `craftReliefBankfullFires`, `recycleReliefFires`,
  `sellReliefFires` predicates (each `¬bankHasRoom ∧ candidate-nonempty`, the
  craft one reusing the `craftReliefFires` candidate signal); insert the three
  into `allInLadderOrder` above `discardCritical`; re-prove the ladder
  liveness/safety theorems under the new ordering.
- **Differential** (`formal/diff/test_ladder_fires_diff.py`): add
  `craftReliefBankfull`/`recycleRelief`/`sellRelief` to `LadderMeans` +
  `ASSERTED_SLOTS`; thread `bankHasRoom` and the candidate-nonempty signals
  through the oracle arg array; add boundary witnesses (bank-full vs
  bank-has-room). This resolves the `ladder_fires` residual: DEPOSIT_FULL no
  longer fires on the bank-full scenario, both sides agree.
- **Mutation**: refresh `mutate.py` anchors after the guard edits; no surviving
  mutants.
- **Craft extension**: `craft_relief_candidates` is a DRIVEN/passthrough oracle
  signal (slot 27), so extending it stays diff-consistent automatically; it
  needs its own production correctness tests, not a new Lean predicate.

Implementation runs through the formal-development workflow (Lean + differential
+ mutation lockstep), NOT plain TDD.

## Testing / success criteria

- 100% coverage; unit tests for `bank_has_room`, each new guard fire predicate,
  the `map_guard` branches, the sole-output craft extension, and the delete-only
  discard restriction.
- A bank-full integration scenario: bag full + bank full → asserts the cascade
  picks craft, then (no craft) recycle, then (no recycle) sell, then (nothing
  else) discard.
- `test_ladder_fires_diff` GREEN (residual resolved); new slots pinned with
  boundary witnesses.
- `gate.sh`: no NEW failures, BankSelection/ladder slot green.
  ⚠️ `gate.sh` is currently red on OTHER pre-existing baseline defects too; this
  work clears the bank-full/ladder slot, not necessarily the entire gate.

## Non-goals / YAGNI

- No new unified opportunity-cost scorer — the priority cascade (craft > recycle
  > sell > discard) encodes the opportunity-cost ordering; each tier keeps its
  existing selection logic.
- No change to behavior when the bank HAS room — deposit stays preferred.
- No "craft anything on hand" — craft is limited to goal-chain intermediates +
  sole-output materials (deterministic, zero-regret).
- Bank-capacity expansion (`BANK_EXPAND`) is unchanged.
