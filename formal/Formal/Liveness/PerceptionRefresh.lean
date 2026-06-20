import Formal.Liveness.ProductionLadder
import Formal.Liveness.WinnableGrounded

/-! # PerceptionRefresh — Brick 1: arm the combat objective below the level cap

The pure transition NEVER sets `objectiveStepFires = true`
(`SettledReach.objectiveStepFires_false_cycleStepN`): it only clears or
preserves `false`. Hence `Settled_unreachable_without_perception` — the
objective-committed half of `hfightFires` cannot be discharged in-model without a
re-arming step. This module supplies that step.

`perceptionRefresh` is the model's faithful image of production's `perceive`:
below the level cap the `ReachCharLevel` meta-goal is committed and its plan LEADS
WITH A FIGHT (provided a winnable XP-positive monster exists in the band — that
proviso is `GearTierLeveling.combatObjective_live_below_fifty`, i.e.
`WinnableAcrossBand`). That proviso is now DISCHARGED, not assumed: Task 4's
`WinnableGrounded.winnableAcrossBand_grounded` kernel-proves `WinnableAcrossBand`
over the live catalog, so `combatTarget_exists_below_fifty` below makes
target-existence a THEOREM and `arming_justified_below_fifty` shows the set
`objectiveStepIsFight := true` is BACKED (kernel target-existence + the production
differential `formal/diff/test_objectivestep_arming_diff.py`, which pins
`objective_step_goal(ReachCharLevel) → GrindCharacterXPGoal` whenever a target
exists and we are not in the long-haul items-task defer case). So arming
`objectiveStepFires`/`objectiveStepIsFight` on `level < 50` is DISCHARGED, not a
free assertion. It arms ONLY those two
Bools — the chore flags (`hasOverstockItems`, `selectBankDepositsNonempty`, …)
read inventory composition the Lean model abstracts, so re-arming them would be a
fabrication; their transience stays the documented `BlockersQuietInfinitelyOften`
gap (FightFairness.lean).

This is PURELY ADDITIVE — `cycleStep` and every existing def/theorem are
untouched. Brick 2 composes `cycleStepP s := cycleStep (perceptionRefresh s)` and
transfers B-0's descent via the preservation bridges proved here.

Proven (these Brick-1 lemmas depend on NO axioms — pure `rfl` / `if`-rewrite; the
import chain transitively carries {propext, Quot.sound, LIV-001} but none are used
here):
* `perceptionRefresh_objectiveStepFires` / `_objectiveStepIsFight` — the armed
  facts below the cap.
