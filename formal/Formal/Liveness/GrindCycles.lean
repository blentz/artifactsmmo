-- formal/Formal/Liveness/GrindCycles.lean
-- @concept: liveness @property: termination, sufficiency
/-
GRIND CYCLES (Phase 2d-L2b of docs/PLAN_decision_architecture_redesign.md).

A grind is the legs its decomposition emits: a CYCLE is the committed plan
for the rung's inputs (withdraws, recycles, gathers and crafts of
intermediates — `Formal.CommittedLoop.committed_loop_delivers` proves it
finishes under any fair schedule) followed by the rung's EARNING leg, which
pays the skill `skillLegXp` XP (`.gather`, `Measure.grantSkillXp`).

Headline (`grind_cycles_reach_target`): with the skill fields in band and a
leg that earns, `skillDeficit` cycles reach the target skill level, whatever
their preparatory legs are, since no leg but the earning one touches the
skill. So the grind ends within the XP owed, in cycles, and each cycle ends
by the committed loop.
-/
import Formal.Liveness.SkillGapClosure

namespace Formal.Liveness.GrindCycles

open Formal.Liveness.Plan
open Formal.Liveness.PlanAction
open Formal.Liveness.Measure
open Formal.Liveness.SkillGapClosure

/-- The skill fields a grind reads. -/
def SkillSame (t s : State) : Prop :=
  t.trackedSkillLevel = s.trackedSkillLevel ∧ t.trackedSkillXp = s.trackedSkillXp ∧
    t.skillXpNeeds = s.skillXpNeeds ∧ t.skillLegXp = s.skillLegXp ∧
    t.targetSkillLevel = s.targetSkillLevel

/-- Every leg but the earning one leaves the skill alone. -/
theorem prep_leg_keeps_skill (a : ActionKind) (s : State) (h : a ≠ .gather) :
    SkillSame (applyActionKind a s) s := by
  unfold SkillSame
  cases a <;> first
    | exact absurd rfl h
    | (simp only [applyActionKind]; split <;> simp_all)
    | simp [applyActionKind]

/-- A run of preparatory legs leaves the skill alone. -/
theorem prep_keeps_skill :
    ∀ (p : List ActionKind) (s : State), (∀ a ∈ p, a ≠ .gather) → SkillSame (applyPlan p s) s := by
  intro p
  induction p with
  | nil => intro s _; simp [applyPlan, SkillSame]
  | cons a p ih =>
    intro s h
    rw [applyPlan_cons]
    obtain ⟨h1, h2, h3, h4, h5⟩ := ih (applyActionKind a s) (fun b hb => h b (List.mem_cons_of_mem _ hb))
    obtain ⟨g1, g2, g3, g4, g5⟩ := prep_leg_keeps_skill a s (h a List.mem_cons_self)
    exact ⟨h1.trans g1, h2.trans g2, h3.trans g3, h4.trans g4, h5.trans g5⟩

theorem SkillSame.deficit {t s : State} (h : SkillSame t s) : t.skillDeficit = s.skillDeficit := by
  obtain ⟨_, h2, h3, _, _⟩ := h
  simp only [State.skillDeficit, h2, h3]

theorem SkillSame.band {t s : State} (h : SkillSame t s) (hb : s.SkillBand) : t.SkillBand := by
  obtain ⟨h1, h2, h3, _, h5⟩ := h
  obtain ⟨b1, b2, b3⟩ := hb
  exact ⟨by rw [h3, h5, h1]; exact b1, by rw [h3]; exact b2, by rw [h3, h2]; exact b3⟩

/-- One cycle: its preparatory legs, then the earning leg. -/
def cycle (p : List ActionKind) : List ActionKind := p ++ [.gather]

/-- A cycle lowers the XP owed by one leg's pay, and keeps the band, the pay
    and the target. -/
