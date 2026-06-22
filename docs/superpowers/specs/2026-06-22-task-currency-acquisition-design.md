# Design: Demand-Driven Task-Currency Acquisition

**Date:** 2026-06-22
**Status:** Approved (design); pending spec review → writing-plans
**Related:** `docs/PLAN_plannable_closure_obtainability.md`, memory
`project_npc_purchase_acquisition` (Phases 2-4, never landed), `project_levelskill_liveness`,
`project_grind_liveness_proven`.

## Problem

The running bot (`play Robby --learn --tui`) pegs at **2.1 GB RSS / 3.2 GB
VmPeak, ~77% CPU**. Trace root cause: `GatherMaterials(satchel, {satchel:1})`
searches **601K–641K GOAP nodes, depth 51, times out, plan_len 0** (re-fired via
DoomedMemo exponential backoff; each spike high-water-marks the CPython heap,
which is never returned to the OS). Steady churn also from
`GatherMaterials(copper_ring)` (114× ~52K-node searches).

`satchel` IS craftable (gearcrafting 5, recipe `{cowhide:5, feather:2,
jasper_crystal:1}`) but its leaf `jasper_crystal` is a **task-currency item**:
no recipe, no monster/resource drop. It is acquired ONLY by buying from NPC
`tasks_trader` for **8 `tasks_coin`** (confirmed via raw API: NPC-item row
`{npc: tasks_trader, currency: tasks_coin, buy_price: 8, sell_price: None}` — a
DETERMINISTIC fixed-price sale, not the random coin-exchange gamble).
`tasks_coin` is earned by completing tasks (each task's reward is API data, e.g.
chicken task → 3 coins, copper_ore task → 2 coins; **every task yields ≥1**).

The capability to acquire `jasper_crystal` (and therefore craft `satchel`) is
missing. The bot cannot plan the chain
`complete tasks → earn coins → buy jasper → craft satchel`.

### Why it is missing (three coupled gaps)

1. **`_producible` blind to currency-buy** (`tiers/strategy.py:239`): checks
   craft ∨ resource-drop ∨ winnable-monster-drop, NOT `npc_purchases`. Returns
   False for `jasper_crystal` → `is_reachable(ObtainItem(satchel))` False → the
   satchel root is filtered from ranking. Meanwhile `is_attainable`
   (`tiers/objective.py:99`) DOES count `npc_purchases` — the two predicates
   disagree.
2. **No modeled coin income**: `CompleteTaskAction.apply`
   (`actions/complete_task.py:46`) clears task state and mints nothing (+0 XP,
   no coins). So a goal "accumulate ≥8 `tasks_coin`" has no action that raises
   the counter → unplannable.
3. **Unknown future task**: `AcceptTaskAction.apply` (`actions/accept_task.py:33`)
   sets `task_code="__pending__"`, `task_total=1` — the taskmaster assigns the
   real task only at execution, so plan-time has no specific task reward/work.

## Design decisions (settled in brainstorming)

- **Funding model: demand-driven.** When a ranked objective is blocked solely on
  an unaffordable currency-buy leaf, actively pursue coins (not opportunistic).
- **Mechanism: literal GOAP funding sub-plan** — a real plannable subgoal
  `ReachCurrency(tasks_coin, N)` whose action set assembles Accept→…→Complete
  cycles.
- **Coin projection: hybrid.**
  - *Proof / soundness layer:* every completed task yields **≥1 `tasks_coin`**
    (API-grounded floor). Funding therefore reaches target `N` in **≤ N**
    accept→complete cycles — finite and sound, no invented default. The
    conservative API minimum `min(tasks_coin)` over level-appropriate task
    definitions sharpens the bound but the proof floor is ≥1.
  - *Planner cost layer (UNPROVED):* the LearningStore's empirically-observed
    expected coin/task tunes the GOAP cost estimate only. It never enters the
    proved core, so the differential test stays deterministic.
- **Cost abstraction: accept the existing abstract task model.** The funding
  sub-plan reuses the `task_total=1` / progress≥total completion abstraction that
  `PursueTask` already relies on. Plan COMPLETENESS (terminates, yields ≥N) is
  sound; plan COST is optimistic (does not model the full grind). This is
  consistent with the rest of the codebase; no task-model rework.

## Architecture — 4 formally-gated components + 1 unproved heuristic

Each component ships whole: Lean computable `def` + role theorems (kernel-checked,
no sorry/native_decide/custom axioms) + `Manifest.lean` roster entry +
`Contracts.lean` exact-statement pin + extracted pure `*_core.py` + Hypothesis
differential test against the Lean oracle + mutation coverage + ≥90% unit tests.

### C1 — Currency-buy producibility
- **Fix site:** `tiers/strategy.py:239` `_producible`; reconcile with
  `tiers/objective.py:99` `is_attainable`.
