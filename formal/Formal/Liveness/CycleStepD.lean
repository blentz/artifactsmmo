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
   conjuncts (`Plan.phaseActive`, `taskProgress < taskTotal`) make it
   self-certifying. (Until Phase 5-2c-iii-c-2 #4 they were the facts the
   PURSUE_TASK descent needed; that rung is retired.)
2. **Mint-driven chore re-arm** (`choreRearm` / `rearmOnMint`, Phase A1): EVERY
   cycle that dispatches a `.fight` re-arms ALL 7 chore latches (worst case of
   loot), and the two MINTING chores re-arm the latches lex-below their own
   descent slot (claim → the 7 non-pending flags; completeTask → everything).
   Reach-50 still holds — each row's strict slot lex-dominates its re-arms.
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
    {accepted, inProgress} (`Plan.phaseActive`) with work remaining
    (`taskProgress < taskTotal`), so the conjuncts under-approximate nothing. -/
def deferGate (s : State) : Bool :=
  s.itemsTaskDeferActive
  && Formal.Liveness.Plan.phaseActive s
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

/-- Phase-A2 worst-case debt restored by a mint: the number of extra chore
    batches a single loot/mint event can create. Provisional constant (like
    `DROP_BOUND`); every lemma is agnostic to its value — a raise at a debt
    slot is always lex-dominated by the minting row's own descent. -/
def DEBT_CAP : Nat := 8

/-- Worst-case chore re-arm: arm ALL 7 chore latches AND restore the three
    multi-batch debts to `DEBT_CAP`. Over-approximates any loot-driven
    production re-arming. -/
def choreRearm (st : State) : State :=
  { st with hasOverstockItems := true,
            selectBankDepositsNonempty := true,
            sellableInventoryNonempty := true,
            recyclableSurplusNonempty := true,
            craftReliefFires := true,
            craftPotionsFires := true,
            pendingItemsNonempty := true,
            overstockDebt := DEBT_CAP,
            depositDebt := DEBT_CAP,
            sellDebt := DEBT_CAP }

/-- The met-task turn-in's mint re-arm (Phase 5-2c-iii-c-2 #6): the objective
    step dispatches `.completeTask` exactly when its Bool is unarmed and the
    held task is met (`planFor .objectiveStep`, non-fight branch), and the
    task reward then re-arms every chore latch — what the retired
    COMPLETE_TASK rung's `rearmOnMint` row did. -/
def turnInRearm (r st : State) : State :=
  if !r.objectiveStepFires && decide (r.taskLifecyclePhase = .complete)
  then choreRearm st else st

/-- No turn-in, no re-arm: a stale-armed Bool or a non-met phase leaves the
    objective step's post-state untouched by `turnInRearm`. -/
theorem turnInRearm_of_not_turnIn {r : State} (st : State)
    (h : r.objectiveStepFires = true ∨ r.taskLifecyclePhase ≠ .complete) :
    turnInRearm r st = st := by
  unfold turnInRearm
  rcases h with h | h
  · simp [h]
  · simp [h]

/-- Phase-A1 mint re-arm map. Fight dispatches re-arm EVERYTHING (worst case of
    loot). The two MINTING chores re-arm the flags lex-BELOW their own descent
    slot: `claimPending` (descends `pendingFlag`, slot 5) re-arms the 6 other
    chore latches — the formerly disclosed claim→overstock cross-arm, now
    modelled; the met-task turn-in (`.completeTask`, descends slot 1/3)
    re-arms everything incl. `pendingFlag` (task rewards mint pending items).
    Phase 5-2c-iii-c-2 #6: that turn-in is no longer a rung of its own — it is
    the objective step's dispatch when the step fired on a met held task alone
    (`planFor .objectiveStep`: Bool unarmed, phase `.complete`), so the re-arm
    is keyed on that dispatch. -/
def rearmOnMint (k : MeansKind) (r st : State) : State :=
  if dispatchesFight k r then choreRearm st
  else
    match k with
    | .claimPending =>
        { st with hasOverstockItems := true,
                  selectBankDepositsNonempty := true,
                  sellableInventoryNonempty := true,
                  recyclableSurplusNonempty := true,
                  craftReliefFires := true,
                  craftPotionsFires := true,
                  overstockDebt := DEBT_CAP,
                  depositDebt := DEBT_CAP,
                  sellDebt := DEBT_CAP }
    | .objectiveStep => turnInRearm r st
    | _ => st

