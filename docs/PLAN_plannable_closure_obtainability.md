# PLAN — GatherMaterials closure-obtainability fast-fail (memory/CPU peg)

## Symptom
Running bot (`play Robby --learn --tui`) at **2.1 GB RSS / 3.2 GB VmPeak, ~77% CPU**.
Trace `play-trace-Robby.jsonl` (2091 cycles): goal
`GatherMaterials(satchel, {satchel:1})` searched **601K–641K nodes, depth 51,
timed_out, plan_len 0** (3× via DoomedMemo exponential backoff). Each spike
high-water-marks the Python heap; CPython never returns it → resident sticks.
Steady churn also from `GatherMaterials(copper_ring, {copper_ring:3})` (114×
~52K-node searches).

## Root cause (corrected against live data — NOT the initial "NPC-only bag" theory)
`satchel` IS craftable: `crafting_skill=gearcrafting`, `crafting_level=5`,
recipe `{cowhide:5, feather:2, jasper_crystal:1}`.
- `cowhide` ← fight `cow` (drop). `feather` ← fight `chicken` (drop). Both
  covered by `GatherMaterialsGoal.relevant_actions` closure fight-loop
  (gathering.py:246, `for item in chain`).
- **`jasper_crystal`**: type=`resource`/subtype=`task`. No recipe, no monster
  drop, no resource node. Obtainable ONLY via `tasks_trader` for `tasks_coin`,
  or GE @2000g.
- **But** `relevant_actions` emits buy actions only for **top-level
  `self._needed`** items (gathering.py:278 `for item, qty in self._needed`),
  i.e. `satchel` itself — never for a deep closure leaf like `jasper_crystal`.

⇒ The goal's action set can produce cowhide+feather and craft, but can NEVER
acquire `jasper_crystal`. No plan exists. GOAP A* expands the whole reachable
space → 641K nodes → memory blow-up.

`is_plannable` (gathering.py:363) only checks the **top-level** craft skill gate
(`SkillGateFastFail.isPlannable`); it never checks that the recipe **closure's
leaves** are acquirable by this goal's own action set. That is the gap.

`_producible` (tiers/strategy.py:239) is **non-recursive** — returns True for
satchel on `crafting_recipe(satchel) is not None`, never descends to
jasper_crystal. `is_reachable` is recursive but keys on `prerequisites()`
expansion of `ObtainItem` roots, which does not gate the `GatherMaterials`
step-goal probe.

## The fork (needs user decision before building)
- **(A) Prune** — extend `is_plannable` to fast-fail when any recipe-closure leaf
  is unacquirable by the goal's emittable action set (not craftable, not a
  winnable+spawned monster drop, not a resource drop, not a top-level buy).
  Memory/CPU fix. Bot stops pursuing satchel (correct: it genuinely cannot).
  New Lean: closure-leaf obtainability model + soundness (prune ⇒ no plan).
- **(B) Enable** — broaden `relevant_actions` to emit buys (tasks_coin / GE) for
  deep closure leaves so satchel becomes genuinely plannable. Behavior change +
  tasks_coin/affordability modeling. Larger scope; not an `is_plannable` fix.

A and B point opposite directions. User picked "full formal fix" of
`is_plannable` ⇒ leaning (A). Confirm.

## Formal surfaces touched (option A)
- `formal/Formal/SkillGateFastFail.lean` — extend model (`isPlannable` + new
  closure-leaf obtainability) or add a sibling component; soundness theorem.
- `src/artifactsmmo_cli/ai/goals/gather_plannable_core.py` — pure core signature
  grows; MUST mirror `relevant_actions`' emittable-action set faithfully.
- `gathering.py:363` `is_plannable` — compute closure-leaf acquirability.
- `formal/Oracle.lean:1970/2246` (`runGatherPlannable`), `Manifest.lean:1090`,
  `Contracts.lean:2817`, `diff/test_skill_gate_fastfail_diff.py`,
  `diff/mutate.py:154/1640`.

## Constraints
- Bot is RUNNING and imports `src`. Do NOT run `diff/mutate.py` or `gate.sh`
  (they rewrite src) until the bot is stopped — see memory
  `feedback_serialize_gate_runs`. `lake build` + read-only differential pytest
  are safe meanwhile.
- Faithfulness obligation: the Python `acquirable-leaf` predicate must mirror
  EXACTLY what `relevant_actions` can emit, else differential test passes but the
  model lies. This mirroring is the careful part.

## CAPABILITY ANSWER (user asked: "how is jasper_crystal acquired? are we missing a capability?")
YES — missing. `jasper_crystal` = task-currency item, acquired by: do tasks →
earn `tasks_coin` → buy from `tasks_trader`. The PIECES exist on main
(NpcBuyAction currency-buy is proved: `npc_buy_currency_*_pure`; `is_attainable`
objective.py:95 already counts `npc_purchases`). What's MISSING is the wiring:

1. **Two attainability predicates disagree.**
   - `is_attainable` (objective.py:99) KNOWS currency-buy → jasper_crystal attainable.
   - `_producible` (strategy.py:239) is BLIND to `npc_purchases` (only craft/
     gather/winnable-fight) → returns False → `is_reachable(ObtainItem(satchel))`
     False → satchel root filtered from ranking. INCONSISTENCY is the core.
2. **No task-currency funding chain.** `GatherMaterialsGoal.relevant_actions`
   never injects `CompleteTaskAction`/`AcceptTaskAction` when a `tasks_coin`
   demand sits in the closure — so even with coins-buy emitted, the chain
   `fight→complete_task→earn_coins→buy_jasper→craft_satchel` is never assembled.
   `TaskExchangeGoal` is opportunistic (means.py:130, fires on coin accumulation),
   NOT demand-driven from "I need jasper_crystal".
3. Deep-leaf buy: `relevant_actions` emits NpcBuy only for top-level `self._needed`
   (gathering.py:278), not closure leaves. For `GatherMaterials(satchel,{satchel:1})`
   jasper_crystal never even gets a buy action.

Stale branches `feat/npc-purchase-acq` / `feat/npc-buy-currency` = 0 ahead of main
(Phase-1 merged; Phases 2-4 of [[project_npc_purchase_acquisition]] never landed).

## ⚠️ MEMORY RISK of a partial fix
Fixing `_producible` ALONE (so satchel becomes reachable) WITHOUT the funding
chain makes the bot ACTIVELY pursue satchel and STILL fail to plan (0 tasks_coin
→ buy inapplicable) — likely WORSENING the 641K-node burn. The capability must
ship WHOLE, or the goal stays pruned until coins are on hand.

## Build (option B — the capability), multi-session, formal-gated
- Unify currency-buy awareness into `_producible` / reconcile with `is_attainable`
  (both have proved cores; needs Lean model + Contracts/Manifest/Oracle/diff/mutation).
- Demand-driven task-currency funding: route a needed task-currency leaf to
  earn-coins (CompleteTask) + buy-with-currency, either via GatherMaterials action
  injection (mirror the monster-drop Fight injection) or a dedicated ObtainItem
  buy-with-currency edge + funding subgoal.
- Affordability / reserve modeling for tasks_coin.
- Re-prove: this is the unfinished Phases 2-4 of the npc-purchase-acquisition feature.

## Status
Diagnosis complete + data-confirmed. Capability gap located. Awaiting scope
decision (full capability build vs. immediate memory mitigation first). No code
changed.
