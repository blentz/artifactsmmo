-- @concept: planner, plan, gather @property: dominance, safety
/-
# The batched gather bound never exceeds the per-unit one

`min_plan_length` (`ai/min_plan_length.py`) feeds `is_plannable`, the A*-budget
admission gate. Its mint term is switching from `ceil_gathers(min_gathers(...))`
— a count of raw UNITS — to `min_gather_steps(...)`, a count of DISTINCT raw
LEAVES, because a batched `GatherAction` mints a whole material deficit in one
action.

This module proves the one property that protects the gate across that switch:

  `min_gather_steps item qty recipes owned ≤ min_gathers item qty recipes owned`

The bound only ever gets SMALLER **against the raw-unit count**, so measured
there `is_plannable` becomes strictly MORE permissive: no goal it admitted is
newly rejected, and the only exposure is wasted search on a goal the planner
then fails to reach.

## What this does NOT prove — read before quoting it

HISTORICAL NOTE (corrected 2026-08-13): the paragraph below described
production's mint term as `ceil_gathers(min_gathers …)`. That stopped being true
at `c6a4089e` — `min_plan_length.py:47` now calls `min_gather_steps` directly,
and the `ceil_gathers` wrapper is gone from that path. The comparison the
paragraph draws is still the right one to understand (it is why the swap could
only make `is_plannable` more permissive), but read it as the term this module
REPLACED, not the term production runs.

Production's mint term was not `min_gathers` but
`ceil_gathers(min_gathers …, max_gather_yield)`, which divides the unit count by
the resource's drop yield. For `max_gather_yield = 1` `ceil_gathers` is the
identity and the switch is exactly the more-permissive direction proved here.
For `max_gather_yield > 1` it is NOT: a demand spread thinly over several
distinct materials makes the leaf count EXCEED the ceiled unit count, and the
gate gets tighter, not looser, in that corner. That is a real gap in the
"strictly more permissive" story and it is pinned as a kernel-checked witness at
the bottom of this file (`spreadRecipes`: 3 leaves versus `ceil_gathers 3 5 = 1`),
not left to prose. The new value is still the STRUCTURALLY right count under a
batched gather — three materials need three actions — so the tightening is a
tighter bound rather than an unsound one; but it is a behaviour change the
switch's own commit message should own, not a proved non-event.

Both sides are the EXTRACTED oracles — `Extracted.MinGatherSteps.min_gather_steps`
and `Extracted.MinGathers.min_gathers`, each generated verbatim from its Python
source by `scripts/extract_lean.py` and pinned by a sha256 drift gate. The
theorem therefore relates the two functions the planner actually runs, not two
hand-written models of them.

## Why the two recursions can be compared at all

`_min_gather_steps` and `_min_gathers` differ ONLY in the accumulator: a
`List String` of already-counted leaves versus an `Int` running total. Every
control-flow decision (`held`, `used`, `remaining`, the recipe lookup, the
sibling `foldl` order) is a function of the threaded `owned` dictionary alone,
which the two recursions update identically. So the two call trees are the same
tree, and the comparison reduces to a per-node accounting: at each counting
node the leaf list grows by AT MOST one while the total grows by `remaining`
(the leaf arm) or by `qty` (the fuel-exhausted arm).

## The hypothesis is REAL, not decoration

`PosRecipes` (every recipe demands ≥ 1 unit of each material — the same
predicate `Formal.PlanModel.PosRecipes` states) is LOAD-BEARING. Without it the bound is FALSE, and the counterexample is
reachable by the actual Python:

    recipes = {"a": {"b": 1, "z": 0}, "b": {"a": 1}}
    min_gather_steps("a", 1, recipes, {}) = 2   >   min_gathers("a", 1, recipes, {}) = 1

A zero-demand material is never counted by `min_gathers` (it adds `remaining`,
which is 0) but IS counted by `min_gather_steps` when the fuel runs out inside
a recipe cycle, because the fuel-exhausted arm files the item as a leaf without
consulting `qty`. Real API recipes have strictly positive quantities, so the
hypothesis holds of every input the planner can construct; it is stated rather
than assumed silently.
-/

import Formal.Extracted.MinGatherSteps
import Formal.Extracted.MinGathers
import Formal.Extracted.GatherFloor

namespace Formal.MinGatherStepsBound

/-- Recipe table: item ↦ (material, per-unit quantity) list, the shape both
extracted cores consume. -/
abbrev Recipes := List (String × List (String × Int))

/-- Holdings: item ↦ quantity. -/
abbrev Dict := List (String × Int)

