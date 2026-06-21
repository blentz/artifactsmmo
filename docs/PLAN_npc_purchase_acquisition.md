# PLAN: NPC-purchase acquisition for bag/rune/artifact slots (task #12)

## Motivation

Audit (2026-06-20, live cache) found the `rune_slot`, `artifact1/2/3_slot`, and
`bag_slot` equipment slots are NEVER targeted by `CharacterObjective`. Cause:
`is_attainable`'s leaf rule is `gatherable OR known-spawn monster drop` (after
task #11). Every rune/artifact/bag item is acquired by **NPC purchase**, which
the attainability closure does not model, so they are rejected and dropped from
`target_gear`.

**Confirmed NOT a reach-50 blocker** (the `WinnableAcrossBand` grounding proves
49/49 band winnability using the best *obtainable* loadout, which already
excludes these slots). This is forward-looking optimization — lifesteal runes
(+10/+20) genuinely help combat — explicitly requested to be built now.

## Key data facts (live cache, 2026-06-20)

* Vendors are PERMANENT static NPCs: `rune_vendor`(8,13), `archaeologist`(6,13),
  `sandwhisper_trader`(-2,18). `nomadic_merchant`(3,2) is event-gated.
* `NPCItem.currency` ("if it's not gold, it's the item code") is the price unit.
  **`GameData._build_npcs` currently DROPS this field** — it stores every
  `buy_price` as if it were gold. THIS IS A BUG: a rune priced "100" at
  `sandwhisper_trader` is 100 `sandwhisper_coin`, not 100 gold.
* Currencies seen: `gold`, `sandwhisper_coin`, `small_pearls`, `elemental_page`,
  `codex_page`, `tasks_coin`, and item currencies `cowhide`/`wool`/`rat_hide`/
  `snake_hide`/`corrupted_gem`/`life_crystal_shard`/`malefic_shard`/
  `page_from_hell`/`sand_snake_hide`.
