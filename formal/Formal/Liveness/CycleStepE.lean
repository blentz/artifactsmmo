import Formal.Liveness.CycleStepD

/-! # CycleStepE — the GEARED cycle (E-tower, C2b)

`docs/PLAN_c2_composed_liveness.md`. The defer-faithful cycle (`cycleStepD`)
with the combat-outcome gaps closed:

1. **Adequacy-gated arming** (`perceptionRefreshE`): below 50, outside the
   defer window, the combat objective is armed ONLY when `loadoutAdequate`
   (production image: the arbiter emits a fight step when `is_winnable`
   finds a band target for the CURRENT gear). When inadequate it arms the
   GEAR latch instead (`gearReviewFires` — the UpgradeEquipment band): the
   model stops crediting xp for fights the real bot could not win, the
   gap-1 fix the B1/B2 trace phases measured.
2. **Gear progress** (`gearProgress`): a `.gearReview` cycle with
   `gearGap > 0` strictly decrements the gap; at an exhausted gap the cycle
   RESTORES adequacy (paid at the measure's `inadequacyFlag` slot) —
   the A2 debt pattern at gear scale, grounded offline by the EMPTY
   acquirable frontier (`WitnessAcquirable.acquirableFrontier_empty`: every
   band's witness loadout is closure-obtainable, so the gap is always
   finitely dischargeable).
3. **Rollover gear re-arm** (`rearmE`): a fight that levels up RESETS
   `gearGap := GEAR_CAP` and drops adequacy (new band, new witness target) —
   paid at the measure's slot 1. Non-rollover fights re-arm the chore
   latches as in the D-tower.
4. **Fight hp-loss** (`fightLoss`): every fight dispatch costs
   `FIGHT_LOSS_BOUND` hp (B1-measured worst case 270, death included:
   at ≤ bound the character respawns at full hp). Raises only `hpDeficit` —
   dominated by the fight's slot-1/3 descent; the rest row heals as before.

Additive only — the D-tower and every existing theorem are untouched.
Liveness namespace — Mathlib allowed. -/

set_option linter.dupNamespace false

namespace Formal.Liveness.CycleStepE

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.CycleStep
open Formal.Liveness.InventoryDynamics
open Formal.Liveness.CycleStepD

/-- Gear re-arm size on a band change (provisional, lemma-agnostic — any raise
    at the gearGap slot is dominated by the rollover's slot-1 descent). -/
def GEAR_CAP : Nat := 8

/-- Worst-case hp loss of one fight (B1 trace measurement: max observed 270).
    Lemma-agnostic.

    FAITHFULNESS NOTE (2026-07-20). This is a trace-measured worst case, NOT the
    production planner's projection, which is `max(1, max_hp / 5)`
    (`ai/actions/combat.py:121`). 270 is the larger loss for any `maxHp < 1350`,
    so the model is PESSIMISTIC here relative to the bot's own projection — the
    safe direction for a descent argument. The two are not the same quantity and
    this docstring previously did not say so. -/
def FIGHT_LOSS_BOUND : Nat := 270

/-- Adequacy-gated arming: fight objective when adequate, gear latch when not;
    identity inside the defer window and at/above the cap. -/
def perceptionRefreshE (s : State) : State :=
  if s.level < 50 && !(deferGate s) then
    if s.loadoutAdequate then
      { s with objectiveStepFires := true, objectiveStepIsFight := true }
    else
      { s with gearReviewFires := true }
  else s

/-- Gear progress: a gear-review cycle with an open gap closes one step and
    restores adequacy exactly at zero. -/
def gearProgress (k : MeansKind) (st : State) : State :=
  match k with
  | .gearReview =>
      if st.gearGap = 0 then { st with loadoutAdequate := true }
      else { st with gearGap := st.gearGap - 1,
                     loadoutAdequate := decide (st.gearGap - 1 = 0) }
  | _ => st

/-- Fight hp cost, flooring at 1 hp.

    CORRECTED 2026-07-20 (adversarial review). The below-bound case previously
    read `hp := st.maxHp` — "death → respawn at full". That was unfaithful in the
    direction that FLATTERS the proof: `hpDeficit = maxHp - hp` is EMeasure slot
    18, so respawning made a death decrease the measure MORE than surviving a
    fight did. The model priced dying better than winning, and a bot that died to
    every monster still reached 50.

    Production never dies and never restores: `FightAction.apply` computes
    `new_hp = max(1, hp - estimated_hp_cost)` (`ai/actions/combat.py:120-122`).
    The floor is now 1, mirroring that. Descent is unaffected — a fight descends
    slot 1 (`levelDeficit`) or slot 4 (`xpDeficit`), both of which lex-dominate
    slot 18 — so the correction costs only the flattering case. -/
def fightLoss (k : MeansKind) (r st : State) : State :=
  if dispatchesFight k r then
    if FIGHT_LOSS_BOUND < st.hp then { st with hp := st.hp - FIGHT_LOSS_BOUND }
    else { st with hp := 1 }
  else st

/-- Fight re-arm: rollover fights reset the gear fields (new band) on top of
    the D-tower's worst-case chore re-arm; the mint re-arms are unchanged. -/
def rearmE (k : MeansKind) (r st : State) : State :=
  if dispatchesFight k r && decide (r.level < st.level) then
    { (rearmOnMint k r st) with gearGap := GEAR_CAP, loadoutAdequate := false }
  else rearmOnMint k r st

/-- One geared cycle. -/
noncomputable def cycleStepE (s : State) : State :=
  match productionLadder (perceptionRefreshE s) with
  | some k =>
      rearmE k (perceptionRefreshE s)
        (gearProgress k
          (fightLoss k (perceptionRefreshE s)
            (partialClear k
              (pressureDeltaD k (perceptionRefreshE s)
                (cycleStep (perceptionRefreshE s))))))
  | none => cycleStep (perceptionRefreshE s)

/-- `n`-fold geared cycle. -/
noncomputable def cycleStepEN : Nat → State → State
  | 0,     s => s
  | n + 1, s => cycleStepEN n (cycleStepE s)

@[simp] theorem cycleStepEN_zero (s : State) : cycleStepEN 0 s = s := rfl

theorem cycleStepEN_succ (n : Nat) (s : State) :
    cycleStepEN (n + 1) s = cycleStepEN n (cycleStepE s) := rfl

theorem cycleStepEN_succ_outer (n : Nat) (s : State) :
    cycleStepEN (n + 1) s = cycleStepE (cycleStepEN n s) := by
  induction n generalizing s with
  | zero => rfl
  | succ n ih =>
      rw [cycleStepEN_succ, ih, cycleStepEN_succ]

/-! ## Field bridges. -/

theorem perceptionRefreshE_level (s : State) :
    (perceptionRefreshE s).level = s.level := by
  unfold perceptionRefreshE
  split
  · split <;> rfl
  · rfl

theorem perceptionRefreshE_xp (s : State) :
    (perceptionRefreshE s).xp = s.xp := by
  unfold perceptionRefreshE
  split
  · split <;> rfl
  · rfl

theorem gearProgress_level (k : MeansKind) (st : State) :
    (gearProgress k st).level = st.level := by
  cases k <;> simp [gearProgress, apply_ite]

theorem gearProgress_xp (k : MeansKind) (st : State) :
    (gearProgress k st).xp = st.xp := by
  cases k <;> simp [gearProgress, apply_ite]

theorem fightLoss_level (k : MeansKind) (r st : State) :
    (fightLoss k r st).level = st.level := by
  unfold fightLoss
  split
  · split <;> rfl
  · rfl

theorem fightLoss_xp (k : MeansKind) (r st : State) :
    (fightLoss k r st).xp = st.xp := by
  unfold fightLoss
  split
  · split <;> rfl
  · rfl

theorem rearmE_level (k : MeansKind) (r st : State) :
    (rearmE k r st).level = st.level := by
  unfold rearmE
  split
  · exact rearmOnMint_level k r st
  · exact rearmOnMint_level k r st

theorem rearmE_xp (k : MeansKind) (r st : State) :
    (rearmE k r st).xp = st.xp := by
  unfold rearmE
  split
  · exact rearmOnMint_xp k r st
  · exact rearmOnMint_xp k r st

/-- Level bridge to the refreshed-applied state. -/
theorem cycleStepE_level (s : State) :
    (cycleStepE s).level = (cycleStep (perceptionRefreshE s)).level := by
  unfold cycleStepE
  cases productionLadder (perceptionRefreshE s) with
  | none => rfl
  | some k =>
      rw [rearmE_level, gearProgress_level, fightLoss_level,
        partialClear_level, pressureDeltaD_level]

/-- Xp bridge. -/
theorem cycleStepE_xp (s : State) :
    (cycleStepE s).xp = (cycleStep (perceptionRefreshE s)).xp := by
  unfold cycleStepE
  cases productionLadder (perceptionRefreshE s) with
  | none => rfl
  | some k =>
      rw [rearmE_xp, gearProgress_xp, fightLoss_xp,
        partialClear_xp, pressureDeltaD_xp]

end Formal.Liveness.CycleStepE
