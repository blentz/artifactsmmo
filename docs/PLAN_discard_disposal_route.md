# PLAN: Discard disposal route — stop deleting recyclable/bankable overstock

## Bug (trace-diagnosed 2026-07-04)

`play-trace-Robby.jsonl`: 35 `DiscardOverstock` deletes, 0 Recycle actions in
5,987 events. Deleted: copper_helmet×33, copper_ring×14, wooden_shield×8 (all
recyclable grind outputs), 40 gems (bankable recipe inputs), recall_potion×82.
Every delete happened with the bank accessible and pre-delete bag at 85–86%.

Root cause (three interacting gaps):
1. **Delete band [85%, 90%)** — DISCARD_HIGH fires at `PRESSURE_HIGH` 17/20,
   DEPOSIT_FULL needs 18/20 (liveness invariant pins it above PRESSURE_HIGH),
   RECYCLE_RELIEF / SELL_RELIEF are gated on bank-FULL. In the band, only
   discard can fire.
2. **`DiscardOverstockGoal.relevant_actions` fallback ladder is
   GE fill → NPC sell → Delete** — no Recycle, no Deposit.
3. RECYCLE_SURPLUS means is discretionary-tier, starved by always-servable
   step goals — never ran once in the whole trace.

## Fix (this plan): differentiate the Delete fallback per item

Guards unchanged (their thresholds carry proven liveness invariants). The fix
is inside `DiscardOverstockGoal`: when neither GE nor NPC sell is executable,
route the overstock item through a proven pure decision core instead of a bare
Delete:

```
disposal_route(recyclable, bank_ok, future_value) -> RECYCLE | DEPOSIT | DELETE
  recyclable            -> RECYCLE   (materials recovery beats everything)
  bank_ok ∧ future_value -> DEPOSIT  (bank items with future use)
  else                  -> DELETE    (true junk only)
```

Input assembly (impure adapter, mirrors `liquidation_venue` shape):
- `recyclable` = an **applicable `RecycleAction` exists right now** for this
  code (same eligibility as `ai/recycle_surplus.py`: craftable equipment,
  skill ≥ recipe level, workshop known, net minted materials fit the bag —
  descending-quantity probe like `RecycleSurplusGoal.relevant_actions`).
  Executability-now preserves the 2026-06-24 liveness fix: the chosen route
  always yields an executable action, so overstock always clears.
- `bank_ok` = `bank_has_room(bank_accessible, state.bank_items,
  game_data.bank_capacity)` and a known bank location. `bank_accessible` is
  not a `WorldState` field — threaded into the goal constructor from
  `SelectionContext` at the `strategy_driver` build site.
- `future_value` = `game_data.max_recipe_demand(code) > 0` (any recipe
  consumes it, incl. far-future skill-gated — those are exactly the
  "deposit-eligible" materials per `reachable_recipe_demand`'s contract)
  OR the item is equippable (`ITEM_TYPE_TO_SLOTS`). Items with neither
  (sap over cap, slimeballs) stay Delete — preserves the anti-hoard
  rationale in `guards.py:240-246`.

### Sap-livelock regression guard

The 2026-06-24 fix (Delete offered whenever sell is not executable) exists so
overstock ALWAYS clears. The route preserves it: RECYCLE only when executable
now; DEPOSIT only when bank accessible + has room; DELETE otherwise. Every
branch emits an executable action.

## Components

| # | Piece | File |
|---|---|---|
| 1 | Pure core `disposal_route` + `Route` enum + adapter `overstock_disposal` | `src/artifactsmmo_cli/ai/disposal_route.py` (new) |
| 2 | `DepositItemAction` (single-code deposit, mirrors `WithdrawItemAction`) | `src/artifactsmmo_cli/ai/actions/deposit_item.py` (new) |
| 3 | Wire fallback + `bank_accessible` ctor param | `ai/goals/discard_overstock.py`, `ai/strategy_driver.py` |
| 4 | Bank re-sync + HTTP 496/478 handling for the new action | `ai/player.py` isinstance tuples |
| 5 | Lean model + proofs | `formal/Formal/DisposalRoute.lean` (new) |
| 6 | Gate wiring | `Manifest.lean`, `Contracts.lean`, `Oracle.lean`, `formal/diff/test_disposal_route_diff.py`, `formal/diff/mutate.py` |
| 7 | Unit tests | `tests/test_ai/test_disposal_route.py`, extend `tests/test_ai/test_overstock.py` |

## Theorem roles (`formal/Formal/DisposalRoute.lean`)

- `recycle_first` (priority): `∀ b f, disposalRoute true b f = .recycle`.
- `deposit_when_bankable`: `∀ , disposalRoute false true true = .deposit`.
- `delete_only_when_worthless` (safety): `route = .delete →
  recyclable = false ∧ (bankOk = false ∨ futureValue = false)` — the goal can
  never destroy an item it could recycle or usefully bank.
- `never_starves` (liveness shape): the function is total over `Bool³`
  (by construction; pinned via Contracts) — some action is always chosen.
- Non-vacuity witnesses: each of the three routes is reachable.

Proofs by `decide` (finite Bool³ domain) — kernel-checked, no axioms.

## Mutation groups

- Pure-core mutations (reorder recycle/deposit, drop `future_value` guard,
  invert to delete-first) — killed by the exhaustive 8-case differential.
- Wiring mutations (goal ignores `bank_accessible`; fallback still emits bare
  Delete; adapter skips recycle probe) — each in its OWN group bound to the
  unit test that kills it (lesson: bag-slot-urgency).

## Out of scope

- Guard threshold changes (DEPOSIT_FULL 90% liveness invariant untouched).
- RECYCLE_RELIEF un-gating (minimal-fix alternative; superseded by this).
- Arbiter tier changes for RECYCLE_SURPLUS means.
