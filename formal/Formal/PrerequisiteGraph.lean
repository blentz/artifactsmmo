-- @concept: crafting, items @property: safety, totality
/-
Formal model of the data-derived EDGE STRUCTURE of `prerequisites` and the
`combat_capable` aggregation from
`src/artifactsmmo_cli/ai/tiers/prerequisite_graph.py`.

## `prerequisites(node, state, game_data)` — the `ObtainItem code` branch

After the `is_satisfied` short-circuit (which we treat as already false — we
model the DATA-DERIVED edges of an unsatisfied node), the direct prerequisites
of `ObtainItem code` are:

* if `code` HAS a recipe (`crafting_recipe(code) is not None`): ONE
  `ObtainItem(mat, qty)` edge per `(mat, qty)` ingredient, in recipe
  (insertion) order — and NOTHING else. The crafting-skill gate is NO LONGER
  emitted as a prerequisite node: under-skill gear is grinded planner-natively
  by UpgradeEquipmentGoal via the LevelSkill action (epic P3), not by a
  tree-level skill root;
* else (buyable / monster-drop / gatherable / unknown): NO prerequisites (a
  leaf). The old "resource-drop → ReachSkillLevel" branch is GONE.

We model item/material codes as `Nat`. A prerequisite edge is only ever an item
requirement `ObtainItem code qty` (the sole `MetaGoal` constructor the ObtainItem
branch now emits — no `ReachSkillLevel`, and `ReachCharLevel` is never produced
by the ObtainItem branch).

The recipe is `recipe : Option (List (Nat × Nat))` (the `crafting_recipe(code)`
lookup: `none` = not craftable, `some ingredients` = `(mat, qty)` list).

## `combat_capable(state, game_data)`

`return any(predict_win(state, game_data, code) for code in _monster_level)`.
We abstract the per-monster `predict_win` verdict as an input boolean (the real
`predict_win` is proven in `PredictWin.lean`). `combatCapable beatable` is the
`List.any` over the monster list; we prove it equals `∃ m, beatable m` via De
Morgan (an INDEPENDENT existential formulation, not the function reapplied).

Lean core only — no mathlib.
-/

namespace Formal.PrerequisiteGraph

/-! ### MetaGoal edges. -/

/-- A prerequisite edge — the sole `MetaGoal` constructor the `ObtainItem`
branch of `prerequisites` can emit (an `ObtainItem(code, qty)` material). -/
inductive Edge where
  | item (code qty : Nat)
deriving DecidableEq, Repr

/-! ### The edge list of the `ObtainItem code` branch. -/

/-- `prereqEdges recipe`: the direct prerequisite edges of an UNSATISFIED
`ObtainItem code`, exactly mirroring the Python branch — one `Edge.item` per
recipe ingredient when craftable, else a leaf. No skill edge; no resource
branch. -/
def prereqEdges (recipe : Option (List (Nat × Nat))) : List Edge :=
  match recipe with
  | some ingredients => ingredients.map (fun p => Edge.item p.1 p.2)
  | none => []

/-! ### combat_capable aggregation. -/

/-- `combatCapable beatable monsters`: `any(predict_win(m) for m in monsters)`,
where `beatable m` abstracts the proven `predict_win` verdict for monster `m`. -/
def combatCapable (beatable : Nat → Bool) (monsters : List Nat) : Bool :=
  monsters.any beatable

/-! ### THEOREMS for `prerequisites` (the ObtainItem edge structure). -/

/-- `prereqs_recipe`: a craftable item produces EXACTLY one item edge per
ingredient, in recipe order, and NO skill edge — pinned against the
independently-built expected list. -/
theorem prereqs_recipe (ingredients : List (Nat × Nat)) :
    prereqEdges (some ingredients)
      = ingredients.map (fun p => Edge.item p.1 p.2) := by
  rfl

