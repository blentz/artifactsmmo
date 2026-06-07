-- @concept: bank, items, crafting @property: safety
/-
Formal model of `select_bank_deposits` (and `_keep_codes`, `_recipe_materials`,
`_best_fighting_weapon`) from `src/artifactsmmo_cli/ai/bank_selection.py`.

## The policy

`select_bank_deposits(state, game_data)` computes a KEEP-SET of protected item
codes, then deposits exactly the inventory items with `qty > 0` NOT in the keep
set, sorted by `(-sell_value, code)`.

KEEP-SET (`_keep_codes`):
* `{TASKS_COIN}` always;
* `{task_code}` if the character has an active task;
* every inventory item whose `hp_restore > 0` (HP-restore consumables);
* the BEST fighting weapon over `inventory ∪ equipped` — the max-attack `weapon`
  with NO `skill_effects` (tools excluded), ties broken by code ascending;
* `_recipe_materials({crafting_target} ∪ {items-task code})` — the transitive
  recipe-material closure of the equipment crafting target and the active
  items-task item. Banking a task's OWN inputs starves PursueTask and FREEZES
  task progress (the documented freeze invariant).

`_recipe_materials(roots)` is a DFS over `_crafting_recipes` adding every
material key reached by following recipe-submaterial edges from the roots. It
adds the CHILDREN (materials), recursing — exactly the recipe-child relation of
`RecipeClosure`. We REUSE `Formal.RecipeClosure.Reachable` / `satN` /
`closureItems` to model this least-fixpoint walk. NOTE: the Python `walk` adds a
material when it is a *child* of a visited item — i.e. `Reachable` from the roots
but reached via at least one recipe edge. A root that is never a child of any
reachable item is NOT added unless it is itself a child. So `recipeMaterials` =
`{m | StepReachable r roots m}` where `StepReachable` is "reachable via ≥ 1
recipe-child edge from the roots". We define it inductively and relate it to
`Reachable`.

## Model

Items are `Nat` codes. `recipe : Nat → List (Nat × Nat)` is the
`_crafting_recipes` ingredient map (reused `RecipeClosure.Recipe`). Each inventory
item carries `(code, qty)`. Weapon attributes are abstracted to
`attack : Nat → Int` (sum of element attacks), `isWeapon : Nat → Bool`,
`isTool : Nat → Bool` (has skill_effects), `hpRestore : Nat → Int`. Sell value is
`sellValue : Nat → Int`. We prove `select_bank_deposits` deposits EXACTLY the
qty>0 inventory codes outside the keep set, the freeze invariant
`deposits ∩ keep = ∅`, task-input protection, and keep-closure under the
recipe-material walk (the reused fixpoint).

Lean core only — no mathlib.
-/

import Formal.RecipeClosure

namespace Formal.BankSelection

open Formal.RecipeClosure

/-! ### State abstraction. -/

/-- The inputs `select_bank_deposits` reads, abstracted to integer/Nat data.
* `tasksCoin`    — the `TASKS_COIN` code (always kept);
* `taskCode`     — `some c` if the character has an active task, else `none`;
* `taskIsItems` — whether `task_type = "items"`;
* `craftingTarget` — `some t` if an equipment crafting target is set;
* `inventory`    — `(code, qty)` association list (Python `state.inventory.items()`);
* `equipped`     — equipped item codes (`state.equipment` values, non-None);
* `recipe`       — `_crafting_recipes` ingredient map;
* `attack`       — Σ element attack for a weapon item;
* `isWeapon`     — `stats.type_ = "weapon"`;
* `isTool`       — `stats.skill_effects` nonempty (a gathering tool);
* `hpRestore`    — `stats.hp_restore`;
* `sellValue`    — max NPC buy price (0 if none). -/
structure State where
  tasksCoin : Nat
  taskCode : Option Nat
  taskIsItems : Bool
  craftingTarget : Option Nat
  inventory : List (Nat × Nat)
  equipped : List Nat
  recipe : Recipe
  attack : Nat → Int
  isWeapon : Nat → Bool
  isTool : Nat → Bool
  hpRestore : Nat → Int
  sellValue : Nat → Int

/-! ### Best fighting weapon (argmax over inventory ∪ equipped). -/