- **REFINEMENT (found during planning):** `is_attainable` ALREADY has the
  recursive permanent-vendor currency-buy edge (`objective.py:88-123`,
  `_permanent_vendor_purchases` already excludes event NPCs). But it dead-ends:
  jasper's currency is `tasks_coin`, and `leaf_ok(tasks_coin)` is False because
  `tasks_coin` is not gatherable / dropped / vendor-bought. The TRUE missing
  leaf-type is **"earned by completing tasks"**. So C1's real change is adding an
  `is_task_earnable` leaf disjunct (NOT re-adding currency-buy, which exists).
- **Change:** a recipe-closure leaf is attainable if
  `gatherable ∨ known-spawn-drop ∨ buyable-with-attainable-currency ∨
  task-earnable`. `task-earnable(code)` ⇔ `code` appears in some task
  definition's reward items (API data — e.g. `tasks_coin`). `_producible`
  (state-aware) reconciled to recognize the same leaf-type (delegate to / mirror
  the `is_attainable` closure walk; differ only in the leaf strength —
  winnable-now vs known-spawn).
- **Data dependency:** `game_data` does NOT currently load task definitions. C1
  adds a `_fetch`/`_build` for the task list (cached like other static loaders)
  exposing `task_reward_item_codes -> frozenset[str]` and
  `is_task_earnable(code) -> bool`. No magic strings; `tasks_coin` is recognized
  because it is in the loaded reward set.
- "Permanent" still excludes event-window vendors (memory
  `project_event_merchants`).
- **Does NOT fix the memory burn alone** — see build-vs-deploy note. C1 only
  unblocks RANKING; the search still can't plan satchel until C2–C4.
- **Pure core:** `src/.../tiers/producible_core.py` →
  `is_producible_pure(has_recipe, has_resource_drop, has_winnable_drop,
  has_currency_buy) -> bool` (the boolean disjunction; the four flags computed
  from `game_data` at the call site).
- **Lean:** `formal/Formal/Producible.lean` — `def isProducible` mirroring the
  disjunction.
  - Role `validity`: `isProducible ⇔ (hasRecipe ∨ hasResource ∨ hasWinnableDrop ∨
    hasCurrencyBuy)`.
  - Role `monotonicity`: adding any acquisition source cannot make a producible
    item non-producible (each flag is positive in the disjunction).
- **Soundness note:** producible(jasper) is sound only because coins are
  *earnable* (tasks always available). The "permanent vendor + earnable currency"
  justification is documented; the proof obligation that coins are earnable is
  discharged by C3 (termination), not assumed in C1.

### C2 — Coin-income model
- **Fix site:** `actions/complete_task.py` `CompleteTaskAction.apply`.
- **Change:** on completion, mint the active task's `tasks_coin` reward into
  inventory. The reward for the CURRENT task (real `task_code`) is API data
  (`game_data` exposes `tasks_coin` per task code — new accessor
  `task_coin_reward(code) -> int`). For a `__pending__` (planned-accept) task the
  reward is unknown → use the conservative floor (≥1, or API min) so the model
  never over-credits.
- **Pure core:** `src/.../actions/complete_task_core.py` →
  `complete_task_apply_pure(inv: Mapping, coin_reward: int) -> Mapping` (mints
  `tasks_coin += coin_reward`; all else unchanged). Mirrors the existing
  `npc_buy_currency_apply_pure` style.
- **Lean:** extend/locate in `formal/Formal/...` —
  - Role `monotonicity`: `coin_reward ≥ 1 ⇒ coins_after = coins_before +
    coin_reward > coins_before` (completion strictly raises coins).
  - Role `floor`: per-task reward ≥ 1 (API-grounded constant fact; cite openapi /
    task data — needs the per-axiom signoff path if expressed as a server axiom,
    per memory `project_liveness_axiom_split`).
- **Faithfulness:** the differential test feeds random `(inv, coin_reward≥1)` to
  both `complete_task_apply_pure` and the Lean `applyComplete`; the real
  `CompleteTaskAction.apply` must call the pure core for its inventory update.

### C3 — Funding subgoal (`ReachCurrency`)
- **New goal:** `src/.../goals/reach_currency.py` `ReachCurrencyGoal(currency,
  target)`. `is_satisfied`: `currency_total(state) ≥ target`. `relevant_actions`:
  {AcceptTask, the existing task-progress actions, CompleteTask} scoped to the
  taskmaster + the active task. `desired_state`: `tasks_coin ≥ target`.
- **Progress actions already exist** (no new action needed): `FightAction`
  (`actions/combat.py:83`, `task_progress + 1`) and `CraftAction`
  (`actions/crafting.py:62`) increment `task_progress`. With the `task_total=1`
  abstraction (C2 cost note), one progress step completes the in-model task, so
  the loop `AcceptTask → Fight/Craft (progress→1) → CompleteTask (mints ≥1 coin)`
  is realizable today — this is the same path `PursueTask` already uses.
- **Pure core:** `src/.../goals/reach_currency_core.py` →
  `funding_cycles_pure(on_hand, target, per_task_floor) -> int` =
  `max(0, ceil((target - on_hand) / per_task_floor))` (the bound, with
  `per_task_floor ≥ 1`). Used both for `is_satisfied`/plannability and as the
  measure.