/-- Every recipe demands a strictly positive quantity of each material. Stated
exactly as `Formal.PlanModel.PosRecipes`, over the extracted `_dictGetD` the
cores themselves use for the lookup. Items with no
recipe give `[]`, so the condition is vacuous for them. -/
def PosRecipes (recipes : Recipes) : Prop :=
  ∀ item mat per,
    (mat, per) ∈ Extracted.MinGatherSteps._dictGetD recipes item ([] : List (String × Int)) →
      0 < per

-- ---------------------------------------------------------------------------
-- The two extracted dictionary helpers agree
-- ---------------------------------------------------------------------------

/-- The two modules carry independently-extracted copies of the assoc-list
lookup. They compute the same function, so the twinned recursions branch
identically. -/
theorem dictGetD_eq {α : Type} (m : List (String × α)) (k : String) (d : α) :
    Extracted.MinGatherSteps._dictGetD m k d = Extracted.MinGathers._dictGetD m k d := by
  induction m with
  | nil => rfl
  | cons hd tl ih =>
    obtain ⟨k', v⟩ := hd
    simp only [Extracted.MinGatherSteps._dictGetD, Extracted.MinGathers._dictGetD, ih]

/-- Likewise for the in-place assoc-list update: the threaded holdings evolve
identically on both sides. -/
theorem dictSet_eq {α : Type} (m : List (String × α)) (k : String) (v : α) :
    Extracted.MinGatherSteps._dictSet m k v = Extracted.MinGathers._dictSet m k v := by
  induction m with
  | nil => rfl
  | cons hd tl ih =>
    obtain ⟨k', v'⟩ := hd
    simp only [Extracted.MinGatherSteps._dictSet, Extracted.MinGathers._dictSet, ih]

-- ---------------------------------------------------------------------------
-- The coupling invariant
-- ---------------------------------------------------------------------------

/-- The relation carried through the twinned recursions: the two threaded
holdings are identical, and the leaf COUNT exceeds the unit TOTAL by at most
the slack `c`. `c` is a constant of the whole descent — the point of the
formulation is that every arm PRESERVES the slack rather than consuming a
budget, which is what makes it compose through the sibling `foldl`. -/
def Twin (c : Int) (s : List String × Dict) (g : Int × Dict) : Prop :=
  s.2 = g.2 ∧ ((s.1.length : Int) - g.1 ≤ c)

/-- `1 ≤ a` and `1 ≤ b` give `1 ≤ a * b` over `Int` (no Mathlib: this module is
outside the `Formal/Liveness/` quarantine). -/
theorem one_le_mul {a b : Int} (ha : 1 ≤ a) (hb : 1 ≤ b) : 1 ≤ a * b := by
  have h1 : 1 * b ≤ a * b := Int.mul_le_mul_of_nonneg_right ha (by omega)
  omega

/-- A `foldl` over the same list, on both sides, preserves `Twin` as soon as
each individual step does. This is the sibling-recursion glue: `_min_gathers`
and `_min_gather_steps` fold over the SAME recipe list in the SAME order. -/
theorem foldl_twin {β : Type} (c : Int)
    (fS : (List String × Dict) → β → (List String × Dict))
    (fG : (Int × Dict) → β → (Int × Dict)) :
    ∀ (r : List β),
      (∀ b ∈ r, ∀ s g, Twin c s g → Twin c (fS s b) (fG g b)) →
      ∀ s g, Twin c s g → Twin c (r.foldl fS s) (r.foldl fG g) := by
  intro r
  induction r with
  | nil => intro _ s g h; exact h
  | cons a t ih =>
    intro hall s g h
    simp only [List.foldl_cons]
    exact ih (fun b hb => hall b (List.mem_cons_of_mem a hb)) _ _
      (hall a (by simp) s g h)

-- ---------------------------------------------------------------------------
-- The step lemma
-- ---------------------------------------------------------------------------

/-- **Core.** One twinned descent preserves `Twin`.

