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

**14/14 pure-logic AI components proven** (kernel-checked ∀ inputs, sorry-free, axioms = {propext, Classical.choice, Quot.sound}). Each row has a Lean def + role theorems + a `Contracts.lean` statement-pin + a real-Python differential test + mutation coverage.

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

The float-heavy parts modeled exactly where reducible (predict_win); the inherently-heuristic geometric estimate in `SkillXpCurve` is abstracted and disclosed in that file's header. Components depending on others' verdicts (e.g. `combat_capable` on `predict_win`) abstract the dependency as an input — the dependency itself is proven in its own module.

Design doc: `docs/superpowers/specs/2026-05-26-lean-formal-verification-design.md`. The retired
TLA+/PlusPy predecessor: `docs/postmortems/2026-05-26-tlaplus-pluspy-formal-verification.md`.
