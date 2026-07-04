import Formal.Liveness.BlockerDescent

/-! # UnconditionalDescent — the hypothesis-free reach-50 capstone

Brick 4 of `docs/PLAN_l50_unconditional_descent.md`. Below level 50 the
perception refresh arms `objectiveStepFires`, so:

1. the ladder can never return `none` (`.objectiveStep` always fires);
2. the selected means always sits in the 18-element ladder prefix ending at
   `.objectiveStep` (`ladder_mem_blockerPrefix`) — the discretionary tail
   (`pursueTask … wait`) is unreachable below the cap;
3. every prefix means strictly descends `FMeasure`
   (`BlockerDescent.descends_*`).

Hence `cycleStepF_descends_below_fifty` — EVERY below-50 faithful cycle
strictly descends — and the capstone

> `ai_reaches_fifty_unconditional : ∀ s, ∃ k, (cycleStepFN k s).level ≥ 50`

with NO hypotheses at all: the `hquiet` (blockers-quiet) residual of
`LevelingDescent.ai_reaches_fifty_grounded` is DISCHARGED, and `hspawn` is not
needed (the proof consumes only the model's set value
`objectiveStepIsFight := true`; the offline faithfulness grounding of that
arming — kernel target-existence + the production differential — is unchanged
and still documented in `PerceptionRefresh.lean`).

Non-vacuity: the theorem is hypothesis-free over ALL states — there is no
hypothesis set left to be unsatisfiable (contrast the removed i.o.-fairness
capstones, `docs/REVIEW_levelfifty_vacuity.md`).

Honesty perimeter (what this does and does NOT claim) — see the FMeasure module
docstring and `docs/PLAN_l50_unconditional_descent.md` §Honesty: LIV-001 (server
xp curve) is the one inherited axiom; the opaque chore Bools carry production's
observed answers with conservative one-shot clearing; the items-task defer-case
remains the model's documented over-approximation of production arming.

Additive only; axioms ⊆ {propext, Classical.choice, Quot.sound, LIV-001}.
Liveness namespace — Mathlib allowed. -/

namespace Formal.Liveness.UnconditionalDescent

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.PerceptionRefresh
open Formal.Liveness.CycleStepF
open Formal.Liveness.CycleStepFIteration
open Formal.Liveness.FMeasure
open Formal.Liveness.BlockerDescent

/-- The ladder prefix up to and including `.objectiveStep` — the only means
    selectable below level 50 (the refresh arms `.objectiveStep`, which
    precedes the discretionary tail in `allInLadderOrder`). -/
def blockerPrefix : List MeansKind :=
  [.hpCritical, .restForCombat, .bankUnlock, .reachUnlockLevel,
   .discardCritical, .craftRelief, .recycleRelief, .sellRelief, .depositFull,
   .discardHigh, .gearReview, .craftPotions, .claimPending, .completeTask,
   .sellPressured, .lowYieldCancel, .taskCancel, .objectiveStep]

/-- The discretionary tail — everything after `.objectiveStep`. -/
def discretionaryTail : List MeansKind :=
  [.pursueTask, .acceptTask, .taskExchange, .maintainConsumables,
   .sellIdle, .recycleSurplus, .bankExpand, .drainBankJunk, .wait]

/-- `allInLadderOrder` splits at `.objectiveStep`. -/
theorem ladder_split : allInLadderOrder = blockerPrefix ++ discretionaryTail := rfl

/-- When `.objectiveStep` fires, the ladder's selection comes from the prefix:
    `findSome?` over `prefix ++ tail` resolves in the prefix because the prefix
    contains a firing element. -/
theorem ladder_mem_blockerPrefix {r : State} {k : MeansKind}
    (hobj : fires .objectiveStep r = true)
    (hk : productionLadder r = some k) : k ∈ blockerPrefix := by
  unfold productionLadder at hk
  rw [ladder_split, List.findSome?_append] at hk
  cases hpre : blockerPrefix.findSome?
      (fun k => if fires k r then some k else none) with
  | none =>
    exfalso
    rw [List.findSome?_eq_none_iff] at hpre
    have hnone : (if fires .objectiveStep r = true
        then some MeansKind.objectiveStep else none) = (none : Option MeansKind) :=
      hpre .objectiveStep (by decide)
    rw [if_pos hobj] at hnone
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

