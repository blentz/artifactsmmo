/-
Formal model of `task_requirement` / `_item_skill_gap` from
`src/artifactsmmo_cli/ai/task_feasibility.py`.

## `_item_skill_gap(item_code, state, game_data, seen) -> SkillRequirement | None`

A cycle-safe DFS over the crafting closure. `_item_skill_gap(item)`:
* return `None` early if `item ∈ seen`;
* add `item` to `seen`;
* `worst := (this item's requirement)` if the item has a `crafting_skill` whose
  required `crafting_level` exceeds the char's current skill level (UNMET), else
  `None`;
* for every ingredient `sub` in `crafting_recipe(item)`: `r := _item_skill_gap(sub)`;
  if `r.required_level > worst.required_level` then `worst := r`;
* return `worst`.

So the returned requirement's `required_level` is the MAXIMUM `crafting_level`
over the set of UNMET items reachable from `item_code` by following recipe-child
edges (the least fixpoint of the recipe-child relation, seeded by the task
item). It is `None` iff no reachable item is unmet. The `seen` guard makes the
recursion cycle-safe: revisits short-circuit, and `seen` strictly grows within
the finite item universe.

## `task_requirement` monster branch

For a `monsters` task: gates (returns a combat requirement) iff
`monster_level > 0 ∧ monster_level > char_level + MONSTER_LEVEL_MARGIN`, with
`MONSTER_LEVEL_MARGIN = 2`. We pin this as an independent decidable predicate
and verify it at the boundary `monster_level = char_level + 2` (must NOT gate).

