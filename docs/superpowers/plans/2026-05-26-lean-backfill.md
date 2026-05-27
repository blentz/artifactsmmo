# Lean 4 Formal Verification — Backfill Plan (13 remaining components → 14/14)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Each component is one task following the FIXED TEMPLATE below; the proof work uses the `lean4:prove` / `lean4:autoprove` / `lean4:formalize` skills. Steps use checkbox (`- [ ]`).

**Goal:** Prove the remaining 13 pure-logic AI components in Lean 4 through the existing four-part+contracts anti-gaming gate, bringing coverage to 14/14. `calculate_path` is the proven reference.

**Architecture:** Replicate the foundation pattern exactly. Lean core only (no mathlib) unless a proof genuinely needs it (then add minimally, never `sorry`). Same gate: kernel build · `#print axioms` lint · `Manifest.lean` role coverage · `Contracts.lean` statement pinning · Hypothesis differential test (Lean oracle vs real Python) · mutation runner. **Green requires real, complete, teeth-bearing proofs.**

---

## Fixed per-component template (every task does ALL of these)

For component `C` (Python `src/.../<mod>.py`):
1. `formal/Formal/<C>.lean` — computable `def`(s) mirroring the Python + the role `theorem`s (∀ inputs, sorry-free). Use `lean4:prove`/`autoprove` for the proofs.
2. Add `import Formal.<C>` to `formal/Formal.lean`.
3. `formal/Formal/Contracts.lean` — add an `example : <EXACT STRONG STATEMENT> := @<thm>` per role theorem (pins the statement; weakening → build RED).
4. `formal/Formal/Manifest.lean` — add `#check @<thm>` per role theorem.
5. `formal/Formal/Audit.lean` — add `#print axioms <thm>` per theorem.
6. `formal/Oracle.lean` — extend to dispatch on an input "kind" tag so one oracle serves all components: stdin `{"kind":"<C>","args":[...]}` → JSON output computed by `C`'s proved defs. (Refactor Oracle to a per-kind match; keep `calculate_path` working.)
7. `formal/diff/test_<C>_diff.py` — Hypothesis: real Python `C` vs Lean oracle over ≥200 random valid inputs; assert all output fields. Add to gate.sh's pytest invocation (or a single test dir run with `--no-cov`).
8. `formal/diff/mutate.py` — add ≥3 mutations of the Python `C` to the catalogue (each must be KILLED by `C`'s diff test).
9. Run `./formal/gate.sh` → "ALL GATE PARTS PASSED", exit 0.
10. Commit. **Never commit with a `sorry` or a non-standard axiom.**

Verification per task: gate green; `#print axioms` clean (only propext/Classical.choice/Quot.sound); a statement-strength review confirms the `Contracts` entries ascribe the STRONG statements (not weakened). If a proof is genuinely intractable in core, report (add minimal mathlib or scope down with the limitation documented) — never `sorry`.

Float handling (precedent: PredictWin/SkillXpCurve): model exact arithmetic where possible (percentages → integer `(x*pct+50)÷100` for round-half-up; ratios → integer cross-multiplication for ceil-div comparisons). Where a value is inherently a heuristic float (growth_ratio mean, geometric estimate), prove the integer/count/branch structure and DISCLOSE the abstraction in the file header. Order-preserving integer surrogates are acceptable for argmax/comparison-only uses (document).

---

## Ordered components (easiest → hardest) with theorem contracts

Each row: Python source · role theorems (the strong statements to pin in Contracts). The implementer writes the Lean defs to mirror the Python (READ each source first).

### Task 1 — `task_batch` (`ai/task_batch.py:19`)
Roles: clamp bounds. `task_batch_size` model `K(state)`; theorems ∀ inputs:
- `batch_ge_one : 1 ≤ K`
- `batch_le_remaining : taskBranch → K ≤ remaining`
- `batch_le_cap : taskBranch → K ≤ BATCH_CAP`
- `batch_fits : taskBranch → usable ≥ mats → K * mats ≤ usable` (usable = free+held−MIN_FREE)
- `non_task_one : ¬taskBranch → K = 1`
Mutations: invert clamp floor, drop cap, off-by-one on remaining. Oracle emits K.

### Task 2 — `inventory_caps` (`ai/inventory_caps.py:30,82`)
Roles: cap formula + overstock. Theorems:
- `cap_eq_max_of_four : useful_quantity_cap = max(recipe_cap, task_cap, action_cap, equip_cap)` (with recipe_cap floored to SAFETY when demand>0; equipped ⇒ ≥1)
- `equipped_ge_one : equipped code → 1 ≤ cap`
- `overstock_exact : overstock[code] = qty − cap when qty>cap (and qty>0), else absent`
Mutations: drop equipped floor, drop safety floor, overstock off-by-one.

### Task 3 — `predict_win` (`ai/combat.py:57`) — EXACT arithmetic
Roles: closed-form = operational sim + monotonicity + MAX_TURNS soundness, with EXACT documented arithmetic (no abstraction):
- model `roundHalfUp(x*pct) = (x*pct+50)÷100`, `elementDamage`, `expectedHit` as exact integers/rationals; `roundsToKill = ceil(hp*200 / (raw*(200+crit)))` via integer ceil-div.
- `predict_win_eq_sim : closedForm = fightSim` (∀ stat tuples) — refinement
- `predict_win_mono_player : raising player attack never flips win→loss`
- `predict_win_mono_monsterhp : lowering monster HP never flips win→loss`
- `maxturns_sound : rounds_to_kill > MAX_TURNS → ¬win`
Mutations: tiebreak `<`↔`≤`, drop crit term, off-by-one in ceil. (Hardest arithmetic; use lean4:autoprove.)

### Task 4 — `equipment/projection` (`ai/equipment/projection.py:30`)
Roles: additive delta. Theorems:
- `proj_identity : loadout = equipment → projected = current` (per field)
- `proj_additive : projected.field = current.field + Σ_slot (new−old)` (= unconditional all-slot sum; guard sound)
Mutations: drop a slot's delta, sign flip, off-by-one.

### Task 5 — `equipment/scoring` (`ai/equipment/scoring.py:9,23,55`)
Roles: per-slot argmax + no-downgrade (integer score surrogate, order-preserving). Theorems:
- `pickslot_score_optimal : candidates≠∅ → score(result) = maxScore`
- `pickslot_no_downgrade : score(result) ≥ score(current)`
- `pickslot_feasible : result≠none → level-feasible ∧ slot matches`
- `pickslot_ties_keep_current : score(current)=maxScore → result=current`
- `weapon_score_nonneg` (the clamp). Mutations: drop level filter, `>`→`≥` no-downgrade, drop clamp.

### Task 6 — `skill_xp_curve` (`ai/learning/skill_xp_curve.py`) — float estimate abstracted
Roles (integer/count/branch; geometric estimate disclosed-abstracted):
- `required_xp_observed : level ∈ observed → required_xp = observed[level]`; `required_xp_zero : (observed=∅ ∨ no-below) → 0`
- `confidence_in_range : 0 ≤ confNum ≤ confDen`; `is_confident_iff_full : is_confident ↔ confNum=confDen`
- `cycles_zero : tgt≤cur → 0`; `cycles_inf : tgt>cur ∧ xp≤0 → ∞`
- `total_monotone : total(cur,tgt) ≤ total(cur,tgt+1)`
- `growth_default_iff : usesDefault ↔ no consecutive observed pair`
Mutations: confidence off-by-one, cycles guard flip, total non-monotone.

### Task 7 — `recipe_closure` + `raw_material_units` (`ai/recipe_closure.py`) — fixpoint (HARD)
Roles:
- `closure_eq_fixpoint : recipe_closure = least-fixpoint of recipe/drop relation` (sound + complete)
- `raw_units_terminates_cyclic : cyclic recipe → raw_material_units finite (revisit→1)`
- `raw_units_eq_recursive_cost : raw_material_units = Σ qty·units(sub)` (the documented quantity math)
Mutations: drop visited guard, recipe-edge omission, qty factor.

### Task 8 — `task_feasibility` (`ai/task_feasibility.py:30,44`)
Roles:
- `worst_eq_max_unmet : task_requirement.required_level = max unmet crafting-level over the craft closure` (cycle-safe)
- `none_iff_feasible : task_requirement = none ↔ no unmet gap`
- `monster_gate : monster branch gates ↔ monster_level>0 ∧ monster_level>char_level+2`
Mutations: worst→min, drop closure recursion, margin off-by-one.

### Task 9 — `prerequisite_graph` + `combat_capable` (`ai/tiers/prerequisite_graph.py:20,41`)
Roles:
- `prereqs_exact : prerequisites(node) = the data-derived direct edges` (recipe ingredients / gather-leaf / monster-drop-leaf)
- `combat_capable_iff : combat_capable ↔ ∃ monster. predict_win` (abstract predict_win verdict as input; the real refinement is Task 3)
Mutations: wrong edge set, any↔all in combat_capable.

### Task 10 — `objective` (`ai/tiers/objective.py:15,57,86`)
Roles:
- `is_attainable_eq_grounding : is_attainable = least-fixpoint grounding` (cycle/drop-only ⇒ not attainable)
- `best_gear_argmax : from_game_data picks highest-equip-value attainable item per slot`
- `gap_nonneg : all gaps ≥ 0 ∧ 0 ≤ gap ≤ denom`; `is_complete_iff : is_complete ↔ all raw targets met`
Mutations: drop attainability filter, gap sign, is_complete weakening.

### Task 11 — `strategy_traversal` (`ai/tiers/strategy.py:69,91,107,125`) — HARDEST
Roles (abstract prereq graph as node tables):
- `is_reachable_eq_grounding : is_reachable = well-founded grounding fixpoint` (cycles unreachable)
- `closure_size_eq_count : unmet_closure_size = |unmet in prereq closure|, ≥1`
- `actionable_correct : actionable_step result is unmet ∧ all direct prereqs satisfied ∧ producible-if-obtain; none ↔ no actionable node` (De Morgan oracle)
- `root_cost_floored : root_cost ≥ 1`
Mutations: cycle-guard flip, closure off-by-one, actionable predicate weakening.

### Task 12 — `bank_selection` (`ai/bank_selection.py:68`)
Roles:
- `deposits_exact : deposits = inventory items qty>0 ∉ keep`
- `freeze_invariant : deposits ∩ keep = ∅`
- `task_inputs_protected : recipe materials of {crafting_target, items-task code} ⊆ keep`
- `keep_closed : keep is closed under the recipe-material walk`
Mutations: drop task-input protection, drop weapon/hp protection, wrong filter.

### Task 13 — `stuck_detector` (`ai/recovery.py`) — state machine
Roles:
- `detect_precedence : detect honors frozen > osc > noprog`
- `thresholds : noprog ↔ last-4 all <no_plan>; osc ↔ last-8 2-distinct goals; frozen ↔ last-10 some state ≥5`
- `recent_since_window : _recent_since returns records with global index ≥ cutoff, last count` (the index arithmetic)
- `ack_suppression : after ack, the signal's window excludes pre-ack records`
Mutations: precedence swap, threshold off-by-one, recent_since index off-by-one.

---

## Self-review notes
- Coverage: 13 tasks = the 13 unproven components; together with `calculate_path` = 14/14.
- Anti-gaming preserved per component: gate green + Contracts pin strong statements + per-task statement-strength review.
- Exact-arithmetic mandate for predict_win (Task 3) removes the old per-turn-integer abstraction; skill_xp_curve (Task 6) discloses the geometric abstraction.
- Hard proofs (recipe_closure fixpoint #7, strategy reachability #11, objective grounding #10) flagged; use lean4:autoprove, report (don't `sorry`) if blocked.
- Each task wires its diff test into the gate and adds mutations; gate.sh must run all component diff tests with `--no-cov`.
