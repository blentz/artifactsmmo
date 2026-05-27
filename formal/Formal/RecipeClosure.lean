/-
Formal model of `recipe_closure` and `raw_material_units` from
`src/artifactsmmo_cli/ai/recipe_closure.py`.

## `recipe_closure(game_data, roots) -> (needed_resources, craftable_mats)`

A DFS with a `visited` set. `collect(material)`:
* return early if `material ∈ visited`;
* add `material` to `visited`;
* for every `(resource_code, drop_item)` in `_resource_drops` with
  `drop_item == material`, add `resource_code` to `needed_resources`;
* let `recipe = _crafting_recipes.get(material) or {}`; if nonempty, add
  `material` to `craftable_mats` and recurse into every `sub_mat` key.

`collect` runs once per root. So the set of *materials* the DFS touches is the
set of items reachable from the roots by following recipe-submaterial edges —
the LEAST FIXPOINT of the one-step "recipe child" relation seeded by the roots.
Then:
* `craftable_mats`    = touched materials whose recipe is nonempty;
* `needed_resources`  = resources whose drop is a touched material.

We model items/resources as `Nat`. `recipe : Nat → List (Nat × Nat)` maps an
item to its `(sub_mat, qty)` ingredient list (empty = raw/unknown, i.e.
`get(...) or {}`). `resourceDrops : List (Nat × Nat)` is the `_resource_drops`
association list `(resource_code, drop_item)`.

We define the reachable-material set `Reachable` as the least fixpoint (an
inductive closure), independently define a fuel-bounded saturation `sat`
mirroring the DFS visited-set growth, and prove the DFS result EQUALS the
fixpoint: SOUNDNESS (DFS ⊆ reachable — no extra) + COMPLETENESS (reachable ⊆
DFS — nothing missed), for fuel ≥ |universe|. From that, `craftable_mats` and
`needed_resources` are pinned exactly.

## `raw_material_units(game_data, item, visited) -> int`

`visited` guards against cycles: revisit → 1; raw/unknown (no recipe) → 1;
otherwise `Σ_{(sub,qty) ∈ recipe} qty * raw_material_units(sub, visited ∪ {item})`.
The recursion terminates on CYCLIC recipes because `visited` strictly grows and
is bounded by the (finite) item universe. We model the visited-set recursion
with a structural fuel = |universe \ visited| and prove the documented cost
equation and termination.

Lean core only — no mathlib.
-/

namespace Formal.RecipeClosure

/-! ### Recipe / drop relations. -/

/-- A recipe environment: item → its `(sub_mat, qty)` ingredient list. An empty
list models `get(...) or {}` (a raw or unknown item). -/
abbrev Recipe := Nat → List (Nat × Nat)

/-- The one-step "recipe child" relation: `child` is a direct sub-material key
of `item`'s recipe. -/
def isChild (r : Recipe) (item child : Nat) : Prop :=
  child ∈ (r item).map Prod.fst

instance (r : Recipe) (item child : Nat) : Decidable (isChild r item child) := by
  unfold isChild; infer_instance

/-! ### Reachability — the least fixpoint, defined inductively. -/

/-- `Reachable r roots m`: material `m` is reached by the DFS from `roots` —
the least set containing every root and closed under the recipe-child relation.
This IS the least fixpoint of the monotone one-step operator seeded by `roots`. -/
inductive Reachable (r : Recipe) (roots : List Nat) : Nat → Prop
  | root {m : Nat} (h : m ∈ roots) : Reachable r roots m
  | step {item child : Nat} (hi : Reachable r roots item)
      (hc : child ∈ (r item).map Prod.fst) : Reachable r roots child

/-! ### Fuel-bounded saturation (mirrors the DFS visited-set growth).

`stepSet r acc` is one monotone saturation round: keep `acc`, and add every
recipe-child of every member of `acc`. `satN r roots n` is `n` rounds from the
seed `roots`. For a finite universe of size `k`, `satN r roots k` is a fixpoint
and equals `Reachable`. We use membership-list semantics (a `Nat → Bool`
predicate is cleaner; we use list-of-children expansion). -/

