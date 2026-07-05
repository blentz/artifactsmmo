import Formal.Liveness.BlockerDescentE
import Formal.Liveness.DeferFaithful

/-! # GearedDescent — `ai_reaches_fifty_geared` (E-tower capstone, C2c)

`docs/PLAN_c2_composed_liveness.md`. The geared cycle closes the combat-outcome
gap-family the trace phases measured: xp is credited only on ADEQUATE-gear
fight cycles (`perceptionRefreshE` arms the objective iff `loadoutAdequate`);
inadequate states route through gear-progress cycles whose finite discharge is
grounded offline by the EMPTY acquirable frontier
(`WitnessAcquirable.acquirableFrontier_empty` — post-P1 multi-drop closure,
every band's winning loadout is provably obtainable); fights pay a worst-case
hp loss with death→respawn; rollovers adversarially reset gear AND every chore
latch/debt.

HYPOTHESIS-FREE: no fairness, no quiescence, no spawn, no adequacy assumption
— from ANY start state. Axioms: standard + the `xpToNextLevel` positivity
axiom (LIV-001), as audited in `LivenessAudit.lean`.

Liveness namespace — Mathlib allowed. -/

set_option linter.dupNamespace false

namespace Formal.Liveness.GearedDescent

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.CycleStep
open Formal.Liveness.EMeasure
open Formal.Liveness.CycleStepD
open Formal.Liveness.CycleStepE
open Formal.Liveness.BlockerDescentE
open Formal.Liveness.UnconditionalDescent
open Formal.Liveness.DeferFaithful

private theorem refreshE_phase' (s : State) :
    (perceptionRefreshE s).taskLifecyclePhase = s.taskLifecyclePhase := by
  unfold perceptionRefreshE
  split
  · split <;> rfl
  · rfl

/-- Below the cap the ladder always selects something: inside the defer window
    `pursueTask` fires; outside it the refresh arms the objective (adequate)
    or the gear latch (inadequate) — all three fire. -/
theorem ladderE_some_below_fifty (s : State) (hlvl : s.level < 50) :
    productionLadder (perceptionRefreshE s) ≠ none := by
  intro hnone
  unfold productionLadder at hnone
  rw [List.findSome?_eq_none_iff] at hnone
  by_cases hgate : deferGate s = true
  · have hpf : fires .pursueTask (perceptionRefreshE s) = true := by
      have hg := hgate
      simp only [deferGate, Bool.and_eq_true] at hg
      simp only [fires, pursueTaskFires, refreshE_phase']
      have := hg.1.2
      simpa [pursueTaskFires] using this
    have h : (if fires .pursueTask (perceptionRefreshE s) = true
        then some MeansKind.pursueTask else none) = (none : Option MeansKind) :=
      hnone .pursueTask (by decide)
    rw [if_pos hpf] at h
    cases h
  · have hg : deferGate s = false := Bool.eq_false_iff.mpr hgate
    have hcondT : (decide (s.level < 50) && !(deferGate s)) = true := by
      simp [hlvl, hg]
    by_cases hadq : s.loadoutAdequate = true
    · have hobj : fires .objectiveStep (perceptionRefreshE s) = true := by
        simp only [fires, ProductionLadder.objectiveStepFires]
        unfold perceptionRefreshE
        rw [if_pos hcondT, if_pos hadq]
      have h : (if fires .objectiveStep (perceptionRefreshE s) = true
          then some MeansKind.objectiveStep else none) = (none : Option MeansKind) :=
        hnone .objectiveStep (by decide)
      rw [if_pos hobj] at h
      cases h
    · have hgear : fires .gearReview (perceptionRefreshE s) = true := by
        simp only [fires, ProductionLadder.gearReviewFires]
        unfold perceptionRefreshE
        rw [if_pos hcondT, if_neg hadq]
      have h : (if fires .gearReview (perceptionRefreshE s) = true
          then some MeansKind.gearReview else none) = (none : Option MeansKind) :=
        hnone .gearReview (by decide)
      rw [if_pos hgear] at h
      cases h

/-- **Total per-cycle descent for the geared cycle.** -/
theorem cycleStepE_descends_below_fifty (s : State) (hlvl : s.level < 50) :
    eMeasureLt (eMeasure (cycleStepE s)) (eMeasure s) := by
  cases hk : productionLadder (perceptionRefreshE s) with
  | none => exact absurd hk (ladderE_some_below_fifty s hlvl)
  | some k =>
    have hmem : k ∈ pursuePrefix := by
      by_cases hgate : deferGate s = true
      · have hpf : fires .pursueTask (perceptionRefreshE s) = true := by
          have hg := hgate
          simp only [deferGate, Bool.and_eq_true] at hg
          simp only [fires, pursueTaskFires, refreshE_phase']
          have := hg.1.2
          simpa [pursueTaskFires] using this
        exact ladder_mem_pursuePrefix hpf hk
      · have hg : deferGate s = false := Bool.eq_false_iff.mpr hgate
        have hcondT : (decide (s.level < 50) && !(deferGate s)) = true := by
          simp [hlvl, hg]
        by_cases hadq : s.loadoutAdequate = true
        · have hobj : fires .objectiveStep (perceptionRefreshE s) = true := by
            simp only [fires, ProductionLadder.objectiveStepFires]
            unfold perceptionRefreshE
            rw [if_pos hcondT, if_pos hadq]
          exact List.mem_append_left _ (ladder_mem_blockerPrefix hobj hk)
        · have hgear : fires .gearReview (perceptionRefreshE s) = true := by
            simp only [fires, ProductionLadder.gearReviewFires]
            unfold perceptionRefreshE
            rw [if_pos hcondT, if_neg hadq]
          -- The gear latch fires and sits in the blocker prefix, so the
          -- selection resolves there too (same argument, gearReview witness).
          have hkmem : k ∈ Formal.Liveness.UnconditionalDescent.blockerPrefix := by
            unfold productionLadder at hk
            rw [Formal.Liveness.UnconditionalDescent.ladder_split,
              List.findSome?_append] at hk
            cases hpre : (Formal.Liveness.UnconditionalDescent.blockerPrefix).findSome?
                (fun k => if fires k (perceptionRefreshE s) then some k else none) with
            | none =>
              exfalso
              rw [List.findSome?_eq_none_iff] at hpre
              have h : (if fires .gearReview (perceptionRefreshE s) = true
                  then some MeansKind.gearReview else none)
                  = (none : Option MeansKind) :=
                hpre .gearReview (by decide)
              rw [if_pos hgear] at h
              cases h
            | some k' =>
              rw [hpre] at hk
              simp only [Option.some_or] at hk
              rw [List.findSome?_eq_some_iff] at hpre
              obtain ⟨pre, x, suf, hl, hbody, _⟩ := hpre
              by_cases hf : fires x (perceptionRefreshE s) = true
              · simp only [hf, if_true] at hbody
                have hx : x = k := (Option.some.inj hbody).trans (Option.some.inj hk)
                rw [hl, ← hx]
                exact List.mem_append_right _ List.mem_cons_self
              · simp [hf] at hbody
          exact List.mem_append_left _ hkmem
    cases k with
    | hpCritical      => exact descendsE_hpCritical s hk
    | restForCombat   => exact descendsE_restForCombat s hk
    | bankUnlock      => exact descendsE_fight s hlvl (Or.inl hk)
    | reachUnlockLevel => exact descendsE_fight s hlvl (Or.inr (Or.inl hk))
    | discardCritical => exact descendsE_discardCritical s hk
    | craftRelief     => exact descendsE_craftRelief s hk
    | recycleRelief   => exact descendsE_recycleRelief s hk
    | sellRelief      => exact descendsE_sellRelief s hk
    | depositFull     => exact descendsE_depositFull s hk
    | discardHigh     => exact descendsE_discardHigh s hk
    | gearReview      => exact descendsE_gearReview s hk
    | craftPotions    => exact descendsE_craftPotions s hk
    | claimPending    => exact descendsE_claimPending s hk
    | completeTask    => exact descendsE_completeTask s hk
    | sellPressured   => exact descendsE_sellPressured s hk
    | lowYieldCancel  => exact descendsE_lowYieldCancel s hk
    | taskCancel      => exact descendsE_taskCancel s hk
    | objectiveStep   =>
        by_cases hisF : (perceptionRefreshE s).objectiveStepIsFight = true
        · exact descendsE_fight s hlvl (Or.inr (Or.inr ⟨hk, hisF⟩))
        · exact descendsE_placeholder s hk (Bool.eq_false_iff.mpr hisF)
    | pursueTask      => exact descendsE_pursueTask s hlvl hk
    | acceptTask      => exact absurd hmem (by decide)
    | taskExchange    => exact absurd hmem (by decide)
    | maintainConsumables => exact absurd hmem (by decide)
    | sellIdle        => exact absurd hmem (by decide)
    | recycleSurplus  => exact absurd hmem (by decide)
    | bankExpand      => exact absurd hmem (by decide)
    | drainBankJunk   => exact absurd hmem (by decide)
    | wait            => exact absurd hmem (by decide)

/-- **The geared reach-50 capstone** — xp credited only behind adequate gear,
    gear progress grounded by the empty acquirable frontier, fights costing
    hp with death→respawn, rollovers adversarially re-arming everything. -/
theorem ai_reaches_fifty_geared (s : State) :
    ∃ k, (cycleStepEN k s).level ≥ 50 :=
  exists_level_ge_of_edescent (fun k => cycleStepEN k s) (fun k hk => by
    show eMeasureLt (eMeasure (cycleStepEN (k + 1) s)) (eMeasure (cycleStepEN k s))
    rw [cycleStepEN_succ_outer k s]
    exact cycleStepE_descends_below_fifty (cycleStepEN k s) hk)

end Formal.Liveness.GearedDescent