- **Lean:** `formal/Formal/Liveness/CurrencyFunding.lean` (liveness namespace —
  may use Mathlib per memory `project_liveness_axiom_split`).
  - Role `termination`: with `per_task_floor ≥ 1`, repeated complete-cycles reach
    `target` in `≤ ceil((target-on_hand)/floor) ≤ target` steps (measure-descent;
    reuse the `MeasureDescent`/`GrindLadder` engine from
    `project_grind_liveness_proven`).
  - Role `plannable`: the goal is plannable whenever a task can be accepted/
    completed (taskmaster reachable) — never fast-fail-pruned when fundable.
- **Demand trigger:** `ReachCurrency` is generated as the active step when an
  objective's currency-buy leaf is unaffordable (C4). It is NOT a standing
  discretionary means.

### C4 — Wiring + affordability gate
- **Fix sites:** `goals/gathering.py` (deep-leaf buy emission + affordability
  fast-fail), arbiter step selection.
- **Changes:**
  1. `GatherMaterials.relevant_actions`: emit `NpcBuyAction` (currency) for a
     currency-buy closure leaf (`jasper_crystal`), not only top-level
     `self._needed`. Affordability via the proved `npc_buy_currency_is_applicable_pure`.
  2. **Affordability-gated fast-fail** (extends `SkillGateFastFail` /
     closure-obtainability): `is_plannable` for the satchel craft chain prunes
     (no node-burn) WHEN a currency-buy leaf is unaffordable AND no funding step
     is active; the demand routes to `ReachCurrency` instead. Once coins ≥ price,
     the buy+craft chain is admitted.
  3. Demand routing: when `ObtainItem(satchel)` is the chosen objective and its
     `jasper_crystal` leaf is unaffordable, the arbiter selects
     `ReachCurrency(tasks_coin, 8)` as the active step.
- **Lean:** extend `formal/Formal/SkillGateFastFail.lean` (or a sibling
  `ClosureObtainable.lean`) so the fast-fail soundness theorem accounts for a
  currency-buy leaf: prune ⇒ no plan in the CURRENT (unfunded) action set, and
  the funding path is exposed elsewhere (not lost).

### Heuristic — learned coin/task cost (UNPROVED, carved out)
- The GOAP cost of `ReachCurrency` may use the LearningStore expected coin/task
  to estimate cycle count for ranking. This is cost-only, never correctness;
  coverage-carved-out with written justification (it is a heuristic estimate, the
  proved floor guarantees termination regardless).

## Error handling
- Bag/inventory full during buy or mint: existing relief ladder applies
  (memory `project_bank_full_cascade`); `npc_buy_currency_is_applicable_pure`
  already gates on a free slot.
- No taskmaster / unreachable: `ReachCurrency` is unplannable that cycle → falls
  through to other ranked objectives (not a crash).
- Coins present but bag full of keep-set: existing last-resort deposit
  (`project_inventory_livelock_fix`).
- NEVER catch `Exception`; NEVER default missing API data — a missing
  `task_coin_reward` is an error, not a 0.

## Testing
- Per-component differential (Hypothesis → Lean oracle) + mutation, ≥90% unit
  coverage, per the formal gate (`formal/gate.sh`, 7 parts).
- New oracle handlers: `is_producible`, `complete_task_apply`,
  `funding_cycles`; register in `Oracle.lean` + `oracle_client.py`.
- New `Manifest.lean` rows + `Contracts.lean` pins for every role theorem.
- New mutation anchors in `formal/diff/mutate.py` for each new `*_core.py`.
- **Serialization constraint:** the bot imports `src`. `mutate.py`/`gate.sh`
  rewrite `src` → MUST NOT run while the bot is live (memory
  `feedback_serialize_gate_runs`). Run `lake build` + read-only differential
  pytest meanwhile; full gate after a bot stop.

## Build order (multi-session; each a writing-plans plan)
PROVE/BUILD incrementally in this order; DEPLOY (let the live bot run the new
code) only once C1–C4 are all complete (see memory-burn interaction).
1. **C1** producibility (smallest, unblocks ranking; prove + gate).
2. **C2** coin-income model (mint coins; prove monotonicity/floor).
3. **C3** `ReachCurrency` funding subgoal (termination liveness).
4. **C4** wiring + affordability fast-fail (ties it together; end-to-end plan for
   satchel).
5. Heuristic + final adversarial proof review (Phase 4) + full gate after bot
   stop.

**Memory-burn interaction (build vs deploy):** C1 makes satchel reachable;
without C4's affordability fast-fail the unfunded craft chain would still burn
nodes (possibly worse, now actively pursued). So although C1 is BUILT/PROVEN
first, the new behavior must not reach the running bot until C1–C4 are all in —
land them together, or guard the new producibility/routing behind a flag that
flips only when C4 is present. Proving C1 in isolation is fine; deploying it
alone is not.

## Out of scope
- `copper_ring` ~52K-node churn (separate, smaller; note for follow-up).
- Random coin-exchange gamble path (`task/exchange`) — we use the deterministic
  `tasks_trader` sale only.
- Other task-currency items beyond what satchel needs (capability generalizes,
  but validate on `jasper_crystal`/`satchel` first).
