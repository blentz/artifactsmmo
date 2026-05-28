# Lean AI Decision-Logic Phase 2 (broad sweep) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove independent *intent* properties of the AI's decision/orchestration logic across ~10 targets; fix real bugs (smallest correct change), refute false guarantees with counterexamples, and lock the rest as regression contracts — all through `formal/gate.sh`.

**Architecture:** Same as Phase 1 — extract a PURE decision core (lift store/game_data/clock/graph reads to parameters), mirror it in a computable Lean `def`, state the intent theorem, then fix-and-prove (bug), refute (false guarantee → documented counterexample + the corrected weaker true theorem), or prove-as-contract (correct). Each target lands through the six-part gate (kernel build · axiom lint · manifest · contracts · differential · mutation).

**Tech Stack:** Lean 4 v4.30.0 (core only, no mathlib), `lake`; Python 3.13 via `uv run`; Hypothesis (deterministic "formal" profile); `formal/diff/` harness + `mutate.py`.

**Recon basis:** `StrategyArbiter.select` (`strategy_driver.py:185-266`) is the LIVE goal selector — ordinal bands (guards>collect>step>discretionary, first-plannable), NOT numeric `value()`. Numeric `value()` survives only as the A* heuristic in `planner.py:81,112`. This reframes the design doc's "priority lattice" target into the band-merge (#3) and planner-admissibility (#2) targets below.

---

## MANDATORY per-task discipline (Phase-1 lessons — non-negotiable)

These are enforced because Phase 1 caught **three proofs that were gate-green but dishonest** (false-premise hypothesis, rigged differential, proof-theater) and **one leaked mutation** from concurrent gate runs:

1. **Adversarial review after every task.** A read-only reviewer reads the proof against REACHABLE states and hunts: (a) hypotheses false/unestablished in real states, (b) differential tests rigged (`unique=`, narrowed strategies, integer-only over a fractional domain) to skip the contested case, (c) theorems whose label/comment overclaims vs the statement, (d) proof-theater (proved defs with no genuine caller), (e) mislabeling correct behavior as a bug or vice-versa, (f) model unfaithful to Python. Gate-green is **necessary, not sufficient**. (See `[[feedback_proofs_tell_false_stories]]`.)
2. **Serialize gate/mutation runs.** NEVER run `formal/gate.sh` or `mutate.py` concurrently (incl. one in background while a subagent runs another) — racing `mutate.py` leaks a mutation into production source. After EVERY gate/mutate run: `git diff -- 'src/**/*.py'` and `git checkout --` any unintended change. A subagent may misdiagnose a leaked mutation as a "pre-existing bug" — verify against git, don't trust that framing. (See `[[feedback_serialize_gate_runs]]`.)
3. **Fix policy:** clear correctness defect → fix Python smallest-change, then prove. Behavioral/tuning change (threshold/constant/ordering that alters intended strategy) → STOP and flag to the human, don't edit unilaterally. A *false guarantee* (e.g. non-admissible heuristic claimed optimal) → don't silently fix the algorithm; report the counterexample + correct the CLAIM, and flag any behavioral fix.
4. Refactors are behavior-preserving; existing suite stays green (`uv run pytest`; the 4 CLI-subprocess tests that fail with `FileNotFoundError: 'uv'` are a known sandbox quirk — ignore ONLY those). Touched files keep 100% coverage.
5. No `sorry`/`admit`/custom axiom/`native_decide`; axioms ⊆ {propext, Classical.choice, Quot.sound}. Differential ≥200 examples over the FULL reachable domain; ≥3 killed mutants per target.
6. Reference shapes: `formal/Formal/PriorityBand.lean` (simple), `OwnedCount.lean` (invariant), `UpgradeSelection.lean` (comparator/argmax + Std order machinery), `Scalarizer.lean` (ℚ model), `StrategyTraversal.lean` (existing graph fixpoints).
7. **Worktree:** execute in a fresh worktree on branch `formal-lean-phase2` (create via `superpowers:using-git-worktrees`), symlink `artifactsmmo-api-client`, confirm baseline `lake build`. Commit per task; FF-merge + push only on user say-so.

