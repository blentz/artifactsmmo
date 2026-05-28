# Formal verification (Lean 4)

Kernel-checked proofs that the AI's pure logic is correct **for all valid inputs**,
plus a gate that mechanically rejects the ways a proof can be faked or made vacuous.

## Soundness chain

> Python function correct ⇐ (Python ≡ Lean def, by the differential test)
> ∧ (Lean def proved correct ∀ inputs, by the kernel).

The only un-proved link — "is the Lean def a faithful model of the Python?" — is checked
**mechanically and randomly** by the Hypothesis differential test, not by assertion.

## The gate (`./formal/gate.sh`)

1. **kernel build** — `lake build` re-checks every proof; an unfinished proof fails.
2. **axiom lint** (`gate/check_axioms.sh`) — `#print axioms` on each role theorem must list
   only `propext, Classical.choice, Quot.sound`; `sorryAx`/custom axioms/`native_decide`
   (`ofReduceBool`) fail.
3. **role manifest** (`Formal/Manifest.lean`) — compiles only if each required theorem exists.
4. **statement contracts** (`Formal/Contracts.lean`) — each role theorem is ascribed its exact
   strong statement; a WEAKENED theorem (same name) fails to elaborate → build RED. This is the
   mechanized theorem-statement review.
5. **differential + mutation** — Hypothesis checks Python ≡ Lean over random inputs; the mutation
   runner perturbs the Python and fails if any mutant survives (spec too weak / coverage gap).

What the gate is demonstrated to reject (see the acceptance commit): a `sorry`, `native_decide`,
a custom axiom, a missing/renamed role theorem, a WEAKENED theorem statement, and a surviving mutant.

## Run locally

```bash
curl -sSf https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh | sh -s -- -y
uv sync --dev
./formal/gate.sh
```

## Coverage

**18/18 AI components proven** (kernel-checked ∀ inputs, sorry-free, axioms = {propext, Classical.choice, Quot.sound}). Each row has a Lean def + role theorems + a `Contracts.lean` statement-pin + a real-Python differential test + mutation coverage. The first 14 are pure-logic components; the last 4 are decision-logic cores extracted from the impure AI orchestration (Phase 1, 2026-05-27).

