# PLAN: autonomous bank-junk drain

**Goal:** The bot drains over-cap BANK junk as part of normal play, so a stockpile
like Robby's 228 sap (sap keep-cap ≈ 1; sap = an L20-40 potion material, low
value) doesn't sit forever. Withdraw the over-cap excess → SELL if a buyer is
ACTIVE (timber_merchant event NPC, +30g each) else DELETE. Handles the current
228 sap AND future accumulation. User-chosen 2026-06-24.

**Why the bot can't do this today:** `overstocked_items` / DiscardOverstock act on
INVENTORY only; nothing inspects BANK holdings vs a cap, and you can't delete/sell
from the bank — items must be withdrawn first. The bank-cleanup memory
[[project_junk_inventory_livelock]] and the inventory fix (shed inv overstock,
delete-when-buyer-dormant) are the foundation this builds on.

## Design
- **Keep-cap (total holdings):** an item's cap = need (soft-target / inventory
  cap) scaled by value. For low-value far-need junk (sap) the cap is small (≈1).
  `bank_excess(code) = max(0, bank_qty(code) − max(0, cap − inv_qty(code)))` — the
  amount in the bank beyond what total-cap allows.
- **New discretionary means `DRAIN_BANK_JUNK`** (tiers/means.py), LOW priority
  (below all progression; only acts when nothing better is pending and the bag has
  room). Fires when: some bank item has `bank_excess > 0` AND `inventory_free ≥ 1`.
- **Goal `DrainBankJunkGoal`:** relevant_actions = `WithdrawItemAction(code,
  min(bank_excess, inventory_free))` for the most-over-cap bank junk. After the
  withdraw, the item is inventory overstock → the existing DiscardOverstock guard
  (already sells-if-active-else-deletes, fixed 2026-06-24) drains it next cycle.
  Loop drains the stockpile a bag at a time; bounded (stops when bank_excess = 0).
- **Anti-thrash:** never withdraw a code whose total holdings are at/below cap
  (so we don't re-withdraw what DiscardOverstock just removed); the withdraw is
  bank→inv, delete is inv→gone, so bank monotonically decreases — no cycle.

## Lockstep (gated — new means in the ladder)
- tiers/means.py: `MeansKind.DRAIN_BANK_JUNK` + firing predicate; bank-excess core.
- Formal/Liveness/ProductionLadder.lean: add `drainBankJunkFires` to `fires` +
  the ladder order; MeansFiring `fires ⇒ drainBankJunkValue > 0`; GuardCoverage /
  means-coverage partition; CycleStep measure (a no-progress means → needs bounded
  fuel or to sit below the progression measure so it can't starve reach-50).
- Oracle + ladder-fires differential + mutation anchors.
- DrainBankJunkGoal + DeleteItemAction/NpcSellAction reuse; unit tests; 100% cov.

## Implementation recipe — MIRROR `RECYCLE_SURPLUS` exactly
`RECYCLE_SURPLUS` is the proven analog (a discretionary no-progress means that
flips an opaque "nonempty" flag, so the cycle-step proof bounds it: fires ⇒ flag
true; apply flips flag false ⇒ can't immediately re-fire). Replicate for
`DRAIN_BANK_JUNK` at every site:
- **Python:** `MeansKind.DRAIN_BANK_JUNK` (means.py) + `_fires` clause
  (`bank_excess nonempty ∧ inventory_free ≥ 1`, low-pressure like RECYCLE) +
  `DISCRETIONARY_ORDER` slot; `bank_drain_core.py` (the bank-excess function);
  `DrainBankJunkGoal`; strategy_driver means→goal map.
- **Formal (the expensive ripple):** add `bankJunkNonempty : Bool` to the liveness
  `State` (Formal/Liveness/*; this field touches EVERY State literal + the
  oracle State decoder — the bulk of the work). Then mirror `recycleSurplus` in:
  ProductionLadder (`drainBankJunkFires` + `fires` match + `allInLadderOrder`),
  CycleStep (means→action map line ~144, `applyActionKind .drainBankJunk` flips the
  flag, the `| drainBankJunk =>` case ~589), MeansFiring (fires ⇒ value>0),
  GuardCoverage/means-coverage partition, Oracle (State decoder + the ladder-fires
  args), the ladder-fires differential, mutation anchors.
- A new action kind `.drainBankJunk` (or reuse `.withdraw`) in `applyActionKind`.

**Scoping verdict (2026-06-24):** mechanical but LARGE — the `State`-field ripple
is the single biggest change-type here. Python-alone is NOT independently
shippable (the MeansKind↔Lean ladder-fires differential + means-coverage break
until the Lean side lands), so it must go in one lockstep. Best executed in a
fresh focused session against this recipe.

## STATUS: BUILT 2026-06-24 (branch feat/drain-bank-junk)

Executed exactly per the recipe. The `.withdrawItem` ActionKind already existed
(unused by other means), so NO new ActionKind / no `productionActionKinds` count
change — drainBankJunk routes to it and `applyActionKind .withdrawItem` flips the
new `bankJunkNonempty` flag false (fire-and-lose, mirroring `.recycle`).

- Python: `bank_drain.bank_drain_excess` (total-holdings cap), `DrainBankJunkGoal`,
  `MeansKind.DRAIN_BANK_JUNK` (enum-last for index stability; DISCRETIONARY_ORDER
  slot below RECYCLE_SURPLUS), `_fires`, `map_means`, decide_key repr. 11 unit
  tests, 100% coverage on both new modules.
- Lean: `State.bankJunkNonempty`; `drainBankJunkFires` + `fires`; CycleStep
  planFor + measure-descent case; CumulativeProgress / CycleStepCharacterization
  cases; FightFairness suffix; allInLadderOrder = 26; LadderEval / GameDataFixture
  literals; DecideKey enum + repr. Root `lake build` green (6289 jobs).
- Oracle/diff/mutation: Oracle State arg[31] + decide_key index 13; sim mirror;
  ladder-fires differential arg[31] from the REAL `bank_drain_excess` helper +
  3 drive/near-miss tests + 1 fill-boundary test; decide_key `_MEANS_INDEX` 13;
  2 mutation anchors (comparator + drop-conjunct), both verified KILLED.

Remaining: full `formal/gate.sh` pass, then merge.

## Note
This is the same "value/need cap on TOTAL holdings" the inventory fix applied to
the bag — now extended to the bank. The 228 sap clears over a few bag-loads once
shipped (sell when timber_merchant spawns, else delete).
