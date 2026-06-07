# Tasks — Items-Task Termination Proof + Python Conformance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Lean proof tasks are driven by the `lean4:*` skills (state the theorem, prove iteratively, checkpoint per theorem).

**Goal:** A complete, gapless Lean proof that a *feasible* items-task pursuit reaches `complete` in finite cycles (feasibility computed, not assumed; no `sorry`), then make the suspect Python keep-set/batch decisions conform to the proven models via a differential, fixing any divergence.

**Architecture:** Compose the existing liveness lemmas (`TaskCompleteReachable` trade→complete, `SkillGapClosure`/`RecipeChainClosure` gather→obtain) into a capstone over a `pursue` model; model the two conformance decisions (`keepSet`, `batchK`) in Lean; differential them against the live Python `_keep_codes`/`task_batch_size`; fix Python; correct the matrix citation.

**Tech Stack:** Lean 4 (`formal/Formal/Liveness/`, Mathlib permitted), Python 3.13 (`uv`, pytest 100% cov), Hypothesis (differential).

**Spec:** `docs/superpowers/specs/2026-06-06-tasks-termination-design.md`

---

## File structure

| File | Responsibility | New? |
|---|---|---|
| `formal/Formal/Liveness/ItemsTaskTermination.lean` | `keepSet`, `batchK`, `feasibleItemsTask`, `pursue`, capstone + supporting theorems | create |
| `formal/Formal/{Manifest,Contracts,Audit}.lean`, `formal/Formal.lean` | register + tag | modify |
| `formal/Formal/Liveness/TaskCompleteReachable.lean` | add `@concept: tasks` tag if missing | maybe modify |
| `formal/Oracle.lean` | `"task_keep_set"` + `"task_batch"` dispatch | modify |
| `formal/diff/test_task_keep_set_diff.py`, `formal/diff/test_task_batch_conform_diff.py` | differentials | create |
| `formal/gate.sh`, `formal/diff/mutate.py` | wire diffs + mutation targets | modify |
| `src/artifactsmmo_cli/ai/bank_selection.py`, `src/artifactsmmo_cli/ai/task_batch.py` | conformance fixes IF differential diverges | maybe modify |
| `docs/behavioral_completeness/{MATRIX,PROOF_CONCEPT_INDEX,BACKLOG}.md` | fix citation, close row | modify |
| tests under `tests/test_ai/` | Python conformance-fix tests | maybe create |

---

## Task 1: Lean conformance models (keepSet, batchK) + their contracts

**Files:** Create `formal/Formal/Liveness/ItemsTaskTermination.lean` (initial: the two models + their contracts); Modify `Formal.lean`/`Manifest`/`Contracts`/`Audit`.

Model the two decisions termination depends on, faithfully mirroring the Python:
- Python `bank_selection._keep_codes(state, gd)` = `{TASKS_COIN, task_code} ∪ recipe_materials(recipe_roots) ∪ {best weapon, ...}`. Model `keepSet` over an abstract `(taskCode, recipeInputs : List ItemCode, ...)` carrying at least the task code + its transitive recipe inputs.
- Python `task_batch.task_batch_size(state, gd)` = `max(1, min(remaining, fit, BATCH_CAP))`. Model `batchK = max 1 (min remaining (min fit BATCH_CAP))`.

- [ ] **Step 1:** write the module header tag `-- @concept: tasks, crafting, bank @property: reachability, totality, safety` + the two computable defs (`keepSet`, `batchK`) mirroring the Python exactly (read `bank_selection._keep_codes` + `task_batch.task_batch_size` first for the exact formula). Define a `Recipe`/`Task` input structure matching what the oracle will pass.

- [ ] **Step 2:** prove the contracts (via `lean4:prove`; `omega`/`decide`/`simp`):
  - `keepSet_contains_task_item : taskCode ∈ keepSet inp` (SAFETY — the task item is always protected).
  - `keepSet_contains_recipe_inputs : ∀ m ∈ recipeInputs inp, m ∈ keepSet inp` (SAFETY — the deposit guard never banks a task recipe input; the stall-prevention invariant).
  - `batchK_ge_one : batchK inp ≥ 1` (TOTALITY — always makes progress).
  - `batchK_le_remaining : batchK inp ≤ remaining inp` (SAFETY — never over-trades past total) — adapt to the real `task_batch_size` clamp.

- [ ] **Step 3:** `lake build Formal.ItemsTaskTermination`; axiom-check; register the 4 theorems in `Manifest`/`Contracts`/`Audit`; add `import` to `Formal.lean`; regenerate index (`--check` OK).

- [ ] **Step 4: commit** `formal: items-task keepSet/batchK conformance models + contracts`.

---

