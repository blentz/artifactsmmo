import Formal.Liveness.BlockerDescentE
import Formal.Liveness.DeferFaithful
import Formal.Liveness.WitnessAcquirable

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

**CONDITIONAL on one NAMED residual: `AdequateArmsFightAt`, quantified along the
trajectory.** Axioms: standard + `xpToNextLevel` (LIV-001), audited in
`LivenessAudit.lean`.

CORRECTED 2026-07-20 (adversarial review). This header previously read
"HYPOTHESIS-FREE: no fairness, no quiescence, no spawn, no adequacy assumption".
That was FALSE. The assumptions were not discharged — they were moved out of the
theorem statement and into `cycleStepE`'s DEFINITION, where `#print axioms`
cannot see them and the gate goes green. `perceptionRefreshE` overwrote the
opaque production observation `objectiveStepFires` with `true`, which is the
retired `hfightFires` fairness obligation wearing a different hat.

Two grants remain definitional — G2 (`gearProgress` restores adequacy within
`GEAR_CAP` cycles at zero cost) and G3 (`.fight` grants a constant `xp + 10` and
cannot fail) — specified as increments 4-7 of
`docs/superpowers/specs/2026-07-20-l50-honest-restatement.md`.

Increment 3 (2026-07-20) took the first real bite out of G2. `GEAR_CAP` was `8`
and self-declared "provisional"; against this repository's own fixture it was
FALSE — 20 of the 49 `acquirableWitness` rows carry loadouts larger than 8, up to
11. It is now `11`, pinned by `witness_loadout_le_gear_cap` /
`witness_loadout_attains_gear_cap` below, which compute `loadoutCodes.length`
IN-KERNEL. `WitnessAcquirable` was previously cited in this docstring while
appearing in NO import and NO proof term — it is now genuinely imported and used.

What is still granted in G2 is the RATE: that one `.gearReview` cycle
accomplishes one acquisition step. `GEAR_CAP` bounds the STEPS, not the cycles
those steps take.

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
theorem ladderE_some_below_fifty (s : State) (hArms : AdequateArmsFightAt s)
    (hlvl : s.level < 50) :
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
        exact (hArms hlvl hg hadq).1
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
theorem cycleStepE_descends_below_fifty (s : State) (hArms : AdequateArmsFightAt s)
    (hlvl : s.level < 50) :
    eMeasureLt (eMeasure (cycleStepE s)) (eMeasure s) := by
  cases hk : productionLadder (perceptionRefreshE s) with
  | none => exact absurd hk (ladderE_some_below_fifty s hArms hlvl)
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
            exact (hArms hlvl hg hadq).1
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
        · exact descendsE_placeholder s hArms hk (Bool.eq_false_iff.mpr hisF)
    | pursueTask      => exact descendsE_pursueTask s hArms hlvl hk
    | acceptTask      => exact absurd hmem (by decide)
    | taskExchange    => exact absurd hmem (by decide)
    | maintainConsumables => exact absurd hmem (by decide)
    | sellIdle        => exact absurd hmem (by decide)
    | recycleSurplus  => exact absurd hmem (by decide)
    | bankExpand      => exact absurd hmem (by decide)
    | drainBankJunk   => exact absurd hmem (by decide)
    | wait            => exact absurd hmem (by decide)

/-- **The geared reach-50 capstone.**

    Every below-50 geared cycle strictly decreases the 20-slot lex `EMeasure`
    (top slot `50 - level`), so some finite iterate reaches 50.

    CONDITIONAL on `AdequateArmsFightAt` holding along the trajectory. That
    hypothesis is the production arming observation, and it is NAMED here rather
    than installed by `perceptionRefreshE` — see the history note on
    `AdequateArmsFightAt`. It is quantified per-iterate because the `∀ s` form is
    false and would make this vacuous.

    Non-vacuity: `adequateArmsFight_satisfiable_with_goal` below. -/
theorem ai_reaches_fifty_geared (s : State)
    (hArms : ∀ k, AdequateArmsFightAt (cycleStepEN k s)) :
    ∃ k, (cycleStepEN k s).level ≥ 50 :=
  exists_level_ge_of_edescent (fun k => cycleStepEN k s) (fun k hk => by
    show eMeasureLt (eMeasure (cycleStepEN (k + 1) s)) (eMeasure (cycleStepEN k s))
    rw [cycleStepEN_succ_outer k s]
    exact cycleStepE_descends_below_fifty (cycleStepEN k s) (hArms k) hk)

/-- **Non-vacuity check.** The residual and the goal hold TOGETHER — the
    degenerate `≥ 50` witness (residual vacuous at every iterate by level
    monotonicity, goal at `k = 0`).

    This is the check the 2026-06-19 vacuity finding taught us to write: the old
    i.o.-fairness residuals could provably NEVER coexist with the goal, which is
    exactly what made those capstones vacuous. Mirrors
    `LevelingDescent.fights_below_cap_satisfiable_with_goal`, and needs
    `cycleStepEN_level_ge` — a lemma the E-tower did not have until the honest
    restatement forced it. -/
theorem adequateArmsFight_satisfiable_with_goal (s : State) (h : s.level ≥ 50) :
    (∀ k, AdequateArmsFightAt (cycleStepEN k s))
      ∧ ∃ k, (cycleStepEN k s).level ≥ 50 := by
  refine ⟨fun k hk => absurd hk (by have := cycleStepEN_level_ge s k; omega), 0, ?_⟩
  rw [cycleStepEN_zero]; exact h

/-! ## `GEAR_CAP` grounding (increment 3 of the honest-restatement spec).

`CycleStepE.gearProgress` decrements `gearGap` by one per `.gearReview` cycle and
restores adequacy at zero, so `CycleStepE.GEAR_CAP` — the value `gearGap` is reset
to on a band change — must bound the number of ACQUISITION STEPS for a band's
witness loadout.

The bound is computed IN-KERNEL from `loadoutCodes.length` over the witness rows.
Nothing is trusted from the generator: had we instead emitted a
`witnessClosureDepth` column, the certificate would only be as good as the Python
that produced it, and `generate_lean_fixture.py:72-78` silently defaults depths on
cycle detection behind a `print(f"WARN: ...")` — a fabricated number the kernel
would then have pinned as truth.

HISTORY: `GEAR_CAP` was `8`, self-declared provisional. That was FALSE against
this very fixture — 20 of the 49 rows carry loadouts larger than 8, up to 11. -/
theorem witness_loadout_le_gear_cap :
    Formal.Liveness.GameDataFixture.acquirableWitness.all
      (fun r => r.loadoutCodes.length ≤ GEAR_CAP) = true := by
  decide

/-- The bound is TIGHT: some band actually needs all `GEAR_CAP` steps. Without
    this a future edit could inflate `GEAR_CAP` to silence the bound above
    instead of confronting a genuinely larger loadout. -/
theorem witness_loadout_attains_gear_cap :
    Formal.Liveness.GameDataFixture.acquirableWitness.any
      (fun r => r.loadoutCodes.length == GEAR_CAP) = true := by
  decide

/-- The witness table is non-empty, so the two bounds above are not vacuous over
    an empty list. -/
theorem Formal.Liveness.GameDataFixture.acquirableWitness_nonempty : Formal.Liveness.GameDataFixture.acquirableWitness ≠ [] := by decide


end Formal.Liveness.GearedDescent
