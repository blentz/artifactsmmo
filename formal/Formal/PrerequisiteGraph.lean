/-
Formal model of the data-derived EDGE STRUCTURE of `prerequisites` and the
`combat_capable` aggregation from
`src/artifactsmmo_cli/ai/tiers/prerequisite_graph.py`.

## `prerequisites(node, state, game_data)` — the `ObtainItem code` branch

After the `is_satisfied` short-circuit (which we treat as already false — we
model the DATA-DERIVED edges of an unsatisfied node), the direct prerequisites
of `ObtainItem code` are:

* if `code` HAS a recipe (`crafting_recipe(code) is not None`):
    - if its `item_stats(code).crafting_skill` is a non-empty string, ONE
      `ReachSkillLevel(crafting_skill, crafting_level)` edge, FIRST;
    - then ONE `ObtainItem(mat, qty)` edge per `(mat, qty)` ingredient, in
      recipe (insertion) order;
* elif `code` is the drop of some resource (first `(res, drop)` in
  `_resource_drops` with `drop == code` that has a `resource_skill_level`):
  ONE `ReachSkillLevel(skill, level)` edge for that resource skill;
* else (buyable / monster-drop / unknown): NO prerequisites (a leaf).

We model item/material/skill codes as `Nat`. A `MetaGoal` edge is either a
skill-level requirement `ReachSkillLevel skill level` or an item requirement
`ObtainItem code qty` (matching the two `MetaGoal` constructors the function
emits — `ReachCharLevel` is never produced by the ObtainItem branch).

The recipe is `recipe : Option (List (Nat × Nat))` (the `crafting_recipe(code)`
lookup: `none` = not craftable, `some ingredients` = `(mat, qty)` list). The
crafting skill is `craftSkill : Option (Nat × Nat)` (`none` = no/empty
`crafting_skill`, `some (skill, level)` = the skill-level pair). The resource
side is `resDrops : List (Nat × Nat × Option (Nat × Nat))` — an association list
`(res_code, drop_item, optional (skill, level))` mirroring the
`for res_code, drop in _resource_drops` scan with the `resource_skill_level`
lookup inside.

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

/-- A prerequisite edge — the two `MetaGoal` constructors the `ObtainItem`
branch of `prerequisites` can emit. -/
inductive Edge where
  | skill (skill level : Nat)
  | item (code qty : Nat)
deriving DecidableEq, Repr

/-! ### Resource-drop scan.

`firstResSkill resDrops code` mirrors:
```
for res_code, drop in _resource_drops.items():
    if drop == code:
        skill_level = resource_skill_level(res_code)
        if skill_level is not None:
            return [ReachSkillLevel(skill_level[0], skill_level[1])]
```
Python's `return` fires on the FIRST `(res, drop)` whose `drop == code` AND
whose `resource_skill_level` is present. Entries with `drop == code` but no
skill are SKIPPED (the `if skill_level is not None` guard fails, the loop
continues). We model exactly that: the first entry with matching drop and a
`some` skill. -/
def firstResSkill : List (Nat × Nat × Option (Nat × Nat)) → Nat → Option (Nat × Nat)
  | [], _ => none
  | (_, drop, skill) :: rest, code =>
    if drop = code then
      match skill with
      | some sl => some sl
      | none => firstResSkill rest code
    else firstResSkill rest code

/-! ### The edge list of the `ObtainItem code` branch. -/

/-- `prereqEdges recipe craftSkill resDrops code`: the direct prerequisite edges
of an UNSATISFIED `ObtainItem code`, exactly mirroring the Python branch. -/
def prereqEdges (recipe : Option (List (Nat × Nat))) (craftSkill : Option (Nat × Nat))
    (resDrops : List (Nat × Nat × Option (Nat × Nat))) (code : Nat) : List Edge :=
  match recipe with
  | some ingredients =>
    (match craftSkill with
      | some (s, l) => [Edge.skill s l]
      | none => []) ++ ingredients.map (fun p => Edge.item p.1 p.2)
  | none =>
    match firstResSkill resDrops code with
    | some (s, l) => [Edge.skill s l]
    | none => []

/-! ### combat_capable aggregation. -/

/-- `combatCapable beatable monsters`: `any(predict_win(m) for m in monsters)`,
where `beatable m` abstracts the proven `predict_win` verdict for monster `m`. -/
def combatCapable (beatable : Nat → Bool) (monsters : List Nat) : Bool :=
  monsters.any beatable

/-! ### THEOREMS for `prerequisites` (the ObtainItem edge structure). -/

/-- `prereqs_recipe_with_skill`: a craftable item WITH a crafting skill produces
EXACTLY the skill edge first, then one item edge per ingredient — pinned against
the independently-built expected list (skill edge `::` ingredient edges). -/
theorem prereqs_recipe_with_skill (ingredients : List (Nat × Nat)) (s l : Nat)
    (resDrops : List (Nat × Nat × Option (Nat × Nat))) (code : Nat) :
    prereqEdges (some ingredients) (some (s, l)) resDrops code
      = Edge.skill s l :: ingredients.map (fun p => Edge.item p.1 p.2) := by
  rfl