| Component | Lean | Roles proved |
|---|---|---|
| `calculate_path` (`utils/pathfinding.py:44`) | `CalculatePath.lean` | validity, optimality (lower-bound + achieved), cost (length≤Manhattan, Chebyshev≤Manhattan), estimated_time |
| `task_batch_size` (`ai/task_batch.py:19`) | `TaskBatch.lean` | clamp bounds: ≥1, ≤remaining, ≤cap, fits available space |
| `useful_quantity_cap`/`overstocked_items` (`ai/inventory_caps.py`) | `InventoryCaps.lean` | cap = max-of-four + equipped floor; overstock exact |
| `predict_win` (`ai/combat.py:57`) | `PredictWin.lean` | **exact** documented arithmetic; closed-form = operational fight-sim; monotonicity; MAX_TURNS soundness |
| `project_loadout_stats` (`ai/equipment/projection.py`) | `LoadoutProjection.lean` | additive delta; identity; guarded sum = unconditional sum |
| `pick_loadout` (`ai/equipment/scoring.py`) | `EquipmentScoring.lean` | per-slot score-optimal, no-downgrade, ties-keep-current, feasible, clamp≥0 |
| `SkillXpCurve` (`ai/learning/skill_xp_curve.py`) | `SkillXpCurve.lean` | required_xp branches, confidence∈[0,1], is_confident iff full, cycles guards, total monotone, default-ratio condition (geometric float estimate abstracted) |
| `recipe_closure`/`raw_material_units` (`ai/recipe_closure.py`) | `RecipeClosure.lean` | closure = least fixpoint (sound+complete); cyclic termination; quantity cost |
| `task_requirement` (`ai/task_feasibility.py`) | `TaskFeasibility.lean` | worst = max unmet over closure; none-iff-feasible; monster gate threshold |
| `prerequisites`/`combat_capable` (`ai/tiers/prerequisite_graph.py`) | `PrerequisiteGraph.lean` | exact direct edges; combat_capable = ∃ beatable (De Morgan) |
| `is_attainable`/`gap`/gear (`ai/tiers/objective.py`) | `Objective.lean` | is_attainable = grounding fixpoint; best-attainable gear argmax; gap bounds; is_complete iff targets met |
| `is_reachable`/`actionable_step`/`unmet_closure_size`/`root_cost` (`ai/tiers/strategy.py`) | `StrategyTraversal.lean` | reachable = grounding fixpoint; closure count; actionable correctness (none-iff, De Morgan); root_cost floored |
| `select_bank_deposits` (`ai/bank_selection.py`) | `BankSelection.lean` | deposits exact; **freeze invariant** (deposits ∩ keep = ∅); task inputs protected; keep-closure |
| `StuckDetector` (`ai/recovery.py`) | `StuckDetector.lean` | detect precedence; thresholds; `_recent_since` window index arithmetic; ack suppression |
| `clamp_into_band` (`ai/priority_band.py`) | `PriorityBand.lean` | result ∈ [floor, ceiling]; ceiling < survival floor ⇒ result < floor (a learned bonus can never reorder a discretionary goal above a survival goal) |
| `owned_count` (`ai/tiers/owned_count.py`) | `OwnedCount.lean` | summation contract; equipped ⇒ count ≥ 1 (item owned only by wearing it still satisfies ObtainItem); monotone per store |
| `best_by_value`/keys/argmax (`ai/goals/upgrade_selection.py`) | `UpgradeSelection.lean` | best_by_value never downgrades (tie→inventory); key comparators trichotomous/antisymmetric/transitive; argmax dominates + is a member (first-wins on same-code ties) |
| `scalar_yield`/coin-inversion (`ai/learning/scalar_core.py`) | `Scalarizer.lean` | **over ℚ**: monotone non-decreasing in char_xp/skill_xp/gold/coins; relevant weight (2) ≥ baseline (1/5); coins_spent = received − delta inverts exactly |
| `GOAPPlanner.plan` A* heuristic (`ai/planner.py:81,112`) | `PlannerAdmissibility.lean` | **OPTIMALITY (post-fix)**: conditional intent (`fScore_eq_g_at_goal_of_admissible`) + general A* optimality (`firstSatisfied_least_cost_of_admissible`) + `zero_h_admissible` and the RestoreHP instance showing the planner's now-zero h is admissible and the cheap plan (cost 7) is the one popped first, not [Rest] (cost 10). See Phase-2 findings. |

The float-heavy parts modeled exactly where reducible (predict_win); the inherently-heuristic geometric estimate in `SkillXpCurve` is abstracted and disclosed in that file's header. Components depending on others' verdicts (e.g. `combat_capable` on `predict_win`) abstract the dependency as an input — the dependency itself is proven in its own module.

### Phase 1 decision-logic findings (2026-05-27)

The four decision-logic targets were chosen as *suspected* bugs. Outcomes:

- **`learned_priority_bonus` — real defect, removed.** An unbounded additive priority bonus that could push a discretionary goal above the survival floor (base 45 + bonus 50 = 95 ≥ 70). It was also dead (no callers) and a duplicate of the live `GrindCharacterXPGoal` band-clamp. Deleted; the sound band-clamp was extracted to `clamp_into_band` and proved safe by construction.
- **`owned_count`, `best_by_value`/argmax, `scalar_yield` — correct code; no behavioral bug.**