The `0 < fuel ∨ 1 ≤ qty` side condition is exactly the fuel-exhausted arm's
requirement: that arm files `item` as a leaf (+1 on the left) while adding
`qty` on the right, so it is sound only for `1 ≤ qty`. Every RECURSIVE call
supplies the right disjunct — `per_unit * remaining` with `1 ≤ per_unit`
(`PosRecipes`) and `1 ≤ remaining` (the `remaining ≤ 0` guard failed) — and the
top-level call supplies the left one, since its seeded fuel is
`recipes.length + 1 ≥ 1`. -/
theorem twin_step (recipes : Recipes) (hpos : PosRecipes recipes) :
    ∀ (fuel : Nat) (item : String) (qty c : Int)
      (s : List String × Dict) (g : Int × Dict),
      (0 < fuel ∨ 1 ≤ qty) → Twin c s g →
      Twin c (Extracted.MinGatherSteps._min_gather_steps fuel item qty recipes s)
             (Extracted.MinGathers._min_gathers fuel item qty recipes g) := by
  intro fuel
  induction fuel with
  | zero =>
    intro item qty c s g hq ht
    obtain ⟨hd, hlen⟩ := ht
    have hq1 : 1 ≤ qty := by
      rcases hq with h | h
      · omega
      · exact h
    simp only [Extracted.MinGatherSteps._min_gather_steps, Extracted.MinGathers._min_gathers,
      Twin]
    refine ⟨hd, ?_⟩
    have hcons : ∀ l : List String, ((l ++ [item]).length : Int) = (l.length : Int) + 1 := by
      intro l; simp
    by_cases hc : List.contains s.1 item = true
    · simp only [if_pos hc]
      omega
    · simp only [if_neg hc, hcons]
      omega
  | succ fuel ih =>
    intro item qty c s g _ ht
    obtain ⟨hd, hlen⟩ := ht
    simp only [Extracted.MinGatherSteps._min_gather_steps, Extracted.MinGathers._min_gathers,
      hd, dictGetD_eq, dictSet_eq, decide_eq_true_eq]
    have hcons : ∀ l : List String, ((l ++ [item]).length : Int) = (l.length : Int) + 1 := by
      intro l; simp
    by_cases hrem : qty - min (Extracted.MinGathers._dictGetD g.2 item 0) qty ≤ 0
    · simp only [if_pos hrem]
      exact ⟨rfl, hlen⟩
    · have hrem1 : 1 ≤ qty - min (Extracted.MinGathers._dictGetD g.2 item 0) qty := by omega
      simp only [if_neg hrem]
      by_cases hemp :
          (Int.ofNat (Extracted.MinGathers._dictGetD recipes item
            ([] : List (String × Int))).length) = 0
      · simp only [if_pos hemp]
        refine ⟨rfl, ?_⟩
        by_cases hc : List.contains s.1 item = true
        · simp only [if_pos hc]
          omega
        · simp only [if_neg hc, hcons]
          omega
      · simp only [if_neg hemp]
        refine foldl_twin c _ _
          (Extracted.MinGathers._dictGetD recipes item ([] : List (String × Int)))
          ?_ _ _ ⟨rfl, hlen⟩
        intro b hb s' g' ht'
        have hbpos : 1 ≤ b.2 := by
          have hmem : (b.1, b.2) ∈
              Extracted.MinGatherSteps._dictGetD recipes item ([] : List (String × Int)) := by
            rw [dictGetD_eq]
            simpa using hb
          have := hpos item b.1 b.2 hmem
          omega
        exact ih b.1 (b.2 * (qty - min (Extracted.MinGathers._dictGetD g.2 item 0) qty)) c s' g'
          (Or.inr (one_le_mul hbpos hrem1)) ht'

-- ---------------------------------------------------------------------------
-- The bound
-- ---------------------------------------------------------------------------

/-- **The batched gather bound is never larger than the per-unit one.**

`min_gather_steps` counts DISTINCT raw leaves (one batched `GatherAction` per
material); `min_gathers` counts raw UNITS. Under `PosRecipes` the leaf count is
dominated by the unit count, so swapping `min_plan_length`'s mint term from the
unit count to the leaf count lowers the bound and `is_plannable` admits a
superset of what it admitted before.

Scope, exactly: this compares against `min_gathers`, NOT against
`ceil_gathers(min_gathers …, max_gather_yield)`. The two coincide at
`max_gather_yield = 1`; above it see the module header and the `spreadRecipes`
witness. -/
theorem minGatherSteps_le_minGathers (recipes : Recipes) (owned : Dict)
    (item : String) (qty : Int) (hpos : PosRecipes recipes) :
    Extracted.MinGatherSteps.min_gather_steps item qty recipes owned
      ≤ Extracted.MinGathers.min_gathers item qty recipes owned := by
  have hfuel : Int.toNat ((Int.ofNat (List.length recipes)) + 1) = List.length recipes + 1 := rfl
  have h := twin_step recipes hpos
    (Int.toNat ((Int.ofNat (List.length recipes)) + 1)) item qty 0
    (([], owned) : List String × Dict) ((0, owned) : Int × Dict)
    (Or.inl (by rw [hfuel]; omega)) ⟨rfl, by simp⟩
  obtain ⟨_, hlen⟩ := h
  simp only [Extracted.MinGatherSteps.min_gather_steps, Extracted.MinGathers.min_gathers,
    Int.ofNat_eq_natCast] at hlen ⊢
  omega