/-- Below the cap the ladder always selects SOMETHING — the refresh-armed
    `.objectiveStep` fires, so `findSome?` cannot be `none`. -/
theorem ladder_some_below_fifty (s : State) (hlvl : s.level < 50) :
    productionLadder (perceptionRefresh s) ≠ none := by
  intro hnone
  unfold productionLadder at hnone
  rw [List.findSome?_eq_none_iff] at hnone
  have hobj : fires .objectiveStep (perceptionRefresh s) = true := by
    simp only [fires, ProductionLadder.objectiveStepFires]
    exact perceptionRefresh_objectiveStepFires s hlvl
  have h : (if fires .objectiveStep (perceptionRefresh s) = true
      then some MeansKind.objectiveStep else none) = (none : Option MeansKind) :=
    hnone .objectiveStep (by decide)
  rw [if_pos hobj] at h
  cases h

/-- **Total per-cycle descent.** EVERY below-50 faithful cycle strictly
    descends `FMeasure`, whatever the ladder selects — the Brick-3 per-means
    lemmas closed under the prefix case analysis. This is the discharged form
    of the capstone's `hquiet` residual: no blockers-quiet assumption, the
    chores themselves make progress. -/
theorem cycleStepF_descends_below_fifty (s : State) (hlvl : s.level < 50) :
    fMeasureLt (fMeasure (cycleStepF s)) (fMeasure s) := by
  have hobj : fires .objectiveStep (perceptionRefresh s) = true := by
    simp only [fires, ProductionLadder.objectiveStepFires]
    exact perceptionRefresh_objectiveStepFires s hlvl
  cases hk : productionLadder (perceptionRefresh s) with
  | none => exact absurd hk (ladder_some_below_fifty s hlvl)
  | some k =>
    have hmem := ladder_mem_blockerPrefix hobj hk
    cases k with
    | hpCritical      => exact descends_hpCritical s hk
    | restForCombat   => exact descends_restForCombat s hk
    | bankUnlock      => exact descends_fight s hlvl (Or.inl hk)
    | reachUnlockLevel => exact descends_fight s hlvl (Or.inr (Or.inl hk))
    | discardCritical => exact descends_discardCritical s hk
    | craftRelief     => exact descends_craftRelief s hk
    | recycleRelief   => exact descends_recycleRelief s hk
    | sellRelief      => exact descends_sellRelief s hk
    | depositFull     => exact descends_depositFull s hk
    | discardHigh     => exact descends_discardHigh s hk
    | gearReview      => exact descends_gearReview s hk
    | craftPotions    => exact descends_craftPotions s hk
    | claimPending    => exact descends_claimPending s hk
    | completeTask    => exact descends_completeTask s hk
    | sellPressured   => exact descends_sellPressured s hk
    | lowYieldCancel  => exact descends_lowYieldCancel s hk
    | taskCancel      => exact descends_taskCancel s hk
    | objectiveStep   =>
        exact descends_fight s hlvl (Or.inr (Or.inr
          ⟨hk, perceptionRefresh_objectiveStepIsFight s hlvl⟩))
    | pursueTask      => exact absurd hmem (by decide)
    | acceptTask      => exact absurd hmem (by decide)
    | taskExchange    => exact absurd hmem (by decide)
    | maintainConsumables => exact absurd hmem (by decide)
    | sellIdle        => exact absurd hmem (by decide)
    | recycleSurplus  => exact absurd hmem (by decide)
    | bankExpand      => exact absurd hmem (by decide)
    | drainBankJunk   => exact absurd hmem (by decide)
    | wait            => exact absurd hmem (by decide)

/-- **The unconditional reach-50 capstone.** For EVERY state, the faithful
    cycle reaches level 50 — no `hquiet`, no `hspawn`, no fairness residual.
    Axioms: {propext, Classical.choice, Quot.sound} + LIV-001
    (`xpToNextLevel`/`_pos`), audited in `LivenessAudit.lean`. -/
theorem ai_reaches_fifty_unconditional (s : State) :
    ∃ k, (cycleStepFN k s).level ≥ 50 :=
  cycleStepF_reaches_fifty_of_fdescent s (fun k hk => by
    rw [cycleStepFN_succ_outer k s]
    exact cycleStepF_descends_below_fifty (cycleStepFN k s) hk)

end Formal.Liveness.UnconditionalDescent
