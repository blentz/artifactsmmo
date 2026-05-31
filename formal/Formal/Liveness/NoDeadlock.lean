/-
  Formal.Liveness.NoDeadlock

  Phase-20b headline. Assembles Phase-20a's per-region firing lemmas
  (`Formal.Liveness.RegionFiring`) into the Tier-2 no-deadlock theorem:
  every planner-side state has at least one Phase-18 goal whose value is
  strictly positive.

  ## Two forms

  * **Strong**: `∀ s : State, ∃ g : FiringGoal, goalValueOf g s > 0`.

    The actual content. Phase 20a's region partition is EXHAUSTIVE on all
    `State`s (not just `Reachable s`) and each `RegionFiring` lemma takes
    only a `State` hypothesis — none of them mention `Reachable`. So the
    strong form is provable directly.

  * **Reachable corollary**: `∀ s, Reachable s → ∃ g, goalValueOf g s > 0`.

    Trivial weakening of the strong form. The `Reachable` hypothesis is
    UNUSED — disclosed in the docstring (per
    `feedback_proofs_tell_false_stories`: false-premise dressing is
    forbidden).

  ## FiringGoal — one constructor per region

  The Phase-20a partition picks exactly one goal per region:

      criticalHP            -> .restoreHp        (RestoreHPGoal,       110)
      pendingItemsWaiting   -> .claimPending     (ClaimPendingGoal,     25)
      taskComplete          -> .completeTask     (CompleteTaskGoal,     90)
      noTask                -> .acceptTask       (AcceptTaskGoal,       20)
      inventoryFull         -> .discardOverstock (DiscardOverstockGoal, ≥40)
      levelBlocker          -> .reachUnlockLevel (ReachUnlockLevelGoal, 85)
      bankLockedFightable   -> .unlockBank       (UnlockBankGoal,    ∈{30,90})
      progressNeeded        -> .pursueTask       (PursueTaskGoal,      ≥35)

  Liveness namespace — Mathlib axioms allowed.
-/
import Formal.Liveness.Measure
import Formal.Liveness.StateRegions
import Formal.Liveness.RegionFiring
import Formal.Liveness.Reachable

set_option linter.dupNamespace false

namespace Formal.Liveness.NoDeadlock

open Formal.Liveness.Measure
open Formal.Liveness.StateRegions
open Formal.Liveness.RegionFiring
open Formal.Liveness.Reachable
open Formal.GoalSystem
open Formal.GoalValueBands

/-! ## Firing-goal sum

One constructor per region of `Formal.Liveness.StateRegions.Region`. -/
inductive FiringGoal where
  | restoreHp
  | claimPending
  | completeTask
  | acceptTask
  | discardOverstock
  | reachUnlockLevel
  | unlockBank
  | pursueTask
  deriving DecidableEq, Repr

/-! ## Dispatch

Maps `FiringGoal` to its Phase-18 value function evaluated against `s`.
The branch arguments mirror the witness used in each `RegionFiring`
lemma — see comments. -/
noncomputable def goalValueOf : FiringGoal → State → Rat
  | .restoreHp,        s =>
      -- region_criticalHP_fires_restoreHP uses `hpPercentRat s`.
      restoreHpValue (hpPercentRat s)
  | .claimPending,     _ =>
      -- region_pendingItemsWaiting_fires_claimPending uses `satisfied=false`.
      claimPendingValue false
  | .completeTask,     _ =>
      -- region_taskComplete_fires_completeTask uses (satisfied=false, accepted=true).
      completeTaskValue false true
  | .acceptTask,       _ =>
      -- region_noTask_fires_acceptTask uses `satisfied=false`.
      acceptTaskValue false
  | .discardOverstock, _ =>
      -- region_inventoryFull_fires_discardOverstock uses (satisfied=false, pressure=0).
      -- The lemma is universally quantified over `pressure`; we pick 0.
      discardOverstockValue false 0
  | .reachUnlockLevel, s =>
      -- region_levelBlocker_fires_reachUnlockLevel uses
      -- (satisfied=false, targetLevel, unlockGap).
      reachUnlockLevelValue false (s.unlockTargetLevel : Int) (unlockGap s)
  | .unlockBank,       s =>
      -- region_bankLockedFightable_fires_unlockBank uses
      -- (bankLocked, bankXpExceeded, bankUnreachable, usedFraction=0, hasSellable=false).
      unlockBankValue s.bankLocked s.bankXpExceeded s.bankUnreachable 0 false
  | .pursueTask,       _ =>
      -- region_progressNeeded_fires_pursueTask uses bonus 0.
      pursueTaskValue 0

/-! ## Headline — strong form -/

/-- **Strong no-deadlock**: every State has at least one firing goal.

This is the load-bearing theorem. Phase 20a's `regionOf` is total on
all States and each `RegionFiring` lemma takes only a `State`
hypothesis (none of them mention `Reachable`), so the existence of a
positive-value goal follows by cases on `regionOf s`.

No `Reachable` hypothesis is needed. The Phase-20b plan's
`no_deadlock_reachable` corollary discharges the Reachable hypothesis
trivially. -/
theorem no_deadlock_strong :
    ∀ s : State, ∃ g : FiringGoal, goalValueOf g s > 0 := by
  intro s
  -- Split on the region of s and exhibit the goal whose firing lemma
  -- discharges that region.
  match hr : regionOf s with
  | .criticalHP =>
      refine ⟨.restoreHp, ?_⟩
      simpa [goalValueOf] using region_criticalHP_fires_restoreHP s hr
  | .pendingItemsWaiting =>
      refine ⟨.claimPending, ?_⟩
      simpa [goalValueOf] using
        region_pendingItemsWaiting_fires_claimPending s hr
  | .taskComplete =>
      refine ⟨.completeTask, ?_⟩
      simpa [goalValueOf] using region_taskComplete_fires_completeTask s hr
  | .noTask =>
      refine ⟨.acceptTask, ?_⟩
      simpa [goalValueOf] using region_noTask_fires_acceptTask s hr
  | .inventoryFull =>
      refine ⟨.discardOverstock, ?_⟩
      simpa [goalValueOf] using
        region_inventoryFull_fires_discardOverstock s hr 0
  | .levelBlocker =>
      refine ⟨.reachUnlockLevel, ?_⟩
      simpa [goalValueOf] using
        region_levelBlocker_fires_reachUnlockLevel s hr
  | .bankLockedFightable =>
      refine ⟨.unlockBank, ?_⟩
      simpa [goalValueOf] using
        region_bankLockedFightable_fires_unlockBank s hr
  | .progressNeeded =>
      refine ⟨.pursueTask, ?_⟩
      simpa [goalValueOf] using region_progressNeeded_fires_pursueTask s hr

/-! ## Headline — Reachable-gated corollary

The plan asked for both the strong form and a Reachable-gated form.
The Reachable hypothesis is **unused** because the strong form does not
need it. This is disclosed honestly per
`feedback_proofs_tell_false_stories`. -/

/-- **No-deadlock for Reachable states** (corollary of
`no_deadlock_strong`).

NOTE — The `Reachable` hypothesis is *unused*: the strong form
`no_deadlock_strong` already holds for every State because Phase-20a's
region partition is exhaustive on all States, not just reachable ones.
We state this corollary because the Phase-20 plan named the Reachable
form as the headline; Phase 20a's investigation discovered the strong
form was the real content. Both are kept for the audit trail. -/
theorem no_deadlock_reachable :
    ∀ s : State, Reachable s → ∃ g : FiringGoal, goalValueOf g s > 0 :=
  fun s _ => no_deadlock_strong s

end Formal.Liveness.NoDeadlock
