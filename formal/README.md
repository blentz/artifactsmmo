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

**28/28 AI components proven** (kernel-checked ∀ inputs, sorry-free, axioms = {propext, Classical.choice, Quot.sound}). Each row has a Lean def + role theorems + a `Contracts.lean` statement-pin + a real-Python differential test + mutation coverage. The first 14 are pure-logic components; the next 5 are decision-logic cores extracted from the impure AI orchestration (Phase 1, 2026-05-27); 5 more extend into orchestration / planning / strategy (Phase 2, 2026-05-28) and include one real-bug fix (the planner heuristic); the last 4 push into actions / learning store / equipment (Phase 3, 2026-05-28) and surface two more real-bug fixes (a missing JSON-decode guard in the learning store, and phantom item duplication in multi-slot loadout selection).

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
| `select_pure` (`ai/arbiter_select.py`, extracted from `StrategyArbiter.select`) | `ArbiterSelect.lean` | **sticky-safety**: head-guard plannable ⇒ guard returned regardless of `committed` (sticky cannot keep a means ahead of a firing plannable guard); sticky-idempotence (no guards ∧ committed plans ⇒ committed kept); no-commit ⇒ walk in band order. Well-formedness: guard ids disjoint from means ids (Python `repr` collision-free across distinct Goal classes). |
| `task_decision_pure` (`ai/task_decision_core.py`) | `TaskDecision.lean` | **ℚ model**: combat/no-history ⇒ PIVOT (safety short-circuit); req=None ⇒ PURSUE; no-div-by-zero from cross-file invariant (task_requirement=None when task_total=0); requiredVpc antitone in confidence; PURSUE preserved under higher confidence or higher skill_up_vpc |
| `weighted_remaining_pure` / `is_complete_pure` (`ai/tiers/objective_completion.py`) | `WeightedRemaining.lean` | **ℚ model**: nonneg under non-neg inputs; complete ⇒ remaining=0 (unconditional); zero ⇔ complete under STRICT POSITIVITY of every weight (production equivalence); **bug-teeth witness**: a zero weight + that category's fraction > 0 makes remaining=0 ∧ ¬complete (latent defect a future zero-weight personality would expose); monotone per fraction |
| `low_yield_fires_pure` (`ai/learning/low_yield_boundary.py`) | `LowYieldCancel.lean` | **ℚ model**: no-task / no-samples ⇒ no-fire; margin monotone in alt; **zero-fast-path semantics pinned**: current=0 ∧ alt>0 ∧ samples>0 ⇒ fires regardless of confidence (intentional — FarmItems char-XP is structurally 0/cycle); under current>0, fires ⇒ alt ≥ 1.5·current ∧ confidence ≥ 0.5 |
| `balancing` + `learned_blend` (`ai/tiers/strategy_blend.py`) | `StrategyBlend.lean` | balancing (Int×4 model): band bounds [0.5, 2.0]; threshold identity (gap=2 ⇒ result=1); leader=current ⇒ 0.5 (clamp); monotone non-decreasing. learned_blend (ℚ model): w=0 identity (warm-up); w=1 endpoint; **convex bound** min(v,n) ≤ blend ≤ max(v,n) over w ∈ [0,1] (anti-Phase-1 unbounded-bonus property); monotone in normalized and value |
| `decide_key` + dispatcher (`ai/tiers/decide_key.py`, `ai/strategy_driver.py`) | `DecideKey.lean` | strict total order on `(-final, effort, repr)` (trichotomy + antisymmetry + transitivity + eq-imp-field); GuardKind (6/6) and MeansKind (10/10) dispatcher EXHAUSTIVENESS via total `match` (no fall-through possible — kernel enforces) |
| `cycles_for_progress_pure` (`ai/learning/cycles_for_progress_core.py`) | `CyclesForProgress.lean` | **ℚ model**: warm-up gate; result `None ∨ > 0` (the `or 15.0` fallback is sound); intentional dual signal — strict-increase intervals and `cycles_to_satisfy` events measure orthogonal quantities (inter-progress-tick spacing vs goal duration), so a single satisfying cycle contributes to both medians by design |
| `gather_is_applicable_pure` / `gather_apply_pure` (`ai/actions/gather_apply_core.py`) | `GatherApply.lean` | `is_applicable_imp_free_ge`; `apply_inventory_safe` (1≤k ∧ is_applicable ⇒ used'≤cap); `chain_safe` (n-step chain stays ≤ cap when n ≤ free) — the planner's per-pop `is_applicable` re-check is the load-bearing invariant |
| every Action.cost (audit + history-modulated cores in `ai/actions/cost_core.py`) | `ActionCostNonneg.lean` | 5 structural cost cores (constant / distance / qty / instance / history) + 26 per-Action `_nonneg` theorems + headline `all_actions_cost_nonneg` — seals the Phase-2 Dijkstra-optimality precondition end-to-end; writer audit for `actual_cooldown_seconds` (only `0.0` literals or `max(0.0, …)`) is the load-bearing assumption |
| `is_realizable` / claimed-codes selector (`ai/equipment/realizable_loadout.py`, `ai/equipment/scoring.py::pick_loadout`) | `RealizableLoadout.lean` | `isRealizable_iff_demand_le_ownership`; `apply_cur_ge_1` (under realizability, every `OptimizeLoadoutAction.apply` decrement has cur ≥ 1); regression pins for the fix `{ring1:B, ring2:A}` and the bug `{ring1:B, ring2:B}` (proven NOT realizable). See Phase-3 finding below. |

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

### Phase 2 other outcomes (2026-05-27/28)

The remaining Phase-2 targets were chosen as *suspected* but turned up correct, with three modeling notes worth recording:

- **`is_reachable ⇒ actionable_step ≠ none`** — a live `assert step is not None` (`strategy.py decide`) was suspected to crash because the two functions use different cycle-trackers (`path` vs shared `visited`). Proved safe: an actionable node has no unmet prereqs to descend, so it returns on first reach; the `visited` set can never block it. The prior `StrategyTraversal.lean` had unified the two trackers and never proved this bridge — `StrategyTraversal.reachable_implies_actionable` + `grounded_unmet_has_actionable` close the gap. The actStep model uses a per-path tracker (not the shared `visited`); model↔Python faithfulness is established by the differential (200+ divergence-prone DAGs) + an independent 200k-graph brute force. No bug.
- **`StrategyArbiter.select` band-merge + sticky-commitment** — proved the head-guard plannable wins over a committed means (sticky cannot keep a means ahead of a firing plannable guard) under id-disjointness, which is a genuine real-system invariant (guard `repr`s and means `repr`s never collide because they come from distinct Goal classes). No bug.
- **`task_decision`** — the cross-file no-div-by-zero invariant (`task_requirement` returns None when `task_total = 0`) holds; combat / no-history short-circuit and monotonicity in confidence and skill_up_vpc all proven. The brief originally omitted a `req=None → PURSUE` branch — implementer caught it during extraction. No bug.
- **`weighted_remaining ⇔ is_complete`** — the equivalence holds under STRICT POSITIVITY of every personality weight (true today: `BalancedPersonality = (1, 1, 1)`); a `bug_teeth_witness` pins a concrete (zero-weight, incomplete) counterexample documenting that a future zero-weight personality would break the equivalence. The strict-positivity contract is documented in `Personality.category_weight` and pinned by the Lean witness. No runtime assert added (behavioral; deferred). Latent, not live.
- **`low_yield_cancel`** — the zero-fast-path (current=0 + alt>0 + 1 sample ⇒ fires regardless of confidence) was suspected to be a flapping defect, but it is genuine design: FarmItems char-XP is paid at `CompleteTask`, not per-cycle, so `current_xp = 0` is the steady-state of an items-task farm, not a noise floor — switching to any positive-XP alternative is correct on a single observation. Documented + pinned. No bug.
- **`balancing` / `learned_blend` / `decide_key`** — regression-locks: band bounds + clamp identity for `balancing`; convex bound and warm-up identity for `learned_blend`; strict total order on the sort key + dispatcher exhaustiveness for `decide` / `map_guard` / `map_means`. No bugs.

**Dishonesty caught and corrected this phase:**
- A first version of the `learned_blend` differential test INLINED the formula instead of calling the live function — three mutations survived. Test fixed; mutants now killed. Additionally, the production `learned_blend` was rewritten `1.0 → 1` so Fraction inputs from the differential test remain exact (no float coercion). Behavior identical for the float callers.
- The Phase-2 recon mis-identified `Goal.priority()` as dead — `player.py:328` calls it in the `verbose` log branch. The deletion target was withdrawn (correctly).
- The gate's axiom-checker grep didn't handle Lean's multi-line `#print axioms` wrapping (long theorem names triggered it). Fixed: pre-process by folding continuation lines so the bracket `[propext, Classical.choice, Quot.sound]` is one token.

### Phase 3 findings (2026-05-28)

Extended the sweep into actions / learning store / equipment. Outcomes:

- **`LearningStore.skill_xp_per_cycle` unguarded `json.loads` — real defect, fixed.** The function called `json.loads(row.delta_skill_xp_json)` inside a `try/except SQLAlchemyError` block, so a malformed JSON row would crash the running average. Mirrored the sibling `projections._parse_skill_xp` guard via a module-level `_parse_skill_xp_value(raw, skill)` helper that tolerates `JSONDecodeError`, `TypeError`, `ValueError`, and non-dict payloads. Test added (`TestSkillXpPerCycle.test_malformed_json_row_is_skipped`).
- **`pick_loadout` × multi-slot phantom duplication — real defect, fixed.** `pick_loadout` scored each equipment slot independently. For multi-slot item types (`ring → [ring1, ring2]`, `artifact → [3 slots]`, `utility → [2 slots]`), the same physical item could be selected for every slot. `OptimizeLoadoutAction.apply` then silently popped the missing inventory key via `pop(code, None)`, materializing an impossible state that the planner accepted. On execute, the API rejected the second equip with "already equipped" and the goal stalled. Reachable from normal API state (own one upgraded ring, currently equipped {ring1: A, ring2: B}, monster vs which B dominates → `pick_loadout = {ring1: B, ring2: B}`). Verified against the real Python. Fix at source: thread a `claimed_codes: dict[str, int]` accumulator across slot iteration, scoring a code C as feasible iff `inventory[C] + |slots equipped to C| - claimed_codes[C] ≥ 1`; `apply` is now two-pass (unequip-all then equip-all) with an asserted `cur ≥ 1` decrement. Lean `RealizableLoadout.lean` proves the realizability invariant of the new selector, with both the fix and the bug-state pinned as regression contracts.

- **`cycles_for_progress`, `GatherAction.apply`, `task_progress` overshoot, every `Action.cost ≥ 0` — proved correct, no bugs.** The recon flagged each as suspect; each held up. `cycles_for_progress`'s two append loops measure orthogonal events (intentional dual signal — verdict (b)). `GatherAction.apply`'s recon-suspected inventory-overrun does not occur because `planner.py:122` re-checks `is_applicable` on every node expansion before applying. `FightAction.apply`'s `task_progress + 1` overshoot is benign — every production downstream check uses `≥`/`<`, never `==` — so the overshoot is tolerated (verdict (c)). And the headline `all_actions_cost_nonneg` theorem now seals the Phase-2 Dijkstra-optimality precondition, with a writer audit confirming `actual_cooldown_seconds` is non-negative at every call site (`player.py:312`, `:362`, `:1222`).

**Process bugs also caught this phase:** the main checkout had a self-loop symlink (`artifactsmmo-api-client → artifactsmmo-api-client`) committed by accident in a Phase-2 `git add -A` slip; every worktree created since had a broken venv. Removed from main; `.gitignore` tightened to match bare names (the trailing-slash form ignored only directories). And a Hypothesis `DeadlineExceeded` perf-flake under heavy gate load was fixed by adding `deadline=None` to the formal profile (the differentials are deterministic equality checks; the deadline wasn't catching real bugs). And the equipment-scoring mutation anchor went stale across the multi-slot refactor — updated to match the new `improves` flag shape.

Design docs: `docs/superpowers/specs/2026-05-26-lean-formal-verification-design.md` (gate architecture),
`docs/superpowers/specs/2026-05-27-lean-decision-logic-design.md` (decision-logic expansion). The retired
TLA+/PlusPy predecessor: `docs/postmortems/2026-05-26-tlaplus-pluspy-formal-verification.md`.