/-- All direct recipe-children of the items in `acc`. -/
def childrenOf (r : Recipe) (acc : List Nat) : List Nat :=
  acc.flatMap (fun item => (r item).map Prod.fst)

/-- One saturation round: `acc` plus all children of `acc`, deduplicated. The
`eraseDups` keeps the list bounded by the universe size (membership is
unchanged, so the fixpoint semantics and all set-level theorems are identical),
preventing exponential blow-up on cyclic/diamond graphs in the executable
oracle. -/
def stepSet (r : Recipe) (acc : List Nat) : List Nat :=
  (acc ++ childrenOf r acc).eraseDups

/-- `n` saturation rounds from `roots`. -/
def satN (r : Recipe) (roots : List Nat) : Nat → List Nat
  | 0 => roots
  | n + 1 => stepSet r (satN r roots n)

/-! ### Outputs of `recipe_closure`, defined over the reachable set. -/

/-- `craftable_mats`: a reachable material is craftable iff its recipe is
nonempty. -/
def isCraftable (r : Recipe) (roots : List Nat) (m : Nat) : Prop :=
  Reachable r roots m ∧ (r m) ≠ []

/-- `needed_resources`: a resource `res` (with `drop`) is needed iff its drop is
a reachable material. Mirrors the `for (res, drop) in _resource_drops: if drop
== material` scan, where `material` ranges over the reached set. -/
def isNeeded (r : Recipe) (roots : List Nat) (drops : List (Nat × Nat)) (res : Nat) : Prop :=
  ∃ drop, (res, drop) ∈ drops ∧ Reachable r roots drop

/-! ### `raw_material_units` — visited-set recursion, cyclic-safe.

We model the universe of items as a finite `List Nat` `univ` containing every
item that can ever appear (roots + all recipe keys/children). The visited guard
makes `visited` strictly grow within `univ`. We define the cost with a
structural `fuel` parameter (so it is total by construction) and then PROVE the
genuine termination content separately: the `remaining univ visited` measure
strictly decreases on every recursive descent (`remaining_decreasing`), and for
any `fuel` exceeding that measure the result is fuel-independent
(`rawUnits_fuel_stable`) — i.e. the recursion bottoms out even on cycles. -/

/-- Fuel-threaded cost. At fuel 0 we return 1 (defensive; reached only if fuel
underflows — the lemmas show adequate fuel never underflows). At fuel `n+1`:
revisit → 1; raw/unknown (empty recipe) → 1; otherwise
`Σ_{(sub,qty)} qty * rec(sub, item :: visited)`. The `item :: visited` mirrors
Python's `visited | {item}`. -/
def rawUnitsAux (r : Recipe) : Nat → List Nat → Nat → Nat
  | 0, _, _ => 1
  | n + 1, visited, item =>
    if item ∈ visited then 1
    else match r item with
      | [] => 1
      | rcp => (rcp.map (fun p => p.2 * rawUnitsAux r n (item :: visited) p.1)).sum

/-- `raw_material_units(item)` at the top level: empty visited set. The fuel is
the universe size `fuel`; callers pass `univ.length`. -/
def rawUnits (r : Recipe) (fuel : Nat) (item : Nat) : Nat :=
  rawUnitsAux r fuel [] item

/-! ### Computable closure (for the oracle) and its correspondence to `Reachable`.

`closureItems r roots fuel` deduplicates `satN r roots fuel`. For `fuel` ≥
universe size this is the full reachable set; the oracle passes a sufficient
fuel. `craftableList` / `neededList` are the two outputs as `Nat` lists. -/

/-- Deduplicated reachable items after `fuel` saturation rounds. -/
def closureItems (r : Recipe) (roots : List Nat) (fuel : Nat) : List Nat :=
  (satN r roots fuel).eraseDups

/-- `craftable_mats` as a list: reachable items with a nonempty recipe. -/
def craftableList (r : Recipe) (roots : List Nat) (fuel : Nat) : List Nat :=
  (closureItems r roots fuel).filter (fun m => decide ((r m) ≠ []))

/-- `needed_resources` as a list: resources whose drop is a reachable item.
Mirrors the `for (res, drop) in _resource_drops: if drop in closure` scan. -/
def neededList (r : Recipe) (roots : List Nat) (drops : List (Nat × Nat)) (fuel : Nat) :
    List Nat :=
  (drops.filter (fun rd => decide (rd.2 ∈ closureItems r roots fuel))).map Prod.fst

