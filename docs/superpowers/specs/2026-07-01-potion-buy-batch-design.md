# Batch Potion-Ingredient NPC Buys

## Problem

`CraftPotionsGoal` rebatches its target potion craft to `runs`
(`craft_potions.py:157-158`) but passes the ingredient `NpcBuyAction`s through
unchanged (`craft_potions.py:163`), so they keep the factory default
`quantity=1`. When the supply ladder picks the buy path, the GOAP planner is left
to chain `runs × per-run-qty` single-item buys — one API call + cooldown each —
to acquire mats for a batch it will craft in one action. This is the buy-side
analogue of the consumable-craft-quantity fix (the cook was batched; the shopping
list still buys one item at a time).

This is the only goal-layer site emitting unsized `NpcBuyAction`s (audit
confirmed: `NpcSell`, `Withdraw`, `Recycle`, `Deposit` all size at the goal
layer already).

## Decision (locked)

- **Locus:** goal layer — `CraftPotionsGoal.relevant_actions`, the `NpcBuyAction`
  branch. (Execution-layer batching can't help: the planner would already have
  emitted N separate buy actions.)
- **Sizing:** buy exactly the batch shortfall per ingredient —
  `demand_for_runs - held` — never more.

## Design

In `craft_potions.py:relevant_actions`, after `runs` is computed (line 138),
compute the whole-batch closure demand alongside the existing per-1 `chain`:

```python
chain: dict[str, int] = {}
closure_demand(code, 1, game_data, chain, frozenset())     # membership (unchanged)
withdrawable |= set(chain)

buy_chain: dict[str, int] = {}
closure_demand(code, runs, game_data, buy_chain, frozenset())   # batch demand
```

`closure_demand(root, multiplier, …)` accumulates per-material required
quantities and is linear in `multiplier` (under today's all-yield-1 data,
`closure_demand(code, runs)` == per-1 `chain × runs` == the mats consumed over
`runs` craft runs). It is the same proven primitive already used at line 148.

Rebatch the buy branch (line 163-164):

```python
elif isinstance(a, NpcBuyAction) and a.item_code in chain:
    qty = max(1, buy_chain.get(a.item_code, 0) - self._held(a.item_code, state))
    result.append(a if a.quantity == qty
                  else dataclasses.replace(a, quantity=qty))
```

- `_held(code, state)` (inventory + bank) already exists (`craft_potions.py:108-111`).
- Membership stays gated on the per-1 `chain` (unchanged) — only the quantity is
  sized from `buy_chain`.
- `max(1, …)`: an ingredient already fully held would size to ≤0; the buy path is
  only chosen when mats are short, so the shortfall is normally positive, and the
  floor of 1 keeps the action applicable without over-buying meaningfully.

### Why safe / bounded

- `runs` was chosen by the proven ladder (`_ladder_runs` → `optimal_buy_mix_pure`)
  under gold affordability, so the batch demand is affordable — sizing the buys to
  that same `runs` cannot exceed what the ladder already committed to.
- Sizing never exceeds the batch's actual need (`demand - held`), so no over-buy /
  inventory bloat.
- The target craft rebatch, gathers, withdraws, intermediate crafts, and the
  EquipAction are all untouched — only the buy quantity changes.

## Testing

Unit tests in `tests/test_ai/test_craft_potions.py` (existing goal test module;
use its fixtures — a GameData with a potion recipe whose ingredient is
gold-buyable, and a state forcing the buy path):
- `runs > 1`, ingredient not held → emitted `NpcBuyAction.quantity == recipe_qty ×
  runs` (batched, not 1).
- Ingredient partially held → quantity == `recipe_qty × runs − held`.
- Ingredient fully held (shortfall ≤ 0) → quantity floors at 1 (or the action is
  simply applicable); assert it is not over-sized.
- `runs == 1` → quantity == `recipe_qty − held` (degenerates correctly; no
  behaviour change vs a correct single-batch).

Success criteria unchanged: 0 errors, 0 warnings, 0 skipped, 100% coverage.

## Formal scope

`relevant_actions` builds the action SET and is **not** in the differential
perimeter (no `formal/diff` oracle). The proven ladder (`_ladder_runs`,
`optimal_buy_mix_pure`, `MaxBatchFromHeld.lean`, potion baseline) is untouched —
this only sizes an already-selected buy action. Unit tests only, matching the
existing coverage of `relevant_actions`.

## Out of scope

- Intermediate CRAFT batching (#1) — separate spec; this touches only the buy
  branch.
- `NpcBuyAction`s from any other goal (none emit unsized buys today).
- Craft-yield > 1 handling: today's data is all yield-1, so
  `closure_demand(code, runs)` gives exact batch mats. If yields > 1 land, the
  target-craft rebatch (`runs`) and this buy sizing must be revisited together —
  flagged, not handled here.
