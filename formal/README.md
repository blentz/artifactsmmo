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
| `GOAPPlanner.plan` A* heuristic (`ai/planner.py:81,112`) | `PlannerAdmissibility.lean` | **REFUTATION** of the `planner.py:99` "first satisfied node is optimal" claim: conditional intent (admissible h ⇒ f=g at goal) + concrete counterexample proving `goal.value` is NOT admissible and the returned plan is strictly costlier than optimal (cost 10 vs 7 with real action costs). See Phase-2 findings. |

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

### Phase 2 finding: planner A* optimality claim is FALSE (2026-05-27)

- **`GOAPPlanner.plan` — real defect, BLOCKED-FOR-DECISION.** The planner is forward A* with `f = g + h`, where `g` is summed `action.cost` (seconds) and `h = goal.value(state)` is the goal's *urgency* (planner.py:81,112). On popping the first goal-satisfying node it returns that plan, with the comment (planner.py:99) *"A* pops nodes in f-score order; first satisfied node is optimal."* That is the textbook A* result, which requires `h` to be **admissible** (`h ≤ true remaining cost`); because the planner closes nodes on pop and never reopens (the `visited` set), it further needs **consistency**. The urgency heuristic is neither: `RestoreHPGoal.value = (1 − hp_percent)·100` (restore_hp.py:33) returns 50 at HP 50/100 while the true remaining cost is ≈2 (one consumable) — a gross overestimate, and dimensionally mismatched (urgency vs seconds). `PlannerAdmissibility.lean` proves the conditional intent theorem (`fScore_eq_g_at_goal_of_admissible`) and a concrete counterexample (`CE_*`): the real Python planner, on a faithful RestoreHP instance, returns `[Rest]` (cost 10) instead of the optimal `[Move, UseConsumable]` (cost 5+2=7 with real `MoveAction`/`UseConsumable` costs from `movement.py:58`/`consumable.py`) — verified by `formal/diff/test_planner_admissibility_diff.py`. The instance tile-gates the consumable to force a multi-step plan; on naturally-multi-step goals (gather→craft→equip chains) the same inadmissibility produces suboptimal plans without contrivance. Severity: efficiency (suboptimal plans / wasted cooldown), not crash. **Fix options (behavioral decision, not made here):** (a) use a zero/admissible heuristic so the search is Dijkstra-optimal — the mutation `g + h → g + 0` confirms this returns the optimal plan; or (b) weaken the planner.py:99 docstring from "optimal" to "satisficing" and drop the optimality claim.

Design docs: `docs/superpowers/specs/2026-05-26-lean-formal-verification-design.md` (gate architecture),
`docs/superpowers/specs/2026-05-27-lean-decision-logic-design.md` (decision-logic expansion). The retired
TLA+/PlusPy predecessor: `docs/postmortems/2026-05-26-tlaplus-pluspy-formal-verification.md`.