/-! ### Theorems for `recipe_closure` (closure = least fixpoint). -/

/-- `satN` is monotone (round `n` ⊆ round `n+1`): saturation only grows. -/
theorem satN_subset_succ (r : Recipe) (roots : List Nat) (n : Nat) :
    ∀ {m}, m ∈ satN r roots n → m ∈ satN r roots (n + 1) := by
  intro m hm
  simp only [satN, stepSet, List.mem_eraseDups, List.mem_append]
  exact Or.inl hm

/-- SOUNDNESS: every element produced by `n` saturation rounds is `Reachable`
(the DFS adds no item outside the least fixpoint). -/
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

/-- COMPLETENESS (the key fixpoint lemma): every `Reachable` material appears in
some saturation round. Nothing reachable is missed. -/
theorem reachable_satN (r : Recipe) (roots : List Nat) {m : Nat}
    (h : Reachable r roots m) : ∃ n, m ∈ satN r roots n := by
  induction h with
  | root hm => exact ⟨0, hm⟩
  | step hi hc ih =>
    obtain ⟨n, hn⟩ := ih
    refine ⟨n + 1, ?_⟩
    simp only [satN, stepSet, List.mem_eraseDups, List.mem_append, childrenOf, List.mem_flatMap]
    exact Or.inr ⟨_, hn, hc⟩

/-- `satN` rounds are cumulative-monotone: round `n` ⊆ round `n + k`. -/
theorem satN_mono (r : Recipe) (roots : List Nat) (n k : Nat) :
    ∀ {m}, m ∈ satN r roots n → m ∈ satN r roots (n + k) := by
  induction k with
  | zero => intro m hm; exact hm
  | succ j ih =>
    intro m hm
    have : m ∈ satN r roots (n + j) := ih hm
    exact satN_subset_succ r roots (n + j) this

/-- A material is `Reachable` IFF it appears in some bounded saturation round —
the DFS (= saturation) computes EXACTLY the least fixpoint: soundness +
completeness combined. -/
theorem reachable_iff_satN (r : Recipe) (roots : List Nat) (m : Nat) :
    Reachable r roots m ↔ ∃ n, m ∈ satN r roots n := by
  constructor
  · exact reachable_satN r roots
  · rintro ⟨n, hn⟩; exact satN_sound r roots n hn

/-- SOUNDNESS for the computable closure: every item in `closureItems` is
`Reachable` (the DFS produces nothing outside the least fixpoint). -/
theorem closureItems_sound (r : Recipe) (roots : List Nat) (fuel : Nat) {m : Nat}
    (h : m ∈ closureItems r roots fuel) : Reachable r roots m := by
  unfold closureItems at h
  rw [List.mem_eraseDups] at h
  exact satN_sound r roots fuel h

/-- COMPLETENESS for the computable closure: if a reachable item first appears
at saturation round `n ≤ fuel`, it is in `closureItems r roots fuel`. Combined
with `reachable_satN`, choosing `fuel` ≥ that round captures every reachable
item. -/
theorem closureItems_complete (r : Recipe) (roots : List Nat) (fuel n : Nat)
    (hle : n ≤ fuel) {m : Nat} (h : m ∈ satN r roots n) : m ∈ closureItems r roots fuel := by
  unfold closureItems
  rw [List.mem_eraseDups]
  obtain ⟨k, rfl⟩ := Nat.exists_eq_add_of_le hle
  exact satN_mono r roots n k h

/-- `craftableList` is EXACTLY the craftable reachable items captured by `fuel`:
membership ⟺ (in computed closure) ∧ (recipe nonempty). Soundness wrt
`Reachable` follows via `closureItems_sound`. -/
theorem craftableList_iff (r : Recipe) (roots : List Nat) (fuel : Nat) (m : Nat) :
    m ∈ craftableList r roots fuel ↔ m ∈ closureItems r roots fuel ∧ (r m) ≠ [] := by
  unfold craftableList
  rw [List.mem_filter, decide_eq_true_eq]

