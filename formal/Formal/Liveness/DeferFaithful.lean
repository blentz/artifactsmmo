import Formal.Liveness.BlockerDescentD

/-! # DeferFaithful — the defer-faithful, adversarially-re-arming capstone

Brick D4 of `docs/PLAN_residual_closure.md`. Below level 50 the defer-gated
refresh either arms the combat objective (outside the items-task defer window)
or leaves the state to pursue its items task (inside it — `pursueTaskFires`
holds by the gate). Either way a means fires, the selection sits in the ladder
prefix up to `pursueTask`, and every such means strictly descends `DMeasure`
(`BlockerDescentD`) — even with the WORST-CASE chore re-arm on every fight.

> `ai_reaches_fifty_defer_faithful : ∀ s, ∃ k, (cycleStepDN k s).level ≥ 50`

Hypothesis-free; axioms = standard + LIV-001. Relative to
`UnconditionalDescent.ai_reaches_fifty_unconditional` this closes residual 3
(items-task defer-case now modelled, not over-approximated) and sharpens
residual 4 (fight-direction re-arming worst-cased) of
`docs/LEVEL_FIFTY_RESIDUALS.md`. -/

set_option linter.dupNamespace false

namespace Formal.Liveness.DeferFaithful

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.PerceptionRefresh
open Formal.Liveness.DMeasure
open Formal.Liveness.CycleStepD
open Formal.Liveness.BlockerDescentD
open Formal.Liveness.UnconditionalDescent

/-- The ladder prefix up to and including `pursueTask` — the only means
    selectable below 50 under the defer-gated refresh. -/
def pursuePrefix : List MeansKind := blockerPrefix ++ [.pursueTask]

/-- `allInLadderOrder` splits at `pursueTask`. -/
theorem ladder_splitD :
    allInLadderOrder = pursuePrefix ++
      [.acceptTask, .taskExchange, .maintainConsumables,
       .sellIdle, .recycleSurplus, .bankExpand, .drainBankJunk, .wait] := rfl

private theorem refreshD_phase' (s : State) :
    (perceptionRefreshD s).taskLifecyclePhase = s.taskLifecyclePhase := by
  unfold perceptionRefreshD; split <;> rfl

/-- When `pursueTask` fires, the ladder's selection comes from `pursuePrefix`. -/
theorem ladder_mem_pursuePrefix {r : State} {k : MeansKind}
    (hpf : fires .pursueTask r = true)
    (hk : productionLadder r = some k) : k ∈ pursuePrefix := by
  unfold productionLadder at hk
  rw [ladder_splitD, List.findSome?_append] at hk
  cases hpre : pursuePrefix.findSome?
      (fun k => if fires k r then some k else none) with
  | none =>
    exfalso
    rw [List.findSome?_eq_none_iff] at hpre
    have hnone : (if fires .pursueTask r = true
        then some MeansKind.pursueTask else none) = (none : Option MeansKind) :=
      hpre .pursueTask (by decide)
    rw [if_pos hpf] at hnone
    cases hnone
  | some k' =>
    rw [hpre] at hk
    simp only [Option.some_or] at hk
    rw [List.findSome?_eq_some_iff] at hpre
    obtain ⟨pre, x, suf, hl, hbody, _⟩ := hpre
    by_cases hf : fires x r = true
    · simp only [hf, if_true] at hbody
      have hx : x = k := (Option.some.inj hbody).trans (Option.some.inj hk)
      rw [hl, ← hx]
      exact List.mem_append_right _ (List.mem_cons_self)
    · simp [hf] at hbody

/-- Below the cap the ladder always selects something: outside the gate the
    refresh arms `objectiveStep`; inside it `pursueTask` fires. -/
