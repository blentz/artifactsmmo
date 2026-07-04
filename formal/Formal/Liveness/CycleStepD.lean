import Formal.Liveness.CycleStepCharacterization
import Formal.Liveness.InventoryDynamics

/-! # CycleStepD — the defer-faithful, adversarially-re-arming cycle

Brick D2 of `docs/PLAN_residual_closure.md`. Three refinements over
`cycleStepF`, each closing (or worst-casing) a named residual of
`docs/LEVEL_FIFTY_RESIDUALS.md`:

1. **Defer-gated arming** (`perceptionRefreshD`): the combat objective is armed
   below 50 ONLY outside the items-task long-haul defer window
   (`deferGate`). Inside the window the cycle pursues the items task —
   production's actual behaviour in the one branch the F-tower
   over-approximated (residual 3). `itemsTaskDeferActive` is a state-carried
   production observation (opaque-Bool discipline); the gate's other two
   conjuncts (`pursueTaskFires`, `taskProgress < taskTotal`) make it
   self-certifying: they are exactly the facts the pursueTask descent needs.
2. **Adversarial chore re-arm** (`choreRearm` / `rearmIfFight`): EVERY cycle
   that dispatches a `.fight` re-arms ALL 8 chore latches — the worst case of
   production's loot-driven re-arming (residual 4, fight direction). Reach-50
   still holds because a fight descends slots 1/2, which lex-dominate every
   flag.
3. **Dispatch-keyed loot** (`pressureDeltaD`): the inventory fill applies iff
   the cycle actually dispatches a `.fight` — the synthetic
   `.objectiveStep` placeholder (a stale-armed Bool inside the defer window)
   loots nothing, matching its no-op production meaning.

Additive only — `cycleStepF` and every existing theorem are untouched.
Liveness namespace — Mathlib allowed. -/

set_option linter.dupNamespace false

namespace Formal.Liveness.CycleStepD

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.CycleStep
open Formal.Liveness.InventoryDynamics

/-- The items-task long-haul DEFER window: production's observed defer decision
    AND the facts making the window self-certifying for the descent proof.
    Production (`test_objectivestep_arming_diff.py`): defer ⟺ `bootstrap_gap >
    4 ∧ items-task active` — an active items task means phase ∈
    {accepted, inProgress} (`pursueTaskFires`) with work remaining
    (`taskProgress < taskTotal`), so the conjuncts under-approximate nothing. -/
def deferGate (s : State) : Bool :=
  s.itemsTaskDeferActive
  && pursueTaskFires s
  && decide (s.taskProgress < s.taskTotal)

/-- Defer-gated perception: arm the combat objective below the cap ONLY outside
    the defer window. Outside it this is exactly `perceptionRefresh` (grounded
    by the arming differential); inside it the state passes through untouched
    and the ladder falls to the items-task means. -/
def perceptionRefreshD (s : State) : State :=
  if s.level < 50 && !(deferGate s)
  then { s with objectiveStepFires := true, objectiveStepIsFight := true }
  else s

/-- Whether the selected means dispatches an actual `.fight` (`planFor` head). -/
def dispatchesFight (k : MeansKind) (r : State) : Bool :=
  match k with
  | .bankUnlock | .reachUnlockLevel => true
  | .objectiveStep => r.objectiveStepIsFight
  | _ => false

/-- Worst-case chore re-arm: arm ALL 8 chore latches. Over-approximates any
    loot-driven production re-arming (loot cannot arm more than everything). -/
def choreRearm (st : State) : State :=
  { st with hasOverstockItems := true,
            selectBankDepositsNonempty := true,
            sellableInventoryNonempty := true,
            recyclableSurplusNonempty := true,
            craftReliefFires := true,
            craftPotionsFires := true,
            gearReviewFires := true,
            pendingItemsNonempty := true }

/-- Re-arm after fight dispatches only. -/
def rearmIfFight (k : MeansKind) (r st : State) : State :=
  if dispatchesFight k r then choreRearm st else st

/-- Dispatch-keyed inventory pressure: fight loot on actual fight dispatch;
    claim mint and reducer drains as in `pressureDelta`; the synthetic
    placeholder (and every other non-fight means) leaves pressure unchanged. -/