/-- `prereqs_recipe_no_skill`: a craftable item with NO crafting skill produces
EXACTLY one item edge per ingredient and NO skill edge. -/
theorem prereqs_recipe_no_skill (ingredients : List (Nat × Nat))
    (resDrops : List (Nat × Nat × Option (Nat × Nat))) (code : Nat) :
    prereqEdges (some ingredients) none resDrops code
      = ingredients.map (fun p => Edge.item p.1 p.2) := by
  rfl

/-- `prereqs_membership`: full characterization of edge membership for a
craftable item. An edge is in the prereq set IFF it is the skill edge (when a
crafting skill is present) OR it is an `Edge.item mat qty` for some ingredient
`(mat, qty)` in the recipe. This pins the EXACT edge set (no extra, none
missing) against an independent disjunction. -/
theorem prereqs_membership (ingredients : List (Nat × Nat)) (craftSkill : Option (Nat × Nat))
    (resDrops : List (Nat × Nat × Option (Nat × Nat))) (code : Nat) (e : Edge) :
    e ∈ prereqEdges (some ingredients) craftSkill resDrops code
      ↔ (∃ s l, craftSkill = some (s, l) ∧ e = Edge.skill s l)
        ∨ (∃ mat qty, (mat, qty) ∈ ingredients ∧ e = Edge.item mat qty) := by
  unfold prereqEdges
  cases craftSkill with
  | none =>
    simp only [List.nil_append, List.mem_map]
    constructor
    · rintro ⟨p, hp, he⟩
      exact Or.inr ⟨p.1, p.2, by simpa using hp, by rw [← he]⟩
    · rintro (⟨s, l, hns, _⟩ | ⟨mat, qty, hmem, he⟩)
      · exact absurd hns (by simp)
      · exact ⟨(mat, qty), hmem, he.symm⟩
  | some sl =>
    obtain ⟨s, l⟩ := sl
    simp only [List.cons_append, List.nil_append, List.mem_cons, List.mem_map]
    constructor
    · rintro (he | ⟨p, hp, he⟩)
      · exact Or.inl ⟨s, l, rfl, he⟩
      · exact Or.inr ⟨p.1, p.2, by simpa using hp, by rw [← he]⟩
    · rintro (⟨s', l', hsl, he⟩ | ⟨mat, qty, hmem, he⟩)
      · rw [Option.some.injEq, Prod.ext_iff] at hsl
        obtain ⟨h1, h2⟩ := hsl
        subst h1; subst h2; exact Or.inl he
      · exact Or.inr ⟨(mat, qty), hmem, he.symm⟩

/-- `prereqs_resource_leaf`: a NON-craftable item whose first matching resource
drop has a skill produces EXACTLY that single resource-skill edge. -/
theorem prereqs_resource (resDrops : List (Nat × Nat × Option (Nat × Nat)))
    (code s l : Nat) (h : firstResSkill resDrops code = some (s, l)) :
    prereqEdges none none resDrops code = [Edge.skill s l] := by
  unfold prereqEdges
  rw [h]

/-- `prereqs_leaf`: a NON-craftable item that is NOT the drop of any
skilled resource is a LEAF — NO prerequisites. -/
theorem prereqs_leaf (resDrops : List (Nat × Nat × Option (Nat × Nat))) (code : Nat)
    (h : firstResSkill resDrops code = none) :
    prereqEdges none none resDrops code = [] := by
  unfold prereqEdges
  rw [h]

/-- The resource branch NEVER emits an item edge — it is purely a single skill
edge or empty. So a recipe is the ONLY source of `Edge.item` edges. -/
theorem resource_branch_no_item (resDrops : List (Nat × Nat × Option (Nat × Nat)))
    (code c q : Nat) : Edge.item c q ∉ prereqEdges none none resDrops code := by
  unfold prereqEdges
  cases h : firstResSkill resDrops code with
  | none => simp
  | some sl => obtain ⟨s, l⟩ := sl; simp

/-- `firstResSkill` SOUNDNESS: a returned skill comes from a real `resDrops`
entry whose `drop == code`. The edge is not invented. -/
theorem firstResSkill_sound (resDrops : List (Nat × Nat × Option (Nat × Nat)))
    (code s l : Nat) (h : firstResSkill resDrops code = some (s, l)) :
    ∃ res, (res, code, some (s, l)) ∈ resDrops := by
  induction resDrops with
  | nil => simp [firstResSkill] at h
  | cons hd tl ih =>
    obtain ⟨res, drop, skill⟩ := hd
    unfold firstResSkill at h
    by_cases hd' : drop = code
    · subst hd'
      cases skill with
      | none =>
        simp only [↓reduceIte] at h
        obtain ⟨r, hr⟩ := ih h
        exact ⟨r, List.mem_cons_of_mem _ hr⟩
      | some sl =>
        simp only [↓reduceIte] at h
        rw [Option.some.injEq] at h; subst h
        exact ⟨res, List.mem_cons_self⟩
    · simp only [if_neg hd'] at h
      obtain ⟨r, hr⟩ := ih h
      exact ⟨r, List.mem_cons_of_mem _ hr⟩

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