## Task 2: the complete termination capstone (the large proof)

**Files:** Extend `formal/Formal/Liveness/ItemsTaskTermination.lean`; Modify `Manifest`/`Contracts`/`Audit`.

Drive with `lean4:prove`/`lean4:autoprove`, checkpointing per theorem (`lean4:checkpoint`). Reuse `TaskCompleteReachable.{taskTrade_progress_succ, replicate_taskTrade_progress, taskComplete_reachable}` and `SkillGapClosure.{gather_skill_succ, replicate_gather_skill_progress, gather_taskProgress_preserved}` and `RecipeChainClosure`.

- [ ] **Step 1:** `feasibleItemsTask (s gd) : Bool` — computable; true iff the task item is gatherable at reachable skill OR craftable via a closing recipe chain. Compose the existing closure predicates; do NOT assume them. Prove `feasibility_sound`: `feasibleItemsTask = false → ¬ obtainable` (no false negative) — stated over the closure models.

- [ ] **Step 2:** `obtainAndTrade (s gd) : State` (using `keepSet` so task inputs survive) and `macro_step_strictly_advances : s.progress < s.total → (obtainAndTrade s gd).progress = s.progress + batchK ... ∧ batchK ... ≥ 1` (TOTALITY/no-stall). Reuse `taskTrade_progress_succ` + the gather lemmas; `gather*_taskProgress_preserved` ensures obtaining doesn't disturb progress before the trade.

- [ ] **Step 3:** `pursue (s gd N) : State` = N-fold `obtainAndTrade` then `completeTask` at `progress ≥ total`. Capstone
  `feasible_items_task_terminates : feasibleItemsTask s gd = true → ∃ N, reachesComplete (pursue s gd N)` —
  build on `replicate_taskTrade_progress` lifted to the macro-step (`N = ceil((total - progress)/batchK)`). NO `sorry`, NO undischarged hypothesis (feasibility is the computed precondition). If a sub-lemma is intractable core-only, Mathlib is permitted (Liveness namespace); if a genuine gap remains, STOP and report — do not `sorry`.

