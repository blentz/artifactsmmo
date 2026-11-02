-- @concept: gear-objective, combat @property: safety, totality
import Formal.CombatTargetExistence

/-! # GearObjectiveWalk — the gear objective's root walk and grind target

The production decision the below-cap combat objective reads (ruling C4-b): the
root walk's entry `WhichPieceIsNext` and the grind target `farm_target`, over the
part of production's `GearObjective` they read. Pure, no Mathlib: the Oracle
evaluates `whichPieceIsNext` and `grindTarget` for
`formal/diff/test_gear_objective_arming_diff.py` (oracle kinds
`which_piece_is_next`, `grind_target`). `Liveness.GearTierLeveling` composes these
with the band guarantee and `LivenessChain`.
-/

namespace Formal.GearObjectiveWalk

open Formal.CombatTargetExistence

/-! ## The gear objective and its root walk

`ObjectiveView` is the part of production's `GearObjective` the walk reads: `m*`
(`monster`), whether `L*` is held (`held`), and the missing pieces in pursuit order
(`missing`, piece codes). Production's `GearObjective.held` is `not missing`
(`gear_objective_result.py`), which `WellFormed` states. -/

/-- The gear objective as the root walk reads it. -/
structure ObjectiveView where
  monster : Int
  held    : Bool
  missing : List Int
  deriving Repr, DecidableEq

/-- `held` exactly when no piece is missing (production: `held = not missing`). -/
def WellFormed (o : ObjectiveView) : Prop := o.held = true ↔ o.missing = []

/-- The root `WhichPieceIsNext` resolves to (no fleet pieces). -/
inductive Root
  | levelUp
  | piece (code : Int)
  deriving Repr, DecidableEq

/-- `WhichPieceIsNext.resolve` with no fleet pieces: no objective is the wall
    (`none`); `L*` held is one more level (`none` at the cap, `next_level`); otherwise
    the first missing piece, in `missing`'s order, whose step the cycle serves
    (`RootWalk.serves`), or `none` when every one is declined. -/
def whichPieceIsNext (o : Option ObjectiveView) (serves : Int → Bool) (atCap : Bool) :
    Option Root :=
  match o with
  | none => none
  | some o =>
    if o.held then (if atCap then none else some .levelUp)
    else (o.missing.find? serves).map Root.piece

/-- The grind target `farm_target` names with no task held and no fleet piece
    waiting: the two-arm cascade on `m*`. -/
def grindTarget (o : ObjectiveView) : Option Int :=
  winnableFarmTarget none (some o.monster) o.held

/-! ## Half 1 — `L*` held arms the fight on `m*` -/

/-- **`L*` held ⇒ the fight step is armed.** Below the cap the root is one more
    level, and the grind target is `m*`. -/
theorem fight_armed_of_held (o : ObjectiveView) (serves : Int → Bool)
    (hheld : o.held = true) :
    whichPieceIsNext (some o) serves false = some .levelUp ∧
      grindTarget o = some o.monster := by
  refine ⟨?_, ?_⟩
  · simp [whichPieceIsNext, hheld]
  · simp [grindTarget, hheld, winnableFarmTarget]

/-! ## Half 2 — `L*` not held: a missing piece is the root, never an XP fight -/

/-- **`L*` not held ⇒ no fight is chosen for XP.** -/
theorem no_xp_fight_of_not_held (o : ObjectiveView) (hheld : o.held = false) :
    grindTarget o = none := by
  simp [grindTarget, hheld, winnableFarmTarget]

/-- **`L*` not held ⇒ the root is a missing piece's acquisition.** When the cycle
    serves some missing piece, the root is the FIRST served piece of `missing`. -/
theorem piece_root_of_not_held (o : ObjectiveView) (serves : Int → Bool) (atCap : Bool)
    (hheld : o.held = false) (hserved : ∃ p ∈ o.missing, serves p = true) :
    ∃ p, whichPieceIsNext (some o) serves atCap = some (.piece p) ∧
      p ∈ o.missing ∧ serves p = true := by
  obtain ⟨q, hq, hsq⟩ := hserved
  cases hf : o.missing.find? serves with
  | none =>
    exact absurd hsq (by simpa using List.find?_eq_none.mp hf q hq)
  | some p =>
    refine ⟨p, ?_, List.mem_of_find?_eq_some hf, by simpa using List.find?_some hf⟩
    simp [whichPieceIsNext, hheld, hf]

/-- Every missing piece declined: no root (no XP trunk stands in for the pieces). -/
theorem no_root_when_every_piece_declined (o : ObjectiveView) (serves : Int → Bool)
    (atCap : Bool) (hheld : o.held = false) (hdecl : ∀ p ∈ o.missing, serves p = false) :
    whichPieceIsNext (some o) serves atCap = none := by
  have hf : o.missing.find? serves = none :=
    List.find?_eq_none.mpr (fun p hp => by simp [hdecl p hp])
  simp [whichPieceIsNext, hheld, hf]

/-- A well-formed objective that is not held misses at least one piece, so the
    served-piece hypothesis of `piece_root_of_not_held` is about a real list. -/
theorem missing_nonempty_of_not_held (o : ObjectiveView) (hwf : WellFormed o)
    (hheld : o.held = false) : o.missing ≠ [] := by
  intro h
  have := hwf.mpr h
  rw [hheld] at this
  exact absurd this (by decide)

/-! ## Non-vacuity witnesses -/

/-- A held, well-formed objective. -/
def witnessHeld : ObjectiveView := ⟨7, true, []⟩
/-- A not-held, well-formed objective with two missing pieces. -/
def witnessMissing : ObjectiveView := ⟨7, false, [11, 12]⟩

example : WellFormed witnessHeld := by simp [WellFormed, witnessHeld]
example : WellFormed witnessMissing := by simp [WellFormed, witnessMissing]
example : whichPieceIsNext (some witnessHeld) (fun _ => true) false = some .levelUp := rfl
example : grindTarget witnessHeld = some 7 := rfl
example : grindTarget witnessMissing = none := rfl
-- The first piece declined, the second served: the root is the second.
example : whichPieceIsNext (some witnessMissing) (fun p => p == 12) false =
    some (.piece 12) := rfl
-- Every piece declined: no root.
example : whichPieceIsNext (some witnessMissing) (fun _ => false) false = none := rfl
-- No objective: the wall.
example : whichPieceIsNext none (fun _ => true) false = none := rfl
-- At the cap a held objective has no level-up root.
example : whichPieceIsNext (some witnessHeld) (fun _ => true) true = none := rfl

end Formal.GearObjectiveWalk
