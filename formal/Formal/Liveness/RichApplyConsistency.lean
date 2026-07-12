import Formal.Liveness.Plan
import Formal.Liveness.PlanAction
import Formal.Liveness.Measure
import Formal.Liveness.Skill
import Mathlib.Tactic

/-! # RichApplyConsistency — Item 4f

After Items 4a-4e added richer state fields (`inventoryItems`,
`equipment`, `posX`/`posY`, `skillXpDelta`, etc.) and updated the
matching apply branches, the scalar fields used by Phase 19's measure
lemmas (`inventoryUsed`, `inventoryMax`, `trackedSkillLevel`, etc.)
ARE PRESERVED as separate, independent state. This module ships the
preservation theorems explicitly so Phase 19 / 23 proofs that read
the scalar fields continue to hold structurally — the richer mutations
ride alongside without disturbing the legacy axes.

The discipline is: scalar fields are the "perception layer's
abstraction" of the per-item composition. Production keeps both in
sync via `_fetch_world_state` updating both `inventory_used` (sum)
and `inventory` (dict). The Lean model treats them as independent
fields; a future differential phase can prove
`inventoryUsed = sum (map snd inventoryItems)` from production data.

For Item 4f, the structural preservation lemmas suffice: every action
preserves the SCALAR axes used by Phase 19 measures.

NO new axioms.
-/

namespace Formal.Liveness.RichApplyConsistency

open Formal.Liveness.Plan
open Formal.Liveness.PlanAction
open Formal.Liveness.Measure
open Formal.Liveness

/-- `.gather` preserves the scalar `inventoryUsed` (legacy field).
    Item 4a added per-item composition without touching the scalar. -/
theorem gather_inventoryUsed_invariant (s : State) :
    (applyActionKind .gather s).inventoryUsed = s.inventoryUsed := by
  rfl

/-- `.gather` preserves the scalar `inventoryMax`. -/
theorem gather_inventoryMax_invariant (s : State) :
    (applyActionKind .gather s).inventoryMax = s.inventoryMax := by
  rfl

/-- `.craft` preserves the scalar `inventoryUsed`. -/
theorem craft_inventoryUsed_invariant (s : State) :
    (applyActionKind .craft s).inventoryUsed = s.inventoryUsed := by
  rfl

/-- `.equip` preserves the scalar `inventoryUsed`. -/
theorem equip_inventoryUsed_invariant (s : State) :
    (applyActionKind .equip s).inventoryUsed = s.inventoryUsed := by
  rfl

/-- `.unequip` preserves the scalar `inventoryUsed`. -/
theorem unequip_inventoryUsed_invariant (s : State) :
    (applyActionKind .unequip s).inventoryUsed = s.inventoryUsed := by
  rfl

/-- `.move` preserves the scalar `inventoryUsed`. -/
theorem move_inventoryUsed_invariant (s : State) :
    (applyActionKind .move s).inventoryUsed = s.inventoryUsed := by
  show (match s.moveTarget with
        | some (tx, ty) => ({s with posX := tx, posY := ty} : State)
        | none => s).inventoryUsed = s.inventoryUsed
  cases s.moveTarget <;> rfl

/-- `.gather` (the modeled grind rung) advances the scalar `trackedSkillLevel`
    by 1 — Item 4e added the per-skill map alongside, not replacing it. -/
theorem gather_trackedSkillLevel_advances (s : State) :
    (applyActionKind .gather s).trackedSkillLevel
    = s.trackedSkillLevel + 1 := by
  rfl

/-- `.completeTask` preserves scalar `inventoryUsed` (Item 4d added
    gold credit but no inventory change). -/
theorem completeTask_inventoryUsed_invariant (s : State) :
    (applyActionKind .completeTask s).inventoryUsed = s.inventoryUsed := by
  rfl

/-- `.npcSell` preserves scalar `inventoryUsed` (Item 4d added
    gold credit but legacy flag-clearing intact). -/
theorem npcSell_inventoryUsed_invariant (s : State) :
    (applyActionKind .npcSell s).inventoryUsed = s.inventoryUsed := by
  rfl

end Formal.Liveness.RichApplyConsistency