What the proofs *did* catch in this phase was **dishonest formalization** — proofs that compiled green but told a false story about correct code (the failure mode this gate exists to prevent). Each was corrected so the proof states the truth:
- `owned_count`'s first proof asserted a *false* disjointness invariant ("equipped items never in inventory") and mislabeled correct spare-counting as a "double-count." Reworked to the true server-slot mechanism with unconditional summation + the load-bearing equipped⇒≥1 property.
- `upgrade_selection`'s first proof claimed the sort key is a tie-free strict total order (false — multi-slot items tie), with a `unique=True`-rigged differential test hiding it, plus a `select_committed` proof-theater call. Corrected to first-wins determinism, the tie case now exercised, the theater removed.
- `scalar_yield`'s first proof modeled an `Int` ×1000 surrogate and tested only integers, while the real domain is fractional. Remodeled over `ℚ` (Lean core `Rat`) with exact rational weights; the differential test now feeds exact `Fraction`s.

These were caught by a mandatory adversarial review reading each proof against reachable states — `lake build` + axiom lint + mutation green is *necessary but not sufficient* for an honest proof.

### Phase 2 finding: planner A* heuristic bug — FOUND, FIXED, PROVED OPTIMAL (2026-05-27/28)

- **`GOAPPlanner.plan` — real defect, fixed.** The planner was forward A* with `f = g + h`, where `g` was summed `action.cost` (seconds) and `h = goal.value(state)` was the goal's *urgency* (e.g. `RestoreHPGoal.value = (1 − hp_percent)·100`, restore_hp.py:33). The planner.py:99 docstring claimed *"A* pops nodes in f-score order; first satisfied node is optimal"* — the textbook A* result, which requires `h` to be **admissible** (`h ≤ true remaining cost`) and, because the planner closes nodes on pop without re-opening, **consistent**. The urgency heuristic was neither: at HP 50/100 it returned 50 while the true remaining cost was ≈2 seconds (one consumable) — dimensionally mismatched and grossly overestimating. On the RestoreHP instance the planner returned `[Rest]` (cost 10) instead of the optimal `[Move, UseConsumable]` (cost 5 + 2 = 7).

  **Fix shipped.** `planner.py` now sets `h = 0.0` at both heuristic call sites (line 81, line 112). Every `action.cost(...)` in the codebase returns a non-negative float (verified across `rest.py`, `movement.py`, `consumable.py`, `combat.py`, `gathering.py`, `crafting.py`, `equip.py`, `claim.py`, `withdraw_*`, `deposit_*`, `npc*`, `task_*`, `transition.py`, `delete.py`, etc.), so the search is now Dijkstra / uniform-cost. `h ≡ 0` is trivially admissible and consistent w.r.t. any `trueRemaining`, so the textbook A* optimality result applies absolutely; the planner.py:99 comment was rewritten to state the Dijkstra-optimality contract truthfully and cite the Lean proof.

  **Proved.** `PlannerAdmissibility.lean` carries `fScore_eq_g_at_goal_of_admissible` (admissible h ⇒ f = g at goal), `firstSatisfied_least_cost_of_admissible` (the general A* optimality conditional), `zero_h_admissible` (h ≡ 0 is admissible), and the now-affirmative RestoreHP instance: `RHP_h_admissible`, `RHP_optimal_popped_before_rest` (f = 7 < 10), and `RHP_first_satisfied_is_optimal` (7 ≤ 10) via the general lemma. `formal/diff/test_planner_admissibility_diff.py` runs the same instance against the real Python planner and asserts it returns the optimal plan; the mutation gate kills three planner mutants (re-introduce urgency, negate g, skip is_applicable), each of which causes the planner to return a non-optimal plan.

  **Tradeoff disclosed.** With `h = 0` the search loses heuristic guidance and may expand more nodes on deep, naturally-multi-step plans (gather→craft→equip chains). The 90s budget covers known-deep recipes today, but per-goal admissible heuristics (each in *seconds* and ≤ true remaining cost) are a future optimization that would prune expansion while keeping the same proved optimality contract. Deferred to a later phase.

Design docs: `docs/superpowers/specs/2026-05-26-lean-formal-verification-design.md` (gate architecture),
`docs/superpowers/specs/2026-05-27-lean-decision-logic-design.md` (decision-logic expansion). The retired
TLA+/PlusPy predecessor: `docs/postmortems/2026-05-26-tlaplus-pluspy-formal-verification.md`.
