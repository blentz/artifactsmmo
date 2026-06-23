-- @concept: core, planner @property: safety, totality
/-
Formal model of `next_craft_target_pure`
(`src/artifactsmmo_cli/ai/next_craft_core.py`): the deterministic next-action
generator that replaces a 52K-node GOAP A* re-run for craft-chain goals.

Given a recipe DAG and current owned inventory, the function walks depth-first
from the target to find the DEEPEST item that is actionable NOW:
  * raw (no recipe)  → `gather` the deficit
  * craftable, all inputs on hand → `craft` the deficit
  * craftable, some input short → recurse into the FIRST short input

CODE FACTS mirrored (next_craft_core.py):
  nextCraftTarget  = None when qty ≤ owned target  (already satisfied)
               | Some (nextHelper ...) otherwise

  nextHelper fuel = 0  → gather (total-function guard; acyclic data never hits)
  nextHelper (fuel+1)  →
     let deficit = need - owned item
     match recipes item with
     | none       → gather (raw resource)
     | some inputs →
       match inputs.find? (fun p => owned p.1 < p.2 * deficit) with
       | some p → recurse into p.1 with need = p.2 * deficit
       | none   → craft (all inputs satisfied)

ROLES proved:
  * validity  — nextCraftTarget = none ↔ qty ≤ owned target
  * ordering  — craft returned ⇒ inputs.find? (short predicate) = none
                (i.e. every input is on hand; never craft before inputs ready)
  * shortness — nextHelper always returns qty ≥ 1 when initial deficit is positive

Lean core only — no mathlib.
-/

namespace Formal.NextCraftAction

/-- The kind of next action: gather a raw resource, or craft from available inputs. -/
inductive Kind where
  | gather
  | craft
  deriving DecidableEq, Repr, Inhabited

/-- The next single action toward a target: what item, how to produce it, how many needed. -/
structure NextAction where
  item : String
  kind : Kind
  qty  : Nat
  deriving DecidableEq, Repr, Inhabited

/-! ## Core definitions (mirrors Python `_next` / `next_craft_target_pure`) -/

/-- Walk the recipe DAG to find the deepest actionable step.

`fuel` bounds recursion for totality; acyclic recipe data guarantees it is
never exhausted (Python uses `len(recipes)+1` at the top level).

`recipes item = none`        → item is a raw resource → gather.
`recipes item = some inputs` and some input `p` has `owned p.1 < p.2 * deficit`
                             → recurse into `p.1` first.
`recipes item = some inputs` and all inputs on hand
                             → craft. -/
def nextHelper
    (recipes : String → Option (List (String × Nat)))
    (owned   : String → Nat)
    : String → Nat → Nat → NextAction
  | item, need, 0 =>
      ⟨item, .gather, need - owned item⟩           -- fuel exhausted (totality guard)
  | item, need, fuel + 1 =>
      let deficit := need - owned item
      match recipes item with
      | none        => ⟨item, .gather, deficit⟩    -- raw resource: gather
      | some inputs =>
          match inputs.find? (fun p => owned p.1 < p.2 * deficit) with
          | some p  => nextHelper recipes owned p.1 (p.2 * deficit) fuel   -- short input: recurse
          | none    => ⟨item, .craft, deficit⟩      -- all inputs on hand: craft

/-- Entry point: returns `none` when the target is already satisfied, else `some` next action.

Mirrors `next_craft_target_pure`; the caller should pass `fuel = |recipes| + 1`. -/
def nextCraftTarget
    (recipes : String → Option (List (String × Nat)))
    (owned   : String → Nat)
    (target  : String)
    (qty fuel : Nat) : Option NextAction :=
  if qty ≤ owned target then none
  else some (nextHelper recipes owned target qty fuel)

/-! ## Theorem 1: validity -/

/-- **VALIDITY.** `nextCraftTarget` returns `none` if and only if the target
quantity is already satisfied (`qty ≤ owned target`). Immediate from the `if`. -/
theorem nextCraftTarget_none_iff
    (recipes : String → Option (List (String × Nat)))
    (owned   : String → Nat)
    (target  : String)
    (qty fuel : Nat) :
    nextCraftTarget recipes owned target qty fuel = none ↔ qty ≤ owned target := by
  simp [nextCraftTarget]

/-! ## Theorem 2: ordering (safety) -/

