# PLAN — O5.4 perception binding (objectiveStepIsFight → production)

_Worktree `liveness-phase23c`. formal-development methodology. Zero-vacuousness hard constraint ([[feedback_zero_vacuousness]])._

## Goal

Bind the opaque Lean liveness Bool `objectiveStepIsFight` (Measure.lean State field)
to the production StrategyArbiter computation via the differential + mutation gate,
so the level-50 capstone's `CombatPersistent`/`hfair` hypothesis is grounded in real
bot behaviour rather than asserted. This is the genuine confidence gain identified in
[[PLAN_reach_fifty]] (the perception wall `Settled_unreachable_without_perception`).

## Proof boundary (Phase-0 decision)

The full `objective_step_goal` (strategy_driver.py:523-753) is NOT a faithful Lean
target — 230 lines entangled with game_data, recipe-closure walks, skill gates, GOAP
depth heuristics. Modeling it whole = modeling the recipe subsystem (wrong boundary,
surrogate risk).

`objectiveStepIsFight` means precisely: *the committed objective is a combat/
char-leveling goal whose plan leads with Fight.* That is exactly the
`ReachCharLevel → GrindCharacterXPGoal → FightAction` slice (strategy_driver.py:719-752).
The routing predicate for that slice is pure and decidable over ~8 scalars:

```
objective_step_is_fight_pure(
    is_reach_char_level: bool, target: int, level: int,
    has_combat_monster: bool,
    task_type: str|None, task_code: str|None, task_total: int, task_progress: int
) -> bool:
    if not is_reach_char_level:   return False
    if not has_combat_monster:    return False
    bootstrap_gap = target - level
    items_active = (task_type == "items" and bool(task_code)
                    and task_total > 0 and task_progress < task_total)
    if bootstrap_gap > 4 and items_active: return False   # long-haul defer
    return True
```

This is the honest slice (not a surrogate): the other `objective_step_goal` branches
(gear/skill/currency goals) are by definition NOT combat-led, so they yield
`objectiveStepIsFight = false`. The GrindCharacterXPGoal → Fight-led property is
structural (grind_character_xp.py relevant_actions ⊆ {Fight(target), recovery, equip}).

## Phases (per component, formal-development gate)

1. **Python pure core (TDD)** — extract `objective_step_is_fight_pure` into a
   `*_core.py`; refactor the ReachCharLevel branch of `objective_step_goal` to call
   it (behaviour-preserving; characterization tests first). `tests/` coverage.
2. **Lean computable def** — `objectiveStepIsFightRoute` in
   `formal/Formal/ObjectiveStepFight.lean` mirroring the predicate (constructive, no
   noncomputable).
3. **Role theorems** — e.g. `route_true_iff` (exact characterization),
   `route_false_when_no_monster`, `route_total` (decidable ∀ inputs). Kernel-checked,
   no sorry/native_decide/custom axioms.
4. **Oracle** — `runObjectiveStepIsFight` in Oracle.lean (JSON args → Bool).
5. **Differential** — `formal/diff/test_objective_step_is_fight_diff.py`: Hypothesis
   feeds random valid inputs to BOTH `objective_step_is_fight_pure` and the oracle;
   assert agreement. Template: test_low_yield_cancel_diff.py / test_arbiter_select_diff.py.
6. **Contract-pin + Manifest** — Contracts.lean exact-statement pin; Manifest.lean #check.
7. **Mutation** — mutate.py must kill perturbations of the pure core via the
   differential check.
8. **Adversarial review** (Phase 4) — confirm the binding tests the LIVE function, the
   slice scoping is honest, no rigged inputs.

## Follow-on (separate component)
- `objectiveStepFires` (the broader "objective tier yields a plannable step") — only
  the combat slice is liveness-relevant; bind later if needed.
- Connect the bound route def to the liveness State Bool (a Lean lemma relating
  `objectiveStepIsFight` field to `objectiveStepIsFightRoute` of the modeled inputs).

## Status
- [x] 1 Python pure core + TDD (objective_step_fight_core.py; 9 tests; wired into live objective_step_goal)
- [x] 2 Lean def (Formal/ObjectiveStepFight.lean::objectiveStepIsFightPure, core-only)
- [x] 3 role theorems (fires_iff characterization + 4 safety/liveness roles; axioms ⊆ {propext, Quot.sound}; 4 non-vacuity witnesses)
- [x] 4 oracle (runObjectiveStepIsFight in Oracle.lean; "objective_step_is_fight" dispatch; oracle exe builds)
- [x] 5 differential (formal/diff/test_objective_step_is_fight_diff.py; 250-example property + gap=4/5 boundary; live Python ↔ proved-def oracle agree)
- [x] 6 contract + manifest (Manifest.lean roster + Contracts.lean exact-statement pins; root import; orphan-free)
- [x] 7 mutation (6 mutants in mutate.py, all killed; task_total>0 deliberately NOT mutated — implied by progress<total, would survive)
- [x] 8 adversarial review (tests live fn; domain unrigged; witnesses concrete; not a surrogate)

## Bootstrap-horizon grounding (DONE 2026-06-29)

`bootstrap_step_always_fires` (ObjectiveStepFight.lean) discharges the `gap ≤ 4`
hypothesis of `bootstrap_always_fires` against the live constant: production sets the
bootstrap target to `level + _CHAR_LEVEL_BOOTSTRAP_HORIZON` and the horizon is `2 ≤ 4`,
so a bootstrap `ReachCharLevel` step is UNCONDITIONALLY Fight-led when a combat monster
exists — regardless of any active items task. The horizon constant is differentially
bound (oracle `bootstrap_char_horizon` == `_CHAR_LEVEL_BOOTSTRAP_HORIZON`) and
mutation-guarded (drift 2→5 killed). This is a concrete `CombatPersistent` ingredient:
while underleveled, the bootstrap mechanism keeps the planner fighting.

## Honest residual (follow-on, separate component)
The binding proves PRODUCTION's Fight-routing predicate == the proved Lean def
(`objectiveStepIsFightPure`). It does NOT yet prove the liveness State field
`objectiveStepIsFight` EQUALS that def on derived inputs — the State-field↔predicate
wiring (a Lean lemma in the liveness namespace + its own differential row) remains.
The capstone (`FightFairness`/`CombatPersistent`) still consumes the opaque field;
this phase grounded the production computation that SETS it. Likewise
`objectiveStepFires` (the broader plannable-step predicate) is a separate future
binding.
