import Formal.Liveness.PerceptionRefresh
import Formal.Liveness.BootstrapReach

/-! # CycleStepP — Brick 2: the perception-refreshed cycle reaches `bankRequiredLevel`

Brick 1 (`PerceptionRefresh`) supplied the re-arming step `perceptionRefresh` and
the field/fire preservation bridges. This module composes it with the pure
transition,

```
cycleStepP s := cycleStep (perceptionRefresh s)
```

and transfers B-0's bootstrap descent (`BootstrapReach`) to the refreshed cycle:
the model that re-arms `objectiveStepFires` every cycle still provably reaches
`bankRequiredLevel`. PURELY ADDITIVE — `cycleStep`, `perceptionRefresh`, B-0, and
every existing def/theorem are untouched.

The transfer is mechanical because `perceptionRefresh` is the IDENTITY on every
field the bootstrap-window descent reads (level/xp/hp/maxHp/bankRequiredLevel,
and the task/skill/inventory measure fields), and it preserves every
bootstrap-window fire predicate (none read the two objective Bools). So:

* `perceptionRefresh_measure` — the lex `Measure` is unchanged by the refresh
  (it reads only preserved fields), via `unfold perceptionRefresh Measure.measure;
  split <;> rfl`.
* `cycleStepP_fights_in_window` — the analog of
  `BootstrapReach.cycleStep_fights_in_window`: under the window hyps on `s`, the
  refreshed cycle runs `.fight` (convert hyps to `perceptionRefresh s` via the
  Brick-1 fire/level bridges, then apply B-0's window-fight lemma).
* `cycleStepP_window_step_decreases_measure` — one refreshed cycle strictly
  descends the measure in the window.
* `cycleStepP_reaches_bankRequiredLevel` — **Brick-2 capstone.** Mirrors B-0's
  well-founded recursion on `measureLt`: the quiet prefix persists because BOTH
  `perceptionRefresh` AND `.fight` preserve `hp`/`maxHp`/`restForCombatReady` and
  `bankRequiredLevel`, so `cycleStepP` keeps hpCritical/restForCombat quiet and
  `bankRequiredLevel` invariant exactly as `cycleStep` does. Axioms match B-0's
  `reaches_bankRequiredLevel`: {propext, Quot.sound, xpToNextLevel}.

Liveness namespace — Mathlib allowed (inherited via BootstrapReach).
-/

namespace Formal.Liveness.CycleStepP

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.PlanAction
open Formal.Liveness.Plan
open Formal.Liveness.CycleStep
open Formal.Liveness.CumulativeProgress
open Formal.Liveness.PerceptionRefresh
open Formal.Liveness.BootstrapReach

/-! ## The perception-refreshed cycle and its iterate -/

/-- **The perception-refreshed cycle step.** Re-arm the combat objective
(`perceptionRefresh`) and then run the pure transition (`cycleStep`).
`noncomputable` because `cycleStep` is (it projects through the axiomatic
`xpToNextLevel`); mirrors `CumulativeProgress.cycleStepN`. -/
noncomputable def cycleStepP (s : State) : State := cycleStep (perceptionRefresh s)

/-- Iterated perception-refreshed cycle. Mirrors
`CumulativeProgress.cycleStepN`. -/
noncomputable def cycleStepPN : Nat → State → State
  | 0,     s => s
  | n + 1, s => cycleStepPN n (cycleStepP s)

@[simp] theorem cycleStepPN_zero (s : State) : cycleStepPN 0 s = s := rfl

theorem cycleStepPN_succ (n : Nat) (s : State) :
    cycleStepPN (n + 1) s = cycleStepPN n (cycleStepP s) := rfl

/-! ## The refresh leaves the lex measure unchanged

`Measure.measure` reads only `level`/`xp`/`taskTotal`/`taskProgress`/
`targetSkillLevel`/`trackedSkillLevel`/`inventoryUsed`/`inventoryMax`/`maxHp`/
`hp` — every one preserved by `perceptionRefresh` (which touches ONLY the two
objective Bools). So the measure is invariant under the refresh. -/

/-- `perceptionRefresh` leaves the lex `Measure` unchanged — it reads only fields
the refresh preserves. -/
theorem perceptionRefresh_measure (s : State) :
    Measure.measure (perceptionRefresh s) = Measure.measure s := by
  unfold perceptionRefresh Measure.measure; split <;> rfl

/-! ## The window always fights — transferred to the refreshed cycle -/

/-- **The refreshed window always fights.** The analog of
`BootstrapReach.cycleStep_fights_in_window`: in the under-`bankRequiredLevel`
window with hpCritical/restForCombat quiet ON `s`, the refreshed cycle runs
`.fight` on `perceptionRefresh s`. The Brick-1 fire/level bridges convert the
window hyps on `s` to hyps on `perceptionRefresh s` (the refresh touches neither
the fire predicates nor `level`/`bankRequiredLevel`), then B-0's window-fight
lemma applies. -/
theorem cycleStepP_fights_in_window (s : State)
    (h0 : fires .hpCritical s = false) (h1 : fires .restForCombat s = false)
    (hbr : s.bankRequiredLevel > 0) (hlt : s.level < s.bankRequiredLevel)
    (hgap : s.bankRequiredLevel - s.level ≤ MAX_ACHIEVABLE_GAP_LV2) :
    cycleStepP s = applyActionKind .fight (perceptionRefresh s) := by
  have h0' : fires .hpCritical (perceptionRefresh s) = false := by
    rw [perceptionRefresh_fires_hpCritical]; exact h0
  have h1' : fires .restForCombat (perceptionRefresh s) = false := by
    rw [perceptionRefresh_fires_restForCombat]; exact h1
  have hbr' : (perceptionRefresh s).bankRequiredLevel > 0 := by
    rw [perceptionRefresh_bankRequiredLevel]; exact hbr
  have hlt' : (perceptionRefresh s).level < (perceptionRefresh s).bankRequiredLevel := by
    rw [perceptionRefresh_level, perceptionRefresh_bankRequiredLevel]; exact hlt
  have hgap' :
      (perceptionRefresh s).bankRequiredLevel - (perceptionRefresh s).level
        ≤ MAX_ACHIEVABLE_GAP_LV2 := by
    rw [perceptionRefresh_level, perceptionRefresh_bankRequiredLevel]; exact hgap
  unfold cycleStepP
  exact cycleStep_fights_in_window (perceptionRefresh s) h0' h1' hbr' hlt' hgap'

/-! ## The refreshed window step strictly descends the measure -/

/-- **The refreshed window's per-cycle measure descent.** One `cycleStepP` in the
under-`bankRequiredLevel` window strictly decreases the lex measure. Chains B-0's
`window_step_decreases_measure` on `perceptionRefresh s` (giving
`measureLt (measure (cycleStep (perceptionRefresh s))) (measure (perceptionRefresh s))`)
with `perceptionRefresh_measure` (the refresh leaves the measure of `s` unchanged)
and the definitional `cycleStep (perceptionRefresh s) = cycleStepP s`. -/
theorem cycleStepP_window_step_decreases_measure (s : State)
    (h0 : fires .hpCritical s = false) (h1 : fires .restForCombat s = false)
    (hbr : s.bankRequiredLevel > 0) (hlt : s.level < s.bankRequiredLevel)
    (hgap : s.bankRequiredLevel - s.level ≤ MAX_ACHIEVABLE_GAP_LV2)
    (hcap : s.bankRequiredLevel ≤ 50) :
    measureLt (Measure.measure (cycleStepP s)) (Measure.measure s) := by
  have h0' : fires .hpCritical (perceptionRefresh s) = false := by
    rw [perceptionRefresh_fires_hpCritical]; exact h0
  have h1' : fires .restForCombat (perceptionRefresh s) = false := by
    rw [perceptionRefresh_fires_restForCombat]; exact h1
  have hbr' : (perceptionRefresh s).bankRequiredLevel > 0 := by
    rw [perceptionRefresh_bankRequiredLevel]; exact hbr
  have hlt' : (perceptionRefresh s).level < (perceptionRefresh s).bankRequiredLevel := by
    rw [perceptionRefresh_level, perceptionRefresh_bankRequiredLevel]; exact hlt
  have hgap' :
      (perceptionRefresh s).bankRequiredLevel - (perceptionRefresh s).level
        ≤ MAX_ACHIEVABLE_GAP_LV2 := by
    rw [perceptionRefresh_level, perceptionRefresh_bankRequiredLevel]; exact hgap
  have hcap' : (perceptionRefresh s).bankRequiredLevel ≤ 50 := by
    rw [perceptionRefresh_bankRequiredLevel]; exact hcap
  have hstep :=
    window_step_decreases_measure (perceptionRefresh s) h0' h1' hbr' hlt' hgap' hcap'
  -- rewrite measure (perceptionRefresh s) = measure s and fold the cycleStepP def.
  rw [perceptionRefresh_measure] at hstep
  exact hstep

/-! ## Step-preservation along the refreshed cycle — the quiet prefix persists

The well-founded recursion needs the window hyps to PERSIST across `cycleStepP`.
In the window, `cycleStepP s = applyActionKind .fight (perceptionRefresh s)`, and
BOTH `perceptionRefresh` and `.fight` preserve `hp`/`maxHp`/`restForCombatReady`
(so hpCritical/restForCombat stay quiet) and `bankRequiredLevel`. -/

/-- In the window, `cycleStepP` keeps hpCritical quiet: it composes to
`.fight ∘ perceptionRefresh`, and both preserve the hpCritical fire. -/
theorem cycleStepP_preserves_hpCriticalFires_in_window (s : State)
    (h0 : fires .hpCritical s = false) (h1 : fires .restForCombat s = false)
    (hbr : s.bankRequiredLevel > 0) (hlt : s.level < s.bankRequiredLevel)
    (hgap : s.bankRequiredLevel - s.level ≤ MAX_ACHIEVABLE_GAP_LV2) :
    fires .hpCritical (cycleStepP s) = fires .hpCritical s := by
  rw [cycleStepP_fights_in_window s h0 h1 hbr hlt hgap,
      fightKind_preserves_hpCriticalFires, perceptionRefresh_fires_hpCritical]

/-- In the window, `cycleStepP` keeps restForCombat quiet: both
`perceptionRefresh` and `.fight` preserve the restForCombat fire. -/
theorem cycleStepP_preserves_restForCombatFires_in_window (s : State)
    (h0 : fires .hpCritical s = false) (h1 : fires .restForCombat s = false)
    (hbr : s.bankRequiredLevel > 0) (hlt : s.level < s.bankRequiredLevel)
    (hgap : s.bankRequiredLevel - s.level ≤ MAX_ACHIEVABLE_GAP_LV2) :
    fires .restForCombat (cycleStepP s) = fires .restForCombat s := by
  rw [cycleStepP_fights_in_window s h0 h1 hbr hlt hgap,
      fightKind_preserves_restForCombatFires, perceptionRefresh_fires_restForCombat]

open Formal.Liveness.BlockerMonotone in
/-- `cycleStepP` leaves `bankRequiredLevel` invariant: `perceptionRefresh`
preserves it (`perceptionRefresh_bankRequiredLevel`) and so does `cycleStep`
(`bankRequiredLevel_cycleStep`). Holds unconditionally (no window hyps). -/
theorem cycleStepP_bankRequiredLevel (s : State) :
    (cycleStepP s).bankRequiredLevel = s.bankRequiredLevel := by
  unfold cycleStepP
  rw [bankRequiredLevel_cycleStep, perceptionRefresh_bankRequiredLevel]

/-- `cycleStepP` never lowers `level` in the window: it composes to
`.fight ∘ perceptionRefresh`, the refresh preserves `level`, and `.fight` never
lowers it (`fightKind_level_ge`). -/
theorem cycleStepP_level_ge_in_window (s : State)
    (h0 : fires .hpCritical s = false) (h1 : fires .restForCombat s = false)
    (hbr : s.bankRequiredLevel > 0) (hlt : s.level < s.bankRequiredLevel)
    (hgap : s.bankRequiredLevel - s.level ≤ MAX_ACHIEVABLE_GAP_LV2) :
    s.level ≤ (cycleStepP s).level := by
  rw [cycleStepP_fights_in_window s h0 h1 hbr hlt hgap]
  calc s.level = (perceptionRefresh s).level := (perceptionRefresh_level s).symm
    _ ≤ (applyActionKind .fight (perceptionRefresh s)).level :=
        fightKind_level_ge (perceptionRefresh s)

/-! ## Descent assembly — well-founded recursion to `bankRequiredLevel` -/

/-- **Brick-2 capstone — the refreshed bootstrap window reaches
`bankRequiredLevel` in-model.** The `cycleStepPN` analog of
`BootstrapReach.reaches_bankRequiredLevel`: given the combat-rest interrupts
initially quiet and the window bounds, some finite number of refreshed cycles
drives `level` up to `bankRequiredLevel` — with NO perception or chore-fairness
hypothesis (the `hfightFires` disjunct is FREE in the bootstrap window, exactly as
in B-0). The proof mirrors B-0's well-founded recursion on the lex `Measure`
(`measureLt_wellFounded`): each in-window `cycleStepP` strictly descends the
measure (`cycleStepP_window_step_decreases_measure`), and the quiet prefix
PERSISTS because BOTH `perceptionRefresh` and `.fight` preserve `hp`/`maxHp`/
`restForCombatReady` and `bankRequiredLevel`
(`cycleStepP_preserves_*Fires_in_window`, `cycleStepP_bankRequiredLevel`,
`cycleStepP_level_ge_in_window`). Axioms = {propext, Quot.sound, xpToNextLevel
(LIV-001)} — the same set as B-0's capstone. -/
theorem cycleStepP_reaches_bankRequiredLevel (s : State)
    (h0 : fires .hpCritical s = false) (h1 : fires .restForCombat s = false)
    (hbr : s.bankRequiredLevel > 0)
    (hgap : s.bankRequiredLevel - s.level ≤ MAX_ACHIEVABLE_GAP_LV2)
    (hcap : s.bankRequiredLevel ≤ 50) :
    ∃ k, (cycleStepPN k s).level ≥ s.bankRequiredLevel := by
  let R : State → State → Prop :=
    fun s₁ s₂ => measureLt (Measure.measure s₁) (Measure.measure s₂)
  have hRwf : WellFounded R := InvImage.wf Measure.measure measureLt_wellFounded
  suffices hgen : ∀ t : State,
      fires .hpCritical t = false → fires .restForCombat t = false →
      t.bankRequiredLevel > 0 →
      t.bankRequiredLevel - t.level ≤ MAX_ACHIEVABLE_GAP_LV2 →
      t.bankRequiredLevel ≤ 50 →
      ∃ k, (cycleStepPN k t).level ≥ t.bankRequiredLevel by
    exact hgen s h0 h1 hbr hgap hcap
  intro t0
  apply hRwf.induction (C := fun t =>
    fires .hpCritical t = false → fires .restForCombat t = false →
    t.bankRequiredLevel > 0 →
    t.bankRequiredLevel - t.level ≤ MAX_ACHIEVABLE_GAP_LV2 →
    t.bankRequiredLevel ≤ 50 →
    ∃ k, (cycleStepPN k t).level ≥ t.bankRequiredLevel) t0
  intro t ih ht0 ht1 htbr htgap htcap
  by_cases hreached : t.level ≥ t.bankRequiredLevel
  · exact ⟨0, hreached⟩
  · replace hreached : t.level < t.bankRequiredLevel := Nat.not_le.mp hreached
    have hstep : R (cycleStepP t) t :=
      cycleStepP_window_step_decreases_measure t ht0 ht1 htbr hreached htgap htcap
    have hq0 : fires .hpCritical (cycleStepP t) = false := by
      rw [cycleStepP_preserves_hpCriticalFires_in_window t ht0 ht1 htbr hreached htgap]
      exact ht0
    have hq1 : fires .restForCombat (cycleStepP t) = false := by
      rw [cycleStepP_preserves_restForCombatFires_in_window t ht0 ht1 htbr hreached htgap]
      exact ht1
    have hbrl : (cycleStepP t).bankRequiredLevel = t.bankRequiredLevel :=
      cycleStepP_bankRequiredLevel t
    have hlvl_ge : t.level ≤ (cycleStepP t).level :=
      cycleStepP_level_ge_in_window t ht0 ht1 htbr hreached htgap
    have hbr' : (cycleStepP t).bankRequiredLevel > 0 := by rw [hbrl]; exact htbr
    have hcap' : (cycleStepP t).bankRequiredLevel ≤ 50 := by rw [hbrl]; exact htcap
    have hgap' :
        (cycleStepP t).bankRequiredLevel - (cycleStepP t).level ≤ MAX_ACHIEVABLE_GAP_LV2 := by
      rw [hbrl]; omega
    obtain ⟨k, hk⟩ := ih (cycleStepP t) hstep hq0 hq1 hbr' hgap' hcap'
    refine ⟨k + 1, ?_⟩
    rw [cycleStepPN_succ]
    rw [hbrl] at hk
    exact hk

/-! ## Brick 3 — the combat objective is armed along the refreshed trajectory

The refreshed cycle SELECTS on `perceptionRefresh (state)`, so the object the
capstone reasons about at step `k` is `perceptionRefresh (cycleStepPN k s)` and the
arming that matters is `objectiveStepFires (perceptionRefresh (cycleStepPN k s))`.
Below the cap, that selection state is provably armed — immediate from Brick 1
applied to `cycleStepPN k s`. This is the in-model fact the capstone needs to
discharge the objective-committed half of `hfightFires` for `cycleStepP`. -/

/-- **Brick-3 arming: `objectiveStepFires` on the refreshed selection state.**
Below the cap, the state the refreshed cycle SELECTS on
(`perceptionRefresh (cycleStepPN k s)`) has `objectiveStepFires = true`. Immediate
from Brick 1's `perceptionRefresh_objectiveStepFires` at `cycleStepPN k s`. -/
theorem cycleStepP_objectiveStepFires_armed (s : State) (k : Nat)
    (h : (cycleStepPN k s).level < 50) :
    (perceptionRefresh (cycleStepPN k s)).objectiveStepFires = true :=
  perceptionRefresh_objectiveStepFires (cycleStepPN k s) h

/-- **Brick-3 arming: `objectiveStepIsFight` on the refreshed selection state.**
Below the cap, the refreshed selection state's committed objective is combat-typed
(`objectiveStepIsFight = true`). Immediate from Brick 1's
`perceptionRefresh_objectiveStepIsFight` at `cycleStepPN k s`. -/
theorem cycleStepP_objectiveStepIsFight_armed (s : State) (k : Nat)
    (h : (cycleStepPN k s).level < 50) :
    (perceptionRefresh (cycleStepPN k s)).objectiveStepIsFight = true :=
  perceptionRefresh_objectiveStepIsFight (cycleStepPN k s) h

/-- **Brick-3 frontier overturn (the headline).** `SettledReach.
objectiveStepFires_false_cycleStepN` shows the PURE transition never sets
`objectiveStepFires = true`: from a spawn with it `false` it stays `false` forever,
so `Settled` (hence the general leveling path) is unreachable WITHOUT perception
(`SettledReach.Settled_unreachable_without_perception`). This lemma is the precise
contrast for the REFRESHED cycle: at every step `k` with `level < 50`, the state
the refreshed cycle actually SELECTS on — `perceptionRefresh (cycleStepPN k s)` —
has `objectiveStepFires = true` AND `objectiveStepIsFight = true`, regardless of
the spawn value. So `perceptionRefresh` re-arms exactly what the pure transition
cleared: the frontier (`objectiveStepFires_false_cycleStepN`) is OVERTURNED for the
selection state of `cycleStepP`. This is what discharges the objective-committed
half of `hfightFires` once it is restated over the refreshed trajectory (Brick 4).
Note: the claim is about the SELECTION state `perceptionRefresh (cycleStepPN k s)`
— NOT `cycleStepP s` post-transition, which (by the same frontier lemma) `cycleStep`
would clear again; the re-arm is per-cycle, at the head of each refreshed step. -/
theorem cycleStepP_objective_armed_overturns_frontier (s : State) (k : Nat)
    (h : (cycleStepPN k s).level < 50) :
    (perceptionRefresh (cycleStepPN k s)).objectiveStepFires = true
    ∧ (perceptionRefresh (cycleStepPN k s)).objectiveStepIsFight = true :=
  ⟨cycleStepP_objectiveStepFires_armed s k h,
   cycleStepP_objectiveStepIsFight_armed s k h⟩

end Formal.Liveness.CycleStepP