/-- **ORDERING.** If `nextHelper` returns a `craft` action, then the recipe
inputs for that item all have sufficient owned quantities — concretely,
`inputs.find?` with the "short" predicate returns `none`, meaning no input
is short.  This guarantees: craft is returned only when all inputs are on hand. -/
theorem nextHelper_craft_inputs_satisfied
    (recipes : String → Option (List (String × Nat)))
    (owned   : String → Nat) :
    ∀ (item : String) (need fuel : Nat) (result : NextAction),
      nextHelper recipes owned item need fuel = result →
      result.kind = Kind.craft →
      ∃ inputs,
        recipes result.item = some inputs ∧
        inputs.find? (fun p => decide (owned p.1 < p.2 * result.qty)) = none := by
  intro item need fuel
  induction fuel generalizing item need with
  | zero =>
    intro result h hkind
    -- fuel=0: always returns gather, contradicts craft
    simp [nextHelper] at h
    subst h
    simp at hkind
  | succ n ih =>
    intro result h hkind
    simp only [nextHelper] at h
    -- split on recipes item
    split at h
    · -- none → gather, contradicts craft
      subst h; simp at hkind
    · rename_i inputs heq
      -- split on find?
      split at h
      · -- some p → recurse into p
        rename_i p _
        exact ih p.1 (p.2 * (need - owned item)) result h hkind
      · -- none → craft returned
        rename_i hnone
        subst h
        exact ⟨inputs, heq, hnone⟩

/-! ## Theorem 3: shortness -/

/-- **SHORTNESS LEMMA.** `nextHelper` always returns a `qty ≥ 1` when the
initial deficit is positive. -/
theorem nextHelper_qty_pos
    (recipes : String → Option (List (String × Nat)))
    (owned   : String → Nat) :
    ∀ (item : String) (need fuel : Nat),
      owned item < need →
      1 ≤ (nextHelper recipes owned item need fuel).qty := by
  intro item need fuel
  induction fuel generalizing item need with
  | zero =>
    intro hdef
    simp [nextHelper]
    omega
  | succ n ih =>
    intro hdef
    simp only [nextHelper]
    split
    · -- raw: qty = need - owned item ≥ 1
      simp; omega
    · -- split on find?
      split
      · rename_i p hp
        -- hp: find? = some p, so p was short: owned p.1 < p.2 * deficit
        have hlt : owned p.1 < p.2 * (need - owned item) := by
          have := List.find?_some hp
          simp only [decide_eq_true_eq] at this
          exact this
        apply ih
        omega
      · -- no short input → craft; qty = need - owned item ≥ 1
        simp; omega

/-- **SHORTNESS.** When `nextCraftTarget` returns `some action`, the action's
qty is ≥ 1 (the returned item has a genuine positive deficit). -/
theorem nextCraftTarget_qty_pos
    (recipes : String → Option (List (String × Nat)))
    (owned   : String → Nat)
    (target  : String)
    (qty fuel : Nat)
    (result  : NextAction)
    (h       : nextCraftTarget recipes owned target qty fuel = some result) :
    1 ≤ result.qty := by
  simp only [nextCraftTarget] at h
  split at h
  · simp at h
  · rename_i hlt
    simp only [Option.some.injEq] at h
    subst h
    apply nextHelper_qty_pos
    omega

/-! ## Non-vacuity witnesses — copper_ring chain -/

/-
copper_ring recipe:
  copper_ring: 1 × copper_bar
  copper_bar:  10 × copper_ore
  copper_ore:  raw (gather)

  Target: 3 copper_ring, qty = 3
  We need 3 bars → 30 ore, all at 0 owned.
  Expected first action: gather copper_ore (30 needed).
-/

private def copperRecipes : String → Option (List (String × Nat))
  | "copper_ring" => some [("copper_bar", 1)]
  | "copper_bar"  => some [("copper_ore", 10)]
  | _             => none

private def ownedZero : String → Nat := fun _ => 0

-- With 0 owned, first action is gather copper_ore (30 needed for 3 bars needed for 3 rings).
example : nextCraftTarget copperRecipes ownedZero "copper_ring" 3 10 =
    some ⟨"copper_ore", .gather, 30⟩ := by decide

-- With 30 ore, next action is craft copper_bar (deficit = 3).
private def owned30ore : String → Nat
  | "copper_ore" => 30
  | _ => 0

example : nextCraftTarget copperRecipes owned30ore "copper_ring" 3 10 =
    some ⟨"copper_bar", .craft, 3⟩ := by decide

-- With 30 ore + 3 bars, next action is craft copper_ring (deficit = 3).
private def owned30ore3bar : String → Nat
  | "copper_ore" => 30
  | "copper_bar" => 3
  | _ => 0

example : nextCraftTarget copperRecipes owned30ore3bar "copper_ring" 3 10 =
    some ⟨"copper_ring", .craft, 3⟩ := by decide

-- Already satisfied → none.
private def owned3ring : String → Nat
  | "copper_ring" => 3
  | _ => 0

example : nextCraftTarget copperRecipes owned3ring "copper_ring" 3 10 = none := by decide

-- ORDERING non-vacuity: craft returned for copper_bar at owned30ore ⇒ inputs satisfied.
example : ∃ inputs,
    copperRecipes "copper_bar" = some inputs ∧
    inputs.find? (fun p => decide (owned30ore p.1 < p.2 * 3)) = none := by decide

-- SHORTNESS non-vacuity: qty ≥ 1 in all above non-none cases.
example : 1 ≤ (nextCraftTarget copperRecipes ownedZero "copper_ring" 3 10).get!.qty := by decide

end Formal.NextCraftAction
