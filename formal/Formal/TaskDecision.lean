/-
Formal model of the pure decision core extracted from
`src/artifactsmmo_cli/ai/task_decision.py` into
`src/artifactsmmo_cli/ai/task_decision_core.py` (`task_decision_pure`).

PYTHON DECISION (`task_decision_pure`):

  if req_is_none:                              return PURSUE
  if req_is_combat or not history_present:     return PIVOT
  required = baseline_vpc * (1 + margin * (1 - confidence))
  return PURSUE if skill_up_vpc ≥ required else PIVOT

EXACT-RATIONAL MODEL (`Rat`, Lean core — no mathlib). The Python inputs are
`float`s with INHERENT FRACTIONAL meaning:

  * `skill_up_vpc = reward / total_cycles` — ratio of floats.
  * `confidence  = SkillXpCurve.confidence(cur, tgt)` — a rational fraction
    `confNum/confDen` in `[0,1]` (already proved over ℚ in `SkillXpCurve.lean`).
  * `baseline_vpc = DEFAULT_COIN_VALUE_GOLD = 5.0` (production constant).
  * `confidence_margin = LOW_CONFIDENCE_MARGIN = 3.0`.

We model the formula over `Rat` so every operation is exact on fractional
inputs; the differential test feeds `fractions.Fraction` inputs to the Python
pure core and compares to this Rat oracle, bit-exactly.

DIV-BY-ZERO INVARIANT (cross-file, proved by code-reading + Lean assumption):
`task_requirement` in `task_feasibility.py:30-33` returns `None` when
`state.task_total == 0`. The PRODUCTION caller `task_decision` only computes
`total_cycles = skill_cycles + task_total` AFTER `req is not None`, so
`task_total ≥ 1` ⇒ `total_cycles ≥ 1`. The pure core ITSELF never divides; it
receives the precomputed `skill_up_vpc`. The Lean theorem
`no_div_by_zero_from_invariant` makes this invariant explicit: under the
production hypothesis (`req_is_none = false` ⇒ caller observed `task_total ≥ 1`),
`total_cycles ≥ 1`, so `total_cycles ≠ 0`, so the caller's division is safe.

Lean core only — no mathlib. Rat order via `Rat.add_le_add_*`,
`Rat.mul_le_mul_of_nonneg_*`, and `grind` (core) for the residual
linear-arithmetic goals; `omega` for Nat.
-/

namespace Formal.TaskDecision

/-- Decision label. Mirrors the strings `PURSUE`/`PIVOT` in
`task_decision_labels.py`; we use a sum so the model is structural. -/
inductive Decision
  | PURSUE
  | PIVOT
  deriving DecidableEq, Repr

/-- `required_vpc = baseline * (1 + margin * (1 - confidence))`. Linear in the
margin and inversely-linear in the confidence. -/
def requiredVpc (baseline margin confidence : Rat) : Rat :=
  baseline * (1 + margin * (1 - confidence))

/-- The pure decision core. Mirrors `task_decision_pure` component-for-component. -/
def taskDecisionPure (reqIsNone reqIsCombat historyPresent : Bool)
    (skillUpVpc baseline margin confidence : Rat) : Decision :=
  if reqIsNone then Decision.PURSUE
  else if reqIsCombat ∨ ¬ historyPresent then Decision.PIVOT
  else if skillUpVpc ≥ requiredVpc baseline margin confidence then Decision.PURSUE
  else Decision.PIVOT

/-! ### Intent theorems. -/

/-- (a) Combat / no-history short-circuit ⇒ PIVOT, UNCONDITIONALLY whenever
`reqIsNone = false`. This is the safety gate: when a skill-gated requirement
exists and either (i) it is combat or (ii) no history store is wired in, the
decision is PIVOT regardless of the other arithmetic. -/
theorem combat_or_no_history_pivots (reqIsCombat historyPresent : Bool)
    (skillUpVpc baseline margin confidence : Rat)
    (h : reqIsCombat = true ∨ historyPresent = false) :
    taskDecisionPure false reqIsCombat historyPresent
        skillUpVpc baseline margin confidence = Decision.PIVOT := by
  unfold taskDecisionPure
  simp only [Bool.false_eq_true, if_false]
  rcases h with hc | hh
  · simp [hc]
  · simp [hh]