theorem cycle_pays (p : List ActionKind) (s : State) (hp : ∀ a ∈ p, a ≠ .gather) :
    (applyPlan (cycle p) s).skillDeficit = s.skillDeficit - s.skillLegXp ∧
    (applyPlan (cycle p) s).skillLegXp = s.skillLegXp ∧
    (applyPlan (cycle p) s).targetSkillLevel = s.targetSkillLevel ∧
    (s.SkillBand → (applyPlan (cycle p) s).SkillBand) := by
  have hsplit : applyPlan (cycle p) s = applyActionKind .gather (applyPlan p s) := by
    simp [cycle, applyPlan, List.foldl_append]
  have hsame := prep_keeps_skill p s hp
  rw [hsplit]
  refine ⟨?_, ?_, ?_, fun hb => gather_band _ (hsame.band hb)⟩
  · rw [gather_skill_pays, hsame.deficit, hsame.2.2.2.1]
  · rw [gather_legXp_preserved]; exact hsame.2.2.2.1
  · show (grantSkillXp (applyPlan p s) (applyPlan p s).skillLegXp).targetSkillLevel = _
    exact hsame.2.2.2.2

/-- Cycles one after another. -/
def cycles (ps : List (List ActionKind)) : List ActionKind := ps.flatMap cycle

theorem cycles_pay :
    ∀ (ps : List (List ActionKind)) (s : State), (∀ p ∈ ps, ∀ a ∈ p, a ≠ .gather) →
      (applyPlan (cycles ps) s).skillDeficit = s.skillDeficit - ps.length * s.skillLegXp ∧
      (applyPlan (cycles ps) s).targetSkillLevel = s.targetSkillLevel ∧
      (s.SkillBand → (applyPlan (cycles ps) s).SkillBand) := by
  intro ps
  induction ps with
  | nil => intro s _; simp [cycles, applyPlan]
  | cons p ps ih =>
    intro s h
    have happ : applyPlan (cycles (p :: ps)) s = applyPlan (cycles ps) (applyPlan (cycle p) s) := by
      simp [cycles, applyPlan, List.flatMap_cons, List.foldl_append]
    obtain ⟨c1, c2, c3, c4⟩ := cycle_pays p s (h p List.mem_cons_self)
    obtain ⟨i1, i2, i3⟩ := ih (applyPlan (cycle p) s) (fun q hq => h q (List.mem_cons_of_mem _ hq))
    rw [happ]
    refine ⟨?_, i2.trans c3, fun hb => i3 (c4 hb)⟩
    rw [i1, c1, c2, List.length_cons, Nat.add_mul, Nat.one_mul]; omega

/-- **The grind reaches its target.** With the skill fields in band and a leg
    that earns, `skillDeficit` cycles — each any run of preparatory legs
    followed by the earning leg — bring the tracked skill to its target level. -/
theorem grind_cycles_reach_target (s : State) (hband : s.SkillBand) (hleg : 0 < s.skillLegXp)
    (ps : List (List ActionKind)) (hlen : ps.length = s.skillDeficit)
    (hprep : ∀ p ∈ ps, ∀ a ∈ p, a ≠ .gather) :
    (applyPlan (cycles ps) s).targetSkillLevel ≤ (applyPlan (cycles ps) s).trackedSkillLevel := by
  obtain ⟨d, _, b⟩ := cycles_pay ps s hprep
  have hzero : (applyPlan (cycles ps) s).skillDeficit = 0 := by
    rw [d, hlen]
    have : s.skillDeficit ≤ s.skillDeficit * s.skillLegXp := Nat.le_mul_of_pos_right _ hleg
    omega
  exact (skillDeficit_zero_iff _ (b hband)).mp hzero

/-! ### Non-vacuity -/

private def grindWitness : State :=
  { Formal.Liveness.LadderEval.inertLadderState with
    trackedSkillLevel := 3
    targetSkillLevel := 5
    trackedSkillXp := 4
    skillXpNeeds := [10, 12]
    skillLegXp := 3 }

-- Six cycles, each a withdraw and a craft of an intermediate before the earning leg.
example : (applyPlan (cycles (List.replicate 6 [.withdrawItem, .craft])) grindWitness).trackedSkillLevel = 5 := by
  rfl

end Formal.Liveness.GrindCycles
