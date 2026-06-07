# Design: Tasks — Complete Items-Task Termination Proof + Python Conformance (Phase 2, gap #3)

Date: 2026-06-06
Status: Approved (brainstorming) — pending implementation plan
Program: behavioral-completeness, backlog rank 1 (tasks, UNPROVEN, score 18).

## Goal

Produce a **complete, gapless** Lean proof that pursuing a **feasible** items-task
reaches `complete` in finitely many cycles — no undischarged hypotheses, no
`sorry` — and then **fix the Python `PursueTask` behavior to conform to the proven
model** wherever a differential exposes divergence. The Python is treated as
suspect (project history: the keep-set/deposit stall froze PursueTask; batch-K
divergence). The proof is the specification; the code is made to match it.

## Honesty boundary (what "complete / no gaps" means)

Unconditional "every items-task terminates" is **false** — some tasks are
genuinely infeasible (require items unobtainable at reachable skill). So the
complete theorem is **feasibility-gated**, where feasibility is a *computed*
decidable predicate, NOT an assumed hypothesis:

> `feasible_items_task_terminates : feasibleItemsTask s gd = true → ∃ N, reachesComplete (pursue s gd N)`

`feasibleItemsTask` is a computable `Bool` discharged from the existing recipe/
skill-closure models (no `axiom`, no hypothesis). Plus `feasibility_sound`:
`feasibleItemsTask = false` implies the task is truly infeasible (no false
negative that would wrongly abandon a doable task). Together these are gapless:
the precondition is computed and shown to imply termination.

## Success criterion

- A kernel-checked `feasible_items_task_terminates` (+ supporting lemmas), no
  `sorry`/`native_decide`/custom axioms, registered in Manifest/Contracts/Audit.
- The Python `PursueTask` behavior **matches** the proven model on every feasible
  state, verified by a differential; any divergence is a Python bug that is FIXED
  (behavior change) until the differential is clean.
- The `tasks` MATRIX row cites the full real proof set (correcting the audit
  under-citation) and is reclassified CLOSED only after Python ≡ model.

## Architecture

The termination of items-task pursuit reduces to three composable facts, each
modeled as a computable function so the proof is complete and the Python is
differentially checkable:

### 1. The pursuit model — `formal/Formal/Liveness/ItemsTaskTermination.lean`

Over the existing Liveness `State`/cycle model, model the per-unit **macro-step**
the bot performs and the full pursuit:

- `keepSet(s, gd) : Set ItemCode` — items the deposit guard must NOT bank
  (the task item + its transitive recipe inputs). The proven-correct version.
- `batchK(s, gd) : Nat` — units traded per macro-step (≥ 1).
- `obtainAndTrade(s, gd) : State` — obtain `batchK` units of the task item
  (gather/craft, finite — discharged by `RecipeChainClosure`/`SkillGapClosure`)
  WITHOUT the deposit guard banking task inputs (because `keepSet` protects them),
  then `taskTrade`, advancing `task_progress` by `batchK`
  (reuse `TaskCompleteReachable.taskTrade_progress_succ`).
- `pursue(s, gd, N)` = `N`-fold `obtainAndTrade` then `completeTask` at
  `progress ≥ total`.

Theorems:
- `feasibleItemsTask(s, gd) : Bool` — computable; true iff the task item is
  gatherable at reachable skill OR craftable via a closing recipe chain (compose
  existing `RecipeChainClosure`/`SkillGapClosure`/`TaskFeasibility`).
- `macro_step_strictly_advances : progress < total → (obtainAndTrade ...).progress
  = progress + batchK ∧ batchK ≥ 1` (TOTALITY — no stall while below total).
- `feasible_items_task_terminates : feasibleItemsTask s gd = true → ∃ N,
  reachesComplete (pursue s gd N)` (REACHABILITY — the capstone, complete).
- `feasibility_sound` (soundness — no false-negative feasibility).
- Safety reused: `task_progress ≤ task_total`, `task_code`/`task_total`
  preserved (`TaskCompleteReachable`), and `keepSet` ⊇ task recipe inputs
  (the deposit-protection invariant).

Core-only where possible; Liveness namespace permits Mathlib if a closure lemma
needs it.