---

## Group A — HIGH-likelihood real-bug suspects (suspected-bugs-first)

### Task 1: `is_reachable ⇒ actionable_step ≠ None` — the live-assert crash invariant
**Files:** `src/artifactsmmo_cli/ai/tiers/strategy.py` (read `is_reachable` ~60, `actionable_step` ~124, the `decide` assert ~230); `formal/Formal/StrategyTraversal.lean` (EXISTING — must reconcile); maybe extract to `src/artifactsmmo_cli/ai/tiers/reachability.py`; `formal/diff/test_*`, `mutate.py`.

- [ ] **Step 1: Reconcile with the existing proof.** Read `StrategyTraversal.lean` and determine what it ACTUALLY proved about `is_reachable`/`actionable_step`. Critically: the Python `is_reachable` tracks cycles with a `path` set; `actionable_step` uses a `visited` set — DIFFERENT traversal logic. Determine whether the existing Lean model unified them into ONE model (papering over the divergence — a Phase-1-style incomplete model) or modeled both. Report the finding.
- [ ] **Step 2: State the invariant theorem.** `is_reachable(root, graph) = true → actionable_step(root, graph) ≠ none`, over the SAME graph the Python walks (model the prereq DAG as an adjacency/predicate structure with the two distinct cycle-trackers faithfully reproduced). Use fuel-bounded or well-founded recursion (Lean core; no mathlib — a `Nat` fuel parameter = graph node count is acceptable and faithful if the Python is bounded by visited/path).
- [ ] **Step 3: Try to prove it.** If it CLOSES → the assert is safe; ship the contract + differential test exercising deep/cyclic graphs. If it WON'T close → construct the concrete graph where `is_reachable` says true but `actionable_step` returns none (the two cycle-trackers diverge) = a real **crash bug**. STOP, report BLOCKED with the graph; the fix (unify the cycle-tracking) is behavioral — flag it.
- [ ] **Step 4: Differential** (`test_reachability_diff.py`): generate random prereq DAGs incl. cycles and satisfied-interior nodes; assert Python `is_reachable`/`actionable_step` == Lean oracle, AND assert the invariant on the Python side (reachable ⇒ step≠None) — which surfaces the bug live if present.
- [ ] **Step 5: Mutations** ≥3 (flip a cycle-guard, drop the satisfied-interior prune, off-by-one in fuel). Each killed.
- [ ] **Step 6: Gate (solo) + `git diff src` clean + adversarial review + commit.**

### Task 2: `planner.value` A* heuristic admissibility — the "first satisfied = optimal" claim
**Files:** `src/artifactsmmo_cli/ai/planner.py` (read `:81,112,96`); each goal's `value()`; `formal/Formal/PlannerAdmissibility.lean`; `formal/diff/test_*`.

- [ ] **Step 1: Read the claim.** `planner.py:96` documents "first satisfied node is optimal"; `h0=goal.value(state)`, `h=goal.value(next_state)`. Optimality of greedy/A* "first goal-satisfying pop" requires `h` admissible (≤ true remaining cost) AND consistent. Identify the action cost model (cooldown/step cost) the planner uses.
- [ ] **Step 2: Model a minimal planner instance.** A tiny pure model: states, an action with cost, a goal `value` as `h`, and the "expand by h, stop at first satisfied" rule. State the intent theorem: `firstSatisfied = leastCost` UNDER `admissible h ∧ consistent h`.
- [ ] **Step 3: Refute for the real `value`s.** Prove the conditional theorem (sound), THEN demonstrate that a real goal's `value` is NOT admissible/consistent: construct a 2–3 action counterexample (e.g. RestoreHP's value jump, or DepositInventory's ramp) where the documented "first satisfied = optimal" yields a non-least-cost plan. This refutation IS the bug report. STOP, report BLOCKED-FOR-DECISION: the fix (use an admissible heuristic, or weaken the optimality claim to "satisficing") is behavioral — flag with the counterexample + options.
- [ ] **Step 4: Differential / counterexample test** pinning the concrete non-optimal-plan instance (Python planner produces the non-least-cost plan the Lean counterexample predicts).
- [ ] **Step 5: Mutations / contract** for the proved conditional (admissible⇒optimal). **Step 6: Gate + review + commit/flag.**

