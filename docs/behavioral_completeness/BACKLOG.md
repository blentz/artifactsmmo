# Behavioral Completeness — Ranked Gap Backlog

Generated from `docs/behavioral_completeness/MATRIX.md` via
`artifactsmmo_cli.audit.leverage` (`GapItem` → `rank_backlog` / `leverage_score`).

`score = journey_impact × live_bottleneck × stall_risk` (each 0–3); `IGNORE` gaps
score 0 by construction. `live_bottleneck` is read from the live bot's recent
traces (`traces.jsonl` / `play-trace-Robby-20260606-194205.jsonl`): the character
is currently dominated by `PursueTask` → `GatherMaterials`/`CraftRelief` for
wooden_shield + copper_boots gear, so the **gather → craft → equip** chain
(resources/crafting/items/tasks/combat) is the binding constraint right now,
while the market/cosmetic/info concepts are not.

**All single-session gaps are closed.** Every remaining open item is either a
multi-session architectural effort (deferred section below) or out-of-scope
(IGNORE). The ranked open backlog is empty.

| Rank | Concept | Gap kind | Score | Next step |
|---|---|---|---|---|
| — | (none) | — | — | all tractable gaps closed; see Deferred + Closed below |

## Deferred — multi-session architectural work

These are genuine but NOT single-session: each needs a model change (and, for
two, code plumbing) before an honest proof is possible. Landing a decision core
without the coupling/plumbing would be a vacuous/inert proof (the rejected-tasks
lesson), so they are tracked here rather than force-closed.

- **tasks — taskTrade↔inventory coupling** (blocks the honest items-task termination
  capstone). The shared Liveness apply model collapses `.taskTrade`: it advances
  `taskProgress` UNCONDITIONALLY without consuming the obtained task item
  (`Plan.lean` ~316-321 "the Lean model does not track per-trade inventory
  deltas... collapse the chain into a single conservative step"). An honest
  end-to-end termination proof requires: (1) `.taskTrade` consumes the task item
  from `inventoryItems`; (2) `.gather`/`.craft` deposit the actual task item;
  (3) re-prove `TaskCompleteReachable`/`RecipeChainClosure`/`SkillGapClosure`
  under the coupled model; (4) the capstone composes obtainment→inventory→trade.
  This is an architectural change to ~100 proven liveness modules — needs its own
  spec→plan cycle, not a single gap-closure. A first vacuous capstone attempt was
  caught by adversarial review (feasibility = "task incomplete", trade decoupled
  from obtainment) and REJECTED; only Task-1's honest keep-set/batch contracts
  were kept.

- **monsters — drop-driven selection needs producibility wiring.** The decision
  (pick the monster minimizing expected kills = rate/avg_qty for a needed drop) is
  a GatherSelection-shaped clone, BUT monster-drops are currently non-producible
  (`tiers/strategy._producible` + `prerequisite_graph` treat them as leaves), so
  no FightAction is ever emitted to obtain a drop — the core would be inert. Honest
  close needs: restore `min_quantity` into `_monster_drops` (dropped at load) +
  wire monster-drops as producible + a FightAction-narrowing call site, THEN the
  proven core. Two-session.

- **grandexchange — needs order-book ingestion.** The GE is in-API but `game_data`
  has zero order-book ingestion. The only honest decision is immediate-fill
  liquidation (sell into an existing fillable buy order vs NPC — an `Option`-gated
  dominance proof); a posted-price proof would be a sham (posted price ≠ realized
  proceeds). Needs `/grandexchange/orders` plumbed into `game_data` +
  `GeFillBuyOrderAction` first, then `liquidation_venue` + `LiquidationVenue.lean`.
  Two-session.

## Closed

| Concept | Gap kind | Score | Resolution |
|---|---|---|---|
| resources | THIN | 0 | CLOSED 2026-06-06 — yield-optimal multi-source narrowing via GatherSelection (dominance, monotonicity, totality, reachability) |
| crafting | UNPROVEN | 0 | CLOSED 2026-06-06 — craft-vs-buy injects NpcBuyAction when cheaper+affordable; CraftVsBuy [dominance, monotonicity, totality, safety] |
| events | THIN | 0 | CLOSED 2026-06-07 — EventWindow trade-window gate proven [totality, safety, dominance, monotonicity, reachability] |
| bank | THIN | 0 | CLOSED 2026-06-07 — BankExpansionTiming: reserve-preserving expansion gate, closed a real gold-drain-below-reserve safety hole [dominance, monotonicity, totality, safety] |
| items | THIN | 0 | CLOSED 2026-06-07 — ConsumableSelection: overheal-aware fit-to-deficit picker, fixed a real spurious-Rest bug [dominance, monotonicity, totality, safety] |
| maps | THIN | 0 | CLOSED 2026-06-07 — NearestTile: unified the triplicated _nearest, closed the apply/execute divergence [safety, dominance, totality, monotonicity] |
| npcs | THIN | 0 | CLOSED 2026-06-07 — buy-vs-gather for raw NPC-sold mats is the raw instance of CraftVsBuy (already proven + wired); cite-only |
| combat | THIN | 0 | CLOSED 2026-06-07 — loadout-swap selection already proven (RealizableLoadout/EquipmentScoring/PurposeRouting); audit under-citation fixed |
| characters | THIN | 0 | CLOSED 2026-06-07 — single-char coherence proven downstream (CycleInvariants/MultiCycleLiveness/ActionApplicability + StrategyTraversal); only multi-char roster out-of-scope |

## Deliberately not actioned (IGNORE — score 0)

| Concept | Gap kind | Score | Reason |
|---|---|---|---|
| effects | IGNORE | 0 | captured via item stats; no standalone model needed |
| achievements | IGNORE | 0 | passive accrual; ClaimPending already collects rewards |
| badges | IGNORE | 0 | cosmetic, no mechanical reward |
| leaderboard | IGNORE | 0 | read-only ranking, nothing to act on |
| simulation | IGNORE | 0 | local winnability model replaces the network endpoint |