* `perceptionRefresh_id_of_ge` — identity at/above the cap.
* `perceptionRefresh_<field>` — identity on `level`/`xp`/`hp`/`maxHp`/
  `bankRequiredLevel` (the fields B-0's descent + bootstrap-window proofs read).
* `perceptionRefresh_fires_<slot>` — the bootstrap-window fire predicates
  (`hpCritical`, `restForCombat`, `bankUnlock`, `reachUnlockLevel`) are unchanged,
  since none read the two objective Bools.

Liveness namespace — Mathlib allowed (none needed).
-/

namespace Formal.Liveness.PerceptionRefresh

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.GearTierLeveling
open Formal.Liveness.WinnableGrounded
open Formal.CombatTargetExistence

/-- **The perception-refresh step.** Below the level cap, arm the objective-step
Bools — the in-model image of production's `perceive` committing the
`ReachCharLevel` meta-goal whose plan leads with a Fight. Identity at/above the
cap (no objective to commit). Computable; touches ONLY the two objective Bools. -/
def perceptionRefresh (s : State) : State :=
  if s.level < 50 then { s with objectiveStepFires := true, objectiveStepIsFight := true } else s

/-! ## Arming lemmas — the core new facts -/

/-- Below the cap, `perceptionRefresh` arms `objectiveStepFires`. -/
theorem perceptionRefresh_objectiveStepFires (s : State) (h : s.level < 50) :
    (perceptionRefresh s).objectiveStepFires = true := by
  unfold perceptionRefresh; rw [if_pos h]

/-! ## Arming justification — the model's set value is grounded OFFLINE for faithfulness.

`perceptionRefresh` SETS `objectiveStepIsFight := true` UNCONDITIONALLY below the cap
(the `if s.level < 50 then … true …` branch).  This is the model's set value, provable
by `unfold perceptionRefresh; rw [if_pos]` alone.

The lemmas below establish MODEL FAITHFULNESS *offline* — they are NOT logically
consumed by proofs that merely need the set value:
* The kernel half (`combatTarget_exists_below_fifty`, Task 4's
  `winnableAcrossBand_grounded` fed through `combatObjective_live_below_fifty`) proves a
  winnable combat target EXISTS at every level `1 ≤ L < 50`.
* The production differential (`formal/diff/test_objectivestep_arming_diff.py`) pins that
  when such a target exists and we are NOT in the long-haul items-task defer case
  (`bootstrap_gap > 4 ∧ items-task active`), production's
  `objective_step_goal(ReachCharLevel)` yields a `GrindCharacterXPGoal`, a FIGHT.

Together these ground the model's unconditional arming as a faithful image of production
behaviour — OUTSIDE the defer-case.  The defer-case (the one production branch yielding
NO fight below 50) is NOT modelled in `perceptionRefresh` (which abstracts the
items-task lifecycle away); it lives in the undischarged `BlockersQuietInfinitelyOften`
residual (`hquiet`) of the capstone. -/

/-- **Kernel half — a winnable combat target exists below the cap.** Instantiates
Task 4's `winnableAcrossBand_grounded` through `combatObjective_live_below_fifty`:
at every level `1 ≤ L < 50` the live catalog's picker returns `some` target. So
below 50 the objective tier ALWAYS has a Fight to emit — target-existence is a
THEOREM, not an assumption. -/
theorem combatTarget_exists_below_fifty (L : Int) (hlo : 1 ≤ L) (hhi : L < 50) :
    ∃ target,
      pickWinnableWindowed L winnableConcrete xpPosConcrete catalogAsMonsters
        = some target :=
  combatObjective_live_below_fifty winnableConcrete xpPosConcrete catalogAsMonsters
    winnableAcrossBand_grounded L hlo hhi

/-- **The arming is grounded.** Below the cap (and at a real spawn level `1 ≤ s.level`),
`arming_justified_below_fifty` bundles two components:
* `.1` — a kernel target-existence proof (from Task 4's `winnableAcrossBand_grounded`):
  a winnable combat target EXISTS at `s.level`.  Together with the production differential
  (`test_objectivestep_arming_diff.py`) this establishes that the model's unconditional
  arming is a FAITHFUL image of production outside the items-task defer-case.  This is
  the offline grounding — it is NOT logically consumed by capstone proofs that only need
  `.2`.
* `.2` — the model's set value: `(perceptionRefresh s).objectiveStepIsFight = true`,
  proved by `unfold perceptionRefresh; rw [if_pos]`.  This is what the capstone proof
  term directly consumes.

The model's unconditional arming is OPTIMISTIC vs production: in the long-haul items-task
defer case production returns None (no fight), but `perceptionRefresh` sets `true`
regardless.  That gap is the items-task component of the undischarged
`BlockersQuietInfinitelyOften` residual — it is named there, not confronted here. -/
theorem arming_justified_below_fifty (s : State) (hlo : 1 ≤ s.level)
    (hhi : s.level < 50) :
    (∃ target,
        pickWinnableWindowed (s.level : Int) winnableConcrete xpPosConcrete
          catalogAsMonsters = some target)
      ∧ (perceptionRefresh s).objectiveStepIsFight = true :=
  ⟨combatTarget_exists_below_fifty (s.level : Int) (by exact_mod_cast hlo)
      (by exact_mod_cast hhi),
   by unfold perceptionRefresh; rw [if_pos hhi]⟩

/-- Below the cap, `perceptionRefresh` arms `objectiveStepIsFight` — the model's set
value `objectiveStepIsFight := true` from the `if s.level < 50` branch.  This is
proved by `unfold perceptionRefresh; rw [if_pos]` alone (no kernel result needed).

For the offline FAITHFULNESS grounding of this set value, see `arming_justified_below_fifty`:
its `.1` (kernel target-existence, Task 4) + the production differential establish that
the model faithfully images production outside the items-task defer-case; its `.2` IS
this theorem.  The unconditional form here is kept for field-preservation callers that
only need the Bool; the bundled form is `arming_justified_below_fifty`. -/
theorem perceptionRefresh_objectiveStepIsFight (s : State) (h : s.level < 50) :
    (perceptionRefresh s).objectiveStepIsFight = true := by
  unfold perceptionRefresh; rw [if_pos h]

/-- At/above the cap, `perceptionRefresh` is the identity (no objective to
commit). -/
theorem perceptionRefresh_id_of_ge (s : State) (h : ¬ s.level < 50) :
    perceptionRefresh s = s := by
  unfold perceptionRefresh; rw [if_neg h]

/-! ## Field-preservation bridges — identity on every field except the two
objective Bools. These let Brick 2 transfer B-0's descent + the bootstrap-window
proofs to `cycleStepP`. -/

/-- `perceptionRefresh` preserves `level`. -/
theorem perceptionRefresh_level (s : State) : (perceptionRefresh s).level = s.level := by
  unfold perceptionRefresh; split <;> rfl

/-- `perceptionRefresh` preserves `xp`. -/
theorem perceptionRefresh_xp (s : State) : (perceptionRefresh s).xp = s.xp := by
  unfold perceptionRefresh; split <;> rfl

/-- `perceptionRefresh` preserves `hp`. -/
theorem perceptionRefresh_hp (s : State) : (perceptionRefresh s).hp = s.hp := by
  unfold perceptionRefresh; split <;> rfl

/-- `perceptionRefresh` preserves `maxHp`. -/
theorem perceptionRefresh_maxHp (s : State) : (perceptionRefresh s).maxHp = s.maxHp := by
  unfold perceptionRefresh; split <;> rfl

/-- `perceptionRefresh` preserves `bankRequiredLevel`. -/
theorem perceptionRefresh_bankRequiredLevel (s : State) :
    (perceptionRefresh s).bankRequiredLevel = s.bankRequiredLevel := by
  unfold perceptionRefresh; split <;> rfl

/-- `perceptionRefresh` preserves `taskExchangeMinCoins` (the `taskExchange`
non-degeneracy config field). Needed for the `hex` analog to relate the refreshed
selection state's config to the raw state. -/
theorem perceptionRefresh_taskExchangeMinCoins (s : State) :
    (perceptionRefresh s).taskExchangeMinCoins = s.taskExchangeMinCoins := by
  unfold perceptionRefresh; split <;> rfl

/-- `perceptionRefresh` preserves `nextExpansionCost` (the `bankExpand`
non-degeneracy config field). Needed for the `hbe` analog to relate the refreshed
selection state's config to the raw state. -/
theorem perceptionRefresh_nextExpansionCost (s : State) :
    (perceptionRefresh s).nextExpansionCost = s.nextExpansionCost := by
  unfold perceptionRefresh; split <;> rfl

/-! ## Fire-predicate preservation for the bootstrap-window slots — none of these
read the two objective Bools, so each fire predicate is unchanged. These let
Brick 2 transfer `cycleStep_fights_in_window` to `cycleStepP`. -/

/-- `perceptionRefresh` preserves the hpCritical fire (reads `hp`/`maxHp`). -/
theorem perceptionRefresh_fires_hpCritical (s : State) :
    fires .hpCritical (perceptionRefresh s) = fires .hpCritical s := by
  unfold perceptionRefresh; split <;> rfl

/-- `perceptionRefresh` preserves the restForCombat fire (reads
`restForCombatReady`/`hp`/`maxHp`). -/
theorem perceptionRefresh_fires_restForCombat (s : State) :
    fires .restForCombat (perceptionRefresh s) = fires .restForCombat s := by
  unfold perceptionRefresh; split <;> rfl

/-- `perceptionRefresh` preserves the bankUnlock fire (reads bank/xp/level
fields). -/
theorem perceptionRefresh_fires_bankUnlock (s : State) :
    fires .bankUnlock (perceptionRefresh s) = fires .bankUnlock s := by
  unfold perceptionRefresh; split <;> rfl

/-- `perceptionRefresh` preserves the reachUnlockLevel fire (reads
`bankRequiredLevel`/`level`). -/
theorem perceptionRefresh_fires_reachUnlockLevel (s : State) :
    fires .reachUnlockLevel (perceptionRefresh s) = fires .reachUnlockLevel s := by
  unfold perceptionRefresh; split <;> rfl

/-! ## Fire-predicate preservation for the remaining `objectiveStepBlockers`
slots (idx 4–13 of `allInLadderOrder`). Brick 4's selection-state discharge needs
EVERY higher-than-objectiveStep means quiet on `perceptionRefresh s`; the four
bootstrap-window fires above cover idx 0–3, and these ten cover the rest. None
read the two objective Bools `perceptionRefresh` touches, so each is unchanged —
same `unfold perceptionRefresh; split <;> rfl` discharge. -/

/-- `perceptionRefresh` preserves the discardCritical fire. -/
theorem perceptionRefresh_fires_discardCritical (s : State) :
    fires .discardCritical (perceptionRefresh s) = fires .discardCritical s := by
  unfold perceptionRefresh; split <;> rfl

/-- `perceptionRefresh` preserves the craftRelief fire. -/
theorem perceptionRefresh_fires_craftRelief (s : State) :
    fires .craftRelief (perceptionRefresh s) = fires .craftRelief s := by
  unfold perceptionRefresh; split <;> rfl

/-- `perceptionRefresh` preserves the depositFull fire. -/
theorem perceptionRefresh_fires_depositFull (s : State) :
    fires .depositFull (perceptionRefresh s) = fires .depositFull s := by
  unfold perceptionRefresh; split <;> rfl

/-- `perceptionRefresh` preserves the discardHigh fire. -/
theorem perceptionRefresh_fires_discardHigh (s : State) :
    fires .discardHigh (perceptionRefresh s) = fires .discardHigh s := by
  unfold perceptionRefresh; split <;> rfl

/-- `perceptionRefresh` preserves the gearReview fire. -/
theorem perceptionRefresh_fires_gearReview (s : State) :
    fires .gearReview (perceptionRefresh s) = fires .gearReview s := by
  unfold perceptionRefresh; split <;> rfl

/-- `perceptionRefresh` preserves the claimPending fire. -/
theorem perceptionRefresh_fires_claimPending (s : State) :
    fires .claimPending (perceptionRefresh s) = fires .claimPending s := by
  unfold perceptionRefresh; split <;> rfl

/-- `perceptionRefresh` preserves the completeTask fire. -/
theorem perceptionRefresh_fires_completeTask (s : State) :
    fires .completeTask (perceptionRefresh s) = fires .completeTask s := by
  unfold perceptionRefresh; split <;> rfl

/-- `perceptionRefresh` preserves the sellPressured fire. -/
theorem perceptionRefresh_fires_sellPressured (s : State) :
    fires .sellPressured (perceptionRefresh s) = fires .sellPressured s := by
  unfold perceptionRefresh; split <;> rfl

/-- `perceptionRefresh` preserves the lowYieldCancel fire. -/
theorem perceptionRefresh_fires_lowYieldCancel (s : State) :
    fires .lowYieldCancel (perceptionRefresh s) = fires .lowYieldCancel s := by
  unfold perceptionRefresh; split <;> rfl

/-- `perceptionRefresh` preserves the taskCancel fire. -/
theorem perceptionRefresh_fires_taskCancel (s : State) :
    fires .taskCancel (perceptionRefresh s) = fires .taskCancel s := by
  unfold perceptionRefresh; split <;> rfl

end Formal.Liveness.PerceptionRefresh