We model items as `Nat`. A recipe `r : Nat → List Nat` maps an item to its
ingredient item codes (the qty is irrelevant to feasibility). `craftLevel item`
is the item's required crafting_level, and `unmet item` is `craftLevel item >
skillLevelOf item` AND the item genuinely has a crafting skill — captured by a
boolean `hasSkill item`. (An item with no `crafting_skill` is never a gap,
matching the Python `if stats.crafting_skill:` guard.)

Lean core only — no mathlib.
-/

namespace Formal.TaskFeasibility

/-! ### Recipe-child relation (mirrors RecipeClosure, ingredient-only). -/

/-- A recipe environment: item → its ingredient item codes (empty = raw/unknown,
i.e. `crafting_recipe(...) or {}`). -/
abbrev Recipe := Nat → List Nat

/-- `Reachable r roots m`: `m` is reached from `roots` by following recipe-child
edges — the least fixpoint of the one-step "recipe child" relation. Here we use
single-root closures (`task_requirement` seeds with the one task item), so we
keep the generic list form for reuse. -/
inductive Reachable (r : Recipe) (roots : List Nat) : Nat → Prop
  | root {m : Nat} (h : m ∈ roots) : Reachable r roots m
  | step {item child : Nat} (hi : Reachable r roots item)
      (hc : child ∈ r item) : Reachable r roots child

/-! ### Fuel-bounded saturation (mirrors the DFS visited-set growth). -/

/-- All direct recipe-children of the items in `acc`. -/
def childrenOf (r : Recipe) (acc : List Nat) : List Nat :=
  acc.flatMap (fun item => r item)

/-- One saturation round: `acc` plus all children of `acc`, deduplicated. -/
def stepSet (r : Recipe) (acc : List Nat) : List Nat :=
  (acc ++ childrenOf r acc).eraseDups

/-- `n` saturation rounds from `roots`. -/
def satN (r : Recipe) (roots : List Nat) : Nat → List Nat
  | 0 => roots
  | n + 1 => stepSet r (satN r roots n)

/-- Deduplicated reachable items after `fuel` saturation rounds. -/
def closureItems (r : Recipe) (roots : List Nat) (fuel : Nat) : List Nat :=
  (satN r roots fuel).eraseDups

/-! ### Per-item skill data. -/

/-- Whether the item has a non-empty `crafting_skill` (the Python
`if stats.crafting_skill:` guard). Items without one are never a gap. -/
abbrev HasSkill := Nat → Bool

/-- The item's required crafting level (`stats.crafting_level`). -/
abbrev CraftLevel := Nat → Nat

/-- The char's current skill level for the skill that produces this item
(`state.skills.get(stats.crafting_skill, 0)`). -/
abbrev SkillLevel := Nat → Nat

/-- An item is an UNMET gap iff it has a crafting skill AND its required
crafting level strictly exceeds the char's current level for that skill. -/
def unmet (hasSkill : HasSkill) (craftLevel : CraftLevel) (skillLevel : SkillLevel)
    (item : Nat) : Bool :=
  hasSkill item && decide (skillLevel item < craftLevel item)

/-! ### The "worst required level" as a max over the unmet closure.

`worstLevel` is the maximum `craftLevel` over the UNMET items in the computed
closure (and 0 if none is unmet — matching `None`, since `required_level` is
always ≥ 1 for a real gap when crafting levels are ≥ 1; we keep 0 as the
"no gap" sentinel and prove `none_iff_feasible` from the unmet-list emptiness,
independent of any level being 0). -/

/-- The unmet items within the computed closure. -/
def unmetItems (r : Recipe) (roots : List Nat) (fuel : Nat)
    (hasSkill : HasSkill) (craftLevel : CraftLevel) (skillLevel : SkillLevel) : List Nat :=
  (closureItems r roots fuel).filter (unmet hasSkill craftLevel skillLevel)

/-- Maximum of `f` over a list (0 on the empty list). -/
def listMax (f : Nat → Nat) : List Nat → Nat
  | [] => 0
  | x :: xs => max (f x) (listMax f xs)

/-- The returned `required_level`: the max `craftLevel` over the unmet closure,
or 0 when there is no unmet item (= the Python `None`). -/
def worstLevel (r : Recipe) (roots : List Nat) (fuel : Nat)
    (hasSkill : HasSkill) (craftLevel : CraftLevel) (skillLevel : SkillLevel) : Nat :=
  listMax craftLevel (unmetItems r roots fuel hasSkill craftLevel skillLevel)

/-! ### Monster branch. -/

/-- `MONSTER_LEVEL_MARGIN`. -/
def monsterLevelMargin : Nat := 2

/-- The monster branch gates iff `monster_level > 0 ∧ monster_level > char_level
+ MONSTER_LEVEL_MARGIN`. Modeled on `Nat` (levels are non-negative). -/
def monsterGates (monsterLevel charLevel : Nat) : Bool :=
  decide (0 < monsterLevel) && decide (charLevel + monsterLevelMargin < monsterLevel)

/-! ### Saturation soundness/completeness (the closure = least fixpoint). -/

theorem satN_subset_succ (r : Recipe) (roots : List Nat) (n : Nat) :
    ∀ {m}, m ∈ satN r roots n → m ∈ satN r roots (n + 1) := by
  intro m hm
  simp only [satN, stepSet, List.mem_eraseDups, List.mem_append]
  exact Or.inl hm

theorem satN_sound (r : Recipe) (roots : List Nat) :
    ∀ (n : Nat) {m}, m ∈ satN r roots n → Reachable r roots m := by
  intro n
  induction n with
  | zero => intro m hm; exact Reachable.root hm
  | succ k ih =>
    intro m hm
    simp only [satN, stepSet, List.mem_eraseDups, List.mem_append] at hm
    rcases hm with h | h
    · exact ih h
    · simp only [childrenOf, List.mem_flatMap] at h
      obtain ⟨item, hitem, hchild⟩ := h
      exact Reachable.step (ih hitem) hchild

theorem reachable_satN (r : Recipe) (roots : List Nat) {m : Nat}
    (h : Reachable r roots m) : ∃ n, m ∈ satN r roots n := by
  induction h with
  | root hm => exact ⟨0, hm⟩
  | step hi hc ih =>
    obtain ⟨n, hn⟩ := ih
    refine ⟨n + 1, ?_⟩
    simp only [satN, stepSet, List.mem_eraseDups, List.mem_append, childrenOf, List.mem_flatMap]
    exact Or.inr ⟨_, hn, hc⟩

theorem satN_mono (r : Recipe) (roots : List Nat) (n k : Nat) :
    ∀ {m}, m ∈ satN r roots n → m ∈ satN r roots (n + k) := by
  induction k with
  | zero => intro m hm; exact hm
  | succ j ih =>
    intro m hm
    exact satN_subset_succ r roots (n + j) (ih hm)

theorem reachable_iff_satN (r : Recipe) (roots : List Nat) (m : Nat) :
    Reachable r roots m ↔ ∃ n, m ∈ satN r roots n := by
  constructor
  · exact reachable_satN r roots
  · rintro ⟨n, hn⟩; exact satN_sound r roots n hn

theorem closureItems_sound (r : Recipe) (roots : List Nat) (fuel : Nat) {m : Nat}
    (h : m ∈ closureItems r roots fuel) : Reachable r roots m := by
  unfold closureItems at h
  rw [List.mem_eraseDups] at h
  exact satN_sound r roots fuel h

theorem closureItems_complete (r : Recipe) (roots : List Nat) (fuel n : Nat)
    (hle : n ≤ fuel) {m : Nat} (h : m ∈ satN r roots n) :
    m ∈ closureItems r roots fuel := by
  unfold closureItems
  rw [List.mem_eraseDups]
  obtain ⟨k, rfl⟩ := Nat.exists_eq_add_of_le hle
  exact satN_mono r roots n k h

/-! ### `listMax` characterization. -/

/-- Every element's `f`-value is ≤ the list max. -/
theorem le_listMax (f : Nat → Nat) {x : Nat} {xs : List Nat} (h : x ∈ xs) :
    f x ≤ listMax f xs := by
  induction xs with
  | nil => exact absurd h (List.not_mem_nil)
  | cons hd tl ih =>
    rcases List.mem_cons.mp h with rfl | h
    · exact Nat.le_max_left _ _
    · exact Nat.le_trans (ih h) (Nat.le_max_right _ _)

/-- The list max (over a nonempty list) is ATTAINED by some element. -/
theorem listMax_mem (f : Nat → Nat) :
    ∀ {xs : List Nat}, xs ≠ [] → ∃ x ∈ xs, f x = listMax f xs := by
  intro xs
  induction xs with
  | nil => intro h; exact absurd rfl h
  | cons hd tl ih =>
    intro _
    by_cases htl : tl = []
    · subst htl
      exact ⟨hd, List.mem_cons_self, by simp [listMax]⟩
    · obtain ⟨y, hy, hey⟩ := ih htl
      rcases Nat.le_total (f hd) (listMax f tl) with hle | hle
      · refine ⟨y, List.mem_cons_of_mem _ hy, ?_⟩
        rw [listMax]; rw [hey]; exact (Nat.max_eq_right hle).symm
      · refine ⟨hd, List.mem_cons_self, ?_⟩
        rw [listMax]; rw [← hey] at hle ⊢; exact (Nat.max_eq_left hle).symm

/-- `listMax = 0` iff every element maps to 0 (used for the none branch). -/
theorem listMax_eq_zero_iff (f : Nat → Nat) (xs : List Nat) :
    listMax f xs = 0 ↔ ∀ x ∈ xs, f x = 0 := by
  induction xs with
  | nil => simp [listMax]
  | cons hd tl ih =>
    rw [listMax, Nat.max_eq_zero_iff]
    constructor
    · rintro ⟨h0, ht⟩ x hx
      rcases List.mem_cons.mp hx with rfl | hx
      · exact h0
      · exact (ih.mp ht) x hx
    · intro h
      exact ⟨h hd List.mem_cons_self, ih.mpr (fun x hx => h x (List.mem_cons_of_mem _ hx))⟩

/-! ### MAIN THEOREMS. -/

/-- `worst_eq_max_unmet`: the returned `required_level` equals the MAXIMUM
`craftLevel` over the UNMET items in the craft closure of the task item.
This is `worstLevel`'s definition, restated as a characterization: it is the
max of `craftLevel` over exactly `unmetItems`. -/
theorem worst_eq_max_unmet (r : Recipe) (roots : List Nat) (fuel : Nat)
    (hasSkill : HasSkill) (craftLevel : CraftLevel) (skillLevel : SkillLevel) :
    worstLevel r roots fuel hasSkill craftLevel skillLevel
      = listMax craftLevel (unmetItems r roots fuel hasSkill craftLevel skillLevel) := rfl

/-- An item is in `unmetItems` iff it is in the computed closure AND is unmet —
pins the set the max is taken over. -/
theorem mem_unmetItems_iff (r : Recipe) (roots : List Nat) (fuel : Nat)
    (hasSkill : HasSkill) (craftLevel : CraftLevel) (skillLevel : SkillLevel) (m : Nat) :
    m ∈ unmetItems r roots fuel hasSkill craftLevel skillLevel
      ↔ m ∈ closureItems r roots fuel ∧ unmet hasSkill craftLevel skillLevel m = true := by
  unfold unmetItems
  rw [List.mem_filter]

/-- A member of the unmet set is genuinely `Reachable` and genuinely unmet. -/
theorem unmetItems_sound (r : Recipe) (roots : List Nat) (fuel : Nat)
    (hasSkill : HasSkill) (craftLevel : CraftLevel) (skillLevel : SkillLevel) {m : Nat}
    (h : m ∈ unmetItems r roots fuel hasSkill craftLevel skillLevel) :
    Reachable r roots m ∧ unmet hasSkill craftLevel skillLevel m = true := by
  rw [mem_unmetItems_iff] at h
  exact ⟨closureItems_sound r roots fuel h.1, h.2⟩

/-- `none_iff_feasible`: the result is "none" (worst = 0) IFF no reachable item
in the closure is unmet (every item in the closure with a crafting skill is
within reach), GIVEN crafting levels of any genuine gap are positive. We state
it via the unmet set being empty of POSITIVE-level gaps. The clean form: the max
is 0 iff every unmet closure item has craftLevel 0. Combined with the fact that
a real gap has `skillLevel < craftLevel` so `craftLevel ≥ 1`, worst = 0 ⟺ no
genuine (positive-level) gap. We prove the exact set-emptiness equivalence. -/
theorem none_iff_feasible (r : Recipe) (roots : List Nat) (fuel : Nat)
    (hasSkill : HasSkill) (craftLevel : CraftLevel) (skillLevel : SkillLevel) :
    worstLevel r roots fuel hasSkill craftLevel skillLevel = 0
      ↔ ∀ m ∈ closureItems r roots fuel,
          unmet hasSkill craftLevel skillLevel m = true → craftLevel m = 0 := by
  unfold worstLevel
  rw [listMax_eq_zero_iff]
  constructor
  · intro h m hm hu
    exact h m (by rw [mem_unmetItems_iff]; exact ⟨hm, hu⟩)
  · intro h m hm
    rw [mem_unmetItems_iff] at hm
    exact h m hm.1 hm.2

/-- A sharper none-direction: under the natural hypothesis that every closure
item's craft level is positive (real game data: crafting levels ≥ 1), worst = 0
IFF there is NO unmet item in the closure at all (the true "feasible" condition).
This is the operational `result is None ↔ no unmet gap`. -/
theorem none_iff_no_unmet (r : Recipe) (roots : List Nat) (fuel : Nat)
    (hasSkill : HasSkill) (craftLevel : CraftLevel) (skillLevel : SkillLevel)
    (hpos : ∀ m ∈ closureItems r roots fuel,
        unmet hasSkill craftLevel skillLevel m = true → 0 < craftLevel m) :
    worstLevel r roots fuel hasSkill craftLevel skillLevel = 0
      ↔ ∀ m ∈ closureItems r roots fuel,
          unmet hasSkill craftLevel skillLevel m = false := by
  rw [none_iff_feasible]
  constructor
  · intro h m hm
    by_cases hu : unmet hasSkill craftLevel skillLevel m = true
    · have := h m hm hu
      have := hpos m hm hu
      omega
    · simpa using hu
  · intro h m hm hu
    rw [h m hm] at hu
    exact absurd hu (by simp)

/-- `worst_is_real_gap`: if the result is positive (> 0), there genuinely EXISTS
an item in the craft closure that is UNMET and whose `craftLevel` equals exactly
the returned worst level. The reported requirement is REAL, not invented. -/
theorem worst_is_real_gap (r : Recipe) (roots : List Nat) (fuel : Nat)
    (hasSkill : HasSkill) (craftLevel : CraftLevel) (skillLevel : SkillLevel)
    (h : 0 < worstLevel r roots fuel hasSkill craftLevel skillLevel) :
    ∃ m, Reachable r roots m ∧ unmet hasSkill craftLevel skillLevel m = true ∧
      craftLevel m = worstLevel r roots fuel hasSkill craftLevel skillLevel := by
  unfold worstLevel at h ⊢
  have hne : unmetItems r roots fuel hasSkill craftLevel skillLevel ≠ [] := by
    intro hnil
    rw [hnil] at h
    simp [listMax] at h
  obtain ⟨m, hm, hem⟩ := listMax_mem craftLevel hne
  refine ⟨m, ?_, ?_, hem⟩
  · exact (unmetItems_sound r roots fuel hasSkill craftLevel skillLevel hm).1
  · exact (unmetItems_sound r roots fuel hasSkill craftLevel skillLevel hm).2

/-- The worst level is ATTAINED: it equals some closure item's craft level, and
every unmet closure item's craft level is ≤ it (max characterization combined). -/
theorem worst_is_max (r : Recipe) (roots : List Nat) (fuel : Nat)
    (hasSkill : HasSkill) (craftLevel : CraftLevel) (skillLevel : SkillLevel) {m : Nat}
    (hm : m ∈ unmetItems r roots fuel hasSkill craftLevel skillLevel) :
    craftLevel m ≤ worstLevel r roots fuel hasSkill craftLevel skillLevel :=
  le_listMax craftLevel hm

/-! ### MONSTER GATE — pinned via an independent statement (not X ↔ X).

We pin the gate against an explicit arithmetic spec, and crucially verify the
BOUNDARY `monster_level = char_level + 2` must NOT gate (a hand-checked false
case), plus `char_level + 3` must gate. This catches an off-by-one margin: an
implementation that used `≥` (margin off by one) would gate at the boundary,
contradicting `monster_gate_boundary_false`. -/

/-- `monster_gate`: the gate fires iff `0 < monster_level` and `monster_level >
char_level + 2`. The RHS is an independent arithmetic predicate (not the
function reapplied), so equality is a genuine specification. -/
theorem monster_gate (monsterLevel charLevel : Nat) :
    monsterGates monsterLevel charLevel = true
      ↔ (0 < monsterLevel ∧ charLevel + 2 < monsterLevel) := by
  unfold monsterGates monsterLevelMargin
  rw [Bool.and_eq_true, decide_eq_true_eq, decide_eq_true_eq]

/-- BOUNDARY (hand-table, must be FALSE): a monster EXACTLY at `char_level + 2`
does NOT gate — the rule is strictly-greater-than the margin. This is the
off-by-one anchor: it would be TRUE under a `≥`-margin bug. -/
theorem monster_gate_boundary_false (charLevel : Nat) :
    monsterGates (charLevel + 2) charLevel = false := by
  unfold monsterGates monsterLevelMargin
  simp

/-- Just past the boundary (`char_level + 3`) the gate MUST fire — the other
side of the off-by-one anchor. -/
theorem monster_gate_just_past (charLevel : Nat) :
    monsterGates (charLevel + 3) charLevel = true := by
  unfold monsterGates monsterLevelMargin
  simp

/-- A zero-level monster (unknown / `monster_level == 0`) never gates, regardless
of char level — the `monster_level > 0` guard. -/
theorem monster_gate_zero_never (charLevel : Nat) :
    monsterGates 0 charLevel = false := by
  unfold monsterGates
  simp

/-- Concrete boundary hand-table at char level 5: monster level 7 (= 5 + 2) does
NOT gate; level 8 does. Fully closed `decide` — pins the exact threshold. -/
example : monsterGates 7 5 = false ∧ monsterGates 8 5 = true := by decide

end Formal.TaskFeasibility