-- ---------------------------------------------------------------------------
-- `PosRecipes` is satisfiable, and the bound is not an identity
-- ---------------------------------------------------------------------------

/-- The value `_dictGetD` returns is either one of the table's own values or the
default. Used to reduce `PosRecipes` (a statement about ALL item strings) to a
decidable statement about the table's entries. -/
theorem dictGetD_mem_or {α : Type} (m : List (String × α)) (k : String) (d : α) :
    (∃ p ∈ m, p.2 = Extracted.MinGatherSteps._dictGetD m k d) ∨
      Extracted.MinGatherSteps._dictGetD m k d = d := by
  induction m with
  | nil => exact Or.inr rfl
  | cons hd tl ih =>
    obtain ⟨k', v⟩ := hd
    by_cases h : (k' == k) = true
    · exact Or.inl ⟨(k', v), by simp, by
        simp only [Extracted.MinGatherSteps._dictGetD, h, if_true]⟩
    · simp only [Extracted.MinGatherSteps._dictGetD, h]
      rcases ih with ⟨p, hp, hpe⟩ | hdef
      · exact Or.inl ⟨p, List.mem_cons_of_mem _ hp, hpe⟩
      · exact Or.inr hdef

/-- Introduction rule: a table whose every listed entry demands a positive
quantity satisfies `PosRecipes`. Makes the hypothesis checkable by `decide` on a
concrete table, which is what the non-vacuity witness below needs. -/
theorem posRecipes_of_entries (recipes : Recipes)
    (h : ∀ p ∈ recipes, ∀ m ∈ p.2, 0 < m.2) : PosRecipes recipes := by
  intro item mat per hmem
  rcases dictGetD_mem_or recipes item ([] : List (String × Int)) with ⟨p, hp, hpe⟩ | hdef
  · exact h p hp (mat, per) (hpe ▸ hmem)
  · rw [hdef] at hmem
    exact absurd hmem (by simp)

/-- A two-level table with strictly positive demands: one iron_sword needs 6
iron, one iron needs 10 iron_ore. -/
def demoRecipes : Recipes :=
  [("iron_sword", [("iron", 6)]), ("iron", [("iron_ore", 10)])]

/-- The hypothesis is SATISFIABLE — `demoRecipes` is a `PosRecipes` table. -/
example : PosRecipes demoRecipes := posRecipes_of_entries demoRecipes (by decide)

/-- ...and on it the bound is STRICT, not an identity: 60 raw units of iron_ore
are exactly ONE batched gather action. A proof that only ever compared a
quantity with itself would not survive this pair of `rfl`s. -/
example : Extracted.MinGatherSteps.min_gather_steps "iron_sword" 1 demoRecipes [] = 1 := by
  rfl

example : Extracted.MinGathers.min_gathers "iron_sword" 1 demoRecipes [] = 60 := by
  rfl

/-- One item whose three materials are three DISTINCT raw leaves, one unit each. -/
def spreadRecipes : Recipes := [("x", [("a", 1), ("b", 1), ("c", 1)])]

example : PosRecipes spreadRecipes := posRecipes_of_entries spreadRecipes (by decide)

/-- **The scope limit, kernel-checked.** Three leaves is three batched gather
ACTIONS... -/
example : Extracted.MinGatherSteps.min_gather_steps "x" 1 spreadRecipes [] = 3 := by
  rfl

/-- ...but the production mint term `ceil_gathers(min_gathers …, max_gather_yield)`
scores the same demand at ONE action for a yield-5 resource. So
`minGatherSteps_le_minGathers` does NOT say the switch is more permissive
against the CEILED term: here the new bound is three times the old one, and the
admission gate tightens. Stated as a witness because a `≤` proved against the
wrong expression is exactly the kind of true theorem that tells a false story. -/
example :
    Extracted.GatherFloor.ceil_gathers
      (Extracted.MinGathers.min_gathers "x" 1 spreadRecipes []) 5 = 1 := by
  rfl

/-- At `max_gather_yield = 1` — `ceil_gathers`' identity case — the ordering the
theorem proves is the one production sees. -/
example :
    Extracted.MinGatherSteps.min_gather_steps "iron_sword" 1 demoRecipes []
      ≤ Extracted.GatherFloor.ceil_gathers
          (Extracted.MinGathers.min_gathers "iron_sword" 1 demoRecipes []) 1 := by
  decide

end Formal.MinGatherStepsBound