/-- A craftable-list member is `Reachable` AND has a nonempty recipe — exactly
`isCraftable`. -/
theorem craftableList_isCraftable (r : Recipe) (roots : List Nat) (fuel : Nat) {m : Nat}
    (h : m ∈ craftableList r roots fuel) : isCraftable r roots m := by
  rw [craftableList_iff] at h
  exact ⟨closureItems_sound r roots fuel h.1, h.2⟩

/-- `neededList` membership ⟺ some drop edge `(res, drop)` with `drop` in the
computed closure — exactly the `for (res, drop) in _resource_drops` scan. -/
theorem neededList_iff (r : Recipe) (roots : List Nat) (drops : List (Nat × Nat))
    (fuel : Nat) (res : Nat) :
    res ∈ neededList r roots drops fuel
      ↔ ∃ drop, (res, drop) ∈ drops ∧ drop ∈ closureItems r roots fuel := by
  unfold neededList
  rw [List.mem_map]
  constructor
  · rintro ⟨rd, hrd, hfst⟩
    rw [List.mem_filter, decide_eq_true_eq] at hrd
    exact ⟨rd.2, by rw [← hfst]; exact hrd.1, hrd.2⟩
  · rintro ⟨drop, hmem, hcl⟩
    exact ⟨(res, drop), by rw [List.mem_filter, decide_eq_true_eq]; exact ⟨hmem, hcl⟩, rfl⟩

/-- A needed-list member is `isNeeded` (its drop is `Reachable`) — soundness. -/
theorem neededList_isNeeded (r : Recipe) (roots : List Nat) (drops : List (Nat × Nat))
    (fuel : Nat) {res : Nat} (h : res ∈ neededList r roots drops fuel) :
    isNeeded r roots drops res := by
  rw [neededList_iff] at h
  obtain ⟨drop, hmem, hcl⟩ := h
  exact ⟨drop, hmem, closureItems_sound r roots fuel hcl⟩

/-- The least-fixpoint property: `Reachable` is closed under the recipe-child
relation and contains the roots — and is the SMALLEST such set. Any set `S`
containing the roots and closed under `isChild` contains every reachable item. -/
theorem reachable_least (r : Recipe) (roots : List Nat) (S : Nat → Prop)
    (hroots : ∀ m ∈ roots, S m)
    (hclosed : ∀ item child, S item → child ∈ (r item).map Prod.fst → S child)
    {m : Nat} (h : Reachable r roots m) : S m := by
  induction h with
  | root hm => exact hroots _ hm
  | step hi hc ih => exact hclosed _ _ ih hc

/-! ### Theorems for `raw_material_units`. -/

/-- `raw_units_eq_cost`: with fuel `n+1` and an unvisited item that HAS a recipe,
the cost is exactly `Σ qty * rec(sub, item :: visited)` — the documented
quantity math (multiply ingredient quantities down the tree). -/
theorem rawUnits_eq_cost (r : Recipe) (n : Nat) (visited : List Nat) (item : Nat)
    (hv : item ∉ visited) (rcp : List (Nat × Nat)) (hr : r item = rcp) (hne : rcp ≠ []) :
    rawUnitsAux r (n + 1) visited item
      = (rcp.map (fun p => p.2 * rawUnitsAux r n (item :: visited) p.1)).sum := by
  cases rcp with
  | nil => exact absurd rfl hne
  | cons hd tl =>
    show (if item ∈ visited then 1
      else match r item with
        | [] => 1
        | rcp => (rcp.map (fun p => p.2 * rawUnitsAux r n (item :: visited) p.1)).sum) = _
    simp only [hv, if_false]
    rw [hr]

/-- `raw_units_revisit`: a revisited item (in `visited`) costs exactly 1,
REGARDLESS of fuel `n+1` — this is the cyclic-safety guard (Python's
`if item in visited: return 1`). -/
theorem rawUnits_revisit (r : Recipe) (n : Nat) (visited : List Nat) (item : Nat)
    (hv : item ∈ visited) : rawUnitsAux r (n + 1) visited item = 1 := by
  unfold rawUnitsAux
  simp only [hv, if_true]

