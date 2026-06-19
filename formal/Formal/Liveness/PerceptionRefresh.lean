import Formal.Liveness.ProductionLadder

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
`WinnableAcrossBand`). So arming `objectiveStepFires`/`objectiveStepIsFight` on
`level < 50` is faithful MODULO `WinnableAcrossBand`. It arms ONLY those two
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

/-- Below the cap, `perceptionRefresh` arms `objectiveStepIsFight` (the objective
plan leads with a Fight). -/
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

end Formal.Liveness.PerceptionRefresh
