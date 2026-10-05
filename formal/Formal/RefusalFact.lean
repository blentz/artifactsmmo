-- @concept: core, planner @property: safety, reachability
/-
Formal model of `src/artifactsmmo_cli/ai/refusal_fact_core.py` (Phase 5-1 of
docs/PLAN_decision_architecture_redesign.md): does a recorded categorical
server refusal still close its action?

CODE FACTS mirrored:
  * 485 ("already equipped") holds exactly while the code is worn.
  * Every other categorical refusal holds while the item's game-data type equals
    the type recorded at the refusal.

Item types are compared for equality only, so they are modelled over any type
with decidable equality (`Option σ`: an item absent from game data has no type).

It replaced `Formal/DoomedMemo.lean`, whose re-probe window let a refused action
be re-sent on a timer: here a refusal is re-opened only by a FACT (the code no
longer worn; the item redefined), never by time.

Lean core only — no mathlib.
-/

namespace Formal.RefusalFact

variable {σ : Type} [DecidableEq σ]

/-- The HTTP code for "This item is already equipped". -/
def alreadyEquipped : Nat := 485

/-- Mirrors `refusal_holds(http_code, recorded_type, current_type, worn)`. -/
def holds (httpCode : Nat) (recordedType currentType : Option σ) (worn : Bool) : Bool :=
  if httpCode = alreadyEquipped then worn else decide (recordedType = currentType)

/-- 485 holds exactly while the code is worn. -/
theorem equipped_holds_iff_worn (r c : Option σ) (w : Bool) :
    holds alreadyEquipped r c w = w := by
  simp [holds]

/-- RE-OPENED BY A FACT: unequip the worn copy and the equip is offered again. -/
theorem equipped_heals_when_unworn (r c : Option σ) :
    holds alreadyEquipped r c false = false := by
  simp [holds]

/-- A game-data refusal does not depend on the loadout. -/
theorem game_fact_ignores_loadout (code : Nat) (h : code ≠ alreadyEquipped)
    (r c : Option σ) (w : Bool) :
    holds code r c w = holds code r c (!w) := by
  simp [holds, h]

/-- SAFETY: while the item is defined as it was when refused, the refusal holds —
the refused call is never re-sent on a timer. -/
theorem game_fact_holds_while_unchanged (code : Nat) (h : code ≠ alreadyEquipped)
    (t : Option σ) (w : Bool) :
    holds code t t w = true := by
  simp [holds, h]

/-- RE-OPENED BY A FACT: redefining the item (a season reset) voids the refusal. -/
theorem game_fact_voids_on_redefinition (code : Nat) (h : code ≠ alreadyEquipped)
    (r c : Option σ) (hne : r ≠ c) (w : Bool) :
    holds code r c w = false := by
  simp [holds, h, hne]

/-! Non-vacuity: every hypothesis above is satisfiable. -/

example : (473 : Nat) ≠ alreadyEquipped := by decide
example : (some 1 : Option Nat) ≠ some 2 := by decide
example : holds (σ := Nat) 473 (some 1) (some 1) false = true := by decide
example : holds (σ := Nat) 473 (some 1) (some 2) true = false := by decide
example : holds (σ := Nat) 485 (some 1) (some 1) true = true := by decide

end Formal.RefusalFact