### 2. The conformance targets (the suspect Python)

Termination depends on two Python decisions being correct; these are the
differential targets (pure cores, extracted if not already pure):

- **Deposit keep-set** — the function deciding which items the bank-deposit guard
  protects. It MUST include the active items-task item + its transitive recipe
  inputs (else `DEPOSIT_FULL` banks them and pursuit freezes — the Robby stall).
  Source: the keep-set logic feeding `DepositInventoryGoal` (`bank_selection.py` /
  the deposit relevant-actions filter). Extract a pure
  `task_keep_set(state, game_data) -> frozenset[str]` if not already pure.
- **Trade batch** — `task_batch.py::task_batch_size`. The units traded per pursuit
  step; must match `batchK` (consistent across the cycle so K can't diverge).

### 3. Differential + Python fix

- Differential cross-checks the Python `task_keep_set` and `task_batch_size`
  against the Lean `keepSet`/`batchK` models over random feasible-task states (the
  oracle evaluates the Lean models; Hypothesis feeds both). A mismatch = a Python
  bug.
- For each mismatch, **fix the Python** (TDD): e.g., extend the keep-set to the
  full transitive recipe-input closure of the task item; make `task_batch_size`
  deterministic/consistent. Re-run the differential until Python ≡ model.
- Mutation over the fixed pure cores; surviving mutants fail the gate.

## Data flow

1. Per cycle, the deposit guard consults `task_keep_set` (now = the proven
   `keepSet`), so task inputs are never banked → `obtainAndTrade` can always
   proceed → `macro_step_strictly_advances` holds in the live bot.
2. `PursueTaskGoal` uses `task_batch_size` (= `batchK`) consistently.
3. The proven `feasible_items_task_terminates` therefore describes the live
   behavior (Python ≡ model), so a feasible items-task provably terminates in the
   running bot.

## Error handling

- Infeasible task (`feasibleItemsTask = false`) → the proof makes no termination
  claim; the bot's existing `TaskCancel`/`LowYieldCancel` handles abandonment
  (unchanged). The conformance is about FEASIBLE tasks.
- Missing game data → feasibility is false (conservative), never fabricated.
- No `except Exception`; keep-set/batch are total pure functions.

## Testing

- Lean: kernel-checked, axiom-clean, no `sorry`; Contracts pins lock the exact
  statements.
- Differential: `task_keep_set` ≡ Lean `keepSet`, `task_batch_size` ≡ Lean
  `batchK`, over Hypothesis-random feasible states (incl. deep recipe chains where
  the keep-set must close transitively). Mutation kills perturbations.
- Python unit (TDD for the fixes): the keep-set includes the task item's
  transitive recipe inputs; `DEPOSIT_FULL` no longer banks them; batch is
  consistent across a cycle. Regression: existing task tests stay green.
- Integration smoke (offline): a feasible items-task state advances `task_progress`
  monotonically over simulated cycles to `complete`; the deposit guard never banks
  a protected task input.

## Risks / open items

- **Proof size:** composing recipe/skill closure + trade replication into one
  complete capstone is the largest proof in `formal/`. If a sub-lemma proves
  intractable core-only, the Liveness namespace permits Mathlib; if a genuine gap
  remains, STOP and report rather than `sorry` — the user requires gapless.
- **"Live Python pursuit" is planner-driven**, not a single pure function — so the
  differential targets the *decisions termination depends on* (keep-set, batch),
  not the whole multi-cycle run. The capstone proves termination GIVEN correct
  keep-set/batch; the differential makes the Python keep-set/batch correct. This
  is the honest, checkable conformance boundary (documented so no one mistakes it
  for a whole-run differential).
- **Behavior change risk:** widening the keep-set could retain more in inventory
  (less deposited); bound it to the task item's recipe-input closure only (not
  arbitrary items) so it doesn't bloat retention. The integration smoke guards
  against a deposit-starvation regression.
- **Already-fixed history:** project memory says the keep-set stall was fixed;
  this gap PROVES it (or exposes residual divergence). If the differential is
  already clean, the deliverable is the proof + citation fix with no Python change
  — but the user's expectation (Python not bug-free) means we look hard first.
