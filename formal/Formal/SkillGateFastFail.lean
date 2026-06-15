-- @concept: core, planner @property: safety, totality
/-
Formal model of the skill-gate fast-fail in `GatherMaterialsGoal.is_plannable`
(`src/artifactsmmo_cli/ai/goals/gathering.py:316-335`): when satisfying a goal
requires CRAFTING the target and the crafting skill is below the recipe's level
gate, no plan exists, so the goal is pruned before the GOAP search (instead of
exhausting the search budget — trace 2026-06-11 18:10: feather_coat at
gearcrafting 2 < 5 burned ~99k nodes to plan_len 0 every probe cycle).

CODE FACTS mirrored (gathering.py:326-335):
  is_plannable = True   if target not among `needed`            (materials-only)
               | True   if the target has no crafting skill gate
               | True   if current skill level ≥ recipe level   (gate OPEN)
               | (owned ≥ needed)   otherwise                   (gate CLOSED)

SOUNDNESS CONDITION (the modeled assumption, true for craftable gear like
feather_coat, a body_armor obtained ONLY by crafting): the target is
craft-acquired — no non-craft action increases the owned count of the target —
and the crafting skill is CONSTANT across a plan. The latter is the invariant
`CraftAction.is_applicable` relies on: it gates on base `state.skills`, NOT on
in-plan projected xp (verified `actions/crafting.py:46-47`). Hence when the gate
is closed the craft action is never applicable, owned never rises, and the goal
`owned ≥ needed` is unreachable — pruning loses no plan.

Lean core only — no mathlib.
-/

namespace Formal.SkillGateFastFail

/-- A plan step: either the gated craft of the target, or any other action (which
never increases the target's owned count, since the target is craft-acquired). -/
inductive Step where
  | craft
  | other
deriving DecidableEq

/-- Owned count of the target after one step. `craft` increases it by one ONLY
when the gate is open (mirrors `CraftAction.is_applicable`: gate closed ⇒ the
action is not applicable ⇒ not taken ⇒ no effect). `other` never touches it. -/
def applyStep (gateOpen : Bool) (owned : Nat) : Step → Nat
  | .craft => if gateOpen then owned + 1 else owned
  | .other => owned

/-- Fold a plan (action sequence) over the owned count. The gate is fixed for the
whole plan: skills do not change in-plan. -/
def runPlan (gateOpen : Bool) (owned : Nat) : List Step → Nat
  | [] => owned
  | s :: rest => runPlan gateOpen (applyStep gateOpen owned s) rest

/-- The fast-fail predicate, mirroring `GatherMaterialsGoal.is_plannable`. -/
def isPlannable (targetInNeeded hasGate : Bool)
    (curLevel craftLevel owned needed : Nat) : Bool :=
  !targetInNeeded || !hasGate || decide (craftLevel ≤ curLevel) || decide (needed ≤ owned)

/-! ### Dynamics under a closed gate. -/

/-- **GATE-BLOCKS-CRAFT.** With the gate closed, NO step changes the owned count
(craft is blocked, other never touches the target). -/
theorem applyStep_gate_closed (owned : Nat) (s : Step) :
    applyStep false owned s = owned := by
  cases s <;> simp [applyStep]

/-- **OWNED-INVARIANT.** With the gate closed, the owned count is invariant across
an ENTIRE plan — no action sequence can raise it. -/
theorem runPlan_gate_closed (owned : Nat) (plan : List Step) :
    runPlan false owned plan = owned := by
  induction plan generalizing owned with
  | nil => rfl
  | cons s rest ih => rw [runPlan, applyStep_gate_closed, ih]

/-! ### Headline soundness. -/

/-- **SOUNDNESS.** When the fast-fail fires (`isPlannable = false` with a real
craft gate), EVERY plan leaves the owned count below `needed` — so the goal
`owned ≥ needed` is unreachable and pruning it discards no satisfiable plan.

`isPlannable = false` forces: target IS in needed, the gate IS real,
`curLevel < craftLevel` (gate closed), and `owned < needed`. The gate being
closed means `gateOpen := decide (craftLevel ≤ curLevel) = false`, so by
`runPlan_gate_closed` the final owned equals the initial `owned < needed`. -/
theorem fastfail_sound (targetInNeeded hasGate : Bool)
    (curLevel craftLevel owned needed : Nat)
    (h : isPlannable targetInNeeded hasGate curLevel craftLevel owned needed = false) :
    ∀ plan, runPlan (decide (craftLevel ≤ curLevel)) owned plan < needed := by
  -- Decompose the disjunctive `false`.
  simp only [isPlannable, Bool.or_eq_false_iff, Bool.not_eq_false',
    decide_eq_false_iff_not, Nat.not_le] at h
  obtain ⟨⟨⟨_, _⟩, hlvl⟩, hown⟩ := h
  -- gate closed: craftLevel > curLevel ⇒ ¬ (craftLevel ≤ curLevel)
  have hgate : decide (craftLevel ≤ curLevel) = false := by
    simp [Nat.not_le.mpr hlvl]
  intro plan
  rw [hgate, runPlan_gate_closed]
  exact hown

/-! ### Non-vacuity / completeness witnesses. -/

-- The fast-fail GENUINELY fires (target in needed, real gate, level 2 < 5, owns 0 < 1).
example : isPlannable true true 2 5 0 1 = false := by decide

-- Gate OPEN (level ≥ recipe) ⇒ plannable (do not prune a craftable goal).
example : isPlannable true true 5 5 0 1 = true := by decide

-- Already owns enough ⇒ plannable even with the gate closed.
example : isPlannable true true 2 5 1 1 = true := by decide

-- Materials-only goal (target NOT among needed — e.g. gathering raw `feather`)
-- stays plannable: regression guard for the c9c0231 fight-for-drops fix.
example : isPlannable false true 0 5 0 1 = true := by decide

-- No craft gate at all ⇒ plannable.
example : isPlannable true false 0 5 0 1 = true := by decide

-- Model non-vacuity: with the gate OPEN, crafting DOES raise the owned count,
-- so the soundness theorem is not vacuously about a frozen counter.
example : runPlan true 0 [Step.craft, Step.craft] = 2 := by decide
example : runPlan false 0 [Step.craft, Step.craft] = 0 := by decide

end Formal.SkillGateFastFail