theorem ladderD_some_below_fifty (s : State) (hlvl : s.level < 50) :
    productionLadder (perceptionRefreshD s) ≠ none := by
  intro hnone
  unfold productionLadder at hnone
  rw [List.findSome?_eq_none_iff] at hnone
  by_cases hgate : deferGate s = true
  · -- pursueTask fires (phase active, from the gate).
    have hpf : fires .pursueTask (perceptionRefreshD s) = true := by
      have hg := hgate
      simp only [deferGate, Bool.and_eq_true] at hg
      simp only [fires, pursueTaskFires, refreshD_phase']
      have := hg.1.2
      simpa [pursueTaskFires] using this
    have h : (if fires .pursueTask (perceptionRefreshD s) = true
        then some MeansKind.pursueTask else none) = (none : Option MeansKind) :=
      hnone .pursueTask (by decide)
    rw [if_pos hpf] at h
    cases h
  · -- The refresh arms objectiveStep.
    have hg : deferGate s = false := Bool.eq_false_iff.mpr hgate
    have hcondT : (decide (s.level < 50) && !(deferGate s)) = true := by
      simp [hlvl, hg]
    have hobj : fires .objectiveStep (perceptionRefreshD s) = true := by
      simp only [fires, ProductionLadder.objectiveStepFires]
      unfold perceptionRefreshD
      rw [if_pos hcondT]
    have h : (if fires .objectiveStep (perceptionRefreshD s) = true
        then some MeansKind.objectiveStep else none) = (none : Option MeansKind) :=
      hnone .objectiveStep (by decide)
    rw [if_pos hobj] at h
    cases h

/-- **Total per-cycle descent for the defer-faithful cycle.** -/
theorem cycleStepD_descends_below_fifty (s : State) (hlvl : s.level < 50) :
    dMeasureLt (dMeasure (cycleStepD s)) (dMeasure s) := by
  cases hk : productionLadder (perceptionRefreshD s) with
  | none => exact absurd hk (ladderD_some_below_fifty s hlvl)
  | some k =>
    -- Selection sits in pursuePrefix, gate or no gate.
    have hmem : k ∈ pursuePrefix := by
      by_cases hgate : deferGate s = true
      · have hpf : fires .pursueTask (perceptionRefreshD s) = true := by
          have hg := hgate
          simp only [deferGate, Bool.and_eq_true] at hg
          simp only [fires, pursueTaskFires, refreshD_phase']
          have := hg.1.2
          simpa [pursueTaskFires] using this
        exact ladder_mem_pursuePrefix hpf hk
      · have hg : deferGate s = false := Bool.eq_false_iff.mpr hgate
        have hcondT : (decide (s.level < 50) && !(deferGate s)) = true := by
          simp [hlvl, hg]
        have hobj : fires .objectiveStep (perceptionRefreshD s) = true := by
          simp only [fires, ProductionLadder.objectiveStepFires]
          unfold perceptionRefreshD
          rw [if_pos hcondT]
        exact List.mem_append_left _ (ladder_mem_blockerPrefix hobj hk)
    cases k with
    | hpCritical      => exact descendsD_hpCritical s hk
    | restForCombat   => exact descendsD_restForCombat s hk
    | bankUnlock      => exact descendsD_fight s hlvl (Or.inl hk)
    | reachUnlockLevel => exact descendsD_fight s hlvl (Or.inr (Or.inl hk))
    | discardCritical => exact descendsD_discardCritical s hk
    | craftRelief     => exact descendsD_craftRelief s hk
    | recycleRelief   => exact descendsD_recycleRelief s hk
    | sellRelief      => exact descendsD_sellRelief s hk
    | depositFull     => exact descendsD_depositFull s hk
    | discardHigh     => exact descendsD_discardHigh s hk
    | gearReview      => exact descendsD_gearReview s hk
    | craftPotions    => exact descendsD_craftPotions s hk
    | claimPending    => exact descendsD_claimPending s hk
    | completeTask    => exact descendsD_completeTask s hk
    | sellPressured   => exact descendsD_sellPressured s hk
    | lowYieldCancel  => exact descendsD_lowYieldCancel s hk
    | taskCancel      => exact descendsD_taskCancel s hk
    | objectiveStep   =>
        by_cases hisF : (perceptionRefreshD s).objectiveStepIsFight = true
        · exact descendsD_fight s hlvl (Or.inr (Or.inr ⟨hk, hisF⟩))
        · exact descendsD_placeholder s hk (Bool.eq_false_iff.mpr hisF)
    | pursueTask      => exact descendsD_pursueTask s hlvl hk
    | acceptTask      => exact absurd hmem (by decide)
    | taskExchange    => exact absurd hmem (by decide)
    | maintainConsumables => exact absurd hmem (by decide)
    | sellIdle        => exact absurd hmem (by decide)
    | recycleSurplus  => exact absurd hmem (by decide)
    | bankExpand      => exact absurd hmem (by decide)
    | drainBankJunk   => exact absurd hmem (by decide)
    | wait            => exact absurd hmem (by decide)

/-- **The defer-faithful, adversarially-re-arming reach-50 capstone.** -/
theorem ai_reaches_fifty_defer_faithful (s : State) :
    ∃ k, (cycleStepDN k s).level ≥ 50 :=
  exists_level_ge_of_ddescent (fun k => cycleStepDN k s) (fun k hk => by
    show dMeasureLt (dMeasure (cycleStepDN (k + 1) s)) (dMeasure (cycleStepDN k s))
    rw [cycleStepDN_succ_outer k s]
    exact cycleStepD_descends_below_fifty (cycleStepDN k s) hk)

end Formal.Liveness.DeferFaithful