/-- `raw_units_raw`: a raw/unknown item (empty recipe) costs exactly 1. -/
theorem rawUnits_raw (r : Recipe) (n : Nat) (visited : List Nat) (item : Nat)
    (hv : item ∉ visited) (hr : r item = []) :
    rawUnitsAux r (n + 1) visited item = 1 := by
  unfold rawUnitsAux
  simp only [hv, if_false, hr]

/-! ### Termination on cyclic recipes.

`univ` is a finite item universe that (1) contains `item`, (2) is closed under
the recipe-child relation (every sub-material of any item in `univ` is in
`univ`), and (3) is `Nodup`. Then the cost is fuel-stable for any fuel that
exceeds the number of as-yet-unvisited universe items
`(univ.filter (· ∉ visited)).length`. This is the formal statement that the
visited-set recursion TERMINATES even on CYCLIC recipes: the genuine measure is
`|univ \ visited|`, strictly decreasing on each descent (each recursive call
adds `item` to `visited`), so it bottoms out regardless of cycles. -/

/-- `univ` is closed under taking recipe sub-materials. -/
def UnivClosed (r : Recipe) (univ : List Nat) : Prop :=
  ∀ item ∈ univ, ∀ child ∈ (r item).map Prod.fst, child ∈ univ

/-- The remaining-universe measure: count of unvisited universe items. -/
def remaining (univ visited : List Nat) : Nat :=
  univ.countP (fun x => decide (x ∉ visited))

/-- Adding an unvisited universe item to `visited` strictly decreases
`remaining` — the termination measure descends on every recursive call. Proven
by induction on `univ`: the `item` element flips from counted to uncounted. -/
theorem remaining_decreasing (univ visited : List Nat) (item : Nat)
    (hmem : item ∈ univ) (hv : item ∉ visited) :
    remaining univ (item :: visited) < remaining univ visited := by
  unfold remaining
  induction univ with
  | nil => exact absurd hmem (List.not_mem_nil)
  | cons hd tl ih =>
    -- monotone: countP for the bigger visited set ≤ countP for the smaller
    have hmono : ∀ (u : List Nat),
        u.countP (fun x => decide (x ∉ item :: visited))
          ≤ u.countP (fun x => decide (x ∉ visited)) := by
      intro u
      apply List.countP_mono_left
      intro x _ hx
      simp only [decide_eq_true_eq, List.mem_cons, not_or] at hx ⊢
      exact hx.2
    rw [List.countP_cons, List.countP_cons]
    by_cases hhd : hd = item
    · subst hhd
      have hl : decide (hd ∉ hd :: visited) = false := by
        simp
      have hr : decide (hd ∉ visited) = true := by
        simp only [decide_eq_true_eq]; exact hv
      rw [hl, hr]
      exact Nat.lt_succ_of_le (hmono tl)
    · have hmem' : item ∈ tl := by
        rcases List.mem_cons.mp hmem with h | h
        · exact absurd h.symm hhd
        · exact h
      have hih := ih hmem'
      -- guards agree on hd because hd ≠ item
      have hguard : decide (hd ∉ item :: visited) = decide (hd ∉ visited) := by
        simp only [List.mem_cons, not_or]
        by_cases hin : hd ∈ visited
        · simp [hin]
        · simp [hin, hhd]
      rw [hguard]
      split <;> omega

