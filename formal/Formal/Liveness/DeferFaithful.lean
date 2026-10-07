import Formal.Liveness.BlockerDescentD

/-! # DeferFaithful — the defer-faithful, adversarially-re-arming capstone

Brick D4 of `docs/PLAN_residual_closure.md`. Below level 50 the defer-gated
refresh either arms the combat objective (outside the items-task defer window)
or leaves the state untouched (inside it). Either way the objective step fires
— inside the window on the gate's active task phase, since a held task's work
is the task objective's step (Phase 5-2c-iii-c-2 #4; the window was the retired
PURSUE_TASK rung's) — so the selection sits in the blocker prefix, and every
such means strictly descends `DMeasure` (`BlockerDescentD`; inside the window
the step dispatches the task trade and descends `taskCycles`) — even with the
WORST-CASE chore re-arm on every fight.

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

/-- Inside the defer window the D refresh is the identity. -/
theorem perceptionRefreshD_window (s : State) (hgate : deferGate s = true) :
    perceptionRefreshD s = s := by
  unfold perceptionRefreshD
  rw [if_neg (by simp [hgate])]

/-- Below the cap the objective step fires on the refreshed state: outside the
    gate the refresh arms it; inside it the gate's active phase fires it — a
    held task's work is the task objective's step (Phase 5-2c-iii-c-2 #4; until
    then the window was covered by the retired `pursueTask` rung). -/
theorem objectiveStepD_fires_below_fifty (s : State) (hlvl : s.level < 50) :
    fires .objectiveStep (perceptionRefreshD s) = true := by
  by_cases hgate : deferGate s = true
  · rw [perceptionRefreshD_window s hgate]
    have hg := hgate
    simp only [deferGate, Bool.and_eq_true] at hg
    have hact := hg.1.2
    simp only [Formal.Liveness.Plan.phaseActive] at hact
    simp only [fires, ProductionLadder.objectiveStepFires, Bool.or_assoc, hact,
      Bool.or_true]
  · have hg : deferGate s = false := Bool.eq_false_iff.mpr hgate
    have hcondT : (decide (s.level < 50) && !(deferGate s)) = true := by
      simp [hlvl, hg]
    simp only [fires, ProductionLadder.objectiveStepFires]
    unfold perceptionRefreshD
    rw [if_pos hcondT]
    simp

/-- Below the cap the ladder always selects something. -/
theorem ladderD_some_below_fifty (s : State) (hlvl : s.level < 50) :
    productionLadder (perceptionRefreshD s) ≠ none := by
  intro hnone
  unfold productionLadder at hnone
  rw [List.findSome?_eq_none_iff] at hnone
  have h : (if fires .objectiveStep (perceptionRefreshD s) = true
      then some MeansKind.objectiveStep else none) = (none : Option MeansKind) :=
    hnone .objectiveStep (by decide)
  rw [if_pos (objectiveStepD_fires_below_fifty s hlvl)] at h
  cases h

/-- **Total per-cycle descent for the defer-faithful cycle.** -/
theorem cycleStepD_descends_below_fifty (s : State) (hlvl : s.level < 50) :
    dMeasureLt (dMeasure (cycleStepD s)) (dMeasure s) := by
  cases hk : productionLadder (perceptionRefreshD s) with
  | none => exact absurd hk (ladderD_some_below_fifty s hlvl)
  | some k =>
    -- Selection sits in the blocker prefix, gate or no gate.
    have hmem : k ∈ blockerPrefix :=
      ladder_mem_blockerPrefix (objectiveStepD_fires_below_fifty s hlvl) hk
    cases k with
    | hpCritical      => exact descendsD_hpCritical s hk
    | restForCombat   => exact descendsD_restForCombat s hk
    | bankUnlock      => exact descendsD_fight s hlvl (Or.inl hk)
    | reachUnlockLevel => exact descendsD_fight s hlvl (Or.inr (Or.inl hk))
    | geCancel        => exact descendsD_geCancel s hk
    | discardCritical => exact descendsD_discardCritical s hk
    | craftRelief     => exact descendsD_craftRelief s hk
    | recycleRelief   => exact descendsD_recycleRelief s hk
    | sellRelief      => exact descendsD_sellRelief s hk
    | depositFull     => exact descendsD_depositFull s hk
    | discardHigh     => exact descendsD_discardHigh s hk
    | craftPotions    => exact descendsD_craftPotions s hk
    | claimPending    => exact descendsD_claimPending s hk
    | completeTask    => exact descendsD_completeTask s hk
    | sellPressured   => exact descendsD_sellPressured s hk
    | objectiveStep   =>
        by_cases hisF : (perceptionRefreshD s).objectiveStepIsFight = true
        · exact descendsD_fight s hlvl (Or.inr (Or.inr ⟨hk, hisF⟩))
        · exact descendsD_placeholder s hlvl hk (Bool.eq_false_iff.mpr hisF)
    | maintainConsumables => exact absurd hmem (by decide)
    | supplyBank      => exact descendsD_supplyBank s hk
    | currencyTurnIn  => exact descendsD_currencyTurnIn s hk
    | sellIdle        => exact absurd hmem (by decide)
    | recycleSurplus  => exact absurd hmem (by decide)
    | bankExpand      => exact descendsD_bankExpand s hk
    | drainBankJunk   => exact absurd hmem (by decide)
    | geBid           => exact absurd hmem (by decide)
    | wait            => exact absurd hmem (by decide)

/-- **The defer-faithful, adversarially-re-arming reach-50 capstone.** -/
theorem ai_reaches_fifty_defer_faithful (s : State) :
    ∃ k, (cycleStepDN k s).level ≥ 50 :=
  exists_level_ge_of_ddescent (fun k => cycleStepDN k s) (fun k hk => by
    show dMeasureLt (dMeasure (cycleStepDN (k + 1) s)) (dMeasure (cycleStepDN k s))
    rw [cycleStepDN_succ_outer k s]
    exact cycleStepD_descends_below_fifty (cycleStepDN k s) hk)

end Formal.Liveness.DeferFaithful