/-- Weapon candidates: inventory codes ∪ equipped codes (deduplicated). Mirrors
`set(state.inventory)`+`equipment.values()`; dedup keeps the fold deterministic. -/
def weaponCandidates (s : State) : List Nat :=
  (s.inventory.map Prod.fst ++ s.equipped).eraseDups

/-- A code is a fighting-weapon candidate: a `weapon` that is NOT a tool. Mirrors
`stats.type_ == "weapon" and not stats.skill_effects`. -/
def isFightingWeapon (s : State) (code : Nat) : Bool :=
  s.isWeapon code && !s.isTool code

/-- Fold step for the best fighting weapon. Carries the running best
`(attack, code)`. A candidate replaces the best iff it is a fighting weapon AND
(`best = none` ∨ strictly higher attack ∨ equal attack with strictly smaller
code). This mirrors the Python `if best is None or attack > best[0] or (attack ==
best[0] and code < best[1])`. -/
def betterWeapon (s : State) (best : Option (Int × Nat)) (code : Nat) :
    Option (Int × Nat) :=
  if isFightingWeapon s code then
    match best with
    | none => some (s.attack code, code)
    | some (batk, bcode) =>
      if s.attack code > batk || (s.attack code == batk && code < bcode)
      then some (s.attack code, code)
      else some (batk, bcode)
  else best

/-- The best-weapon fold: left fold over the candidates carrying the running best
`(attack, code)`. The candidate list is fixed by `weaponCandidates`. -/
def bestWeaponFold (s : State) : Option (Int × Nat) :=
  (weaponCandidates s).foldl (betterWeapon s) none

/-- The best fighting weapon code. -/
def bestWeaponCode (s : State) : Option Nat :=
  match bestWeaponFold s with
  | none => none
  | some (_, code) => some code

/-! ### Recipe-material walk — REUSED from `RecipeClosure`.

`_recipe_materials(roots)` adds a material when it is reached as a recipe CHILD of
a visited item (the root itself is added only if it is also a child). We model the
"reachable via ≥ 1 recipe-child edge" relation and relate it to the reused
`Reachable`. -/

/-- The protected recipe roots: the crafting target (if any) and the items-task
code (if the task is an items task). Mirrors the `recipe_roots` list. -/
def recipeRoots (s : State) : List Nat :=
  (match s.craftingTarget with | some t => [t] | none => []) ++
  (if s.taskIsItems then (match s.taskCode with | some c => [c] | none => []) else [])

/-- `StepReachable r roots m`: `m` is reached from `roots` via AT LEAST ONE
recipe-child edge — exactly the materials the DFS `walk` ADDS (a material is added
only as a `mat` child of some visited item). -/
inductive StepReachable (r : Recipe) (roots : List Nat) : Nat → Prop
  | base {item child : Nat} (h : item ∈ roots)
      (hc : child ∈ (r item).map Prod.fst) : StepReachable r roots child
  | step {item child : Nat} (hi : StepReachable r roots item)
      (hc : child ∈ (r item).map Prod.fst) : StepReachable r roots child

/-- The recipe-material set as a Prop: exactly `StepReachable`. -/
def recipeMaterials (s : State) (m : Nat) : Prop :=
  StepReachable s.recipe (recipeRoots s) m

/-- Every step-reachable material is `Reachable` (it sits in the reused least
fixpoint seeded by the roots). The walk never escapes the recipe closure. -/
theorem stepReachable_reachable (r : Recipe) (roots : List Nat) {m : Nat}
    (h : StepReachable r roots m) : Reachable r roots m := by
  induction h with
  | base hr hc => exact Reachable.step (Reachable.root hr) hc
  | step _ hc ih => exact Reachable.step ih hc

/-! ### The keep set. -/

/-- A code is HP-restoring AND in the inventory (Python iterates `state.inventory`
adding codes with `hp_restore > 0`). -/
def isKeptHp (s : State) (code : Nat) : Bool :=
  decide (code ∈ s.inventory.map Prod.fst) && decide (s.hpRestore code > 0)

/-- The keep-set as a decidable predicate over codes EXCEPT the recipe-material
closure (which is a Prop via the reused fixpoint). `inKeepBase` is the
finitely-checkable part:
* `code = tasksCoin`, or
* `some code = taskCode`, or
* HP-restore item in inventory, or
* `code = bestWeaponCode`. -/
def inKeepBase (s : State) (code : Nat) : Bool :=
  decide (code = s.tasksCoin)
  || decide (s.taskCode = some code)
  || isKeptHp s code
  || decide (bestWeaponCode s = some code)