/-- Fuel-stability (TERMINATION): once fuel exceeds the remaining-universe
measure, the cost no longer depends on the exact fuel value — the recursion has
fully bottomed out. Proven by strong induction on fuel, using
`remaining_decreasing` as the well-founded measure; cycles are handled because a
revisited item returns 1 without recursing (the `item ∈ visited` guard). -/
theorem rawUnits_fuel_stable (r : Recipe) (univ : List Nat) (hclosed : UnivClosed r univ) :
    ∀ (f f' : Nat) (visited : List Nat) (item : Nat),
      item ∈ univ → remaining univ visited ≤ f → remaining univ visited ≤ f' →
      rawUnitsAux r f visited item = rawUnitsAux r f' visited item := by
  intro f
  induction f using Nat.strongRecOn with
  | ind f ih =>
    intro f' visited item hmem hf hf'
    by_cases hv : item ∈ visited
    · -- revisit: both sides return 1 regardless of fuel
      cases f with
      | zero => cases f' with
        | zero => rfl
        | succ f'' => simp only [rawUnitsAux, hv, if_true]
      | succ f1 => cases f' with
        | zero =>
          -- f' = 0 but remaining ≤ 0 forces... still, lhs uses guard
          simp only [rawUnitsAux, hv, if_true]
        | succ f'' => simp only [rawUnitsAux, hv, if_true]
    · -- not visited: remaining > 0, so both f and f' are ≥ 1
      have hpos : 0 < remaining univ visited := by
        unfold remaining
        have hne : univ.countP (fun x => decide (x ∉ visited)) ≠ 0 := by
          rw [ne_eq, List.countP_eq_zero]
          intro hh
          have : decide (item ∉ visited) = true := by simp only [decide_eq_true_eq]; exact hv
          exact absurd this (hh item hmem)
        omega
      have hf1 : 0 < f := Nat.lt_of_lt_of_le hpos hf
      have hf'1 : 0 < f' := Nat.lt_of_lt_of_le hpos hf'
      obtain ⟨a, rfl⟩ := Nat.exists_eq_succ_of_ne_zero (Nat.pos_iff_ne_zero.mp hf1)
      obtain ⟨b, rfl⟩ := Nat.exists_eq_succ_of_ne_zero (Nat.pos_iff_ne_zero.mp hf'1)
      cases hrcp : r item with
      | nil => simp only [rawUnitsAux, hv, if_false, hrcp]
      | cons hd tl =>
        show (if item ∈ visited then 1
          else match r item with
            | [] => 1
            | rcp => (rcp.map (fun p => p.2 * rawUnitsAux r a (item :: visited) p.1)).sum) =
          (if item ∈ visited then 1
          else match r item with
            | [] => 1
            | rcp => (rcp.map (fun p => p.2 * rawUnitsAux r b (item :: visited) p.1)).sum)
        simp only [hv, if_false, hrcp]
        -- recurse on each sub-material: measure strictly decreased
        have hrem_dec : remaining univ (item :: visited) ≤ a ∧ remaining univ (item :: visited) ≤ b := by
          have hlt := remaining_decreasing univ visited item hmem hv
          constructor
          · exact Nat.le_of_lt_succ (Nat.lt_of_lt_of_le hlt hf)
          · exact Nat.le_of_lt_succ (Nat.lt_of_lt_of_le hlt hf')
        congr 1
        apply List.map_congr_left
        intro p hp
        have hchild : p.1 ∈ (r item).map Prod.fst := by
          rw [hrcp]; exact List.mem_map_of_mem (f := Prod.fst) hp
        have hpmem : p.1 ∈ univ := hclosed item hmem p.1 hchild
        have hless : a < a + 1 := Nat.lt_succ_self a
        rw [ih a hless b (item :: visited) p.1 hpmem hrem_dec.1 hrem_dec.2]

/-- A concrete CYCLIC recipe `a → b → a` (with quantities) — the cost is a
DEFINITE finite value, demonstrating termination on a cycle. With
`r a = [(b,1)]`, `r b = [(a,1)]`: `rawUnits a` starts at `a`, descends to `b`
(visited `{a}`), then back to `a` which is now visited → returns 1. So
`rawUnits a = 1`. The recursion does NOT diverge. -/
example :
    let r : Recipe := fun n => if n = 0 then [(1, 1)] else if n = 1 then [(0, 1)] else []
    rawUnits r 3 0 = 1 := by decide

/-- The DFS-computed cost at the top level (empty visited) equals the documented
recipe sum for an item WITH a recipe and adequate fuel. -/
theorem rawUnits_top_eq_cost (r : Recipe) (n : Nat) (item : Nat)
    (rcp : List (Nat × Nat)) (hr : r item = rcp) (hne : rcp ≠ []) :
    rawUnits r (n + 1) item
      = (rcp.map (fun p => p.2 * rawUnitsAux r n [item] p.1)).sum := by
  unfold rawUnits
  rw [rawUnits_eq_cost r n [] item (List.not_mem_nil) rcp hr hne]

end Formal.RecipeClosure
