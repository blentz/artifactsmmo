import Formal.Liveness.Plan
import Formal.Liveness.PlanAction
import Formal.Liveness.Measure
import Mathlib.Tactic

/-! # ApplyXpLevelPreservation — Item 1g-B2 per-action xp/level preservation

Under XP=0 fix (taskCompleteXpEstimate=0, user commit 7ad19e5), only
`.fight` and `.completeTask` can mutate (level, xp). All other 25
ActionKinds preserve both.

This module ships the per-action preservation lemmas used by the
fight-count accumulation argument for `lifecycle_progress_from_bounds`.

NO new axioms.
-/

namespace Formal.Liveness.ApplyXpLevelPreservation

open Formal.Liveness.Plan
open Formal.Liveness.PlanAction
open Formal.Liveness.Measure

/-- Every action EXCEPT `.fight` and `.completeTask` preserves `level`. -/
theorem applyActionKind_level_preserved_except_fight_completeTask
    (k : ActionKind) (s : State)
    (hne_fight : k ≠ .fight) (hne_ct : k ≠ .completeTask) :
    (applyActionKind k s).level = s.level := by
  cases k with
  | fight => exact absurd rfl hne_fight
  | completeTask => exact absurd rfl hne_ct
  | _ => rfl

/-- Every action EXCEPT `.fight` and `.completeTask` preserves `xp`. -/
theorem applyActionKind_xp_preserved_except_fight_completeTask
    (k : ActionKind) (s : State)
    (hne_fight : k ≠ .fight) (hne_ct : k ≠ .completeTask) :
    (applyActionKind k s).xp = s.xp := by
  cases k with
  | fight => exact absurd rfl hne_fight
  | completeTask => exact absurd rfl hne_ct
  | _ => rfl

/-- `.completeTask` preserves `level` AND `xp` when xp threshold isn't
    met, i.e. when `s.xp < xpToNextLevel s.level` OR `s.level ≥ 50`.
    (Under XP=0: completeTask is effectively a no-op on (level, xp)
    EXCEPT when accumulated xp has already reached the threshold —
    in which case it acts like a rollover trigger.) -/
theorem completeTask_level_preserved_when_no_rollover (s : State)
    (h : s.xp < xpToNextLevel s.level ∨ s.level ≥ 50) :
    (applyActionKind .completeTask s).level = s.level := by
  show ((if (decide (s.xp + taskCompleteXpEstimate ≥ xpToNextLevel s.level)
              && decide (s.level < 50))
            then s.level + 1
            else s.level) = s.level)
  have hcond :
      (decide (s.xp + taskCompleteXpEstimate ≥ xpToNextLevel s.level)
        && decide (s.level < 50)) = false := by
    -- taskCompleteXpEstimate = 0 (def), so s.xp + 0 = s.xp.
    -- If s.xp < xpToNextLevel s.level, decide ≥ is false.
    -- If s.level ≥ 50, decide < is false.
    rcases h with hxp | hlvl
    · have : ¬ (s.xp + taskCompleteXpEstimate ≥ xpToNextLevel s.level) := by
        show ¬ (s.xp + 0 ≥ xpToNextLevel s.level)
        omega
      simp [this]
    · have : ¬ (s.level < 50) := by omega
      simp [this]
  rw [if_neg]
  intro hcond_true
  rw [hcond] at hcond_true
  exact Bool.noConfusion hcond_true

/-- Same shape for xp: `.completeTask` preserves `xp` when no rollover. -/
theorem completeTask_xp_preserved_when_no_rollover (s : State)
    (h : s.xp < xpToNextLevel s.level ∨ s.level ≥ 50) :
    (applyActionKind .completeTask s).xp = s.xp := by
  show ((if (decide (s.xp + taskCompleteXpEstimate ≥ xpToNextLevel s.level)
              && decide (s.level < 50))
            then 0
            else s.xp + taskCompleteXpEstimate)
        = s.xp)
  have hcond :
      (decide (s.xp + taskCompleteXpEstimate ≥ xpToNextLevel s.level)
        && decide (s.level < 50)) = false := by
    rcases h with hxp | hlvl
    · have : ¬ (s.xp + taskCompleteXpEstimate ≥ xpToNextLevel s.level) := by
        show ¬ (s.xp + 0 ≥ xpToNextLevel s.level)
        omega
      simp [this]
    · have : ¬ (s.level < 50) := by omega
      simp [this]
  rw [if_neg]
  · show s.xp + taskCompleteXpEstimate = s.xp
    show s.xp + 0 = s.xp
    omega
  · intro hcond_true
    rw [hcond] at hcond_true
    exact Bool.noConfusion hcond_true

end Formal.Liveness.ApplyXpLevelPreservation