- [ ] **Step 4:** `lake build`; axiom-check each (`#print axioms` ⊆ allowed; for Liveness, the gate's `check_axioms_liveness` set — confirm any extra axiom is a registered liveness axiom or escalate). Register `feasibleItemsTask`-related theorems + the capstone in `Manifest`/`Contracts`/`Audit`; regenerate index.

- [ ] **Step 5: commit** `formal: complete feasible-items-task termination capstone (gapless)`.

---

## Task 3: differential — Python keep-set/batch vs the proven models

**Files:** Modify `formal/Oracle.lean`, `formal/gate.sh`, `formal/diff/mutate.py`; Create the two diff tests.

- [ ] **Step 1:** add `"task_keep_set"` and `"task_batch"` branches to `Oracle.lean` (read the modeled inputs — task code, recipe-input list, remaining/fit/cap ints — and emit the `keepSet` membership / `batchK` value). `lake build oracle`.

- [ ] **Step 2:** differential `formal/diff/test_task_keep_set_diff.py`: over Hypothesis-random `(task_code, recipe with transitive inputs, inventory)`, assert the LIVE `bank_selection._keep_codes(state, game_data)` contains exactly the proven `keepSet` membership for the task-related codes (focus on the invariant: every task recipe input is kept). And `test_task_batch_conform_diff.py`: `task_batch.task_batch_size(state, gd)` == Lean `batchK` over random `(remaining, fit, cap)`. Read `oracle_client.py` + an existing diff for the call shape; build the `state`/`game_data` fixtures minimally.

- [ ] **Step 3:** run them: `cd formal && lake build oracle && cd .. && uv run pytest formal/diff/test_task_keep_set_diff.py formal/diff/test_task_batch_conform_diff.py -q --no-cov`. **A failure = a Python bug** (the keep-set misses a transitive recipe input, or batch diverges). RECORD every divergence with its input — these drive Task 4. If BOTH pass on the first run, record "Python already conforms" (the keep-set history says the stall was fixed) and Task 4 is a no-op.

- [ ] **Step 4:** wire both diffs into `gate.sh` part (d); add the two pure cores (`_keep_codes`, `task_batch_size`) to `mutate.py`'s target set (mutate the keep-set union and the batch clamp); confirm mutants killed.

- [ ] **Step 5: commit** `formal(diff): task keep-set + batch conformance differentials`.

---

## Task 4: fix the Python to conform (only if Task 3 found divergence)

**Files:** Modify `src/artifactsmmo_cli/ai/bank_selection.py` and/or `src/artifactsmmo_cli/ai/task_batch.py`; Tests under `tests/test_ai/`.

For EACH divergence Task 3 recorded:
- [ ] **Step 1:** write a failing Python unit test reproducing it (e.g. a deep-recipe task where `_keep_codes` omits a transitive intermediate → assert it IS kept; or a batch input where `task_batch_size` diverges from `batchK`).
- [ ] **Step 2:** run → confirm fail.
- [ ] **Step 3:** fix the Python to match the proven model (e.g. extend `_keep_codes`'s `_recipe_materials` to the full TRANSITIVE recipe-input closure of the task item; make `task_batch_size` match `batchK`'s clamp). Bound the keep-set to the task item's recipe-input closure only (no retention bloat).
- [ ] **Step 4:** run the unit test (pass) + the Task-3 differential (now clean) + regression: `uv run pytest tests/test_ai/ -k "task or keep or bank or deposit or batch or pursue" -q --no-cov` (existing task/deposit tests stay green — if the keep-set widening breaks a deposit test, reconcile honestly; the proven invariant wins, update the test if it encoded the bug).
- [ ] **Step 5: commit** `fix(ai): conform task keep-set/batch to the proven termination model`.

If Task 3 found NO divergence, skip Task 4 and note "Python already conforms" in the Task 5 matrix update.

---

## Task 5: fix the under-citation + close the row + full gate

**Files:** Modify `docs/behavioral_completeness/{MATRIX,BACKLOG}.md`

- [ ] **Step 1:** correct the `### tasks` MATRIX row (keep all 7 fields + citations):
  - Proof coverage → `ItemsTaskTermination [reachability, totality, safety] + TaskCompleteReachable [reachability] + TaskFeasibility [reachability, safety] + AcceptTaskGate [totality, safety] + TaskTradeReadyPriority [safety, totality] + WeightedRemaining [monotonicity, safety] + LowYieldCancel [safety, monotonicity] + TaskDecision [dominance, monotonicity] (PROOF_CONCEPT_INDEX)` (the real set — corrects the under-citation).
  - Gap + policy → `CLOSED — act: pursue feasible items-tasks (proven to terminate); keep-set/batch conform to the model (synthesis)`.
  Ensure `TaskCompleteReachable` + `ItemsTaskTermination` carry `@concept: tasks` tags so they appear in `PROOF_CONCEPT_INDEX`; regenerate the index. `uv run pytest tests/test_audit/test_matrix_complete.py -q --no-cov` → PASS.

- [ ] **Step 2:** re-rank `BACKLOG.md` — tasks CLOSED; the next-highest open gap becomes rank 1.

- [ ] **Step 3:** full gates:
  - `uv run pytest tests/ -q` → 100% coverage, all pass.
  - Formal: `cd formal && bash gate/check_no_orphan_modules.sh && bash gate/check_no_sorry.sh && bash gate/check_axioms.sh && bash gate/check_axioms_liveness.sh && bash gate/check_proof_concept_index.sh && lake build oracle 2>&1 | tail -2 && lake build 2>&1 | tail -2` → all OK; the new differentials pass.
  - `uv run mypy` + `ruff` on any changed Python → clean.

- [ ] **Step 4: commit** `docs(audit): close tasks row (items-task termination proven + Python conforms)`.

---

## Self-review notes (author)

- **Spec coverage:** complete capstone (feasibility computed)→Task 2; keepSet/batchK models + contracts→Task 1; conformance differential→Task 3; Python fix→Task 4 (conditional); citation fix + close→Task 5. The "no Python core, only conformance differential on keep-set/batch" boundary from the spec is honored (Tasks 3-4 target those two decisions, not a whole-run differential).
- **Placeholder scan:** none. "If Task 3 found no divergence" is a real conditional branch, not a placeholder — both outcomes are specified.
- **Proof-task realism:** Tasks 1-2 are lean4-skill-driven (statements + reuse list given; tactics discovered while proving) — the established pattern from the prior gaps' formal tasks. The capstone (Task 2) is explicitly the largest proof; the gapless requirement is restated (report, don't `sorry`).
- **Type consistency:** `keepSet`/`batchK`/`feasibleItemsTask`/`obtainAndTrade`/`pursue` defined Task 1-2, oracle-dispatched Task 3; Python `_keep_codes`/`task_batch_size` are the live conformance targets Tasks 3-4.
- **Execution reads:** the exact `_keep_codes` + `task_batch_size` formulas (Task 1 reads them to mirror); the Liveness `State` fields + the existing lemma signatures in `TaskCompleteReachable`/`SkillGapClosure` (Task 2 reads them to compose); the oracle input-encoding for set-membership (Task 3 mirrors an existing branch); whether `TaskCompleteReachable` is already `@concept`-tagged (Task 5 checks).
