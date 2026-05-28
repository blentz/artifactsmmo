# Lean AI Verification Phase 3 (extended bug-hunt) — Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to execute task-by-task. Steps use `- [ ]` checkboxes.

**Goal:** Continue the suspected-bug hunt into the still-untouched actions/, learning store, projections, and cross-cutting inventory invariants. Phase 2 confirmed real bugs exist where untouched orchestration meets pure arithmetic; this phase targets the recon's top finds.

**Architecture:** Same as Phases 1 and 2 — extract pure cores → model in Lean → prove intent properties → fix-or-flag if false. Mandatory adversarial review per task (gate-green ≠ honest). Serialize gate runs, `git diff src/` after each, commit-before-gate where a mutation target is touched.

**Tech stack:** Lean 4 v4.30.0 core only (no mathlib), `lake`; Python 3.13 via `uv run`; Hypothesis (deterministic "formal" profile); the existing `formal/diff/` + `mutate.py` harness; `check_axioms.sh` (Phase-2 multi-line fix).

**Worktree:** `.claude/worktrees/lean-phase3` on branch `formal-lean-phase3` from `main` (b5d3b65). Symlink `artifactsmmo-api-client`, confirm baseline `lake build`.

**Discipline (Phase-1/2 lessons baked in):**
- No `sorry`/`admit`/custom axiom/`native_decide`. Axioms ⊆ {propext, Classical.choice, Quot.sound}.
- No false-premise hypotheses, no rigged differentials (`unique=True`, integer-only over fractional domains, narrowed strategies that skip contested cases), no proof-theater (proved functions with no genuine caller).
- Adversarial review per task hunts those failure modes.
- Differential ≥200 random examples per target; ≥3 killed mutants per target; both real domain (including the contested case).
- Behavior-preserving refactors; existing suite stays green except for the documented sandbox-environmental `uv` CLI failures.
- If a property is false in reachable states → STOP and flag (BLOCKED-FOR-DECISION) with concrete Python-verified counterexample + fix options. Do not unilaterally fix behavior.

---

## Targets (suspected-bugs-first, ranked from recon)

### Task 1: `learning/store.py::skill_xp_per_cycle` unguarded `json.loads` — **direct fix**
**Files:** `src/artifactsmmo_cli/ai/learning/store.py:281-291` (verify line numbers); tests.

The function calls `json.loads(row.delta_skill_xp_json)` without a `JSONDecodeError` guard, while the `try/except SQLAlchemyError` around it does NOT catch JSON errors — so a malformed JSON row will crash the bot. The sibling `projections._parse_skill_xp` correctly guards.

This is a direct correctness fix, not a Lean target. The CLAUDE.md rule "NEVER catch Exception" still applies — catch the specific exceptions (`json.JSONDecodeError, TypeError`) only.

- [ ] **Step 1:** Confirm the bug: read the function, grep for sibling guarded paths, find the test that exercises a malformed-JSON row (or write one).
- [ ] **Step 2:** Fix the guard: catch `(json.JSONDecodeError, TypeError)` for the JSON decode specifically; on bad row, skip (matching `_parse_skill_xp` semantics) and log a debug warning if a logger is in scope.
- [ ] **Step 3:** Add a real test in the existing test suite (`tests/test_ai/test_learning_store.py` or similar) that inserts a Cycle row with malformed `delta_skill_xp_json` and confirms `skill_xp_per_cycle` skips it instead of crashing.
- [ ] **Step 4:** Run suite green; commit.

### Task 2: `learning/projections.py::cycles_for_progress` double-count
**Files:** `src/artifactsmmo_cli/ai/learning/projections.py` (the cycles_for_progress function ~line 144-160); pure-core extract location; `formal/Formal/CyclesForProgress.lean`; `formal/diff/test_cycles_for_progress_diff.py`.

Recon: the function appends to `intervals` from two sources — strict-increase markers and `cycles_to_satisfy` events — across the same cycle stream. If a single cycle contributes to both, the median is double-weighted on it.