/-- The FULL keep predicate: the base part OR a recipe material. -/
def InKeep (s : State) (code : Nat) : Prop :=
  inKeepBase s code = true ∨ recipeMaterials s code

/-! ### Computable keep set (for the oracle).

The recipe-material walk is computed via the reused `closureItems`; a code is a
material iff it is in the closure of `recipeRoots` AND is itself a recipe child of
something (i.e. `StepReachable`). For the oracle we compute the closure and then
filter to those reached via an edge. The simplest faithful executable form: the
walk's added set is `closureItems r roots fuel` minus any root that is never a
child. We compute the material list directly as the children-union over the
closure. -/

/-- Computable recipe-material list: every recipe child of every item in the
reachable closure of `recipeRoots`. Mirrors the DFS adding `mat` for each
`(mat) ∈ recipe[item]` over every visited `item`. -/
def recipeMaterialList (s : State) (fuel : Nat) : List Nat :=
  (childrenOf s.recipe (closureItems s.recipe (recipeRoots s) fuel)).eraseDups

/-- Computable keep-set list: the base codes present in inventory/equipped plus the
recipe materials. We collect over the universe of relevant codes = inventory ∪
equipped ∪ {tasksCoin} ∪ taskCode ∪ recipe materials. -/
def keepList (s : State) (fuel : Nat) : List Nat :=
  let baseUniverse :=
    (s.tasksCoin :: (match s.taskCode with | some c => [c] | none => []) ++
      s.inventory.map Prod.fst ++ s.equipped)
  ((baseUniverse.filter (fun c => inKeepBase s c)) ++ recipeMaterialList s fuel).eraseDups

/-! ### The deposit list. -/

/-- Whether an inventory entry is deposited: `qty > 0` AND code is not in the keep
set (computable form, fuel-parametrized). -/
def isDeposited (s : State) (fuel : Nat) (cq : Nat × Nat) : Bool :=
  decide (cq.2 > 0) && !decide (cq.1 ∈ keepList s fuel)

/-- The deposit candidates: inventory entries with `qty > 0` not in the keep set,
BEFORE sorting. -/
def depositCandidates (s : State) (fuel : Nat) : List (Nat × Nat) :=
  s.inventory.filter (isDeposited s fuel)

/-- Sort key comparison: `(-sellValue, code)` ascending = sellValue descending,
then code ascending. `cq₁` sorts before-or-equal `cq₂` iff higher sell value, or
equal sell value with `≤` code. -/
def depositLe (s : State) (cq₁ cq₂ : Nat × Nat) : Bool :=
  let v1 := s.sellValue cq₁.1
  let v2 := s.sellValue cq₂.1
  decide (v1 > v2) || (decide (v1 = v2) && decide (cq₁.1 ≤ cq₂.1))

/-- The deposit list, sorted by `(-sellValue, code)`. -/
def deposits (s : State) (fuel : Nat) : List (Nat × Nat) :=
  (depositCandidates s fuel).mergeSort (fun a b => depositLe s a b)

/-! ### Theorems. -/

