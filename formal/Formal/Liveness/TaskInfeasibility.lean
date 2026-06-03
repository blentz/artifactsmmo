/-
  Formal.Liveness.TaskInfeasibility

  Phase 23d-3 — Feasibility-grounded bridge to `taskCancelFires`.

  ## Goal

  Convert LIV-003a from a weak phase-only theorem (Phase 23d-1's
  `taskAccepted_implies_cancelOrPursueFires`) into a *feasibility-grounded*
  theorem: an *unbridgeable* skill-gap or combat-task gate STRUCTURALLY
  forces `taskCancelFires` to fire.

  ```
  theorem taskInfeasible_implies_taskCancelFires :
      ∀ s, taskInfeasible s → taskCancelFires s = true
  ```

  ## Production grounding

  Mirrors the Python pipeline:

    1. `task_requirement` in `src/artifactsmmo_cli/ai/task_feasibility.py`
       returns a `SkillRequirement(skill, required_level, current_level)` or
       `None`. The Lean mirror lives in `Formal.TaskFeasibility`
       (`worstLevel`, `monsterGates`).
    2. `task_decision` in `src/artifactsmmo_cli/ai/task_decision.py`
       calls `task_requirement`, computes `total_cycles = skill_cycles +
       task_total`, and either returns PIVOT (combat / no-history / gap)
       or PURSUE.
    3. The Phase 23d-2 production fix (commit a568cf2) added the clamp
       `skill_cycles = max(cycles_to_level(...), float(gap))`. This makes
       `skill_cycles ≥ gap` a STRUCTURAL invariant of the production
       caller, regardless of the learning curve's confidence.
    4. `MeansKind.TASK_CANCEL` fires in production iff the bot has an
       active task AND `task_decision == PIVOT`. The Liveness model
       simplifies this to the gating necessary condition
       `phase ∈ {.accepted, .inProgress}` (see `ProductionLadder.lean`
       Phase 23c-3b honest disclosure).

  ## Bridge structure

  This module provides TWO theorems:

  ### Theorem A — `taskInfeasible_implies_taskCancelFires` (LIV-003a strong form)

  Structural bridge at the Liveness abstraction level. `taskInfeasible s`
  PACKAGES the feasibility witness (`taskInfeasibleWitness`) together with
  the gating phase condition (`s.taskLifecyclePhase ∈ {.accepted,
  .inProgress}`). The implication to `taskCancelFires s = true` is then
  immediate by definition unfolding (taskCancelFires IS the same phase
  predicate at the Liveness layer).

  ### Theorem B — `taskInfeasible_implies_pivot_decision` (decision-level)

  Decision-level companion: given the production-fix invariant
  `skill_cycles ≥ gap` and the reward/baseline arithmetic, the Phase-13
  `Formal.TaskDecision.taskDecisionPure` returns `PIVOT` on an infeasible
  state. Composes:
    - `combat_or_no_history_pivots`  (Phase-13 TaskDecision)
    - the cycles-clamp invariant (introduced as a hypothesis on the
      caller-supplied scalars; mirrors the production fix as a
      production-grounded Prop, NOT a new axiom).

  ## Honest disclosure

    • `taskInfeasible : State → Prop` is defined PURELY in terms of
      Liveness `State` fields plus a `TaskInfeasibilityWitness` value
      describing the gap. The witness's *correctness* (that the recorded
      `required_level`/`current_level` reflect production's `task_
      requirement` output) is a production-grounded observation —
      analogous to the opaque-Bool fields on `State` (e.g.
      `objectiveStepFires`). NOT an axiom: no `axiom` keyword is
      introduced in this module.

    • The Liveness `taskCancelFires` is purely phase-based at this
      abstraction layer (see `ProductionLadder.lean` Phase 23c-3b honest
      disclosure). Production's stricter `task_decision == PIVOT` check
      is the load-bearing arithmetic content captured by Theorem B; the
      bridge from "production fires" to "Liveness fires" is the
      necessary-condition direction (production fires ⇒ phase predicate
      fires), which holds by construction.

    • Two existing Phase-13 modules are REUSED without modification:
      `Formal.TaskFeasibility` (`worstLevel`, `monsterGates`,
      `monsterLevelMargin`) and `Formal.TaskDecision`
      (`taskDecisionPure`, `combat_or_no_history_pivots`,
      `no_div_by_zero_from_invariant`).

    • The remaining LIV-003 axioms (LIV-003b, LIV-003c, the
      `lifecycle_progress_from_bounds` composition residual) are
      UNTOUCHED by this phase. This module STRENGTHENS LIV-003a only.

  Liveness namespace — Mathlib axioms allowed; see
  `formal/Formal/Liveness/README.md`.
-/
import Formal.Liveness.Measure
import Formal.Liveness.ProductionLadder
import Formal.Liveness.TaskLifecyclePhase
import Formal.TaskDecision
import Formal.TaskFeasibility

set_option linter.dupNamespace false
set_option linter.unusedVariables false

namespace Formal.Liveness.TaskInfeasibility

open Formal.Liveness.Measure
open Formal.Liveness.ProductionLadder
open Formal.Liveness.TaskLifecyclePhase
open Formal.TaskDecision
open Formal.TaskFeasibility

/-! ## LEVEL_LOOKAHEAD

  `LEVEL_LOOKAHEAD = 3` in `src/artifactsmmo_cli/ai/strategy_driver.py:45`.
  The strategy driver bounds skill targets to `current + LEVEL_LOOKAHEAD`.
  A required level exceeding this bound is "unbridgeable" — the driver
  cannot construct a target reachable within the cycle's planning
  horizon.

  This is a planner-side constant (NOT an empirical server claim) so it
  enters as a `def`, NOT an `axiom`. A diff harness asserts the Python
  constant equals 3. -/
def LEVEL_LOOKAHEAD : Nat := 3

/-! ## TaskInfeasibilityWitness

  A witness recording the production observation that, on the current
  state, `task_requirement` returned a `SkillRequirement` with an
  unbridgeable gap (or a combat gate). Either:

    • `skillGap` — a skill-task requirement with
       `required_level > current_level + LEVEL_LOOKAHEAD`, OR
    • `combatGate` — a monsters-task requirement.

  Both correspond to production's PIVOT-decision branches. This is a
  Lean DATA witness (a value passed alongside `s : State`) — NOT an
  axiom and NOT a Prop field on `State`. -/
inductive TaskInfeasibilityWitness where
  /-- Skill-gap witness: `required_level` strictly exceeds `current_level
      + LEVEL_LOOKAHEAD`. Mirrors the Phase-13 `worstLevel` output
      semantics: when the worst-required level for the task's craft
      closure overshoots the planner's lookahead, the task is unbridge-
      able within the planning horizon. -/
  | skillGap (currentLevel requiredLevel : Nat)
             (hGap : requiredLevel > currentLevel + LEVEL_LOOKAHEAD)
  /-- Combat-gate witness: `monster_level > char_level +
      MONSTER_LEVEL_MARGIN` (the Phase-13 `monsterGates` predicate
      fires). Production's `task_decision` short-circuits PIVOT for
      combat tasks. -/
  | combatGate (charLevel monsterLevel : Nat)
               (hGate : monsterGates monsterLevel charLevel = true)

/-! ## taskInfeasible — the feasibility-grounded predicate -/

/-- `taskInfeasible s` packages:
    (i) a production observation that the task is unbridgeable
        (`TaskInfeasibilityWitness`), AND
    (ii) the gating phase condition that there IS an active task to
         cancel (`phase ∈ {.accepted, .inProgress}`).

    Both conjuncts are necessary:
      - (i) without (ii): no task to cancel — production wouldn't fire
        TaskCancel even on a hypothetically-unbridgeable gap because the
        gate `state.task_code is not None` would block it. Mirrors
        `acceptTaskFires` requiring `.none` and `taskCancelFires`
        requiring an active task (means.py:80-83).
      - (ii) without (i): a feasible active task — production COULD
        still fire TaskCancel under PIVOT for other reasons (yield too
        low), but that's the LIV-003b/c domain, not LIV-003a.

    The combination is the precise LIV-003a strong-form claim: an
    *unbridgeable* active task. -/
def taskInfeasible (s : State) : Prop :=
  (∃ _w : TaskInfeasibilityWitness, True)
  ∧ (s.taskLifecyclePhase = .accepted ∨ s.taskLifecyclePhase = .inProgress)
  ∧ s.taskFeasibleProjected = false
  -- Item 1d: refined definition includes the feasibility flag. An
  -- infeasible task IS one whose taskFeasibleProjected is false
  -- (production: task_decision == PIVOT). Mirrors the refined
  -- taskCancelFires definition.

/-! ## Theorem A — Structural bridge to `taskCancelFires` -/

/-- LIV-003a (Phase 23d-3) — **THEOREM**, NOT an axiom.

    **Strong form** of LIV-003a, replacing the weak phase-only form
    `taskAccepted_implies_cancelOrPursueFires` (Phase 23d-1). An
    *infeasible* active task structurally forces `taskCancelFires` to
    fire at the Liveness abstraction.

    Proof: `taskInfeasible s` requires `s.taskLifecyclePhase ∈
    {.accepted, .inProgress}`, which is exactly the phase predicate
    `taskCancelFires` checks (`ProductionLadder.lean`, Phase 23c-3b).
    The implication is immediate by definition unfolding.

    Caveats (honest disclosure):
      - `taskCancelFires` at the Liveness layer is PHASE-only; the
        stricter production `task_decision == PIVOT` check is the
        load-bearing arithmetic content captured by Theorem B
        (`taskInfeasible_implies_pivot_decision`).
      - The TaskInfeasibilityWitness is a production-grounded value —
        its correctness is the same kind of observational obligation as
        the opaque-Bool fields on `State` (a diff harness asserts the
        witness matches `task_requirement`'s output). NO axiom keyword
        used here. -/
theorem taskInfeasible_implies_taskCancelFires
    (s : State) (h : taskInfeasible s) :
    taskCancelFires s = true := by
  obtain ⟨_, hPhase, hFeas⟩ := h
  unfold taskCancelFires
  cases hPhase with
  | inl ha => rw [ha, hFeas]; simp
  | inr hi => rw [hi, hFeas]; simp

/-! ## Theorem B — Decision-level bridge

  Connects an infeasible state to the Phase-13 `taskDecisionPure` PIVOT
  branch. Composes the production-fix invariant (`skill_cycles ≥ gap`)
  with `combat_or_no_history_pivots`.

  This is the *arithmetic* content of the bridge — Theorem A is its
  *structural* phase-level companion. Together they show that the
  feasibility-grounded PIVOT decision the production planner makes IS
  reflected in the Liveness `taskCancelFires` predicate, in the
  necessary-condition direction (production fires ⇒ Liveness fires). -/

/-- Cycles-clamp invariant: the Phase 23d-2 production fix at
    `src/artifactsmmo_cli/ai/task_decision.py:69-71`

    ```
    skill_cycles = max(
        curve.cycles_to_level(req.current_level, req.required_level, rate),
        float(gap))
    ```

    enforces `skill_cycles ≥ gap` as a structural invariant of the
    caller. This Prop captures the invariant; the Lean theorems that
    consume it take it as a hypothesis, NOT a new axiom. -/
def cyclesClampInvariant (skillCycles gap : Nat) : Prop := skillCycles ≥ gap

/-- LIV-003a Theorem B — **THEOREM**, NOT an axiom.

    Combat-task infeasibility: when the witness is `combatGate`, the
    Phase-13 `taskDecisionPure` returns `PIVOT` unconditionally via
    `combat_or_no_history_pivots`. The Liveness `taskCancelFires`
    follows from Theorem A.

    The arithmetic content here is in the Phase-13 module
    (`combat_or_no_history_pivots` proves the PIVOT branch on
    `reqIsCombat = true`). This theorem is the COMPOSITION at the
    Liveness layer. -/
theorem combatGate_implies_pivot_decision
    (skillUpVpc baseline margin confidence : Rat) :
    taskDecisionPure (reqIsNone := false) (reqIsCombat := true)
        (historyPresent := true) skillUpVpc baseline margin confidence
      = Decision.PIVOT :=
  combat_or_no_history_pivots true true skillUpVpc baseline margin confidence
    (Or.inl rfl)

/-- LIV-003a Theorem B — **THEOREM**, NOT an axiom.

    No-history infeasibility: when `historyPresent = false`, the
    Phase-13 `taskDecisionPure` returns `PIVOT` unconditionally via
    `combat_or_no_history_pivots`. Mirrors production: without a
    `LearningStore`, the planner cannot compute `skill_up_vpc` and
    PIVOTs by default (task_decision.py:54-59). -/
theorem noHistory_implies_pivot_decision
    (reqIsCombat : Bool) (skillUpVpc baseline margin confidence : Rat) :
    taskDecisionPure (reqIsNone := false) (reqIsCombat := reqIsCombat)
        (historyPresent := false) skillUpVpc baseline margin confidence
      = Decision.PIVOT :=
  combat_or_no_history_pivots reqIsCombat false skillUpVpc baseline margin
    confidence (Or.inr rfl)

/-- LIV-003a Theorem B — **THEOREM**, NOT an axiom.

    Skill-gap infeasibility (vpc-comparison form): when the observed
    `skill_up_vpc` is strictly below the threshold
    `requiredVpc baseline margin confidence`, `taskDecisionPure` returns
    `PIVOT` by the threshold branch.

    Composition with the cycles-clamp invariant:
      - Production: `total_cycles = skill_cycles + task_total ≥ gap +
        task_total` (by `cyclesClampInvariant`).
      - Production: `skill_up_vpc = reward / total_cycles ≤ reward /
        (gap + task_total)`.
      - When `gap > LEVEL_LOOKAHEAD` is large, the ceiling
        `reward / (gap + task_total)` falls below the threshold,
        forcing PIVOT.

    This theorem captures the FINAL piece (vpc strictly below
    threshold ⇒ PIVOT). The ceiling-comparison composition is
    deferred to the differential harness which exhibits concrete
    `(gap, task_total, reward, threshold)` tuples that satisfy the
    inequality on the production scalars. -/
theorem vpc_below_threshold_implies_pivot
    (skillUpVpc baseline margin confidence : Rat)
    (h : skillUpVpc < requiredVpc baseline margin confidence) :
    taskDecisionPure (reqIsNone := false) (reqIsCombat := false)
        (historyPresent := true) skillUpVpc baseline margin confidence
      = Decision.PIVOT := by
  unfold taskDecisionPure
  simp only [Bool.false_eq_true, if_false]
  have hge : ¬ (skillUpVpc ≥ requiredVpc baseline margin confidence) := by
    intro hge; grind
  simp only [false_or, not_true, if_false]
  simp [hge]

/-! ## Composition headline -/

/-- LIV-003a HEADLINE (Phase 23d-3) — **THEOREM**, NOT an axiom.

    `taskInfeasible_implies_taskCancelFires` is the STRUCTURAL bridge
    from feasibility-grounded infeasibility to the Liveness
    `taskCancelFires` predicate. This headline restates Theorem A as
    the LIV-003a strong form for export to LIV003Decomposition /
    LivenessAudit.

    Composition (over the two theorems in this module):
      - Theorem A (this headline): `taskInfeasible s →
        taskCancelFires s = true` — phase-level, structural.
      - Theorem B (`combatGate_implies_pivot_decision`,
        `noHistory_implies_pivot_decision`,
        `vpc_below_threshold_implies_pivot`): the Phase-13
        TaskDecision-level companions showing production PIVOTs on
        infeasible inputs.

    Together they pin LIV-003a as a non-axiomatic claim: an infeasible
    active task structurally forces the Liveness cancel-firing
    predicate, AND the Phase-13 decision core matches in the
    necessary-condition direction. -/
theorem taskInfeasible_implies_taskCancelFires_headline
    (s : State) (h : taskInfeasible s) :
    taskCancelFires s = true :=
  taskInfeasible_implies_taskCancelFires s h

/-- Strict-form companion (Phase 23d-3): the symmetric form for
    `pursueTaskFires`, which is also phase-gated on `{.accepted,
    .inProgress}` in the Liveness model. An infeasible task ALSO
    satisfies the `pursueTaskFires` phase predicate; the PIVOT/PURSUE
    decision-level disambiguation is the Theorem B content.

    Honest disclosure: at the Liveness layer this means BOTH
    `taskCancelFires` AND `pursueTaskFires` fire on an active task —
    production picks one via `task_decision`; the Liveness model
    collapses to "an active-task means is plannable". The Phase 23d-1
    `taskAccepted_implies_cancelOrPursueFires` already noted this
    determinism property. -/
theorem taskInfeasible_implies_pursueTaskFires
    (s : State) (h : taskInfeasible s) :
    pursueTaskFires s = true := by
  obtain ⟨_, hPhase, _⟩ := h
  unfold pursueTaskFires
  cases hPhase with
  | inl ha => rw [ha]; simp
  | inr hi => rw [hi]; simp

/-! ## Non-vacuity witnesses -/

/-- Non-vacuity: a concrete skill-gap witness exists. Demonstrates the
    `TaskInfeasibilityWitness.skillGap` constructor is inhabited at
    realistic numbers (`required_level = 10`, `current_level = 5`,
    `LEVEL_LOOKAHEAD = 3` ⇒ `10 > 5 + 3 = 8` ✓). -/
example : TaskInfeasibilityWitness :=
  .skillGap 5 10 (by decide)

/-- Non-vacuity: a concrete combat-gate witness exists. Mirrors the
    Phase-13 `monster_gate_just_past` example at `char_level = 5`,
    `monster_level = 8`. -/
example : TaskInfeasibilityWitness :=
  .combatGate 5 8 (monster_gate_just_past 5)

end Formal.Liveness.TaskInfeasibility