* So acquisition is RECURSIVE: an NPC-bought item is attainable iff its currency
  is attainable. `gold` is always attainable; a currency *item* recurses through
  the same closure (cowhide/wool are monster drops → attainable post-#11).

## Formal boundary

The proved `Formal.Objective` already models attainability as the least fixpoint
`Grounded` (leaf | craft-all-materials). A purchase is structurally a third
grounding constructor:

```
Grounded.buy : buyable item currency = true → Grounded currency → Grounded item
```

i.e. an item grounds if a reachable vendor sells it for a grounded currency.
`gold` is a distinguished always-grounded currency. This is provable exactly like
`.craft` (recurse on a single prerequisite). The Python closure generalizes from
"recipe edge OR leaf" to "recipe edge OR purchase edge OR leaf".

## Phases

### Phase 1 — Loader: capture currency (data foundation) [START HERE]
* `_build_npcs`: store `(buy_price, currency)` not bare `buy_price`.
* `npc_stock` / `npcs_selling_item` expose the currency.
* New accessor: `npc_purchase(item) -> list[(npc, price, currency)]` (sellers
  with a buy_price), and `permanent_npc_sellers(item)` filtered to non-event
  reachable vendors.
* Update all existing callers of `npc_stock`/`npcs_selling_item` for the new
  shape (craft_vs_buy, buy_source_venue, etc. — audit references).
* Unit tests; 100% coverage. NO formal change yet (pure data plumbing).

### Phase 2 — Attainability: NPC-buy grounding edge
* Generalize the closure: an item is attainable if buyable from a reachable
  PERMANENT vendor for an attainable currency. `gold` always attainable;
  currency-item recurses (cycle-safe via the existing `_path`).
* `is_attainable` (perfect sheet): state-independent (assume max gold/reachable).
* `is_attainable_now`: add affordability (have ≥ price of an *owned/earnable*
  currency) + reachability. Keep semantics conservative.
* Cycle guard must cover purchase cycles (A bought with B, B bought with A).

### Phase 3 — Lean model extension
* Add `Buyable : Nat → Nat → Bool` (item → currency) + a distinguished
  always-grounded `gold` token, a `Grounded.buy` constructor, extend
  `groundedByN` / `attainAux` with the purchase edge, re-prove soundness +
  completeness + the headline equivalence. Update `Oracle.lean` encoding.

### Phase 4 — Differential + mutation lockstep
* Extend `test_objective_diff.py`: random graphs with purchase edges + currencies
  (incl. gold, item-currency, and purchase cycles); oracle agreement.
* Mutations: drop the buy edge; treat non-gold currency as always-affordable;
  drop the permanent-vendor gate.

### Phase 5 — Targeting + goals (likely separate session)
* Confirm rune/artifact/bag surface into `target_gear`.
* NpcBuy goal/action for PERMANENT vendors (existing NpcBuy is event-gated per
  [[project_event_merchants]] — needs a non-event path), gated on reachable
  vendor + affordable currency. Currency-earning sub-goals (sell drops for
  sandwhisper_coin etc.) may be out of scope for v1.

### Phase 6 — Unit suite ≥100% + adversarial proof review.

## Phase 2 design note (decided)

The buy edge FOLDS INTO the no-recipe leaf, not a separate top-level edge: every
rune/artifact/bag item has NO craft recipe, so it already reaches `leaf_ok`. A
craftable-AND-buyable item is attainable via its recipe path regardless, so the
buy edge only ever matters at no-recipe items. So `leaf_ok` gains a third
disjunct AND becomes recursive on currency:

```
leaf_ok(leaf, path):
  gatherable(leaf) or drops_from_spawning_monster(leaf)  -> True
  if leaf in path: return False                          # currency-cycle guard
  for (npc, price, currency) in npc_purchases(leaf):
    if is_event_npc(npc) or npc_location(npc) is None: continue   # permanent+reachable
    if currency == 'gold': return True                  # gold always attainable
    if _attainable_closure(currency, ..., path|{leaf}): return True
  return False
```

`leaf_ok` therefore takes `path` (the closure passes it). `is_attainable_now`
adds affordability (owned/earnable currency) — v1 may keep it conservative.

Lean (phase 3): `drop` is no longer a flat predicate. Add `Buyable : item ->
currency` + a distinguished always-grounded `gold`; a `Grounded.buy` constructor
(grounded currency -> grounded item), extend `groundedByN`/`attainAux` with the
buy disjunct at the leaf, re-prove soundness/completeness/equivalence.

## Status
* Phase 1: DONE (ac2ffda) — currency captured, accessors, 100% cov.
* Phase 2-4: DONE (236926d) — buy edge in is_attainable + is_attainable_now
  (Python); Lean `Buys` + `Grounded.buy` (gated hasRec=false; gold as drop-leaf),
  re-proved soundness/completeness/equivalence (axioms clean
  {propext,Classical.choice,Quot.sound}); Oracle + Contracts threaded;
  differential 12/12 (400 random graphs w/ gold/item-currency/event-excluded/
  buy-cycle edges); 3 new mutations + refreshed #11 — all 7 objective mutants
  killed. Full suite 3660, 100% cov, mypy clean, Lean green.
  LIVE PAYOFF: rune_slot→greater_lifesteal_rune (←sandwhisper_coin←monster drop),
  bag_slot→sandwhisper_bag now surface in target_gear (were None). Artifacts stay
  None — their currencies (small_pearls/elemental_page/codex_page) are NOT
  obtainable via gather/drop/craft/permanent-NPC, the truthful answer (deeper
  dungeon/archaeology content; out of scope).
* Phase 5-6: REMAINING — the slots are now TARGETED (in target_gear) but the
  planner has no NpcBuy GOAL for permanent vendors to actually execute the
  purchase (existing NpcBuy is event-gated, [[project_event_merchants]]). Also:
  is_attainable_now affordability ignores currency QUANTITY (v1
  over-approximation). Latent: craft_vs_buy/progression_reserve treat
  npcs_selling_item prices as gold (wrong for non-gold currency) — pre-existing.
* Decision recorded: build now (user, 2026-06-20). Recommended-defer was declined.