/-- `deposits_exact`: the deposit CANDIDATES are EXACTLY the inventory entries with
`qty > 0` and code ∉ keep. Membership characterization (the sort is a permutation;
`deposits_perm` relates the sorted list to the candidates). -/
theorem deposits_exact (s : State) (fuel : Nat) (cq : Nat × Nat) :
    cq ∈ depositCandidates s fuel
      ↔ cq ∈ s.inventory ∧ cq.2 > 0 ∧ cq.1 ∉ keepList s fuel := by
  unfold depositCandidates isDeposited
  rw [List.mem_filter]
  constructor
  · rintro ⟨hmem, hcond⟩
    rw [Bool.and_eq_true] at hcond
    obtain ⟨hq, hk⟩ := hcond
    refine ⟨hmem, by simpa using hq, ?_⟩
    rw [Bool.not_eq_true', decide_eq_false_iff_not] at hk
    exact hk
  · rintro ⟨hmem, hq, hk⟩
    refine ⟨hmem, ?_⟩
    rw [Bool.and_eq_true]
    refine ⟨by simpa using hq, ?_⟩
    rw [Bool.not_eq_true', decide_eq_false_iff_not]
    exact hk

/-- The sorted deposit list is a PERMUTATION of the candidates (so it contains
exactly the same entries; only the order changes). -/
theorem deposits_perm (s : State) (fuel : Nat) :
    (deposits s fuel).Perm (depositCandidates s fuel) :=
  List.mergeSort_perm _ _

/-- `deposits` membership = candidate membership (via the permutation) — the
sorted list deposits EXACTLY the qty>0 non-kept inventory entries. -/
theorem deposits_mem_iff (s : State) (fuel : Nat) (cq : Nat × Nat) :
    cq ∈ deposits s fuel
      ↔ cq ∈ s.inventory ∧ cq.2 > 0 ∧ cq.1 ∉ keepList s fuel := by
  rw [← deposits_exact]
  exact (deposits_perm s fuel).mem_iff

/-- `freeze_invariant`: NO deposited code is in the keep set — `deposits ∩ keep =
∅`. This is the PursueTask-freeze guarantee: a protected item (task coin, task
item, HP consumable, best weapon, or a recipe material of a protected root) is
NEVER banked. -/
theorem freeze_invariant (s : State) (fuel : Nat) (cq : Nat × Nat)
    (h : cq ∈ deposits s fuel) : cq.1 ∉ keepList s fuel :=
  ((deposits_mem_iff s fuel cq).mp h).2.2

/-- Every deposited entry came from the inventory and has positive quantity. -/
theorem deposits_from_inventory (s : State) (fuel : Nat) (cq : Nat × Nat)
    (h : cq ∈ deposits s fuel) : cq ∈ s.inventory ∧ cq.2 > 0 :=
  let hm := (deposits_mem_iff s fuel cq).mp h
  ⟨hm.1, hm.2.1⟩

/-! ### Task-input protection (the freeze root cause). -/

/-- Membership in the computable recipe-material list ⟺ the code is a recipe child
of some item in the reachable closure. -/
theorem recipeMaterialList_iff (s : State) (fuel : Nat) (m : Nat) :
    m ∈ recipeMaterialList s fuel
      ↔ ∃ item ∈ closureItems s.recipe (recipeRoots s) fuel,
          m ∈ (s.recipe item).map Prod.fst := by
  unfold recipeMaterialList childrenOf
  rw [List.mem_eraseDups, List.mem_flatMap]

/-- A `Reachable` item that is a recipe child of another item is itself
`StepReachable` (reached via ≥ 1 edge). Proven by induction on the reachability
derivation. -/
theorem stepReachable_of_reachable (r : Recipe) (roots : List Nat) {item : Nat}
    (hi : Reachable r roots item) :
    ∀ {child : Nat}, child ∈ (r item).map Prod.fst → StepReachable r roots child := by
  induction hi with
  | root hroot => intro child hc; exact StepReachable.base hroot hc
  | step _ hc' ih => intro child hc; exact StepReachable.step (ih hc') hc

/-- A code in the computable recipe-material list is a genuine recipe material
(`StepReachable`) — SOUNDNESS of the executable walk wrt the inductive relation. -/
theorem recipeMaterialList_sound (s : State) (fuel : Nat) {m : Nat}
    (h : m ∈ recipeMaterialList s fuel) : recipeMaterials s m := by
  rw [recipeMaterialList_iff] at h
  obtain ⟨item, hitem, hchild⟩ := h
  have hr : Reachable s.recipe (recipeRoots s) item := closureItems_sound _ _ _ hitem
  exact stepReachable_of_reachable s.recipe (recipeRoots s) hr hchild

/-- `task_inputs_protected`: every recipe material of the protected roots
(crafting target ∪ items-task code) is in the keep set. Banking a task's own
inputs is impossible. We state it over the computable keep set: any recipe
material captured within `fuel` is kept. -/
theorem task_inputs_protected (s : State) (fuel : Nat) {m : Nat}
    (h : m ∈ recipeMaterialList s fuel) : m ∈ keepList s fuel := by
  unfold keepList
  rw [List.mem_eraseDups, List.mem_append]
  exact Or.inr h

/-- A protected recipe material is NEVER deposited — the direct freeze guarantee
for task inputs (combines `task_inputs_protected` with `freeze_invariant`). -/
theorem task_material_not_deposited (s : State) (fuel : Nat) (cq : Nat × Nat)
    (hmat : cq.1 ∈ recipeMaterialList s fuel) : cq ∉ deposits s fuel := by
  intro hdep
  exact freeze_invariant s fuel cq hdep (task_inputs_protected s fuel hmat)

/-! ### Keep-closure under the recipe-material walk (the reused fixpoint).

The protected roots' transitive materials are ALL kept: the keep set is closed
under the recipe-material walk. We show the keep set contains every
`StepReachable` material captured by `fuel`, and that `StepReachable` is closed
under taking further recipe children. -/

/-- `StepReachable` is closed under taking a recipe child: a material's own recipe
children are also materials. This is the closure property of the walk — once a
material is protected, all its sub-materials are too. -/
theorem recipeMaterials_closed (s : State) {item child : Nat}
    (hi : recipeMaterials s item) (hc : child ∈ (s.recipe item).map Prod.fst) :
    recipeMaterials s child :=
  StepReachable.step hi hc

/-- `keep_closed`: the keep set is closed under the recipe-material walk seeded by
the protected roots. Formally: every `StepReachable` material that is captured in
the computable closure within `fuel` is in the keep set. Combined with
`recipeMaterials_closed`, the protected roots' ENTIRE transitive material set is
kept (the reused least-fixpoint closure). -/
theorem keep_closed (s : State) (fuel : Nat) {m : Nat}
    (hmat : m ∈ recipeMaterialList s fuel) :
    m ∈ keepList s fuel ∧ recipeMaterials s m :=
  ⟨task_inputs_protected s fuel hmat, recipeMaterialList_sound s fuel hmat⟩

/-- COMPLETENESS of the recipe-material capture: any material reachable via a
recipe edge from an item captured at round `n ≤ fuel` is in the material list (so
with adequate fuel, the full `StepReachable` set is kept). -/
theorem recipeMaterialList_complete (s : State) (fuel n : Nat) (hle : n ≤ fuel)
    {item m : Nat} (hitem : item ∈ satN s.recipe (recipeRoots s) n)
    (hc : m ∈ (s.recipe item).map Prod.fst) : m ∈ recipeMaterialList s fuel := by
  rw [recipeMaterialList_iff]
  exact ⟨item, closureItems_complete _ _ _ _ hle hitem, hc⟩

/-! ### Base keep-set membership: the non-recipe protections. -/

/-- The TASKS_COIN is always kept (it is in the base universe and satisfies
`inKeepBase`). -/
theorem tasks_coin_kept_base (s : State) : inKeepBase s s.tasksCoin = true := by
  unfold inKeepBase
  simp

/-- The active task code is kept (base). -/
theorem task_code_kept_base (s : State) (c : Nat) (h : s.taskCode = some c) :
    inKeepBase s c = true := by
  unfold inKeepBase
  simp [h]

/-- An inventory HP-restore item is kept (base). -/
theorem hp_item_kept_base (s : State) (c : Nat)
    (hmem : c ∈ s.inventory.map Prod.fst) (hhp : s.hpRestore c > 0) :
    inKeepBase s c = true := by
  unfold inKeepBase isKeptHp
  simp [hmem, hhp]

/-- The best fighting weapon is kept (base), when one exists. -/
theorem best_weapon_kept_base (s : State) (c : Nat) (h : bestWeaponCode s = some c) :
    inKeepBase s c = true := by
  unfold inKeepBase
  simp [h]

/-! ### best_weapon_argmax (optional): the best fighting weapon is the max-attack
non-tool weapon over inventory ∪ equipped, ties broken by code ascending. -/

/-- The running best after a fold prefix is always a fighting weapon (or none). -/
theorem bestWeaponFold_isFighting (s : State) :
    ∀ (l : List Nat) (acc : Option (Int × Nat)),
      (∀ p, acc = some p → isFightingWeapon s p.2 = true) →
      (∀ p, l.foldl (betterWeapon s) acc = some p → isFightingWeapon s p.2 = true) := by
  intro l
  induction l with
  | nil => intro acc hacc p hp; exact hacc p hp
  | cons x xs ih =>
    intro acc hacc p hp
    simp only [List.foldl_cons] at hp
    apply ih (betterWeapon s acc x) _ p hp
    intro q hq
    unfold betterWeapon at hq
    by_cases hf : isFightingWeapon s x = true
    · rw [if_pos hf] at hq
      cases acc with
      | none =>
        simp only [Option.some.injEq] at hq
        rw [← hq]; exact hf
      | some bp =>
        obtain ⟨batk, bcode⟩ := bp
        simp only at hq
        by_cases hcmp : (decide (s.attack x > batk) || (s.attack x == batk && decide (x < bcode))) = true
        · rw [if_pos hcmp, Option.some.injEq] at hq
          rw [← hq]; exact hf
        · rw [if_neg hcmp] at hq
          exact hacc q hq
    · rw [if_neg hf] at hq
      exact hacc q hq

/-- `best_weapon_is_fighting`: the chosen best weapon is a fighting weapon (a
`weapon` that is not a tool) — tools are excluded. -/
theorem best_weapon_is_fighting (s : State) (c : Nat) (h : bestWeaponCode s = some c) :
    isFightingWeapon s c = true := by
  unfold bestWeaponCode at h
  cases hf : bestWeaponFold s with
  | none => rw [hf] at h; simp at h
  | some p =>
    rw [hf] at h
    simp only [Option.some.injEq] at h
    have hfight : isFightingWeapon s p.2 = true := by
      apply bestWeaponFold_isFighting s (weaponCandidates s) none (by simp) p
      exact hf
    rw [← h]; exact hfight

/-- The fold result's attack dominates the running accumulator's attack and every
fighting-weapon candidate's attack in the prefix processed. The argmax is the
MAXIMUM attack over fighting weapons. -/
theorem bestWeaponFold_ge (s : State) :
    ∀ (l : List Nat) (acc : Option (Int × Nat)),
      (∃ q, l.foldl (betterWeapon s) acc = some q ∧
        (∀ ap, acc = some ap → ap.1 ≤ q.1) ∧
        (∀ y ∈ l, isFightingWeapon s y = true → s.attack y ≤ q.1))
      ∨ (l.foldl (betterWeapon s) acc = none) := by
  intro l
  induction l with
  | nil =>
    intro acc
    cases acc with
    | none => exact Or.inr rfl
    | some ap =>
      refine Or.inl ⟨ap, rfl, ?_, ?_⟩
      · intro ap' h; rw [Option.some.injEq] at h; rw [h]; exact Int.le_refl _
      · intro y hy; exact absurd hy (List.not_mem_nil)
  | cons x xs ih =>
    intro acc
    simp only [List.foldl_cons]
    -- compute acc' = betterWeapon s acc x and its attack relationship
    rcases ih (betterWeapon s acc x) with ⟨q, hfold, hacc', hcands'⟩ | hnone
    · refine Or.inl ⟨q, hfold, ?_, ?_⟩
      · -- acc ≤ acc' ≤ q
        intro ap hap
        -- show ap.1 ≤ q.1 via acc' chain
        have hkey : ∀ ap', acc = some ap' →
            ∃ bp, betterWeapon s acc x = some bp ∧ ap'.1 ≤ bp.1 := by
          intro ap' hap'
          by_cases hf : isFightingWeapon s x = true
          · obtain ⟨batk, bcode⟩ := ap'
            by_cases hcmp : (decide (s.attack x > batk)
                || (s.attack x == batk && decide (x < bcode))) = true
            · refine ⟨(s.attack x, x), ?_, ?_⟩
              · simp only [betterWeapon, hf, hap', if_true]; rw [if_pos hcmp]
              · simp only [Bool.or_eq_true, decide_eq_true_eq, beq_iff_eq, Bool.and_eq_true] at hcmp
                rcases hcmp with h1 | ⟨h2, _⟩
                · exact Int.le_of_lt h1
                · exact Int.le_of_eq h2.symm
            · refine ⟨(batk, bcode), ?_, Int.le_refl _⟩
              simp only [betterWeapon, hf, hap', if_true]; rw [if_neg hcmp]
          · refine ⟨ap', ?_, Int.le_refl _⟩
            rw [hap']; unfold betterWeapon; rw [if_neg hf]
        obtain ⟨bp, hbp, hle⟩ := hkey ap hap
        exact Int.le_trans hle (hacc' bp hbp)
      · -- candidates: x and every y ∈ xs
        intro y hy hfy
        rcases List.mem_cons.mp hy with hyx | hyxs
        · subst hyx
          -- y = x is a fighting weapon ⇒ betterWeapon picks attack ≥ s.attack y
          have hkey : ∃ bp, betterWeapon s acc y = some bp ∧ s.attack y ≤ bp.1 := by
            cases acc with
            | none => exact ⟨(s.attack y, y), by simp only [betterWeapon, hfy, if_true], Int.le_refl _⟩
            | some ap =>
              obtain ⟨batk, bcode⟩ := ap
              by_cases hcmp : (decide (s.attack y > batk)
                  || (s.attack y == batk && decide (y < bcode))) = true
              · refine ⟨(s.attack y, y), ?_, Int.le_refl _⟩
                simp only [betterWeapon, hfy, if_true]; rw [if_pos hcmp]
              · refine ⟨(batk, bcode), ?_, ?_⟩
                · simp only [betterWeapon, hfy, if_true]; rw [if_neg hcmp]
                · simp only [Bool.or_eq_true, decide_eq_true_eq, beq_iff_eq, Bool.and_eq_true,
                    not_or, not_and, Int.not_lt] at hcmp
                  exact hcmp.1
          obtain ⟨bp, hbp, hle⟩ := hkey
          exact Int.le_trans hle (hacc' bp hbp)
        · exact hcands' y hyxs hfy
    · exact Or.inr hnone

/-- The recorded attack in the fold equals `s.attack` of the recorded code. -/
theorem bestWeaponFold_attack_eq (s : State) :
    ∀ (l : List Nat) (acc : Option (Int × Nat)) (q : Int × Nat),
      l.foldl (betterWeapon s) acc = some q →
      (∀ ap, acc = some ap → ap.1 = s.attack ap.2) →
      q.1 = s.attack q.2 := by
  intro l
  induction l with
  | nil =>
    intro acc q hfold hinv
    simp only [List.foldl_nil] at hfold
    exact hinv q hfold
  | cons x xs ih =>
    intro acc q hfold hinv
    simp only [List.foldl_cons] at hfold
    apply ih (betterWeapon s acc x) q hfold
    intro ap hap
    unfold betterWeapon at hap
    by_cases hf : isFightingWeapon s x = true
    · rw [if_pos hf] at hap
      cases acc with
      | none => simp only [Option.some.injEq] at hap; rw [← hap]
      | some bp =>
        obtain ⟨batk, bcode⟩ := bp
        simp only at hap
        by_cases hcmp : (decide (s.attack x > batk)
            || (s.attack x == batk && decide (x < bcode))) = true
        · rw [if_pos hcmp, Option.some.injEq] at hap; rw [← hap]
        · rw [if_neg hcmp, Option.some.injEq] at hap
          rw [← hap]; exact hinv (batk, bcode) rfl
    · rw [if_neg hf] at hap
      exact hinv ap hap

/-- `best_weapon_argmax`: the best fighting weapon's attack is ≥ every fighting
weapon candidate's attack — the argmax (maximum) over inventory ∪ equipped of the
non-tool weapons. -/
theorem best_weapon_argmax (s : State) (c : Nat) (h : bestWeaponCode s = some c) :
    ∀ y ∈ weaponCandidates s, isFightingWeapon s y = true →
      s.attack y ≤ s.attack c := by
  intro y hy hfy
  rcases bestWeaponFold_ge s (weaponCandidates s) none with ⟨q, hfold, _, hcands⟩ | hnone
  · have hcode : q.2 = c := by
      unfold bestWeaponCode bestWeaponFold at h
      rw [hfold] at h
      simp only [Option.some.injEq] at h
      exact h
    have hcands' := hcands y hy hfy
    have hq2 : q.1 = s.attack q.2 :=
      bestWeaponFold_attack_eq s (weaponCandidates s) none q hfold (by simp)
    rw [hq2, hcode] at hcands'
    exact hcands'
  · unfold bestWeaponCode bestWeaponFold at h
    rw [hnone] at h
    simp at h

end Formal.BankSelection