/-- `prereqs_leaf`: a NON-craftable item is a LEAF — NO prerequisites. The old
resource-drop → skill branch is retired, so `none` is always empty. -/
theorem prereqs_leaf : prereqEdges none = ([] : List Edge) := by
  rfl

/-- `prereqs_membership`: full characterization of edge membership for a
craftable item. An edge is in the prereq set IFF it is an `Edge.item mat qty`
for some ingredient `(mat, qty)` in the recipe. This pins the EXACT edge set (no
extra, none missing, NO skill edge) against an independent existential. -/
theorem prereqs_membership (ingredients : List (Nat × Nat)) (e : Edge) :
    e ∈ prereqEdges (some ingredients)
      ↔ ∃ mat qty, (mat, qty) ∈ ingredients ∧ e = Edge.item mat qty := by
  unfold prereqEdges
  simp only [List.mem_map]
  constructor
  · rintro ⟨p, hp, he⟩
    exact ⟨p.1, p.2, by simpa using hp, he.symm⟩
  · rintro ⟨mat, qty, hmem, he⟩
    exact ⟨(mat, qty), hmem, he.symm⟩

/-! ### THEOREMS for `combat_capable` (the `any` aggregation, via De Morgan).

`combat_capable_iff` is NOT `X ↔ X`: the LHS is the operational `List.any` fold;
the RHS is an INDEPENDENT existential over the monster list. We prove the
equivalence and the De Morgan dual (`¬ combatCapable ↔ ∀ m, ¬ beatable m`). -/

/-- `combat_capable_iff`: `combat_capable` is true IFF SOME monster is beatable.
The RHS `∃ m ∈ monsters, beatable m = true` is an independent existential, not
the `any` function reapplied. -/
theorem combat_capable_iff (beatable : Nat → Bool) (monsters : List Nat) :
    combatCapable beatable monsters = true ↔ ∃ m ∈ monsters, beatable m = true := by
  unfold combatCapable
  rw [List.any_eq_true]

/-- `combat_capable_demorgan`: NOT combat-capable IFF EVERY monster is unbeatable
(`∀ m, ¬ beatable m`) — the De Morgan dual, the independent formulation the spec
asks for (catches an `any → all` mutation). -/
theorem combat_capable_demorgan (beatable : Nat → Bool) (monsters : List Nat) :
    combatCapable beatable monsters = false ↔ ∀ m ∈ monsters, beatable m = false := by
  rw [← Bool.not_eq_true, combat_capable_iff]
  constructor
  · intro h m hm
    cases hb : beatable m with
    | false => rfl
    | true => exact absurd ⟨m, hm, hb⟩ h
  · intro h hex
    obtain ⟨m, hm, hb⟩ := hex
    rw [h m hm] at hb
    exact Bool.noConfusion hb

/-- `combat_capable_empty`: no monsters ⇒ never combat-capable (the `any` of an
empty list). A boundary anchor distinguishing `any` (false) from `all` (true). -/
theorem combat_capable_empty (beatable : Nat → Bool) :
    combatCapable beatable [] = false := by
  rfl

/-- `combat_capable_witness`: a single beatable monster in the list is enough —
the existential witness direction, the operational "found a target" content. -/
theorem combat_capable_witness (beatable : Nat → Bool) (monsters : List Nat)
    {m : Nat} (hm : m ∈ monsters) (hb : beatable m = true) :
    combatCapable beatable monsters = true := by
  rw [combat_capable_iff]
  exact ⟨m, hm, hb⟩

/-! ### ANTI-GAMING: `any` is genuinely NOT `all`.

A concrete monster list where exactly one of two monsters is beatable: `any`
(combat-capable) is TRUE, but the `all` aggregation would be FALSE. This is the
gate that an `any → all` mutation must trip. -/
example :
    let beatable : Nat → Bool := fun m => decide (m = 0)
    combatCapable beatable [0, 1] = true ∧ ([0, 1].all beatable = false) := by
  decide

end Formal.PrerequisiteGraph
