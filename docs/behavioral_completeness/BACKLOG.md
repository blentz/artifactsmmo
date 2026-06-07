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

These are genuine but NOT single-session: each needs a model change (coupling or
wiring) before an honest proof is possible. Landing a decision core without the
coupling/wiring would be a vacuous/inert proof (the rejected-tasks lesson), so
they are tracked here rather than force-closed.

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

- **monsters — selection core PROVEN; producibility wiring deferred.** The decision
  (pick the monster minimizing expected kills = rate/avg_qty for a needed drop) is
  now a landed, proven, differentially+mutation-locked GatherSelection-shaped core:
  `src/artifactsmmo_cli/ai/monster_drop_selection.py` ↔ `formal/Formal/MonsterDropSelection.lean`
  (axiom-clean). The DATA fix landed too: `_monster_drops` restores `min_quantity`
  (was dropped at load) so avg_qty is faithful, + a `GameData.monsters_dropping(item)`
  accessor. STILL DEFERRED: monster-drops remain non-producible (`tiers/strategy._producible`
  + `prerequisite_graph` treat them as leaves) and FightAction is only emitted by
  combat-XP goals, NOT by any `ObtainItem(drop_item)` goal — so `select_monster_for_drop`
  has NO live caller and is INERT. Remaining work: a new ObtainItem→FightAction goal/action
  path wired into the arbiter action set with `select_monster_for_drop` as the target
  picker (deep model change). NOT CLOSED until that wiring lands.

_(grandexchange is no longer deferred: order-book ingestion landed and BOTH
immediate-fill sides are proven + live-wired-CLOSED — see Closed below. Posting a
new order is reclassified IGNORE-with-reason — see the IGNORE table.)_

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
| grandexchange | UNPROVEN | 0 | CLOSED 2026-06-07 — immediate-fill BOTH sides proven + live-wired: SELL via LiquidationVenue (fill standing buy order vs NPC sell-back), BUY/source via BuySourceVenue (fill standing sell order vs NPC buy) [dominance, totality, safety, monotonicity]. Posting a new order reclassified IGNORE (see below) |

## Deliberately not actioned (IGNORE — score 0)

| Concept | Gap kind | Score | Reason |
|---|---|---|---|
| effects | IGNORE | 0 | captured via item stats; no standalone model needed |
| achievements | IGNORE | 0 | passive accrual; ClaimPending already collects rewards |
| badges | IGNORE | 0 | cosmetic, no mechanical reward |
| leaderboard | IGNORE | 0 | read-only ranking, nothing to act on |
| simulation | IGNORE | 0 | local winnability model replaces the network endpoint |
| grandexchange (posting) | IGNORE | 0 | posting a NEW order is speculative (may never fill); immediate-fill BOTH sides already cover liquidation + sourcing; `/grandexchange/history/{code}` records only completed sales (no unfilled-order denominator) so the API cannot support a fill-probability model; a posted-price realizability proof would be a surrogate sham |
