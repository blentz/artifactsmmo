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

| Rank | Concept | Gap kind | Score | Next step |
|---|---|---|---|---|
| 1 | tasks | UNPROVEN | 18 | prove PursueTask reachability (task completion terminates) |
| 2 | items | THIN | 18 | model item give/transfer; extend gear proofs to consumables |
| 3 | combat | THIN | 18 | prove loadout-swap-before-fight optimality |
| 4 | characters | THIN | 12 | model multi-character roster (create/select) |
| 5 | bank | THIN | 12 | prove bank-expansion purchase timing |
| 6 | maps | THIN | 8 | prove multi-layer/obstacle traversal |
| 7 | monsters | UNPROVEN | 8 | prove drop-driven monster selection (kill X for drop Y) |
| 8 | npcs | THIN | 2 | model npc-buy of recipe inputs (buy-vs-gather) |
| 9 | grandexchange | MISSING | 2 | add GE buy/sell goal (high-tier liquidity) |
| 10 | events | THIN | 1 | prove event-merchant trade window; pursue event content |

## Closed

| Concept | Gap kind | Score | Resolution |
|---|---|---|---|
| resources | THIN | 0 | CLOSED 2026-06-06 — yield-optimal multi-source narrowing via GatherSelection (dominance, monotonicity, totality, reachability proven) |
| crafting | UNPROVEN | 0 | CLOSED 2026-06-06 — craft-vs-buy injects NpcBuyAction when cheaper+affordable; CraftVsBuy [dominance, monotonicity, totality, safety] proven |

## Deliberately not actioned (IGNORE — score 0)

| Concept | Gap kind | Score | Reason |
|---|---|---|---|
| effects | IGNORE | 0 | captured via item stats; no standalone model needed |
| achievements | IGNORE | 0 | passive accrual; ClaimPending already collects rewards |
| badges | IGNORE | 0 | cosmetic, no mechanical reward |
| leaderboard | IGNORE | 0 | read-only ranking, nothing to act on |
| simulation | IGNORE | 0 | local winnability model replaces the network endpoint |