/-- Witness for non-vacuity of `combat_or_no_history_pivots`: a concrete combat
case PIVOTs. The threshold is `5 * (1 + 3 * 0) = 5`, and `skillUpVpc = 1000`
which would otherwise clear it — combat short-circuit dominates. -/
example : taskDecisionPure false true true (1000 : Rat) 5 3 1 = Decision.PIVOT := by
  unfold taskDecisionPure; simp

/-- Witness for non-vacuity (no-history branch). -/
example : taskDecisionPure false false false (1000 : Rat) 5 3 1 = Decision.PIVOT := by
  unfold taskDecisionPure; simp

/-- (b) Div-by-zero invariant. The pure core does not divide. The production
caller `task_decision` divides by `total_cycles = skill_cycles + task_total`
ONLY when `task_requirement(...) ≠ None`; per `task_feasibility.py:30-33`,
`task_requirement` returns `None` whenever `state.task_total = 0`. Therefore
`reqIsNone = false ⇒ task_total ≥ 1`, hence `total_cycles ≥ 1 > 0`.

The Lean theorem makes the cross-file invariant explicit as a hypothesis on the
caller-supplied `taskTotal`: under that hypothesis, `total_cycles ≥ 1`. -/
theorem no_div_by_zero_from_invariant (reqIsNone : Bool)
    (skillCycles taskTotal : Nat)
    (hInv : reqIsNone = false → taskTotal ≥ 1) :
    reqIsNone = false → skillCycles + taskTotal ≥ 1 := by
  intro hReq
  have ht : taskTotal ≥ 1 := hInv hReq
  omega

/-- Non-vacuity for `no_div_by_zero_from_invariant`: the conclusion fires
concretely when the hypothesis is met. -/
example : (0 : Nat) + 1 ≥ 1 :=
  no_div_by_zero_from_invariant false 0 1 (fun _ => Nat.le_refl 1) rfl