def pressureDeltaD (k : MeansKind) (r st : State) : State :=
  if dispatchesFight k r then
    { st with inventoryUsed := min st.inventoryMax (st.inventoryUsed + DROP_BOUND) }
  else
    match k with
    | .claimPending => { st with inventoryUsed := min st.inventoryMax (st.inventoryUsed + 1) }
    | .depositFull | .discardCritical | .discardHigh | .sellPressured | .craftRelief =>
        { st with inventoryUsed := 0 }
    | _ => st

/-- One defer-faithful cycle: gated refresh, ladder select, apply, dispatch-keyed
    pressure, worst-case re-arm on fights. -/
noncomputable def cycleStepD (s : State) : State :=
  match productionLadder (perceptionRefreshD s) with
  | some k =>
      rearmIfFight k (perceptionRefreshD s)
        (pressureDeltaD k (perceptionRefreshD s) (cycleStep (perceptionRefreshD s)))
  | none => cycleStep (perceptionRefreshD s)

/-- `n`-fold defer-faithful cycle. -/
noncomputable def cycleStepDN : Nat → State → State
  | 0,     s => s
  | n + 1, s => cycleStepDN n (cycleStepD s)

@[simp] theorem cycleStepDN_zero (s : State) : cycleStepDN 0 s = s := rfl

theorem cycleStepDN_succ (n : Nat) (s : State) :
    cycleStepDN (n + 1) s = cycleStepDN n (cycleStepD s) := rfl

/-- Outer-recursion form (mirror of `cycleStepFN_succ_outer`). -/
theorem cycleStepDN_succ_outer (n : Nat) (s : State) :
    cycleStepDN (n + 1) s = cycleStepD (cycleStepDN n s) := by
  induction n generalizing s with
  | zero => rfl
  | succ n ih =>
      rw [cycleStepDN_succ, ih, cycleStepDN_succ]

/-! ## Field bridges — `perceptionRefreshD` mutates only the two objective
Bools; `rearmIfFight`/`choreRearm` mutate only the 8 chore latches;
`pressureDeltaD` mutates only `inventoryUsed`. -/

theorem perceptionRefreshD_level (s : State) :
    (perceptionRefreshD s).level = s.level := by
  unfold perceptionRefreshD; split <;> rfl

theorem perceptionRefreshD_xp (s : State) :
    (perceptionRefreshD s).xp = s.xp := by
  unfold perceptionRefreshD; split <;> rfl

theorem rearmIfFight_level (k : MeansKind) (r st : State) :
    (rearmIfFight k r st).level = st.level := by
  unfold rearmIfFight choreRearm; split <;> rfl

theorem rearmIfFight_xp (k : MeansKind) (r st : State) :
    (rearmIfFight k r st).xp = st.xp := by
  unfold rearmIfFight choreRearm; split <;> rfl

theorem pressureDeltaD_level (k : MeansKind) (r st : State) :
    (pressureDeltaD k r st).level = st.level := by
  unfold pressureDeltaD; split
  · rfl
  · cases k <;> rfl

theorem pressureDeltaD_xp (k : MeansKind) (r st : State) :
    (pressureDeltaD k r st).xp = st.xp := by
  unfold pressureDeltaD; split
  · rfl
  · cases k <;> rfl

/-- Level bridge: the defer-faithful cycle's level is the refreshed-applied
    level (rearm/pressure never touch it). -/
theorem cycleStepD_level (s : State) :
    (cycleStepD s).level = (cycleStep (perceptionRefreshD s)).level := by
  unfold cycleStepD
  cases productionLadder (perceptionRefreshD s) with
  | none => rfl
  | some k => rw [rearmIfFight_level, pressureDeltaD_level]

/-- Xp bridge. -/
theorem cycleStepD_xp (s : State) :
    (cycleStepD s).xp = (cycleStep (perceptionRefreshD s)).xp := by
  unfold cycleStepD
  cases productionLadder (perceptionRefreshD s) with
  | none => rfl
  | some k => rw [rearmIfFight_xp, pressureDeltaD_xp]

end Formal.Liveness.CycleStepD