---

## Group B — MED-likelihood suspects

### Task 3: `StrategyArbiter.select` band-merge + sticky-commitment
**Files:** `src/artifactsmmo_cli/ai/tiers/strategy_driver.py:185-266`; extract `src/artifactsmmo_cli/ai/tiers/arbiter_select.py`; `formal/Formal/ArbiterSelect.lean`.

- [ ] **Step 1: Extract pure core.** `select(guard_kinds, collect_kinds, step: Option, discretionary_kinds, committed: Option, plannable: repr→Bool) -> Option goal` mirroring the band concatenation (guards ++ collect ++ [step] ++ discretionary in the *_ORDER tuples) + the sticky-commitment `_precedes` index logic (lines 230-246). Production `select` builds the lists then delegates.
- [ ] **Step 2: Intent theorems.** (a) **Band soundness:** if any guard fires AND is plannable, the result is a guard (no means/discretionary preempts a plannable guard). (b) **Determinism/totality:** result is the first plannable in the fixed band order — deterministic, independent of input collection order. (c) **Sticky safety:** a committed means is NEVER returned ahead of a newly-firing plannable guard (`guard_precedes`); i.e. sticky commitment can't override a guard. This (c) is the bug-likely one (index-comparison in `_precedes`).
- [ ] **Step 3: Prove or refute.** If (c) can't close → construct the repr/index scenario where a sticky means survives a firing guard = bug → flag. Else prove + ship.
- [ ] **Step 4: Differential** (`test_arbiter_select_diff.py`): generate random band lists + committed + a `plannable` bitmask; assert Python `select` == Lean oracle, incl. sticky cases. **Step 5: Mutations** ≥3 (drop guard_precedes check, reverse band order, sticky always-wins). **Step 6: Gate + review + commit.**

### Task 4: `task_decision` — confidence-margin threshold + div-by-zero invariant + monotonicity
**Files:** `src/artifactsmmo_cli/ai/tiers/task_decision.py:39-60` (+ wherever it lives); extract pure core; `formal/Formal/TaskDecision.lean`.

- [ ] **Step 1: Read.** `combat/history-None ⇒ PIVOT` (line ~44); else PURSUE iff `skill_up_vpc ≥ required_vpc`, `required_vpc = baseline·(1+3·(1−confidence))`; `total_cycles = skill_cycles + task_total` divides somewhere (div-by-zero risk if 0).
- [ ] **Step 2: Extract pure core** over (req_skill, history_present, skill_up_vpc, baseline, confidence, reward, total_cycles) → Decision. Mirror exactly.
- [ ] **Step 3: Intent theorems.** (a) `req_skill = combat ∨ ¬history ⇒ PIVOT` (unconditional). (b) **No div-by-zero:** the cross-file invariant `task_requirement ≠ None ⇒ total_cycles ≥ 1` (model as hypothesis; verify it really holds — that `task_requirement` returns None when `task_total = 0`). (c) **Monotone:** higher `confidence` lowers `required_vpc` (PURSUE no harder); higher `reward`/`skill_up_vpc` ⇒ PURSUE no less readily. If (b) is false in reachable state → div-by-zero bug → flag.
- [ ] **Step 4: Differential + Step 5 Mutations (sign of the 3·(1−conf), the ≥ comparison) + Step 6 Gate + review + commit.**