- [ ] **Step 1:** Read the function and the cycle-data shape. Determine whether the two append paths can both fire on the same cycle (read the field semantics: `cycle.task_progress` increments vs `cycle.cycles_to_satisfy is not None`). Quote concretely.
- [ ] **Step 2:** Extract the pure core `cycles_for_progress_pure(cycles: Sequence[CycleRow]) -> float | None` over a minimal `CycleRow` dataclass with just the fields it inspects. Refactor production to delegate. Behavior IDENTICAL.
- [ ] **Step 3:** Run suite green; 100% coverage on touched files.
- [ ] **Step 4:** Lean model `CyclesForProgress.lean` (Nat for counts; ℚ for the median return). State the intent theorem: **each input cycle contributes AT MOST ONE interval point to the median's input list** (no-double-count). Plus: result is `none` or `> 0` (chases the `or 15.0` fallback safety).
- [ ] **Step 5:** Try to prove. If a single-cycle counterexample exists where both branches fire → BUG. Construct concrete CycleRow, run real Python `cycles_for_progress_pure` and confirm it counts that cycle twice. STOP, BLOCKED-FOR-DECISION (fix options: (a) gate one branch with the other's absence; (b) deduplicate by cycle id). Otherwise prove the no-double-count + positivity contract; ship.
- [ ] **Step 6:** Differential test (≥200 examples; include sequences where both branches plausibly fire); ≥3 mutants (drop one of the two append loops; flip `is not None` to `is None`; off-by-one on the strict-increase gate). Each killed.
- [ ] **Step 7:** Wire gate (Formal.lean / Manifest / Contracts / Audit / Oracle / gate.sh). Commit. Run solo gate; verify src clean post-gate; adversarial review.

### Task 3: `actions/gathering.py::GatherAction.apply` inventory-overrun
**Files:** `src/artifactsmmo_cli/ai/actions/gathering.py:42-84`; possibly extract a pure core for the inventory-update; `formal/Formal/GatherApply.lean`; `formal/diff/test_gather_apply_diff.py`.

Recon: `apply` mints `+1` of `drop_item` into inventory without enforcing `inventory_used + 1 ≤ inventory_max`. The `is_applicable` requires `inventory_free ≥ _MIN_FREE_SLOTS=3`, but a multi-step planner state can have `inventory_used` already at `inventory_max` after prior simulated `apply`s in the chain.

- [ ] **Step 1:** Read `is_applicable` and `apply`. Verify the guard structure (cite line refs). Construct or model a 2-action chain state where applying `GatherAction` twice consecutively could push `inventory_used > inventory_max`.
- [ ] **Step 2:** Extract a pure inventory-step function `apply_gather_pure(inventory, inventory_max, drop_item) -> inventory'` over a minimal value object.
- [ ] **Step 3:** Lean model + intent theorem: `apply_gather_pure` preserves `inventory_used ≤ inventory_max` ASSUMING the precondition `inventory_used < inventory_max`. State the precondition precisely; verify it is actually enforced upstream by `is_applicable` AND by every reachable planner path. If the planner can chain `apply`s without re-checking `is_applicable` between them, the precondition may fail mid-chain → **the bug**.
- [ ] **Step 4:** Read `planner.py` and confirm whether intermediate states are re-checked. If not → BUG → BLOCKED-FOR-DECISION with the concrete chain + Python verification of `inventory_used > inventory_max`. Fix options: (a) make `apply` clamp/raise on overflow; (b) make the planner re-check `is_applicable` between chained apply's; (c) tighten `is_applicable` to require `inventory_free ≥ chain_length` (not knowable a priori).
- [ ] **Step 5:** Differential + ≥3 mutants. Gate + adversarial review + commit.

### Task 4: Action cost non-negativity invariant (Dijkstra-optimality sealant)
**Files:** every `actions/*.py::cost`; pure extract or per-file inspection; `formal/Formal/ActionCostNonneg.lean`; differential.

Recon: the planner fix (Phase 2) only stays optimal if every reachable `action.cost(...)` returns ≥ 0. Most are trivially safe (positive constants + non-negative distance), but `Fight/Gather/Move` use `learned = history.action_cost(...) = median(actual_cooldown_seconds)` which has no DB-level non-negativity constraint.

- [ ] **Step 1:** Audit every `Action.cost` to confirm structurally ≥ 0 under the precondition `learned ≥ 0`. List each action with its cost formula. Identify which actions depend on `learned ≥ 0`.
- [ ] **Step 2:** Verify the precondition: grep every site that WRITES `actual_cooldown_seconds`; confirm all writers produce `≥ 0` values. If any writer can produce negative (clock skew, mis-subtraction, server bug), that's the bug — fix it (smallest correct change) or add a Pydantic validator on the model.
- [ ] **Step 3:** Lean model: a per-action `cost_nonneg` proof, parameterised by `learned ≥ 0` where the action consumes it. Most are unconditional. State + prove.
- [ ] **Step 4:** Differential ≥200 examples across the action set; mutants flip a sign in one cost formula. Gate + review + commit.

### Task 5: `FightAction.apply` and `OptimizeLoadoutAction.apply` boundary correctness
**Files:** `actions/combat.py:63-95`, `actions/optimize_loadout.py:46-87`.

Recon: `FightAction.apply` increments `task_progress + 1` only for `monsters` tasks but could overshoot `task_total`. `OptimizeLoadoutAction.apply` at line 58 has `if cur <= 1: pop` else `cur-1` — when `cur == 0` it silently pops a missing key, decoupling planner state from reality.

- [ ] **Step 1:** Read both apply methods; quote the exact branch points and constants.
- [ ] **Step 2:** Extract minimal pure cores: `fight_apply_pure(task_progress, task_total, task_type) -> task_progress'` and `loadout_apply_pure(inventory, swaps) -> inventory'`.
- [ ] **Step 3:** Lean: prove `fight_apply_pure` preserves `task_progress ≤ task_total + 1` (the +1 overshoot is acceptable iff downstream `==`/`≥` checks don't break); document the contract. Prove `loadout_apply_pure` only decrements counts that are ≥ 1 (i.e. `cur ≥ 1` precondition holds at every callsite). If `cur == 0` is reachable, that's the bug → flag.
- [ ] **Step 4:** Differential + mutants. Gate + review + commit.

---

## Task N (wrap-up)
- [ ] Full gate green from clean tree (solo).
- [ ] Full `uv run pytest` (note known sandbox env failures).
- [ ] Update `formal/README.md` coverage table (24 → 24 + new) + Phase-3 findings note (bugs found/fixed, intent properties shipped as contracts).
- [ ] FF-merge `formal-lean-phase3` → `main` + push on user say-so.

---

## Self-Review

**Scope coverage:** all top-5 recon shortlist items mapped 1:1 to Tasks 1-5. The minor LOW-tractability items (inventory_caps≥0, recipe_closure cycle handling) are deferred — they have less bug-find value and are clean for a Phase 4 if useful.

**Suspected-bugs-first ordering:** Task 1 is a known direct bug (the unguarded JSON decode); Tasks 2, 3 are HIGH × EASY/MED bug-likelihood; Task 4 is the load-bearing Dijkstra invariant; Task 5 catches two MED suspects from the action apply layer.

**Honesty risks:** Tasks 2, 3, 4, 5 each route to STOP-and-flag, not unilateral fix, when a property is false. Task 4 may surface that no writer produces negative `actual_cooldown_seconds` in current code — in which case the proof closes as a precondition contract documenting the load-bearing assumption.

**Placeholders:** none. Every step lists concrete files + property + outcome paths. The Lean theorem names are illustrative; actual names land per the per-task implementer's design.