/-- (c) Confidence monotonicity of the threshold: higher confidence ⇒ lower
`required_vpc` (the bar drops). Needs only `baseline ≥ 0` and `margin ≥ 0` —
both production constants (5.0, 3.0). -/
theorem requiredVpc_antitone_in_confidence
    (baseline margin c c' : Rat)
    (hb : 0 ≤ baseline) (hm : 0 ≤ margin) (hcc : c ≤ c') :
    requiredVpc baseline margin c' ≤ requiredVpc baseline margin c := by
  unfold requiredVpc
  have h1 : 1 - c' ≤ 1 - c := by grind
  have h2 : margin * (1 - c') ≤ margin * (1 - c) :=
    Rat.mul_le_mul_of_nonneg_left h1 hm
  have h3 : 1 + margin * (1 - c') ≤ 1 + margin * (1 - c) := by grind
  exact Rat.mul_le_mul_of_nonneg_left h3 hb

/-- (c′) Confidence monotonicity of the DECISION: if PURSUE was returned at
confidence `c` (lower), then at higher confidence `c' ≥ c` it is STILL PURSUE
(the bar can only drop, so a beat at the higher bar still beats the lower bar).
Skill/non-combat branch (other arguments fixed). -/
theorem decision_pursue_confidence_monotone
    (skillUpVpc baseline margin c c' : Rat)
    (hb : 0 ≤ baseline) (hm : 0 ≤ margin) (hcc : c ≤ c')
    (h : taskDecisionPure false false true skillUpVpc baseline margin c
         = Decision.PURSUE) :
    taskDecisionPure false false true skillUpVpc baseline margin c'
      = Decision.PURSUE := by
  -- Reduce both decisions to the threshold compare.
  have hAtC : skillUpVpc ≥ requiredVpc baseline margin c := by
    unfold taskDecisionPure at h
    simp only [Bool.false_eq_true, if_false] at h
    -- h : (if skillUpVpc ≥ requiredVpc baseline margin c then PURSUE else PIVOT) = PURSUE
    by_cases hge : skillUpVpc ≥ requiredVpc baseline margin c
    · exact hge
    · simp [hge] at h
  have hAnti :
      requiredVpc baseline margin c' ≤ requiredVpc baseline margin c :=
    requiredVpc_antitone_in_confidence baseline margin c c' hb hm hcc
  have hAtC' : skillUpVpc ≥ requiredVpc baseline margin c' :=
    Rat.le_trans hAnti hAtC
  unfold taskDecisionPure
  simp only [Bool.false_eq_true, if_false]
  simp [hAtC']

/-- Non-vacuity for `decision_pursue_confidence_monotone`. Demonstrates a
fractional confidence pair that genuinely exercises the monotonicity (c = 1/2,
c' = 1). -/
example :
    taskDecisionPure false false true (10 : Rat) 1 1 (1/2)
      = Decision.PURSUE := by
  unfold taskDecisionPure requiredVpc
  -- threshold = 1 * (1 + 1 * (1 - 1/2)) = 3/2 ≤ 10
  rw [if_neg (by decide : ¬ (false = true))]
  rw [if_neg (by simp : ¬ (false = true ∨ ¬ true = true))]
  rw [if_pos (by grind : (10 : Rat) ≥ 1 * (1 + 1 * (1 - 1/2)))]

/-- Witness used together with the previous example to show the lemma is non-vacuous. -/
example :
    taskDecisionPure false false true (10 : Rat) 1 1 1 = Decision.PURSUE := by
  unfold taskDecisionPure requiredVpc
  rw [if_neg (by decide : ¬ (false = true))]
  rw [if_neg (by simp : ¬ (false = true ∨ ¬ true = true))]
  rw [if_pos (by grind : (10 : Rat) ≥ 1 * (1 + 1 * (1 - 1)))]

/-- (d) skill_up_vpc monotonicity of the DECISION: if PURSUE was returned at
`v`, then at any `v' ≥ v` it is STILL PURSUE (raising the observed VPC can
only help). -/
theorem decision_pursue_vpc_monotone
    (v v' baseline margin confidence : Rat)
    (hvv : v ≤ v')
    (h : taskDecisionPure false false true v baseline margin confidence
         = Decision.PURSUE) :
    taskDecisionPure false false true v' baseline margin confidence
      = Decision.PURSUE := by
  have hAtV : v ≥ requiredVpc baseline margin confidence := by
    unfold taskDecisionPure at h
    simp only [Bool.false_eq_true, if_false] at h
    by_cases hge : v ≥ requiredVpc baseline margin confidence
    · exact hge
    · simp [hge] at h
  have hAtV' : v' ≥ requiredVpc baseline margin confidence := Rat.le_trans hAtV hvv
  unfold taskDecisionPure
  simp only [Bool.false_eq_true, if_false]
  simp [hAtV']

/-- Non-vacuity for `decision_pursue_vpc_monotone`. -/
example :
    taskDecisionPure false false true (10 : Rat) 1 1 1 = Decision.PURSUE := by
  unfold taskDecisionPure requiredVpc
  rw [if_neg (by decide : ¬ (false = true))]
  rw [if_neg (by simp : ¬ (false = true ∨ ¬ true = true))]
  rw [if_pos (by grind : (10 : Rat) ≥ 1 * (1 + 1 * (1 - 1)))]

/-- (e) reqIsNone short-circuit ⇒ PURSUE (the "already feasible" branch). -/
theorem req_none_pursues (reqIsCombat historyPresent : Bool)
    (skillUpVpc baseline margin confidence : Rat) :
    taskDecisionPure true reqIsCombat historyPresent
        skillUpVpc baseline margin confidence = Decision.PURSUE := by
  unfold taskDecisionPure
  simp

end Formal.TaskDecision