### Task 5: `weighted_remaining ⇔ is_complete` under personality weights
**Files:** `src/artifactsmmo_cli/ai/.../personality.py:28-34`; `src/artifactsmmo_cli/ai/tiers/objective.py:46` (`is_complete`); `formal/Formal/WeightedRemaining.lean`.

- [ ] **Step 1: Read.** `weighted_remaining = Σ weight(cat)·fraction(cat)`; `is_complete = all three fractions == 0`. Check the `Personality` protocol: is weight positivity enforced anywhere?
- [ ] **Step 2: Extract pure core** `weighted_remaining(weights: triple, fractions: triple)`.
- [ ] **Step 3: Intent theorems.** (a) monotone non-decreasing in each fraction; (b) **`weighted_remaining = 0 ⇔ is_complete` HOLDS IFF all weights > 0** — prove the iff under `weights > 0`, AND prove the counterexample: with a zero weight, an incomplete category reads as done (`weighted_remaining = 0 ∧ ¬is_complete`). This is a latent bug the protocol doesn't prevent.
- [ ] **Step 4: Resolve.** If only `BalancedPersonality` (all weights 1.0) ships today, the iff holds NOW → prove it under the positivity invariant and either (i) document the invariant as a `Personality` contract requirement, or (ii) STOP-and-flag adding a positivity guard (behavioral). Differential over weight/fraction triples incl. a zero weight. **Step 5 Mutations + Step 6 Gate + review + commit.**

### Task 6: `low_yield_cancel_fires` decision boundary
**Files:** `src/artifactsmmo_cli/ai/learning/projections.py:373-409`; extract the pure boundary `src/artifactsmmo_cli/ai/learning/low_yield_boundary.py`; `formal/Formal/LowYieldCancel.lean`.

- [ ] **Step 1: Read the fire condition.** task held ∧ farm samples>0 ∧ alt samples>0 ∧ ((current_xp==0 ∧ alt>0) ∨ (confidence≥0.5 ∧ alt ≥ current·1.5)). Note the zero-fast-path bypasses the confidence gate (cancel on 1 sample).
- [ ] **Step 2: Extract pure boundary** `low_yield_fires(current_xp, alt_xp, confidence, farm_samples, alt_samples) -> bool` (the LearningStore aggregate reads stay in the caller — boundary-core only).
- [ ] **Step 3: Intent theorems.** (a) monotone: fires no less readily as `alt` rises / `current` falls; (b) **confidence-gate soundness:** the only path that fires below confidence 0.5 is the `current==0` fast path — state it precisely; (c) the 1.5 margin is applied correctly (fires ⇒ `alt ≥ 1.5·current` OR current==0). Decide whether the zero-fast-path "cancel on a single alt sample" is a soundness bug (flag) or intended (document). 
- [ ] **Step 4: Differential (full domain incl. current=0, 1-sample) + Step 5 Mutations (drop fast path, flip ≥, change 1.5/0.5) + Step 6 Gate + review + commit.**

---

## Group C — cheap regression-locks (low bug-likelihood, fast)

### Task 7: `strategy._balancing` clamp
**Files:** `strategy.py:198-204`; fold into an existing or new `formal/Formal/StrategyBlend.lean`.
- [ ] Extract `balancing(leader, current) = clamp(0.5, 2.0, 1 + 0.25·(leader−current−2))` (reuse the `clamp_into_band` shape). Prove: result ∈ [0.5, 2.0]; monotone non-decreasing in `(leader−current)`. Differential + ≥3 mutants (clamp bounds, slope sign) + gate + review + commit.