/-- Dispatch-keyed inventory pressure: fight loot on actual fight dispatch;
    claim mint and reducer drains as in `pressureDelta`; the synthetic
    placeholder (and every other non-fight means) leaves pressure unchanged. -/
def pressureDeltaD (k : MeansKind) (r st : State) : State :=
  if dispatchesFight k r then
    { st with inventoryUsed := min st.inventoryMax (st.inventoryUsed + DROP_BOUND) }
  else
    match k with
    | .claimPending => { st with inventoryUsed := min st.inventoryMax (st.inventoryUsed + 1) }
    -- CORRECTED 2026-07-22: reducers make NO drain claim. The `-> 0` model was
    -- falsified by docs/REVIEW_pressuredelta_differential.md (no production
    -- reducer drops the bag below the 85% watermark); see the long note in
    -- InventoryDynamics.lean. Latch behaviour is carried by `partialClear`.
    | _ => st

/-- Phase-A2 partial clear: the three multi-batch chores clear their latch
    only when the debt is exhausted; otherwise the apply's clear is UNDONE
    (latch re-armed) and the debt strictly decrements — production needing
    `debt + 1` batches, modelled step for step. -/
def partialClear (k : MeansKind) (st : State) : State :=
  match k with
  | .discardCritical | .discardHigh =>
      if st.overstockDebt = 0 then st
      else { st with hasOverstockItems := true, overstockDebt := st.overstockDebt - 1 }
  | .depositFull =>
      if st.depositDebt = 0 then st
      else { st with selectBankDepositsNonempty := true, depositDebt := st.depositDebt - 1 }
  | .sellPressured | .sellRelief =>
      if st.sellDebt = 0 then st
      else { st with sellableInventoryNonempty := true, sellDebt := st.sellDebt - 1 }
  | _ => st

/-- One defer-faithful cycle: gated refresh, ladder select, apply,
    dispatch-keyed pressure, partial clear, mint re-arm. -/
noncomputable def cycleStepD (s : State) : State :=
  match productionLadder (perceptionRefreshD s) with
  | some k =>
      rearmOnMint k (perceptionRefreshD s)
        (partialClear k
          (pressureDeltaD k (perceptionRefreshD s) (cycleStep (perceptionRefreshD s))))
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
Bools; `rearmOnMint`/`choreRearm` mutate only the 7 chore latches;
`pressureDeltaD` mutates only `inventoryUsed`. -/

theorem perceptionRefreshD_level (s : State) :
    (perceptionRefreshD s).level = s.level := by
  unfold perceptionRefreshD; split <;> rfl

theorem perceptionRefreshD_xp (s : State) :
    (perceptionRefreshD s).xp = s.xp := by
  unfold perceptionRefreshD; split <;> rfl

theorem rearmOnMint_level (k : MeansKind) (r st : State) :
    (rearmOnMint k r st).level = st.level := by
  unfold rearmOnMint turnInRearm choreRearm; split
  · rfl
  · cases k <;> first | rfl | (dsimp only; split <;> rfl)

theorem rearmOnMint_xp (k : MeansKind) (r st : State) :
    (rearmOnMint k r st).xp = st.xp := by
  unfold rearmOnMint turnInRearm choreRearm; split
  · rfl
  · cases k <;> first | rfl | (dsimp only; split <;> rfl)

theorem partialClear_level (k : MeansKind) (st : State) :
    (partialClear k st).level = st.level := by
  cases k <;> simp [partialClear, apply_ite]

theorem partialClear_xp (k : MeansKind) (st : State) :
    (partialClear k st).xp = st.xp := by
  cases k <;> simp [partialClear, apply_ite]

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
  | some k => rw [rearmOnMint_level, partialClear_level, pressureDeltaD_level]

/-- Xp bridge. -/
theorem cycleStepD_xp (s : State) :
    (cycleStepD s).xp = (cycleStep (perceptionRefreshD s)).xp := by
  unfold cycleStepD
  cases productionLadder (perceptionRefreshD s) with
  | none => rfl
  | some k => rw [rearmOnMint_xp, partialClear_xp, pressureDeltaD_xp]

end Formal.Liveness.CycleStepD