### Task 8: `strategy._learned_blend` convexity/bounds/warm-up
**Files:** `strategy.py:207-214`; `formal/Formal/StrategyBlend.lean` (same module as Task 7).
- [ ] Extract `learned_blend(value, normalized, w) = (1−w)·value + w·normalized` with `w ∈ [0, 0.5]`, `normalized ∈ [0,1]`. Prove: (a) `w=0 ⇒ = value` (warm-up identity); (b) convex bound `min(value, normalized) ≤ blend ≤ max(value, normalized)` (so blending can't exceed either endpoint — the anti-Phase-1-bonus property); (c) monotone in `normalized`. Model over ℚ (Scalarizer pattern) for exactness. Differential (fractional) + ≥3 mutants + gate + review + commit.

### Task 9: `decide` sort totality + guard/means map exhaustiveness
**Files:** `strategy.py decide ~224-256`; `strategy_driver.py map_guard ~53 / map_means ~72`; `formal/Formal/DecideTotality.lean`.
- [ ] (a) Model the `decide` sort key `(-final, effort, repr)` as a comparator; prove it's a strict total order (repr tiebreak ⇒ total) so the sort is deterministic (reuse UpgradeSelection comparator machinery). (b) Model GuardKind/MeansKind as Lean inductives and `mapGuard`/`mapMeans` as total functions — prove exhaustiveness (no fall-through to `raise ValueError`); the Lean `match` proves it mechanically, regression-locking against a future enum variant. Differential (the map: every enum value → a goal repr, matches Python) + mutants (drop a case) + gate + review + commit.

---

## Group D — cleanup

### Task 10: delete dead `Goal.priority()`
**Files:** `src/artifactsmmo_cli/ai/goals/base.py:33`; any tests.
- [ ] **Step 1: Verify truly dead** — `grep -rn "\.priority(" src/ tests/` returns only the def (recon found no caller). If any caller exists, STOP (not dead).
- [ ] **Step 2: Delete** the method + any tests that exclusively call it (Phase-1 dead-code pattern). 
- [ ] **Step 3:** suite green, 100% coverage on touched files, no orphaned references (grep clean). **Step 4: gate (solo) + git diff src clean + commit.**

---

## Task 11: Phase-2 wrap-up
- [ ] Full gate green from a clean tree (solo run). Full `uv run pytest` (note the 4 known env failures). Update `formal/README.md` coverage table (18 → 18 + new components) and append a Phase-2 findings note (bugs found/fixed, false guarantees refuted, the lattice-is-not-live reframing). Commit. FF-merge `formal-lean-phase2` → main + push on user say-so.

---

## Self-Review

**Scope coverage:** Broad-sweep = all recon targets. Group A = the 2 HIGH suspects (#1 reachable-crash, #2 planner admissibility) 1:1. Group B = the 4 MED (band-merge, task_decision, weighted_remaining, low_yield_cancel) 1:1. Group C = the cheap regression-locks (_balancing, _learned_blend, decide-totality + map-exhaustiveness). Group D = dead `priority()`. The design doc's "later phases" list (strategy.decide total-order, _learned_blend convexity, guards/means, discard_overstock, priority lattice, task_decision, strategy_driver exhaustiveness, personality, low_yield_cancel) all map to a task; `discard_overstock` constants are absorbed into the band-merge/lattice reframing (recon showed they're band-mapped, not numeric-compared — covered by Task 3's band soundness).

**Placeholder scan:** No "TBD"/"handle edge cases". The HARD targets (#1,#2) legitimately may end in BLOCKED-with-counterexample (that's the bug-find outcome, defined per step), not a placeholder. Pure-core signatures are concrete.

**Type/name consistency:** Lean modules named per target; pure-core module paths given; reuse of `clamp_into_band` (Task 7), Scalarizer-ℚ (Task 8), UpgradeSelection comparator (Task 9) is explicit.

**Ordering:** suspected-bugs-first (A→B→C→D) matches Phase 1's validated approach; the two genuine bug suspects run first so a real finding surfaces early.

**Honesty risk note:** Tasks 1, 2, 5, 6 each have a real chance of revealing a behavioral defect or false guarantee — every one routes to STOP-and-flag, not unilateral fix. Tasks 1 and 2 also risk Lean-core tractability limits (graph recursion, planner model) — if a proof genuinely can't be done in Lean core without mathlib after real effort, document the limitation (never `sorry`-paper it) and scope it down, per the design doc's honest-risks clause.
