import Formal.Extracted.RecipeClosure
import Formal.Extracted.TaskBatch
import Formal.Extracted.TaskReservation
import Formal.RecipeClosure
import Formal.TaskBatch
import Formal.TaskReservation

/-!
# Extracted ↔ hand-model bridge lemmas, part 3 (P3a: the recipe family)

HAND-WRITTEN (size split of Bridges.lean/Bridges2.lean; same namespace).
The P3a wave hoisted the GameData reads out of `recipe_closure.py`,
`task_batch.py` and `task_reservation.py` into pure cores over plain data
(recipes/drops mappings + scalar state fields), mechanically extracted to
`Formal/Extracted/{RecipeClosure,TaskBatch,TaskReservation}.lean`. This file
proves them against the pre-existing hand models.

Encoding: the hand models code items as `Nat`; Python uses `str` and
insertion-ordered dicts. As in the combat-picker bridge, we quantify over an
arbitrary INJECTIVE embedding `f : Nat → String` (injectivity is required
here because the extracted cores KEY dict lookups by the codes) and prove the
extracted definitions equal to the hand models through the encoding.

* `task_batch_bridge` — FULL bridge: the extracted decision equals the hand
  `Formal.TaskBatch.batchSize` at the gate boolean `eTaskGate` and the
  extracted recipe-plumbing terms `eMats`/`eHeld` (which are themselves the
  extracted RecipeClosure cores, bridged below). `task_batch_ge_one_extracted`
  transfers THE floor-at-1 safety theorem.

* `closure_demand_bridge` — the extracted `_closure_demand` (threaded dict,
  replace-or-append writes) computes the SAME demand map as the proved hand
  `Formal.TaskReservation.closureDemand` (prepend-record list): pointwise
  lookup equality + key-set equivalence (`DemRel`), for EVERY fuel, root,
  multiplier ≥ 1, recipe graph and corresponding visited/accumulator states.
  On top of it, `reserved_demand_bridge` and `consumes_reserved_bridge` give
  the API correspondences; the three proved reservation contracts
  (task-done inertness, surplus carve-out, monotone shrinking) transfer.

* `raw_units_bridge` — the extracted `_raw_units` equals the hand
  `Formal.RecipeClosure.rawUnitsAux` (`Int.ofNat` image) for EVERY fuel and
  corresponding visited states — the quantity math (`rawUnits_eq_cost`,
  revisit/raw guards, cyclic termination) transfers.

* `closure_visited_sound` — every key the extracted closure DFS marks is
  `Formal.RecipeClosure.Reachable` (the least-fixpoint spec): the extracted
  closure never over-collects, for EVERY graph.

* `closure_visited_complete` / `recipe_closure_pure_complete` /
  `recipe_closure_pure_spec` (P4c) — the COMPLETENESS direction, now
  UNIVERSAL. The never-exhausts-fuel invariant is the `unmarkedKeys`
  measure (recipe entries whose key is still unmarked in the threaded
  visited dict): every recursing frame first marks a previously-unmarked
  recipe key, marks only grow along the thread, so the measure strictly
  decreases down every recursion path; the wrapper seed `|recipes| + 1`
  strictly dominates it at every entry state (`eFuel_sufficient`), so the
  fuel-0 base case is unreachable on every frame with work pending. With
  fuel above the measure the DFS marks its root and leaves every newly
  marked key children-closed (`closure_visited_complete`); folding over the
  roots yields a `MarkedClosed` dict containing the roots, and every
  spec-`Reachable` item is marked (`closure_visited_marks_reachable`).
  `recipe_closure_pure_spec` combines this with soundness into the exact
  iff: output membership ⟺ `isCraftable` / `isNeeded`, for EVERY graph,
  drop table and root set. The former kernel pins on the mutation graphs
  (`closure_pin_*`) are superseded and dropped; the `_raw_units` quantity
  pins stay (they pin exact numeric outputs the mutation suite cites).

Multiplier-1 honesty note: `consumes_reserved_pure` reads reserved-key
presence as `demand.get(r, 0) != 0` where the original Python read `r in
demand`. These agree on EVERY input of the pure core because both `demand`
and `conflict` are built with multiplier ≥ 1 and zero-quantity edges skipped,
so recorded values are always ≥ 1 (`lookup_pos` below proves the hand-side
invariant; the bridge itself carries it through `DemRel`).

No sorry/admit, no new axioms; Lean core only (the hand models are safety
namespaces).
-/

namespace Extracted.Bridges

/-! ## Shared dict/encoding machinery. -/

/-- First-match lookup on a `Nat`-keyed association list (the hand-side mirror
of the extracted `_dictGetD`). -/
def lookAssoc {α : Type} : List (Nat × α) → Nat → α → α
  | [], _, d => d
  | (k, v) :: rest, i, d => if k = i then v else lookAssoc rest i d

/-- Encode a `Nat`-keyed association list through `f` on keys and `g` on
values. -/
def encAssoc {α β : Type} (f : Nat → String) (g : α → β) (es : List (Nat × α)) :
    List (String × β) :=
  es.map (fun e => (f e.1, g e.2))

/-- Key presence in an extracted association list. -/
def keyIn {α : Type} (m : List (String × α)) (s : String) : Prop :=
  ∃ v, (s, v) ∈ m

/-- Unfolding `_dictGetD` over a cons cell with a propositional condition. -/
private theorem getD_cons {α : Type} (ek : String) (ev : α)
    (rest : List (String × α)) (k : String) (d : α) :
    Extracted.RecipeClosure._dictGetD ((ek, ev) :: rest) k d
      = if ek = k then ev else Extracted.RecipeClosure._dictGetD rest k d := by
  by_cases h : ek = k <;> simp [Extracted.RecipeClosure._dictGetD, h]

/-- Unfolding `_dictSet` over a cons cell with a propositional condition. -/
private theorem setD_cons {α : Type} (ek : String) (ev : α)
    (rest : List (String × α)) (k : String) (v : α) :
    Extracted.RecipeClosure._dictSet ((ek, ev) :: rest) k v
      = if ek = k then (ek, v) :: rest
        else (ek, ev) :: Extracted.RecipeClosure._dictSet rest k v := by
  by_cases h : ek = k <;> simp [Extracted.RecipeClosure._dictSet, h]

private theorem dictGetD_encAssoc {α β : Type} (f : Nat → String)
    (hf : ∀ {a b : Nat}, f a = f b → a = b) (g : α → β)
    (es : List (Nat × α)) (i : Nat) (d : α) :
    Extracted.RecipeClosure._dictGetD (encAssoc f g es) (f i) (g d)
      = g (lookAssoc es i d) := by
  induction es with
  | nil => rfl
  | cons e rest ih =>
    obtain ⟨ek, ev⟩ := e
    rw [show encAssoc f g ((ek, ev) :: rest) = (f ek, g ev) :: encAssoc f g rest from rfl,
        getD_cons]
    by_cases h : ek = i
    · subst h
      simp [lookAssoc]
    · have hne : f ek ≠ f i := fun hc => h (hf hc)
      rw [if_neg hne, ih]
      simp [lookAssoc, h]

/-- `_dictGetD` after `_dictSet`: the set key reads the new value, every other
key is untouched (replace-first-else-append preserves first matches). -/
private theorem dictGetD_dictSet {α : Type} (m : List (String × α))
    (k k' : String) (v d : α) :
    Extracted.RecipeClosure._dictGetD (Extracted.RecipeClosure._dictSet m k v) k' d
      = if k' = k then v else Extracted.RecipeClosure._dictGetD m k' d := by
  induction m with
  | nil =>
    show Extracted.RecipeClosure._dictGetD [(k, v)] k' d = _
    rw [getD_cons]
    by_cases h : k' = k
    · rw [if_pos h.symm, if_pos h]
    · rw [if_neg (Ne.symm h), if_neg h]
  | cons e rest ih =>
    obtain ⟨ek, ev⟩ := e
    rw [setD_cons]
    by_cases hek : ek = k
    · rw [if_pos hek, getD_cons, getD_cons]
      by_cases h' : ek = k'
      · rw [if_pos h', if_pos (h'.symm.trans hek)]
      · rw [if_neg h', if_neg (fun hc : k' = k => h' (hek.trans hc.symm)), if_neg h']
    · rw [if_neg hek, getD_cons, getD_cons]
      by_cases h' : ek = k'
      · rw [if_pos h', if_pos h', if_neg (fun hc : k' = k => hek (h'.trans hc))]
      · rw [if_neg h', if_neg h', ih]

/-- First component of a pair equality. -/
private theorem pair_eq_fst {α β : Type} {s k : β} {w v : α}
    (h : (s, w) = (k, v)) : s = k := by
  injection h with h1 _

/-- A `_dictGetD` read that differs from the default witnesses key presence. -/
private theorem keyIn_of_getD_ne {α : Type} (m : List (String × α)) (k : String)
    (d : α) (h : Extracted.RecipeClosure._dictGetD m k d ≠ d) : keyIn m k := by
  induction m with
  | nil => exact absurd rfl h
  | cons e rest ih =>
    obtain ⟨ek, ev⟩ := e
    rw [getD_cons] at h
    by_cases hek : ek = k
    · exact ⟨ev, by simp [hek]⟩
    · rw [if_neg hek] at h
      obtain ⟨v, hv⟩ := ih h
      exact ⟨v, List.mem_cons_of_mem _ hv⟩

/-- Key presence after `_dictSet`: exactly the old keys plus the written key. -/
private theorem keyIn_dictSet {α : Type} (m : List (String × α)) (k : String)
    (v : α) (s : String) :
    keyIn (Extracted.RecipeClosure._dictSet m k v) s ↔ keyIn m s ∨ s = k := by
  induction m with
  | nil =>
    show keyIn [(k, v)] s ↔ _
    constructor
    · rintro ⟨w, hw⟩
      simp only [List.mem_singleton, Prod.mk.injEq] at hw
      exact Or.inr hw.1
    · rintro (⟨w, hw⟩ | rfl)
      · exact absurd hw (List.not_mem_nil)
      · exact ⟨v, by simp⟩
  | cons e rest ih =>
    obtain ⟨ek, ev⟩ := e
    rw [setD_cons]
    by_cases hek : ek = k
    · subst hek
      rw [if_pos rfl]
      constructor
      · rintro ⟨w, hw⟩
        rcases List.mem_cons.mp hw with h | h
        · exact Or.inr (pair_eq_fst h)
        · exact Or.inl ⟨w, List.mem_cons_of_mem _ h⟩
      · rintro (⟨w, hw⟩ | rfl)
        · rcases List.mem_cons.mp hw with h | h
          · exact ⟨v, by rw [pair_eq_fst h]; simp⟩
          · exact ⟨w, List.mem_cons_of_mem _ h⟩
        · exact ⟨v, by simp⟩
    · rw [if_neg hek]
      constructor
      · rintro ⟨w, hw⟩
        rcases List.mem_cons.mp hw with h | h
        · exact Or.inl ⟨ev, by rw [pair_eq_fst h]; simp⟩
        · rcases ih.mp ⟨w, h⟩ with h' | h'
          · obtain ⟨w', hw'⟩ := h'
            exact Or.inl ⟨w', List.mem_cons_of_mem _ hw'⟩
          · exact Or.inr h'
      · rintro (⟨w, hw⟩ | rfl)
        · rcases List.mem_cons.mp hw with h | h
          · exact ⟨ev, by rw [pair_eq_fst h]; simp⟩
          · obtain ⟨w', hw'⟩ := ih.mpr (Or.inl ⟨w, h⟩)
            exact ⟨w', List.mem_cons_of_mem _ hw'⟩
        · obtain ⟨w', hw'⟩ := ih.mpr (Or.inr rfl)
          exact ⟨w', List.mem_cons_of_mem _ hw'⟩

/-- Every entry of `_dictSet m k v` is an entry of `m` or carries key `k`. -/
private theorem mem_dictSet {α : Type} (m : List (String × α)) (k : String)
    (v : α) (s : String) (w : α)
    (h : (s, w) ∈ Extracted.RecipeClosure._dictSet m k v) : (s, w) ∈ m ∨ s = k := by
  induction m with
  | nil =>
    simp only [Extracted.RecipeClosure._dictSet, List.mem_singleton, Prod.mk.injEq] at h
    exact Or.inr h.1
  | cons e rest ih =>
    obtain ⟨ek, ev⟩ := e
    rw [setD_cons] at h
    by_cases hek : ek = k
    · rw [if_pos hek] at h
      rcases List.mem_cons.mp h with h' | h'
      · exact Or.inr ((pair_eq_fst h').trans hek)
      · exact Or.inl (List.mem_cons_of_mem _ h')
    · rw [if_neg hek] at h
      rcases List.mem_cons.mp h with h' | h'
      · exact Or.inl (h' ▸ List.mem_cons_self ..)
      · rcases ih h' with h'' | h''
        · exact Or.inl (List.mem_cons_of_mem _ h'')
        · exact Or.inr h''

/-- The TaskReservation module's emitted `_dictGetD` is the RecipeClosure one
(byte-identical generated helpers in distinct namespaces). -/
private theorem tr_dictGetD_eq {α : Type} (m : List (String × α)) (k : String) (d : α) :
    Extracted.TaskReservation._dictGetD m k d
      = Extracted.RecipeClosure._dictGetD m k d := by
  induction m with
  | nil => rfl
  | cons e rest ih =>
    obtain ⟨ek, ev⟩ := e
    show (if ek == k then ev else Extracted.TaskReservation._dictGetD rest k d) = _
    rw [ih, getD_cons]
    by_cases h : ek = k <;> simp [h]

/-- Likewise for the TaskBatch module's `_dictGetD`. -/
private theorem tb_dictGetD_eq {α : Type} (m : List (String × α)) (k : String) (d : α) :
    Extracted.TaskBatch._dictGetD m k d
      = Extracted.RecipeClosure._dictGetD m k d := by
  induction m with
  | nil => rfl
  | cons e rest ih =>
    obtain ⟨ek, ev⟩ := e
    show (if ek == k then ev else Extracted.TaskBatch._dictGetD rest k d) = _
    rw [ih, getD_cons]
    by_cases h : ek = k <;> simp [h]

/-! ## TaskBatch: extracted decision = hand `batchSize` at the extracted
recipe-plumbing inputs. -/

/-- The fuel the extracted cores seed: `len(recipes) + 1`. -/
def eFuel (recipes : List (String × List (String × Int))) : Nat :=
  Int.toNat ((Int.ofNat (List.length recipes)) + 1)

/-- `mats_per_unit` exactly as the extracted core computes it. The yield map is
`[]` (the Python `task_batch` passes `{}` — all-`Y=1`). -/
def eMats (recipes : List (String × List (String × Int))) (code : String) : Int :=
  Extracted.RecipeClosure._raw_units (eFuel recipes) code recipes [] []

/-- The task item's closure exactly as the extracted core computes it. -/
def eClosure (recipes : List (String × List (String × Int))) (code : String) :
    List (String × Int) :=
  Extracted.RecipeClosure._closure_visited (eFuel recipes) code recipes []

/-- `held_recipe` exactly as the extracted core computes it: for every
`(resource, drop_item)` entry whose drop is in the closure, the inventory
count of the drop item. -/
def eHeld (recipes : List (String × List (String × Int)))
    (drops : List (String × String)) (inventory : List (String × Int))
    (code : String) : Int :=
  List.foldl
    (fun held_recipe _x =>
      let drop_item := _x.2
      if (decide ((Extracted.TaskBatch._dictGetD (eClosure recipes code) drop_item 0) = 1))
      then (held_recipe + (Extracted.TaskBatch._dictGetD inventory drop_item 0))
      else held_recipe)
    0 drops

/-- The items-task gate exactly as Python evaluates it: an items task with a
present, nonempty code, positive total and positive remaining. -/
def eTaskGate (task_type : Option String) (task_code : Option String)
    (task_total task_progress : Int) : Bool :=
  match task_code with
  | none => false
  | some c =>
    !((!(decide (task_type = some "items"))) || (decide (c = ""))
        || (decide (task_total ≤ 0)))
      && !(decide (task_total - task_progress ≤ 0))

/-- BRIDGE (no task code): both sides return 1. -/
theorem task_batch_bridge_none (task_type : Option String)
    (task_total task_progress inventory_free : Int)
    (inventory : List (String × Int))
    (recipes : List (String × List (String × Int)))
    (drops : List (String × String)) :
    Extracted.TaskBatch.task_batch_size_pure task_type none task_total task_progress
        inventory inventory_free recipes drops
      = Formal.TaskBatch.batchSize false (task_total - task_progress) 1
          inventory_free 0 := by
  rfl

/-- BRIDGE: the extracted `task_batch_size_pure` IS the hand
`Formal.TaskBatch.batchSize` evaluated at the Python gate (`eTaskGate`) and
the extracted recipe-plumbing inputs (`eMats`/`eHeld`) — for EVERY input.
Every `Formal.TaskBatch` clamp theorem (floor at 1, ≤ remaining, ≤ cap,
fits-in-usable) transfers. -/
theorem task_batch_bridge (task_type : Option String) (c : String)
    (task_total task_progress inventory_free : Int)
    (inventory : List (String × Int))
    (recipes : List (String × List (String × Int)))
    (drops : List (String × String)) :
    Extracted.TaskBatch.task_batch_size_pure task_type (some c) task_total task_progress
        inventory inventory_free recipes drops
      = Formal.TaskBatch.batchSize
          (eTaskGate task_type (some c) task_total task_progress)
          (task_total - task_progress)
          (eMats recipes c) inventory_free
          (eHeld recipes drops inventory c) := by
  show (if ((!(decide (task_type = some "items"))) || (decide (c = ""))
            || (decide (task_total ≤ 0)))
        then (1 : Int)
        else
          let remaining := (task_total - task_progress)
          (if (decide (remaining ≤ 0))
           then (1 : Int)
           else
            let no_visited : List (String × Int) := []
            let mats_per_unit := (Extracted.RecipeClosure._raw_units
              (Int.toNat ((Int.ofNat (List.length recipes)) + 1)) c recipes [] no_visited)
            let closure : List (String × Int) := []
            let closure := (Extracted.RecipeClosure._closure_visited
              (Int.toNat ((Int.ofNat (List.length recipes)) + 1)) c recipes closure)
            let held_recipe : Int := 0
            let held_recipe := List.foldl
              (fun held_recipe _x =>
                let _res := (_x.1)
                let drop_item := (_x.2)
                let held_recipe := (if (decide ((Extracted.TaskBatch._dictGetD closure drop_item 0) = 1)) then (held_recipe + (Extracted.TaskBatch._dictGetD inventory drop_item 0)) else held_recipe)
                held_recipe)
              held_recipe drops
            let usable := ((inventory_free + held_recipe) - Extracted.TaskBatch._MIN_FREE_SLOTS)
            let fit := (Int.fdiv usable mats_per_unit)
            (max 1 (min remaining (min fit Extracted.TaskBatch.BATCH_CAP)))))
      = _
  by_cases h1 : ((!(decide (task_type = some "items"))) || (decide (c = ""))
      || (decide (task_total ≤ 0))) = true
  · rw [if_pos h1]
    have hg : eTaskGate task_type (some c) task_total task_progress = false := by
      simp only [eTaskGate, h1]
      rfl
    rw [hg]
    rfl
  · rw [if_neg h1]
    by_cases h2 : (decide (task_total - task_progress ≤ 0)) = true
    · simp only [h2, if_true]
      have hg : eTaskGate task_type (some c) task_total task_progress = false := by
        simp only [eTaskGate, h2]
        rw [Bool.not_eq_true] at h1
        rw [h1]
        rfl
      rw [hg]
      rfl
    · simp only [h2]
      have hg : eTaskGate task_type (some c) task_total task_progress = true := by
        simp only [eTaskGate]
        rw [Bool.not_eq_true] at h1 h2
        rw [h1, h2]
        rfl
      rw [hg]
      show _ = (let usable := (inventory_free + eHeld recipes drops inventory c)
                  - Formal.TaskBatch.minFree
                let fit := Int.fdiv usable (eMats recipes c)
                max 1 (min (task_total - task_progress) (min fit Formal.TaskBatch.batchCap)))
      rfl

/-- THE transferred safety theorem on the EXTRACTED definition: the batch
size is always at least 1 (the planner never plans a zero-unit batch). -/
theorem task_batch_ge_one_extracted (task_type task_code : Option String)
    (task_total task_progress inventory_free : Int)
    (inventory : List (String × Int))
    (recipes : List (String × List (String × Int)))
    (drops : List (String × String)) :
    1 ≤ Extracted.TaskBatch.task_batch_size_pure task_type task_code task_total
          task_progress inventory inventory_free recipes drops := by
  cases task_code with
  | none =>
    rw [task_batch_bridge_none]
    exact Formal.TaskBatch.batch_ge_one false _ _ _ _
  | some c =>
    rw [task_batch_bridge]
    exact Formal.TaskBatch.batch_ge_one _ _ _ _ _

/-! ## Recipe-graph encoding (shared by the RecipeClosure and TaskReservation
bridges): a finite entry list `es : List (Nat × List (Nat × Nat))` denotes the
hand-side recipe FUNCTION `rOf es` and encodes to the extracted-side dict
`encRecipes f es`. -/

/-- Encode one ingredient list. -/
def encRcp (f : Nat → String) (rcp : List (Nat × Nat)) : List (String × Int) :=
  encAssoc f Int.ofNat rcp

/-- Encode a recipe entry list to the extracted dict. -/
def encRecipes (f : Nat → String) (es : List (Nat × List (Nat × Nat))) :
    List (String × List (String × Int)) :=
  encAssoc f (encRcp f) es

/-- The hand-side recipe function an entry list denotes (first match, raw
items absent). -/
def rOf (es : List (Nat × List (Nat × Nat))) : Nat → List (Nat × Nat) :=
  fun i => lookAssoc es i []

private theorem recipes_getD (f : Nat → String)
    (hf : ∀ {a b : Nat}, f a = f b → a = b)
    (es : List (Nat × List (Nat × Nat))) (i : Nat) :
    Extracted.RecipeClosure._dictGetD (encRecipes f es) (f i) []
      = encRcp f (rOf es i) := by
  have h := dictGetD_encAssoc f hf (encRcp f) es i []
  exact h

/-- The fuel the extracted cores seed over an encoded graph is the hand
models' `|entries| + 1`. -/
private theorem eFuel_enc (f : Nat → String) (es : List (Nat × List (Nat × Nat))) :
    eFuel (encRecipes f es) = es.length + 1 := by
  unfold eFuel
  rw [show (Int.ofNat (List.length (encRecipes f es)) + 1) = Int.ofNat (es.length + 1) by
    simp [encRecipes, encAssoc]]
  rfl

/-- Visited-set correspondence: the extracted membership dict reads 1 exactly
on the encoded members of the hand visited list. -/
def VisRel (f : Nat → String) (ev : List (String × Int)) (hv : List Nat) : Prop :=
  ∀ i, Extracted.RecipeClosure._dictGetD ev (f i) 0
      = (if hv.contains i then (1 : Int) else 0)

private theorem visRel_nil (f : Nat → String) : VisRel f [] [] := by
  intro i
  rfl

private theorem visRel_mark (f : Nat → String)
    (hf : ∀ {a b : Nat}, f a = f b → a = b)
    (ev : List (String × Int)) (hv : List Nat) (root : Nat)
    (h : VisRel f ev hv) :
    VisRel f (Extracted.RecipeClosure._dictSet ev (f root) 1) (root :: hv) := by
  intro i
  rw [dictGetD_dictSet]
  by_cases hir : i = root
  · subst hir
    rw [if_pos rfl]
    have : (i :: hv).contains i = true := by simp
    rw [this, if_pos rfl]
  · rw [if_neg (fun hc : f i = f root => hir (hf hc)), h i]
    have : (root :: hv).contains i = hv.contains i := by
      simp [fun hc : i = root => hir hc]
    rw [this]

/-! ## TaskReservation: extracted = hand through the encoding. -/

/-- Hand-side: a key absent from the demand list looks up to 0. -/
private theorem lookup_zero_of_not_hasKey (ho : Formal.TaskReservation.Demand)
    (i : Nat) (h : Formal.TaskReservation.hasKey ho i = false) :
    Formal.TaskReservation.lookup ho i = 0 := by
  induction ho with
  | nil => rfl
  | cons e rest ih =>
    obtain ⟨k, v⟩ := e
    simp only [Formal.TaskReservation.hasKey, Bool.or_eq_false_iff] at h
    have hne : ¬ i = k := by
      intro hc
      rw [hc] at h
      simp at h
    simp only [Formal.TaskReservation.lookup, if_neg hne]
    exact ih h.2

/-- Hand-side: a positive lookup witnesses key presence. -/
private theorem hasKey_of_lookup_pos (ho : Formal.TaskReservation.Demand)
    (i : Nat) (h : 0 < Formal.TaskReservation.lookup ho i) :
    Formal.TaskReservation.hasKey ho i = true := by
  by_cases hk : Formal.TaskReservation.hasKey ho i = true
  · exact hk
  · rw [Bool.not_eq_true] at hk
    rw [lookup_zero_of_not_hasKey ho i hk] at h
    omega

/-- Hand-side: an entry witnesses key presence. -/
private theorem hasKey_of_mem (ho : Formal.TaskReservation.Demand)
    (i : Nat) (v : Nat) (h : (i, v) ∈ ho) :
    Formal.TaskReservation.hasKey ho i = true := by
  induction ho with
  | nil => exact absurd h (List.not_mem_nil)
  | cons e rest ih =>
    rcases List.mem_cons.mp h with h' | h'
    · obtain ⟨k, w⟩ := e
      simp [Formal.TaskReservation.hasKey, pair_eq_fst h']
    · obtain ⟨k, w⟩ := e
      simp [Formal.TaskReservation.hasKey, ih h']

/-- Hand-side: key presence witnesses an entry. -/
private theorem mem_of_hasKey (ho : Formal.TaskReservation.Demand) (i : Nat)
    (h : Formal.TaskReservation.hasKey ho i = true) : ∃ v, (i, v) ∈ ho := by
  induction ho with
  | nil => simp [Formal.TaskReservation.hasKey] at h
  | cons e rest ih =>
    obtain ⟨k, w⟩ := e
    simp only [Formal.TaskReservation.hasKey, Bool.or_eq_true] at h
    rcases h with h' | h'
    · have : i = k := of_decide_eq_true h'
      exact ⟨w, by rw [this]; simp⟩
    · obtain ⟨v, hv⟩ := ih h'
      exact ⟨v, List.mem_cons_of_mem _ hv⟩

/-- Hand-side positivity invariant: every present key has demand ≥ 1.
Closure demands with multiplier ≥ 1 (zero-quantity edges skipped) preserve
it — this is what licenses the extracted `get(r, 0) != 0` presence read. -/
def DPos (ho : Formal.TaskReservation.Demand) : Prop :=
  ∀ i, Formal.TaskReservation.hasKey ho i = true →
    1 ≤ Formal.TaskReservation.lookup ho i

private theorem hasKey_record (ho : Formal.TaskReservation.Demand)
    (k v i : Nat) :
    Formal.TaskReservation.hasKey (Formal.TaskReservation.record ho k v) i
      = (decide (i = k) || Formal.TaskReservation.hasKey ho i) := by
  rfl

private theorem dpos_record (ho : Formal.TaskReservation.Demand)
    (k v : Nat) (hv : 1 ≤ v) (h : DPos ho) :
    DPos (Formal.TaskReservation.record ho k v) := by
  intro i hi
  rw [Formal.TaskReservation.lookup_record]
  by_cases hik : i = k
  · rw [if_pos hik]
    exact Nat.le_trans hv (Nat.le_max_right _ _)
  · rw [if_neg hik]
    rw [hasKey_record] at hi
    rcases Bool.or_eq_true _ _ |>.mp hi with h' | h'
    · exact absurd (of_decide_eq_true h') hik
    · exact h i h'

private theorem foldl_children_dpos (r : Formal.TaskReservation.Recipe) (y : Nat → Nat) (fuel : Nat)
    (hcd : ∀ (root mult : Nat) (visited : List Nat)
        (out : Formal.TaskReservation.Demand), DPos out → 1 ≤ mult →
        DPos (Formal.TaskReservation.closureDemand r y fuel root mult visited out)) :
    ∀ (l : List (Nat × Nat)) (mult : Nat) (visited : List Nat)
      (out : Formal.TaskReservation.Demand), DPos out → 1 ≤ mult →
      DPos (l.foldl
        (fun acc p => if p.2 = 0 then acc
          else Formal.TaskReservation.closureDemand r y fuel p.1 (mult * p.2) visited acc)
        out) := by
  intro l
  induction l with
  | nil => intro mult visited out hout _; exact hout
  | cons p rest ihl =>
    intro mult visited out hout hm
    simp only [List.foldl_cons]
    by_cases hq : p.2 = 0
    · rw [if_pos hq]
      exact ihl mult visited out hout hm
    · rw [if_neg hq]
      have hm' : 1 ≤ mult * p.2 := Nat.one_le_iff_ne_zero.mpr
        (Nat.mul_ne_zero (Nat.one_le_iff_ne_zero.mp hm) hq)
      exact ihl mult visited _ (hcd p.1 (mult * p.2) visited out hout hm') hm

/-- The hand `closureDemand` preserves the positivity invariant for any
multiplier ≥ 1, given every yield is ≥ 1 (so each batch count is ≥ 1). -/
private theorem closureDemand_dpos (r : Formal.TaskReservation.Recipe) (y : Nat → Nat)
    (hy : ∀ k, 1 ≤ y k) :
    ∀ (fuel root mult : Nat) (visited : List Nat)
      (out : Formal.TaskReservation.Demand), DPos out → 1 ≤ mult →
      DPos (Formal.TaskReservation.closureDemand r y fuel root mult visited out) := by
  intro fuel
  induction fuel with
  | zero => intro root mult visited out hout _; exact hout
  | succ fuel ih =>
    intro root mult visited out hout hm
    simp only [Formal.TaskReservation.closureDemand]
    by_cases hv : visited.contains root = true
    · rw [if_pos hv]
      exact hout
    · rw [if_neg hv]
      exact foldl_children_dpos r y fuel ih (r root)
        (Formal.TaskReservation.ceilDiv mult (y root)) (root :: visited)
        (Formal.TaskReservation.record out root mult)
        (dpos_record out root mult hm hout)
        (Formal.TaskReservation.one_le_ceilDiv hm (hy root))

/-- Demand-map correspondence: pointwise lookup equality at every encoded key
plus key-set equivalence in both directions. -/
def DemRel (f : Nat → String) (eo : List (String × Int))
    (ho : Formal.TaskReservation.Demand) : Prop :=
  (∀ i, Extracted.RecipeClosure._dictGetD eo (f i) 0
      = Int.ofNat (Formal.TaskReservation.lookup ho i))
  ∧ (∀ s, keyIn eo s → ∃ i, f i = s ∧ Formal.TaskReservation.hasKey ho i = true)
  ∧ (∀ i, Formal.TaskReservation.hasKey ho i = true → keyIn eo (f i))

private theorem demRel_nil (f : Nat → String) : DemRel f [] [] := by
  refine ⟨fun i => rfl, ?_, ?_⟩
  · rintro s ⟨v, hv⟩
    exact absurd hv (List.not_mem_nil)
  · intro i hi
    simp [Formal.TaskReservation.hasKey] at hi

/-- Record step, set branch: the extracted write `out[root] := mult` matches
the hand `record` when `mult` exceeds the current demand. -/
private theorem demRel_record_gt (f : Nat → String)
    (hf : ∀ {a b : Nat}, f a = f b → a = b)
    (eo : List (String × Int)) (ho : Formal.TaskReservation.Demand)
    (root mult : Nat) (hrel : DemRel f eo ho)
    (hgt : Formal.TaskReservation.lookup ho root < mult) :
    DemRel f (Extracted.RecipeClosure._dictSet eo (f root) (Int.ofNat mult))
      (Formal.TaskReservation.record ho root mult) := by
  obtain ⟨hvals, hkeys, hkeys'⟩ := hrel
  refine ⟨?_, ?_, ?_⟩
  · intro i
    rw [dictGetD_dictSet, Formal.TaskReservation.lookup_record]
    by_cases hir : i = root
    · subst hir
      rw [if_pos rfl, if_pos rfl]
      have hmax : Nat.max (Formal.TaskReservation.lookup ho i) mult = mult :=
        Nat.max_eq_right (Nat.le_of_lt hgt)
      rw [hmax]
    · rw [if_neg (fun hc : f i = f root => hir (hf hc)), if_neg hir]
      exact hvals i
  · intro s hs
    rcases (keyIn_dictSet eo (f root) (Int.ofNat mult) s).mp hs with h | rfl
    · obtain ⟨i, hfi, hk⟩ := hkeys s h
      exact ⟨i, hfi, by rw [hasKey_record]; simp [hk]⟩
    · exact ⟨root, rfl, by rw [hasKey_record]; simp⟩
  · intro i hi
    rw [hasKey_record] at hi
    rcases Bool.or_eq_true _ _ |>.mp hi with h' | h'
    · have : i = root := of_decide_eq_true h'
      subst this
      exact (keyIn_dictSet eo (f i) (Int.ofNat mult) (f i)).mpr (Or.inr rfl)
    · exact (keyIn_dictSet eo (f root) (Int.ofNat mult) (f i)).mpr
        (Or.inl (hkeys' i h'))

/-- Record step, skip branch: when `mult` does not exceed the current demand
the extracted side leaves the dict alone while the hand `record` prepends a
shadowed duplicate — the maps stay corresponding (the key is already present
because demands are ≥ 1). -/
private theorem demRel_record_le (f : Nat → String)
    (eo : List (String × Int)) (ho : Formal.TaskReservation.Demand)
    (root mult : Nat) (hrel : DemRel f eo ho) (hm : 1 ≤ mult)
    (hle : mult ≤ Formal.TaskReservation.lookup ho root) :
    DemRel f eo (Formal.TaskReservation.record ho root mult) := by
  obtain ⟨hvals, hkeys, hkeys'⟩ := hrel
  have hkroot : Formal.TaskReservation.hasKey ho root = true :=
    hasKey_of_lookup_pos ho root (by omega)
  refine ⟨?_, ?_, ?_⟩
  · intro i
    rw [Formal.TaskReservation.lookup_record]
    by_cases hir : i = root
    · subst hir
      rw [if_pos rfl, show Nat.max (Formal.TaskReservation.lookup ho i) mult
          = Formal.TaskReservation.lookup ho i from Nat.max_eq_left hle]
      exact hvals i
    · rw [if_neg hir]
      exact hvals i
  · intro s hs
    obtain ⟨i, hfi, hk⟩ := hkeys s hs
    exact ⟨i, hfi, by rw [hasKey_record]; simp [hk]⟩
  · intro i hi
    rw [hasKey_record] at hi
    rcases Bool.or_eq_true _ _ |>.mp hi with h' | h'
    · have : i = root := of_decide_eq_true h'
      subst this
      exact hkeys' i hkroot
    · exact hkeys' i h'

/-- The extracted children-walk lambda (the generated fold body of
`_closure_demand`, zeta-reduced). -/
private def eChild (fuel : Nat) (multiplier : Int)
    (recipes : List (String × List (String × Int)))
    (sub_visited : List (String × Int)) :
    List (String × Int) → (String × Int) → List (String × Int) :=
  fun out _x =>
    if (decide ((_x.2 : Int) ≤ 0)) then out
    else Extracted.RecipeClosure._closure_demand fuel (_x.1) (multiplier * (_x.2))
      recipes [] sub_visited out

/-- Children-walk correspondence, GIVEN node-level correspondence at the same
fuel (fuel induction is outside, list induction here — the hand
`foldl_children_mono` pattern). -/
private theorem foldl_children_bridge (f : Nat → String)
    (es : List (Nat × List (Nat × Nat))) (fuel : Nat)
    (hcd : ∀ (root mult : Nat) (hv : List Nat) (ev : List (String × Int))
        (ho : Formal.TaskReservation.Demand) (eo : List (String × Int)),
        VisRel f ev hv → DemRel f eo ho → DPos ho → 1 ≤ mult →
        DemRel f
          (Extracted.RecipeClosure._closure_demand fuel (f root) (Int.ofNat mult)
            (encRecipes f es) [] ev eo)
          (Formal.TaskReservation.closureDemand (rOf es) (fun _ => 1) fuel root mult hv ho)) :
    ∀ (l : List (Nat × Nat)) (mult : Nat) (hv : List Nat)
      (ev : List (String × Int)) (ho : Formal.TaskReservation.Demand)
      (eo : List (String × Int)),
      VisRel f ev hv → DemRel f eo ho → DPos ho → 1 ≤ mult →
      DemRel f
        (List.foldl (eChild fuel (Int.ofNat mult) (encRecipes f es) ev) eo (encRcp f l))
        (l.foldl
          (fun acc p => if p.2 = 0 then acc
            else Formal.TaskReservation.closureDemand (rOf es) (fun _ => 1) fuel p.1 (mult * p.2)
              hv acc)
          ho) := by
  intro l
  induction l with
  | nil =>
    intro mult hv ev ho eo _ hrel _ _
    exact hrel
  | cons p rest ihl =>
    intro mult hv ev ho eo hvr hrel hpos hm
    rw [show encRcp f (p :: rest) = (f p.1, Int.ofNat p.2) :: encRcp f rest from rfl,
        List.foldl_cons, List.foldl_cons]
    by_cases hq : p.2 = 0
    · have he : eChild fuel (Int.ofNat mult) (encRecipes f es) ev eo (f p.1, Int.ofNat p.2)
          = eo := by
        unfold eChild
        rw [if_pos (show (decide (((f p.1, Int.ofNat p.2).2 : Int) ≤ 0)) = true by
          simp [hq])]
      rw [he, if_pos hq]
      exact ihl mult hv ev ho eo hvr hrel hpos hm
    · have hq1 : 1 ≤ p.2 := Nat.one_le_iff_ne_zero.mpr hq
      have he : eChild fuel (Int.ofNat mult) (encRecipes f es) ev eo (f p.1, Int.ofNat p.2)
          = Extracted.RecipeClosure._closure_demand fuel (f p.1) (Int.ofNat (mult * p.2))
              (encRecipes f es) [] ev eo := by
        unfold eChild
        rw [if_neg (show ¬ (decide (((f p.1, Int.ofNat p.2).2 : Int) ≤ 0)) = true by
          simp; omega)]
        rw [show (Int.ofNat mult) * (Int.ofNat p.2 : Int) = Int.ofNat (mult * p.2) from rfl]
      rw [he, if_neg hq]
      have hm' : 1 ≤ mult * p.2 := Nat.one_le_iff_ne_zero.mpr
        (Nat.mul_ne_zero (Nat.one_le_iff_ne_zero.mp hm) hq)
      exact ihl mult hv ev _ _ hvr
        (hcd p.1 (mult * p.2) hv ev ho eo hvr hrel hpos hm')
        (closureDemand_dpos (rOf es) (fun _ => 1) (fun _ => Nat.le_refl 1) fuel p.1 (mult * p.2)
          hv ho hpos hm') hm

/-- The extracted ceil-batch `-(fdiv (-mult) (yields.get root 1))` at the
all-`Y=1` integration yield (`yields = []`, so the lookup is the default `1`)
is exactly `mult` — `Int.fdiv _ 1` is the identity. -/
private theorem batches_one (m : Nat) (k : String) :
    -(Int.fdiv (-(Int.ofNat m))
        (Extracted.RecipeClosure._dictGetD ([] : List (String × Int)) k 1)) = Int.ofNat m := by
  show -(Int.fdiv (-(Int.ofNat m)) 1) = Int.ofNat m
  rw [Int.fdiv_one]; omega

/-- BRIDGE: the extracted `_closure_demand` (threaded dict, replace-or-append
writes, fall-through max-record `if`) computes the SAME demand map as the
proved hand `Formal.TaskReservation.closureDemand` (prepend-record list) —
pointwise lookups and key sets — for EVERY fuel, root, multiplier ≥ 1,
encoded recipe graph and corresponding visited/accumulator states.

The yield map is the all-`Y=1` integration value (`[]` on the extracted side,
`fun _ => 1` on the hand side): both the Python `task_reservation` and the
extracted closure pass `{}` / `[]`, so the ceil-batch reduces to the identity
(`batches_one` / `ceilDiv_one`) and the demand math matches the original. The
general-`Y` ceil-batch correctness lives in the hand role theorem
`closureDemand_mono` (kernel, ∀ yield) and the Python differential. -/
theorem closure_demand_bridge (f : Nat → String)
    (hf : ∀ {a b : Nat}, f a = f b → a = b)
    (es : List (Nat × List (Nat × Nat))) :
    ∀ (fuel : Nat) (root mult : Nat) (hv : List Nat) (ev : List (String × Int))
      (ho : Formal.TaskReservation.Demand) (eo : List (String × Int)),
      VisRel f ev hv → DemRel f eo ho → DPos ho → 1 ≤ mult →
      DemRel f
        (Extracted.RecipeClosure._closure_demand fuel (f root) (Int.ofNat mult)
          (encRecipes f es) [] ev eo)
        (Formal.TaskReservation.closureDemand (rOf es) (fun _ => 1) fuel root mult hv ho) := by
  intro fuel
  induction fuel with
  | zero =>
    intro root mult hv ev ho eo _ hrel _ _
    exact hrel
  | succ fuel ih =>
    intro root mult hv ev ho eo hvr hrel hpos hm
    have hguard := hvr root
    simp only [Extracted.RecipeClosure._closure_demand,
      Formal.TaskReservation.closureDemand, batches_one,
      Formal.TaskReservation.ceilDiv_one]
    by_cases hcv : hv.contains root = true
    · -- revisit: both sides return their accumulators untouched.
      have hguard1 : Extracted.RecipeClosure._dictGetD ev (f root) 0 = 1 := by
        rw [hguard, if_pos hcv]
      rw [if_pos hcv,
          if_pos (show (decide ((Extracted.RecipeClosure._dictGetD ev (f root) 0) = 1))
            = true by rw [hguard1]; decide)]
      exact hrel
    · rw [Bool.not_eq_true] at hcv
      have hguard0 : Extracted.RecipeClosure._dictGetD ev (f root) 0 = 0 := by
        rw [hguard, if_neg (show ¬ (hv.contains root = true) from
          fun hc => by rw [hcv] at hc; cases hc)]
      rw [if_neg (show ¬ (hv.contains root = true) from
            fun hc => by rw [hcv] at hc; cases hc),
          if_neg (show ¬ ((decide ((Extracted.RecipeClosure._dictGetD ev (f root) 0) = 1))
            = true) by rw [hguard0]; decide)]
      rw [recipes_getD f hf es root]
      have hvr' : VisRel f (Extracted.RecipeClosure._dictSet ev (f root) 1) (root :: hv) :=
        visRel_mark f hf ev hv root hvr
      have hpos' : DPos (Formal.TaskReservation.record ho root mult) :=
        dpos_record ho root mult hm hpos
      have hvals := hrel.1 root
      rw [hvals]
      by_cases hgt : Formal.TaskReservation.lookup ho root < mult
      · -- mult exceeds the recorded demand: the extracted side writes.
        rw [if_pos (show (decide ((Int.ofNat mult)
              > (Int.ofNat (Formal.TaskReservation.lookup ho root) : Int))) = true
            from decide_eq_true (Int.ofNat_lt.mpr hgt))]
        exact foldl_children_bridge f es fuel ih (rOf es root) mult (root :: hv)
          (Extracted.RecipeClosure._dictSet ev (f root) 1)
          (Formal.TaskReservation.record ho root mult)
          (Extracted.RecipeClosure._dictSet eo (f root) (Int.ofNat mult))
          hvr' (demRel_record_gt f hf eo ho root mult hrel hgt) hpos' hm
      · -- mult at or below the recorded demand: the extracted side skips.
        rw [if_neg (show ¬ (decide ((Int.ofNat mult)
              > (Int.ofNat (Formal.TaskReservation.lookup ho root) : Int))) = true
            by intro hc; exact hgt (Int.ofNat_lt.mp (of_decide_eq_true hc)))]
        exact foldl_children_bridge f es fuel ih (rOf es root) mult (root :: hv)
          (Extracted.RecipeClosure._dictSet ev (f root) 1)
          (Formal.TaskReservation.record ho root mult) eo
          hvr' (demRel_record_le f eo ho root mult hrel hm (Nat.not_lt.mp hgt)) hpos' hm

private theorem dpos_nil : DPos [] := by
  intro i hi
  simp [Formal.TaskReservation.hasKey] at hi

/-- The hand task context the extracted scalar inputs denote. -/
def encCtx (tt : Option String) (code total progress : Nat) :
    Formal.TaskReservation.TaskCtx :=
  ⟨tt == some "items", code, total, progress⟩

/-- BRIDGE: the extracted `task_reserved_demand_pure` corresponds (`DemRel`)
to the proved hand `reservedDemand` at fuel `|entries| + 1` — for EVERY
encoded task context and recipe graph. The hand contracts (done ⇒ inert,
demand monotone in progress) therefore read on the extracted map. -/
theorem reserved_demand_bridge (f : Nat → String)
    (hf : ∀ {a b : Nat}, f a = f b → a = b)
    (code : Nat) (hne : f code ≠ "")
    (es : List (Nat × List (Nat × Nat)))
    (tt : Option String) (total progress : Nat) :
    DemRel f
      (Extracted.TaskReservation.task_reserved_demand_pure tt (some (f code))
        (Int.ofNat total) (Int.ofNat progress) (encRecipes f es))
      (Formal.TaskReservation.reservedDemand (rOf es) (fun _ => 1) (es.length + 1)
        (encCtx tt code total progress)) := by
  show DemRel f
    (if ((!(decide (tt = some "items"))) || (decide (f code = "")))
     then []
     else
      let remaining := ((Int.ofNat total) - (Int.ofNat progress))
      (if (decide (remaining ≤ 0))
       then []
       else
        Extracted.RecipeClosure._closure_demand
          (Int.toNat ((Int.ofNat (List.length (encRecipes f es))) + 1)) (f code) remaining
          (encRecipes f es) [] [] []))
    _
  unfold Formal.TaskReservation.reservedDemand
  by_cases htt : tt = some "items"
  · rw [if_neg (show ¬ (((!(decide (tt = some "items"))) || (decide (f code = ""))) = true)
      by rw [decide_eq_true htt, decide_eq_false hne]; decide)]
    have hitems : (encCtx tt code total progress).taskIsItems = true := by
      show (tt == some "items") = true
      exact beq_iff_eq.mpr htt
    by_cases hrem : total ≤ progress
    · rw [if_pos (show (decide (((Int.ofNat total) - (Int.ofNat progress)) ≤ 0)) = true
        from decide_eq_true (by simp only [Int.ofNat_eq_natCast]; omega))]
      rw [if_neg (show ¬ ((encCtx tt code total progress).taskIsItems = true
          ∧ 0 < Formal.TaskReservation.remaining (encCtx tt code total progress)) by
        intro hc
        have := hc.2
        unfold Formal.TaskReservation.remaining at this
        show False
        have hr0 : (encCtx tt code total progress).taskTotal
            - (encCtx tt code total progress).taskProgress = total - progress := rfl
        rw [hr0] at this
        omega)]
      exact demRel_nil f
    · have hgt : progress < total := Nat.not_le.mp hrem
      rw [if_neg (show ¬ ((decide (((Int.ofNat total) - (Int.ofNat progress)) ≤ 0)) = true)
          by intro hc; have := of_decide_eq_true hc
             simp only [Int.ofNat_eq_natCast] at this; omega)]
      rw [if_pos (show (encCtx tt code total progress).taskIsItems = true
          ∧ 0 < Formal.TaskReservation.remaining (encCtx tt code total progress) from
        ⟨hitems, by show 0 < total - progress; omega⟩)]
      rw [show ((Int.ofNat total) - (Int.ofNat progress)) = Int.ofNat (total - progress)
        by simp only [Int.ofNat_eq_natCast]; omega]
      rw [show (Int.toNat ((Int.ofNat (List.length (encRecipes f es))) + 1)) = es.length + 1
        from eFuel_enc f es]
      exact closure_demand_bridge f hf es (es.length + 1) code (total - progress) [] [] [] []
        (visRel_nil f) (demRel_nil f) dpos_nil (by omega)
  · rw [if_pos (show (((!(decide (tt = some "items"))) || (decide (f code = ""))) = true)
      by rw [decide_eq_false htt]; simp)]
    rw [if_neg (show ¬ ((encCtx tt code total progress).taskIsItems = true
        ∧ 0 < Formal.TaskReservation.remaining (encCtx tt code total progress)) by
      intro hc
      have := hc.1
      rw [show (encCtx tt code total progress).taskIsItems = (tt == some "items") from rfl,
        beq_iff_eq] at this
      exact htt this)]
    exact demRel_nil f

/-- The hand `reservedDemand` satisfies the ≥ 1 invariant. -/
private theorem reserved_demand_dpos (r : Formal.TaskReservation.Recipe) (y : Nat → Nat)
    (hy : ∀ k, 1 ≤ y k) (fuel : Nat) (t : Formal.TaskReservation.TaskCtx) :
    DPos (Formal.TaskReservation.reservedDemand r y fuel t) := by
  unfold Formal.TaskReservation.reservedDemand
  by_cases h : t.taskIsItems = true ∧ 0 < Formal.TaskReservation.remaining t
  · rw [if_pos h]
    exact closureDemand_dpos r y hy fuel t.taskCode (Formal.TaskReservation.remaining t) []
      [] dpos_nil h.2
  · rw [if_neg h]
    exact dpos_nil

/-- A `_findSome` whose body only ever yields `none` or `some true` returns
either `none` or `some true`. -/
private theorem findSome_none_or_some_true {α : Type} (F : α → Option Bool)
    (hF : ∀ x, F x = none ∨ F x = some true) (xs : List α) :
    Extracted.TaskReservation._findSome F xs = none
      ∨ Extracted.TaskReservation._findSome F xs = some true := by
  induction xs with
  | nil => exact Or.inl rfl
  | cons x rest ih =>
    simp only [Extracted.TaskReservation._findSome]
    rcases hF x with h | h
    · rw [h]
      exact ih
    · rw [h]
      exact Or.inr rfl

/-- `_findSome` finds `some true` exactly when some element produces it. -/
private theorem findSome_some_true_iff {α : Type} (F : α → Option Bool)
    (hF : ∀ x, F x = none ∨ F x = some true) (xs : List α) :
    Extracted.TaskReservation._findSome F xs = some true
      ↔ ∃ x, x ∈ xs ∧ F x = some true := by
  induction xs with
  | nil =>
    simp [Extracted.TaskReservation._findSome]
  | cons x rest ih =>
    simp only [Extracted.TaskReservation._findSome]
    rcases hF x with h | h
    · rw [h]
      constructor
      · intro hr
        obtain ⟨y, hy, hFy⟩ := ih.mp hr
        exact ⟨y, List.mem_cons_of_mem _ hy, hFy⟩
      · rintro ⟨y, hy, hFy⟩
        rcases List.mem_cons.mp hy with rfl | hy'
        · rw [h] at hFy
          cases hFy
        · exact ih.mpr ⟨y, hy', hFy⟩
    · rw [h]
      constructor
      · intro _
        exact ⟨x, List.mem_cons_self .., h⟩
      · intro _
        rfl

/-- The conflict-closure fold of `consumes_reserved_pure` corresponds to the
hand `conflictClosure` fold. -/
private theorem conflict_fold_bridge (f : Nat → String)
    (hf : ∀ {a b : Nat}, f a = f b → a = b)
    (es : List (Nat × List (Nat × Nat))) :
    ∀ (ns : List Nat) (eo : List (String × Int)) (ho : Formal.TaskReservation.Demand),
      DemRel f eo ho → DPos ho →
      DemRel f
        (List.foldl
          (fun conflict _x => Extracted.RecipeClosure._closure_demand
            (Int.toNat ((Int.ofNat (List.length (encRecipes f es))) + 1)) (_x.1) 1
            (encRecipes f es) [] [] conflict)
          eo (ns.map (fun i => (f i, (1 : Int)))))
        (ns.foldl
          (fun acc root => Formal.TaskReservation.closureDemand (rOf es) (fun _ => 1)
            (es.length + 1) root 1 [] acc)
          ho) := by
  intro ns
  induction ns with
  | nil =>
    intro eo ho hrel _
    exact hrel
  | cons i rest ih =>
    intro eo ho hrel hpos
    rw [List.map_cons, List.foldl_cons, List.foldl_cons]
    exact ih _ _
      (by
        rw [show (Int.toNat ((Int.ofNat (List.length (encRecipes f es))) + 1))
            = es.length + 1 from eFuel_enc f es]
        exact closure_demand_bridge f hf es (es.length + 1) i 1 [] [] ho eo (visRel_nil f)
          hrel hpos (Nat.le_refl 1))
      (closureDemand_dpos (rOf es) (fun _ => 1) (fun _ => Nat.le_refl 1) (es.length + 1) i 1 []
        ho hpos (Nat.le_refl 1))

/-- The suppression-loop body of `consumes_reserved_pure` (the generated
`_findSome` lambda, zeta-reduced), named so the loop lemma can quantify it. -/
private def consumesF (edemand einv ebank : List (String × Int)) :
    (String × Int) → Option Bool := fun _x =>
  if (decide ((Extracted.TaskReservation._dictGetD edemand (_x.1) 0) = 0))
  then none
  else
    if ((decide ((0 : Int) < ((Extracted.TaskReservation._dictGetD einv (_x.1) 0)
            + (Extracted.TaskReservation._dictGetD ebank (_x.1) 0))))
        && (decide (((Extracted.TaskReservation._dictGetD einv (_x.1) 0)
            + (Extracted.TaskReservation._dictGetD ebank (_x.1) 0))
          ≤ (Extracted.TaskReservation._dictGetD edemand (_x.1) 0))))
    then (some true)
    else none

private theorem consumesF_none_or_true (edemand einv ebank : List (String × Int)) :
    ∀ x, consumesF edemand einv ebank x = none
      ∨ consumesF edemand einv ebank x = some true := by
  intro x
  unfold consumesF
  by_cases h1 : (decide ((Extracted.TaskReservation._dictGetD edemand (x.1) 0) = (0 : Int)))
      = true
  · rw [if_pos h1]
    exact Or.inl rfl
  · rw [if_neg h1]
    by_cases h2 : ((decide ((0 : Int) < ((Extracted.TaskReservation._dictGetD einv (x.1) 0)
          + (Extracted.TaskReservation._dictGetD ebank (x.1) 0))))
        && (decide (((Extracted.TaskReservation._dictGetD einv (x.1) 0)
            + (Extracted.TaskReservation._dictGetD ebank (x.1) 0))
          ≤ (Extracted.TaskReservation._dictGetD edemand (x.1) 0)))) = true
    · rw [if_pos h2]
      exact Or.inr rfl
    · rw [if_neg h2]
      exact Or.inl rfl

/-- The suppression loop of `consumes_reserved_pure` equals the hand `any`
predicate over corresponding demand/conflict maps and owned counts. -/
private theorem consumes_loop_bridge (f : Nat → String)
    (edemand : List (String × Int)) (hdemand : Formal.TaskReservation.Demand)
    (hd : DemRel f edemand hdemand) (hdp : DPos hdemand)
    (econflict : List (String × Int)) (hconflict : Formal.TaskReservation.Demand)
    (hc : DemRel f econflict hconflict)
    (einv ebank : List (String × Int)) (owned : Nat → Nat)
    (hov : ∀ i, ((Extracted.TaskReservation._dictGetD einv (f i) 0)
        + (Extracted.TaskReservation._dictGetD ebank (f i) 0) : Int)
        = Int.ofNat (owned i)) :
    (match Extracted.TaskReservation._findSome (consumesF edemand einv ebank) econflict with
     | some r => r
     | none => false)
      = hconflict.any (fun p =>
          Formal.TaskReservation.hasKey hdemand p.1
            && decide (0 < owned p.1)
            && decide (owned p.1 ≤ Formal.TaskReservation.lookup hdemand p.1)) := by
  have hF := consumesF_none_or_true edemand einv ebank
  -- Pointwise predicate equivalence at an encoded key.
  have hpt : ∀ (i : Nat) (v : Int),
      consumesF edemand einv ebank (f i, v) = some true
        ↔ (Formal.TaskReservation.hasKey hdemand i
            && decide (0 < owned i)
            && decide (owned i ≤ Formal.TaskReservation.lookup hdemand i)) = true := by
    intro i v
    unfold consumesF
    have hdem : (Extracted.TaskReservation._dictGetD edemand ((f i, v) : String × Int).1 0 : Int)
        = Int.ofNat (Formal.TaskReservation.lookup hdemand i) := by
      rw [tr_dictGetD_eq]
      exact hd.1 i
    have hown : (((Extracted.TaskReservation._dictGetD einv ((f i, v) : String × Int).1 0)
        + (Extracted.TaskReservation._dictGetD ebank ((f i, v) : String × Int).1 0)) : Int)
        = Int.ofNat (owned i) := hov i
    by_cases hk : Formal.TaskReservation.hasKey hdemand i = true
    · have hpos := hdp i hk
      rw [hdem, hown]
      rw [if_neg (show ¬ ((decide ((Int.ofNat (Formal.TaskReservation.lookup hdemand i) : Int)
          = 0)) = true) by
        intro hcd
        have := of_decide_eq_true hcd
        simp only [Int.ofNat_eq_natCast] at this
        omega)]
      rw [show (decide ((0 : Int) < (Int.ofNat (owned i) : Int)))
          = (decide (0 < owned i)) from decide_eq_decide.mpr
            (by simp only [Int.ofNat_eq_natCast]; omega),
        show (decide ((Int.ofNat (owned i) : Int)
            ≤ (Int.ofNat (Formal.TaskReservation.lookup hdemand i) : Int)))
          = (decide (owned i ≤ Formal.TaskReservation.lookup hdemand i)) from
            decide_eq_decide.mpr (by simp only [Int.ofNat_eq_natCast]; omega),
        hk, Bool.true_and]
      by_cases hcc : ((decide (0 < owned i))
          && (decide (owned i ≤ Formal.TaskReservation.lookup hdemand i))) = true
      · rw [if_pos hcc, hcc]
        simp
      · rw [if_neg hcc]
        constructor
        · intro hsome
          cases hsome
        · intro hand
          exact absurd hand hcc
    · rw [Bool.not_eq_true] at hk
      have hlz := lookup_zero_of_not_hasKey hdemand i hk
      rw [hdem, hlz]
      rw [if_pos (show (decide ((Int.ofNat 0 : Int) = 0)) = true from by decide)]
      rw [hk]
      simp
  rcases findSome_none_or_some_true _ hF econflict with hfs | hfs
  · rw [hfs]
    show false = _
    have hall : ∀ p ∈ hconflict,
        (Formal.TaskReservation.hasKey hdemand p.1
          && decide (0 < owned p.1)
          && decide (owned p.1 ≤ Formal.TaskReservation.lookup hdemand p.1)) = false := by
      intro p hp
      by_cases hpred : (Formal.TaskReservation.hasKey hdemand p.1
          && decide (0 < owned p.1)
          && decide (owned p.1 ≤ Formal.TaskReservation.lookup hdemand p.1)) = true
      · obtain ⟨pk, pv⟩ := p
        obtain ⟨v, hv⟩ := hc.2.2 pk (hasKey_of_mem hconflict pk pv hp)
        have hsome : consumesF edemand einv ebank (f pk, v) = some true :=
          (hpt pk v).mpr hpred
        have hcontra : Extracted.TaskReservation._findSome
            (consumesF edemand einv ebank) econflict = some true :=
          (findSome_some_true_iff _ hF econflict).mpr ⟨(f pk, v), hv, hsome⟩
        rw [hfs] at hcontra
        cases hcontra
      · exact Bool.not_eq_true _ ▸ hpred
    exact (Formal.TaskReservation.any_false hconflict _ hall).symm
  · rw [hfs]
    show true = _
    obtain ⟨x, hx, hFx⟩ := (findSome_some_true_iff _ hF econflict).mp hfs
    obtain ⟨xs, xv⟩ := x
    obtain ⟨i, hfi, hki⟩ := hc.2.1 xs ⟨xv, hx⟩
    obtain ⟨w, hw⟩ := mem_of_hasKey hconflict i hki
    have hsome : consumesF edemand einv ebank (f i, xv) = some true := by
      rw [show f i = xs from hfi]
      exact hFx
    have hpred := (hpt i xv).mp hsome
    symm
    rw [List.any_eq_true]
    exact ⟨(i, w), hw, hpred⟩

/-- BRIDGE: the extracted `consumes_reserved_pure` equals the proved hand
`Formal.TaskReservation.consumesReserved` through the encoding, for EVERY
injective embedding, recipe graph, task context, needed set and
inventory/bank split (bank present or `None`). The three kernel-proved
reservation contracts — task-done inertness, surplus carve-out, monotone
shrinking — therefore govern the running decision. -/
theorem consumes_reserved_bridge (f : Nat → String)
    (hf : ∀ {a b : Nat}, f a = f b → a = b)
    (code : Nat) (hne : f code ≠ "")
    (es : List (Nat × List (Nat × Nat)))
    (tt : Option String) (total progress : Nat) (ns : List Nat)
    (invE bankE : List (Nat × Nat)) (bank_present : Bool) :
    Extracted.TaskReservation.consumes_reserved_pure
        (ns.map (fun i => (f i, (1 : Int)))) tt (some (f code))
        (Int.ofNat total) (Int.ofNat progress)
        (encAssoc f Int.ofNat invE)
        (if bank_present then some (encAssoc f Int.ofNat bankE) else none)
        (encRecipes f es)
      = Formal.TaskReservation.consumesReserved (rOf es) (fun _ => 1) (es.length + 1)
          (encCtx tt code total progress)
          (fun i => lookAssoc invE i 0
            + (if bank_present then lookAssoc bankE i 0 else 0))
          ns := by
  have hd := reserved_demand_bridge f hf code hne es tt total progress
  have hdp' := reserved_demand_dpos (rOf es) (fun _ => 1) (fun _ => Nat.le_refl 1)
    (es.length + 1) (encCtx tt code total progress)
  cases hde : Extracted.TaskReservation.task_reserved_demand_pure tt (some (f code))
      (Int.ofNat total) (Int.ofNat progress) (encRecipes f es) with
  | nil =>
    rw [hde] at hd
    unfold Extracted.TaskReservation.consumes_reserved_pure
    simp only []
    rw [hde]
    rw [if_pos (show (decide ((Int.ofNat (List.length ([] : List (String × Int)))) = 0))
        = true from by decide)]
    have hknone : ∀ i, Formal.TaskReservation.hasKey
        (Formal.TaskReservation.reservedDemand (rOf es) (fun _ => 1) (es.length + 1)
          (encCtx tt code total progress)) i = false := by
      intro i
      by_cases hk : Formal.TaskReservation.hasKey
          (Formal.TaskReservation.reservedDemand (rOf es) (fun _ => 1) (es.length + 1)
            (encCtx tt code total progress)) i = true
      · obtain ⟨v, hv⟩ := hd.2.2 i hk
        exact absurd hv (List.not_mem_nil)
      · exact Bool.not_eq_true _ ▸ hk
    unfold Formal.TaskReservation.consumesReserved
    refine (Formal.TaskReservation.any_false _ _ ?_).symm
    intro p _
    rw [hknone p.1]
    rfl
  | cons dhead dtail =>
    rw [hde] at hd
    have hcf := conflict_fold_bridge f hf es ns [] [] (demRel_nil f) dpos_nil
    have hlen : ¬ ((decide ((Int.ofNat (List.length (dhead :: dtail))) = 0)) = true) := by
      intro hc
      have := of_decide_eq_true hc
      simp only [List.length_cons, Int.ofNat_eq_natCast] at this
      omega
    cases bank_present with
    | true =>
      rw [if_pos rfl]
      unfold Extracted.TaskReservation.consumes_reserved_pure
      simp only []
      rw [hde, if_neg hlen]
      unfold Formal.TaskReservation.consumesReserved Formal.TaskReservation.conflictClosure
      refine consumes_loop_bridge f (dhead :: dtail) _ hd hdp' _ _ hcf
        (encAssoc f Int.ofNat invE) (encAssoc f Int.ofNat bankE)
        (fun i => lookAssoc invE i 0 + (if (true : Bool) then lookAssoc bankE i 0 else 0)) ?_
      intro i
      rw [tr_dictGetD_eq, tr_dictGetD_eq]
      have h1 : (Extracted.RecipeClosure._dictGetD (encAssoc f Int.ofNat invE) (f i) (0 : Int))
          = Int.ofNat (lookAssoc invE i 0) := dictGetD_encAssoc f hf Int.ofNat invE i 0
      have h2 : (Extracted.RecipeClosure._dictGetD (encAssoc f Int.ofNat bankE) (f i) (0 : Int))
          = Int.ofNat (lookAssoc bankE i 0) := dictGetD_encAssoc f hf Int.ofNat bankE i 0
      rw [h1, h2]
      simp only [Int.ofNat_eq_natCast]
      rw [if_pos trivial]
      omega
    | false =>
      rw [if_neg (show ¬ ((false : Bool) = true) by decide)]
      unfold Extracted.TaskReservation.consumes_reserved_pure
      simp only []
      rw [hde, if_neg hlen]
      unfold Formal.TaskReservation.consumesReserved Formal.TaskReservation.conflictClosure
      refine consumes_loop_bridge f (dhead :: dtail) _ hd hdp' _ _ hcf
        (encAssoc f Int.ofNat invE) []
        (fun i => lookAssoc invE i 0 + (if (false : Bool) then lookAssoc bankE i 0 else 0)) ?_
      intro i
      rw [tr_dictGetD_eq, tr_dictGetD_eq]
      have h1 : (Extracted.RecipeClosure._dictGetD (encAssoc f Int.ofNat invE) (f i) (0 : Int))
          = Int.ofNat (lookAssoc invE i 0) := dictGetD_encAssoc f hf Int.ofNat invE i 0
      have h2 : (Extracted.RecipeClosure._dictGetD ([] : List (String × Int)) (f i) (0 : Int))
          = (0 : Int) := rfl
      rw [h1, h2]
      simp only [Int.ofNat_eq_natCast]
      rw [if_neg (show ¬ ((false : Bool) = true) by decide)]
      omega

/-- Transferred contract (1) on the EXTRACTED definition: a completed (or
overshot) items task reserves nothing — the suppression predicate is inert. -/
theorem task_reservation_done_inert_extracted (f : Nat → String)
    (hf : ∀ {a b : Nat}, f a = f b → a = b)
    (code : Nat) (hne : f code ≠ "")
    (es : List (Nat × List (Nat × Nat)))
    (tt : Option String) (total progress : Nat) (hdone : total ≤ progress)
    (ns : List Nat) (invE bankE : List (Nat × Nat)) (bank_present : Bool) :
    Extracted.TaskReservation.consumes_reserved_pure
        (ns.map (fun i => (f i, (1 : Int)))) tt (some (f code))
        (Int.ofNat total) (Int.ofNat progress)
        (encAssoc f Int.ofNat invE)
        (if bank_present then some (encAssoc f Int.ofNat bankE) else none)
        (encRecipes f es)
      = false := by
  rw [consumes_reserved_bridge f hf code hne es tt total progress ns invE bankE bank_present]
  exact (Formal.TaskReservation.remaining_zero_no_reserve (rOf es) (fun _ => 1) (es.length + 1)
    (encCtx tt code total progress) _ ns
    (by show total - progress = 0; omega)).2

/-! ### Pinned production-trace witnesses on the EXTRACTED definitions
(the 2026-06-09 case: helmet "2" ← 6 x bar "1" ← 10 x ore "0"; items task =
bar, 0/11) — kernel-evaluated, mirroring the hand model's pinned traces. -/

private def traceRecipesE : List (String × List (String × Int)) :=
  [("2", [("1", 6)]), ("1", [("0", 10)])]

/-- 5 bars held, task 0/11 → the helmet step IS deferred (5 ≤ demand 11). -/
theorem trace_helmet_deferred_extracted :
    Extracted.TaskReservation.consumes_reserved_pure [("2", 1)] (some "items") (some "1")
      11 0 [("1", 5)] none traceRecipesE = true := by decide

/-- 17 bars held (surplus over demand 11) → the helmet step is allowed. -/
theorem trace_surplus_allowed_extracted :
    Extracted.TaskReservation.consumes_reserved_pure [("2", 1)] (some "items") (some "1")
      11 0 [("1", 17)] none traceRecipesE = false := by decide

/-- Task complete (11/11) → nothing reserved, the helmet step is allowed. -/
theorem trace_done_allowed_extracted :
    Extracted.TaskReservation.consumes_reserved_pure [("2", 1)] (some "items") (some "1")
      11 11 [("1", 5)] none traceRecipesE = false := by decide

/-! ## RecipeClosure: extracted = hand through the encoding. -/

private theorem mem_of_contains_true {l : List Nat} {a : Nat}
    (h : l.contains a = true) : a ∈ l :=
  List.contains_iff_mem.mp h

private theorem not_mem_of_contains_false {l : List Nat} {a : Nat}
    (h : l.contains a = false) : ¬ (a ∈ l) := by
  intro hm
  have hc := List.contains_iff_mem.mpr hm
  rw [hc] at h
  cases h

/-- The children-walk of the extracted `_raw_units` accumulates exactly the
hand model's `Σ qty * units` map-sum (`Int.ofNat` image). -/
private theorem foldl_units_bridge (f : Nat → String)
    (es : List (Nat × List (Nat × Nat))) (fuel : Nat)
    (deeper : List (String × Int)) (hv' : List Nat)
    (hEH : ∀ j : Nat,
      Extracted.RecipeClosure._raw_units fuel (f j) (encRecipes f es) [] deeper
        = Int.ofNat (Formal.RecipeClosure.rawUnitsAux (rOf es) (fun _ => 1) fuel hv' j)) :
    ∀ (l : List (Nat × Nat)) (acc : Nat),
      List.foldl
        (fun total _x => total
          + ((_x.2 : Int)
            * (Extracted.RecipeClosure._raw_units fuel (_x.1) (encRecipes f es) [] deeper)))
        (Int.ofNat acc) (encRcp f l)
        = Int.ofNat (acc
            + (l.map (fun p =>
                p.2 * Formal.RecipeClosure.rawUnitsAux (rOf es) (fun _ => 1) fuel hv' p.1)).sum) := by
  intro l
  induction l with
  | nil =>
    intro acc
    rw [show encRcp f ([] : List (Nat × Nat)) = ([] : List (String × Int)) from rfl]
    simp
  | cons p rest ihl =>
    intro acc
    rw [show encRcp f (p :: rest) = (f p.1, Int.ofNat p.2) :: encRcp f rest from rfl,
        List.foldl_cons]
    rw [show ((Int.ofNat acc : Int)
          + (((f p.1, Int.ofNat p.2) : String × Int).2
            * (Extracted.RecipeClosure._raw_units fuel
                ((f p.1, Int.ofNat p.2) : String × Int).1 (encRecipes f es) [] deeper)))
        = Int.ofNat (acc + p.2
            * Formal.RecipeClosure.rawUnitsAux (rOf es) (fun _ => 1) fuel hv' p.1) by
      rw [show ((f p.1, Int.ofNat p.2) : String × Int).1 = f p.1 from rfl,
          show ((f p.1, Int.ofNat p.2) : String × Int).2 = Int.ofNat p.2 from rfl, hEH p.1]
      simp only [Int.ofNat_eq_natCast, Int.natCast_add, Int.natCast_mul]]
    rw [ihl (acc + p.2 * Formal.RecipeClosure.rawUnitsAux (rOf es) (fun _ => 1) fuel hv' p.1)]
    rw [List.map_cons, List.sum_cons, Nat.add_assoc]

/-- BRIDGE: the extracted `_raw_units` equals the hand
`Formal.RecipeClosure.rawUnitsAux` (`Int.ofNat` image) for EVERY fuel,
encoded recipe graph and corresponding visited states. The hand quantity
theorems (`rawUnits_eq_cost`, revisit/raw guards, fuel-stable cyclic
termination) therefore govern the extracted recipe math. -/
theorem raw_units_bridge (f : Nat → String)
    (hf : ∀ {a b : Nat}, f a = f b → a = b)
    (es : List (Nat × List (Nat × Nat))) :
    ∀ (fuel : Nat) (hv : List Nat) (ev : List (String × Int)),
      VisRel f ev hv → ∀ (i : Nat),
      Extracted.RecipeClosure._raw_units fuel (f i) (encRecipes f es) [] ev
        = Int.ofNat (Formal.RecipeClosure.rawUnitsAux (rOf es) (fun _ => 1) fuel hv i) := by
  intro fuel
  induction fuel with
  | zero =>
    intro hv ev _ i
    rfl
  | succ fuel ihf =>
    intro hv ev hvr i
    simp only [Extracted.RecipeClosure._raw_units]
    have hguard := hvr i
    by_cases hcv : hv.contains i = true
    · rw [if_pos (show (decide ((Extracted.RecipeClosure._dictGetD ev (f i) 0) = 1)) = true
        by rw [hguard, if_pos hcv]; decide)]
      rw [Formal.RecipeClosure.rawUnits_revisit (rOf es) (fun _ => 1) fuel hv i
        (mem_of_contains_true hcv)]
      rfl
    · rw [Bool.not_eq_true] at hcv
      have hguard0 : Extracted.RecipeClosure._dictGetD ev (f i) 0 = 0 := by
        rw [hguard, if_neg (show ¬ (hv.contains i = true) from
          fun hc => by rw [hcv] at hc; cases hc)]
      rw [if_neg (show ¬ ((decide ((Extracted.RecipeClosure._dictGetD ev (f i) 0) = 1)) = true)
        by rw [hguard0]; decide)]
      rw [recipes_getD f hf es i]
      have hmem : i ∉ hv := not_mem_of_contains_false hcv
      cases hrcp : rOf es i with
      | nil =>
        rw [if_pos (show (decide ((Int.ofNat (List.length (encRcp f ([] : List (Nat × Nat)))))
            = 0)) = true from decide_eq_true (show (Int.ofNat (List.length
              (encRcp f ([] : List (Nat × Nat))))) = 0 from rfl))]
        rw [Formal.RecipeClosure.rawUnits_raw (rOf es) (fun _ => 1) fuel hv i hmem hrcp]
        rfl
      | cons phead ptail =>
        rw [if_neg (show ¬ ((decide ((Int.ofNat (List.length (encRcp f (phead :: ptail))))
            = 0)) = true) by
          intro hc
          have := of_decide_eq_true hc
          simp only [encRcp, encAssoc, List.length_map, List.length_cons,
            Int.ofNat_eq_natCast] at this
          omega)]
        rw [Formal.RecipeClosure.rawUnits_eq_cost (rOf es) (fun _ => 1) fuel hv i hmem
          (phead :: ptail) hrcp (by intro hc; cases hc)]
        have hvr' : VisRel f (Extracted.RecipeClosure._dictSet ev (f i) 1) (i :: hv) :=
          visRel_mark f hf ev hv i hvr
        have hfold := foldl_units_bridge f es fuel
          (Extracted.RecipeClosure._dictSet ev (f i) 1) (i :: hv)
          (fun j => ihf (i :: hv) (Extracted.RecipeClosure._dictSet ev (f i) 1) hvr' j)
          (phead :: ptail) 0
        rw [Nat.zero_add] at hfold
        -- extracted ceil `-(fdiv (-Σ) (yields.get i 1))` at yields=[] is Σ (fdiv by 1);
        -- hand `ceilDiv Σ ((fun _=>1) i)` is Σ (ceilDiv_one): both the bare map-sum.
        simp only [Formal.RecipeClosure.ceilDiv_one]
        rw [show Extracted.RecipeClosure._dictGetD ([] : List (String × Int)) (f i) (1 : Int) = 1
          from rfl, Int.fdiv_one, Int.neg_neg]
        exact hfold

/-- Every key of an extracted visited map is the encoding of a reachable
item — the soundness invariant of the closure DFS. -/
def KeysReach (f : Nat → String) (es : List (Nat × List (Nat × Nat)))
    (roots : List Nat) (m : List (String × Int)) : Prop :=
  ∀ s v, (s, v) ∈ m
    → ∃ i, f i = s ∧ Formal.RecipeClosure.Reachable (rOf es) roots i

private theorem foldl_visited_keysreach (f : Nat → String)
    (es : List (Nat × List (Nat × Nat))) (roots : List Nat) (fuel : Nat)
    (IH : ∀ (root : Nat), Formal.RecipeClosure.Reachable (rOf es) roots root →
        ∀ ev, KeysReach f es roots ev →
        KeysReach f es roots
          (Extracted.RecipeClosure._closure_visited fuel (f root) (encRecipes f es) ev)) :
    ∀ (l : List (Nat × Nat)),
      (∀ p ∈ l, Formal.RecipeClosure.Reachable (rOf es) roots p.1) →
      ∀ ev, KeysReach f es roots ev →
      KeysReach f es roots
        (List.foldl
          (fun visited _x => Extracted.RecipeClosure._closure_visited fuel (_x.1)
            (encRecipes f es) visited)
          ev (encRcp f l)) := by
  intro l
  induction l with
  | nil =>
    intro _ ev hev
    exact hev
  | cons p rest ihl =>
    intro hl ev hev
    rw [show encRcp f (p :: rest) = (f p.1, Int.ofNat p.2) :: encRcp f rest from rfl,
        List.foldl_cons]
    exact ihl (fun q hq => hl q (List.mem_cons_of_mem _ hq)) _
      (IH p.1 (hl p (List.mem_cons_self ..)) ev hev)

/-- SOUNDNESS of the extracted closure DFS: every key it marks is
`Formal.RecipeClosure.Reachable` from the roots — the extracted closure never
over-collects, for EVERY fuel, graph and accumulated state. -/
theorem closure_visited_sound (f : Nat → String)
    (hf : ∀ {a b : Nat}, f a = f b → a = b)
    (es : List (Nat × List (Nat × Nat))) (roots : List Nat) :
    ∀ (fuel : Nat) (root : Nat),
      Formal.RecipeClosure.Reachable (rOf es) roots root →
      ∀ ev, KeysReach f es roots ev →
      KeysReach f es roots
        (Extracted.RecipeClosure._closure_visited fuel (f root) (encRecipes f es) ev) := by
  intro fuel
  induction fuel with
  | zero =>
    intro root _ ev hev
    exact hev
  | succ fuel ihf =>
    intro root hroot ev hev
    simp only [Extracted.RecipeClosure._closure_visited]
    by_cases hg : (decide ((Extracted.RecipeClosure._dictGetD ev (f root) 0) = 1)) = true
    · rw [if_pos hg]
      exact hev
    · rw [if_neg hg]
      rw [recipes_getD f hf es root]
      have hev' : KeysReach f es roots (Extracted.RecipeClosure._dictSet ev (f root) 1) := by
        intro s v hsv
        rcases mem_dictSet ev (f root) 1 s v hsv with h | rfl
        · exact hev s v h
        · exact ⟨root, rfl, hroot⟩
      refine foldl_visited_keysreach f es roots fuel ihf (rOf es root) ?_ _ hev'
      intro p hp
      exact Formal.RecipeClosure.Reachable.step hroot
        (List.mem_map_of_mem (f := Prod.fst) hp)

private theorem roots_fold_keysreach (f : Nat → String)
    (hf : ∀ {a b : Nat}, f a = f b → a = b)
    (es : List (Nat × List (Nat × Nat))) (roots : List Nat) :
    ∀ (rs : List Nat), (∀ r ∈ rs, r ∈ roots) →
      ∀ ev, KeysReach f es roots ev →
      KeysReach f es roots
        (List.foldl
          (fun visited root => Extracted.RecipeClosure._closure_visited
            (Int.toNat ((Int.ofNat (List.length (encRecipes f es))) + 1)) root
            (encRecipes f es) visited)
          ev (rs.map f)) := by
  intro rs
  induction rs with
  | nil =>
    intro _ ev hev
    exact hev
  | cons r rest ihl =>
    intro hsub ev hev
    rw [List.map_cons, List.foldl_cons]
    exact ihl (fun q hq => hsub q (List.mem_cons_of_mem _ hq)) _
      (closure_visited_sound f hf es roots _ r
        (Formal.RecipeClosure.Reachable.root (hsub r (List.mem_cons_self ..))) ev hev)

/-- SOUNDNESS of the extracted `recipe_closure_pure` outputs: every reported
craftable is a `Reachable` item with a nonempty recipe (`isCraftable`), and
every reported needed resource has a `Reachable` drop (`isNeeded`) — for
EVERY encoded graph, drop table and root set. -/
theorem recipe_closure_pure_sound (f : Nat → String)
    (hf : ∀ {a b : Nat}, f a = f b → a = b)
    (es : List (Nat × List (Nat × Nat))) (roots : List Nat)
    (ds : List (Nat × Nat)) :
    (∀ s, s ∈ (Extracted.RecipeClosure.recipe_closure_pure (roots.map f)
        (encRecipes f es) (encAssoc f f ds)).2
      → ∃ i, f i = s ∧ Formal.RecipeClosure.isCraftable (rOf es) roots i)
    ∧ (∀ s, s ∈ (Extracted.RecipeClosure.recipe_closure_pure (roots.map f)
        (encRecipes f es) (encAssoc f f ds)).1
      → ∃ res, f res = s ∧ Formal.RecipeClosure.isNeeded (rOf es) roots ds res) := by
  have hvf : KeysReach f es roots
      (List.foldl
        (fun visited root => Extracted.RecipeClosure._closure_visited
          (Int.toNat ((Int.ofNat (List.length (encRecipes f es))) + 1)) root
          (encRecipes f es) visited)
        [] (roots.map f)) :=
    roots_fold_keysreach f hf es roots roots (fun _ hr => hr) []
      (fun s v hsv => absurd hsv (List.not_mem_nil))
  unfold Extracted.RecipeClosure.recipe_closure_pure
  simp only []
  constructor
  · intro s hs
    simp only [List.mem_map, List.mem_filter] at hs
    obtain ⟨kv, ⟨hmem, hpred⟩, hfst⟩ := hs
    obtain ⟨i, hfi, hreach⟩ := hvf kv.1 kv.2 (by
      obtain ⟨ks, kvv⟩ := kv
      exact hmem)
    refine ⟨i, hfi.trans hfst, hreach, ?_⟩
    intro hempty
    rw [← hfi, recipes_getD f hf es i, hempty] at hpred
    have := of_decide_eq_true hpred
    simp [encRcp, encAssoc] at this
  · intro s hs
    simp only [List.mem_map, List.mem_filter] at hs
    obtain ⟨kv, ⟨hmem, hpred⟩, hfst⟩ := hs
    -- kv is an encoded drop entry: kv = (f res, f drop) for some (res, drop) ∈ ds
    obtain ⟨rd, hrd, hkv⟩ := List.mem_map.mp (show kv ∈ encAssoc f f ds from hmem)
    have hkeyne : Extracted.RecipeClosure._dictGetD
        (List.foldl
          (fun visited root => Extracted.RecipeClosure._closure_visited
            (Int.toNat ((Int.ofNat (List.length (encRecipes f es))) + 1)) root
            (encRecipes f es) visited)
          [] (roots.map f)) kv.2 0 ≠ 0 := by
      intro hzero
      rw [hzero] at hpred
      have := of_decide_eq_true hpred
      cases this
    obtain ⟨v, hv⟩ := keyIn_of_getD_ne _ kv.2 0 hkeyne
    obtain ⟨j, hfj, hreachj⟩ := hvf kv.2 v hv
    refine ⟨rd.1, ?_, rd.2, hrd, ?_⟩
    · rw [← hfst, ← hkv]
    · have hdrop : f rd.2 = kv.2 := by rw [← hkv]
      have : j = rd.2 := hf (hfj.trans hdrop.symm)
      rw [← this]
      exact hreachj

/-! ### Completeness of the closure DFS (P4c): the never-exhausts-fuel
invariant, formalized over the extracted defs.

Why the wrapper seed `len(recipes) + 1` suffices: a frame of
`_closure_visited` recurses only when its material was UNMARKED in the
threaded visited dict AND has a nonempty recipe — so before recursing it
marks a previously-unmarked recipe key. Marks are never erased along the
thread, so the count of recipe entries whose key is still unmarked
(`unmarkedKeys`) strictly decreases on every recursive descent; it starts
≤ `|recipes|`, so seeded fuel `|recipes| + 1` strictly dominates it at every
state and the fuel-0 base case is never reached on a frame with work to do.
`closure_visited_complete` packages this: with fuel above the measure, the
DFS marks its root and leaves every newly marked key children-closed. The
roots fold then yields a fully `MarkedClosed` visited dict containing every
root, and `Formal.RecipeClosure.Reachable` (the least fixpoint) transfers
EVERY reachable item into the marked set — completeness, for EVERY graph. -/

/-- A key is marked (membership value 1) in an extracted visited dict. -/
def Marked (v : List (String × Int)) (k : String) : Prop :=
  Extracted.RecipeClosure._dictGetD v k 0 = 1

instance (v : List (String × Int)) (k : String) : Decidable (Marked v k) := by
  unfold Marked
  infer_instance

/-- Mark-set inclusion between visited dicts (the threaded dict only grows). -/
def MSub (v v' : List (String × Int)) : Prop :=
  ∀ k, Marked v k → Marked v' k

/-- Every recipe child of `k` is marked in `res`. -/
def ChildrenMarked (recipes : List (String × List (String × Int)))
    (res : List (String × Int)) (k : String) : Prop :=
  ∀ c q, (c, q) ∈ Extracted.RecipeClosure._dictGetD recipes k [] → Marked res c

/-- Every marked key is children-closed — the saturation property of the
final visited dict that makes the marked set a fixpoint. -/
def MarkedClosed (recipes : List (String × List (String × Int)))
    (v : List (String × Int)) : Prop :=
  ∀ k, Marked v k → ChildrenMarked recipes v k

/-- THE FUEL MEASURE: recipe entries whose key is still unmarked. Every
recursing frame marks a distinct recipe key first, so this strictly
decreases along every recursion path. -/
def unmarkedKeys (recipes : List (String × List (String × Int)))
    (v : List (String × Int)) : Nat :=
  recipes.countP (fun e => decide (¬ Extracted.RecipeClosure._dictGetD v e.1 0 = 1))

private theorem marked_dictSet_self (v : List (String × Int)) (k : String) :
    Marked (Extracted.RecipeClosure._dictSet v k 1) k := by
  unfold Marked
  rw [dictGetD_dictSet, if_pos rfl]

private theorem msub_dictSet (v : List (String × Int)) (k : String) :
    MSub v (Extracted.RecipeClosure._dictSet v k 1) := by
  intro k' hk'
  unfold Marked at hk' ⊢
  rw [dictGetD_dictSet]
  by_cases h : k' = k
  · rw [if_pos h]
  · rw [if_neg h]
    exact hk'

private theorem marked_dictSet_inv (v : List (String × Int)) (k k' : String)
    (h : Marked (Extracted.RecipeClosure._dictSet v k 1) k') :
    k' = k ∨ Marked v k' := by
  by_cases hk : k' = k
  · exact Or.inl hk
  · refine Or.inr ?_
    unfold Marked at h ⊢
    rw [dictGetD_dictSet, if_neg hk] at h
    exact h

/-- A marked key is present in the dict (its read differs from the default). -/
private theorem marked_keyIn (m : List (String × Int)) (k : String)
    (h : Marked m k) : keyIn m k := by
  unfold Marked at h
  exact keyIn_of_getD_ne m k 0 (by rw [h]; decide)

/-- Children-walk monotonicity, GIVEN node-level monotonicity at the same
fuel (the `foldl_children_mono` pattern). -/
private theorem foldl_closure_msub (fuel : Nat)
    (recipes : List (String × List (String × Int)))
    (ihf : ∀ (root : String) (v : List (String × Int)),
      MSub v (Extracted.RecipeClosure._closure_visited fuel root recipes v)) :
    ∀ (l : List (String × Int)) (v : List (String × Int)),
      MSub v (List.foldl
        (fun visited _x =>
          Extracted.RecipeClosure._closure_visited fuel (_x.1) recipes visited)
        v l) := by
  intro l
  induction l with
  | nil => intro v k hk; exact hk
  | cons x rest ihl =>
    intro v
    rw [List.foldl_cons]
    intro k hk
    exact ihl _ k (ihf x.1 v k hk)

/-- The closure DFS only grows the mark set (threaded-dict monotonicity),
for EVERY fuel, root, graph and visited state. -/
theorem closure_visited_msub :
    ∀ (fuel : Nat) (root : String) (recipes : List (String × List (String × Int)))
      (v : List (String × Int)),
      MSub v (Extracted.RecipeClosure._closure_visited fuel root recipes v) := by
  intro fuel
  induction fuel with
  | zero => intro root recipes v k hk; exact hk
  | succ fuel ihf =>
    intro root recipes v
    simp only [Extracted.RecipeClosure._closure_visited]
    by_cases hg : (decide ((Extracted.RecipeClosure._dictGetD v root 0) = 1)) = true
    · rw [if_pos hg]
      intro k hk
      exact hk
    · rw [if_neg hg]
      intro k hk
      exact foldl_closure_msub fuel recipes (fun r w => ihf r recipes w)
        (Extracted.RecipeClosure._dictGetD recipes root [])
        (Extracted.RecipeClosure._dictSet v root 1) k (msub_dictSet v root k hk)

/-- Marks only grow ⇒ the unmarked-recipe-key measure only shrinks. -/
private theorem unmarkedKeys_le_of_msub (recipes : List (String × List (String × Int)))
    (v v' : List (String × Int)) (h : MSub v v') :
    unmarkedKeys recipes v' ≤ unmarkedKeys recipes v := by
  unfold unmarkedKeys
  apply List.countP_mono_left
  intro e _ he
  simp only [decide_eq_true_eq] at he ⊢
  intro hm
  exact he (h e.1 hm)

/-- Marking a present, previously-unmarked recipe key strictly shrinks the
measure — the heart of the never-exhausts-fuel argument: every recursing
frame performs exactly this mark before descending. -/
private theorem unmarkedKeys_strict (recipes : List (String × List (String × Int)))
    (v : List (String × Int)) (root : String) (l : List (String × Int))
    (hmem : (root, l) ∈ recipes)
    (hroot : ¬ Extracted.RecipeClosure._dictGetD v root 0 = 1) :
    unmarkedKeys recipes (Extracted.RecipeClosure._dictSet v root 1)
      < unmarkedKeys recipes v := by
  unfold unmarkedKeys
  induction recipes with
  | nil => exact absurd hmem (List.not_mem_nil)
  | cons e rest ih =>
    rw [List.countP_cons, List.countP_cons]
    have hmono : rest.countP (fun e => decide (¬ Extracted.RecipeClosure._dictGetD
          (Extracted.RecipeClosure._dictSet v root 1) e.1 0 = 1))
        ≤ rest.countP (fun e => decide (¬ Extracted.RecipeClosure._dictGetD v e.1 0 = 1)) := by
      apply List.countP_mono_left
      intro x _ hx
      simp only [decide_eq_true_eq] at hx ⊢
      intro hm
      exact hx (msub_dictSet v root x.1 hm)
    by_cases he : e.1 = root
    · have h1 : (decide (¬ Extracted.RecipeClosure._dictGetD
          (Extracted.RecipeClosure._dictSet v root 1) e.1 0 = 1)) = false := by
        rw [he, dictGetD_dictSet, if_pos rfl]
        decide
      have h2 : (decide (¬ Extracted.RecipeClosure._dictGetD v e.1 0 = 1)) = true := by
        rw [he]
        exact decide_eq_true hroot
      rw [h1, h2, if_neg Bool.false_ne_true, if_pos rfl]
      have := hmono
      omega
    · have hag : (decide (¬ Extracted.RecipeClosure._dictGetD
            (Extracted.RecipeClosure._dictSet v root 1) e.1 0 = 1))
          = (decide (¬ Extracted.RecipeClosure._dictGetD v e.1 0 = 1)) := by
        rw [dictGetD_dictSet, if_neg he]
      have hmem' : (root, l) ∈ rest := by
        rcases List.mem_cons.mp hmem with h' | h'
        · exact absurd (show e.1 = root by rw [← h']) he
        · exact h'
      rw [hag]
      exact Nat.add_lt_add_right (ih hmem') _

/-- THE SEED DOMINATES THE MEASURE: the Python wrapper's fuel seed
`len(recipes) + 1` (`eFuel`) strictly exceeds the unmarked-recipe-key count
at every visited state — fuel sufficiency at every seeded call. -/
theorem eFuel_sufficient (recipes : List (String × List (String × Int)))
    (v : List (String × Int)) :
    unmarkedKeys recipes v < eFuel recipes := by
  have h1 : unmarkedKeys recipes v ≤ recipes.length := by
    unfold unmarkedKeys
    apply List.countP_le_length
  have h2 : eFuel recipes = recipes.length + 1 := rfl
  omega

/-- Children-walk completeness, GIVEN the node-level invariant at the same
fuel (fuel induction outside, list induction here): the fold marks every
listed child and leaves all newly marked keys children-closed. -/
private theorem foldl_closure_complete (fuel : Nat)
    (recipes : List (String × List (String × Int)))
    (ihf : ∀ (root : String) (v : List (String × Int)),
      unmarkedKeys recipes v < fuel →
      Marked (Extracted.RecipeClosure._closure_visited fuel root recipes v) root
      ∧ ∀ k, Marked (Extracted.RecipeClosure._closure_visited fuel root recipes v) k →
          ¬ Marked v k →
          ChildrenMarked recipes
            (Extracted.RecipeClosure._closure_visited fuel root recipes v) k) :
    ∀ (l : List (String × Int)) (v : List (String × Int)),
      unmarkedKeys recipes v < fuel →
      (∀ x ∈ l, Marked
        (List.foldl
          (fun visited _x =>
            Extracted.RecipeClosure._closure_visited fuel (_x.1) recipes visited)
          v l) x.1)
      ∧ ∀ k, Marked
          (List.foldl
            (fun visited _x =>
              Extracted.RecipeClosure._closure_visited fuel (_x.1) recipes visited)
            v l) k →
          ¬ Marked v k →
          ChildrenMarked recipes
            (List.foldl
              (fun visited _x =>
                Extracted.RecipeClosure._closure_visited fuel (_x.1) recipes visited)
              v l) k := by
  intro l
  induction l with
  | nil =>
    intro v _
    refine ⟨?_, ?_⟩
    · intro x hx
      exact absurd hx (List.not_mem_nil)
    · intro k hk hnk
      exact absurd hk hnk
  | cons x rest ihl =>
    intro v hv
    rw [List.foldl_cons]
    have hx := ihf x.1 v hv
    have hmsub1 : MSub v (Extracted.RecipeClosure._closure_visited fuel x.1 recipes v) :=
      closure_visited_msub fuel x.1 recipes v
    have hv1 : unmarkedKeys recipes
        (Extracted.RecipeClosure._closure_visited fuel x.1 recipes v) < fuel :=
      Nat.lt_of_le_of_lt (unmarkedKeys_le_of_msub recipes v _ hmsub1) hv
    have hrest := ihl (Extracted.RecipeClosure._closure_visited fuel x.1 recipes v) hv1
    have hmsubR : MSub (Extracted.RecipeClosure._closure_visited fuel x.1 recipes v)
        (List.foldl
          (fun visited _x =>
            Extracted.RecipeClosure._closure_visited fuel (_x.1) recipes visited)
          (Extracted.RecipeClosure._closure_visited fuel x.1 recipes v) rest) :=
      foldl_closure_msub fuel recipes
        (fun r w => closure_visited_msub fuel r recipes w) rest _
    refine ⟨?_, ?_⟩
    · intro y hy
      rcases List.mem_cons.mp hy with rfl | hy'
      · exact hmsubR y.1 hx.1
      · exact hrest.1 y hy'
    · intro k hk hnk
      by_cases hk1 : Marked (Extracted.RecipeClosure._closure_visited fuel x.1 recipes v) k
      · intro c q hcq
        exact hmsubR c (hx.2 k hk1 hnk c q hcq)
      · exact hrest.2 k hk hk1

/-- THE NEVER-EXHAUSTS-FUEL INVARIANT: with fuel strictly above the
unmarked-recipe-key measure, the closure DFS (a) marks its root and (b)
leaves every key it newly marks children-closed in its result — for EVERY
root, graph and visited state. Every recursing frame marks a distinct
recipe key first (`unmarkedKeys_strict`), so the recursive calls again have
sufficient fuel and the fuel-0 base case is never reached with work
pending. -/
theorem closure_visited_complete :
    ∀ (fuel : Nat) (root : String) (recipes : List (String × List (String × Int)))
      (v : List (String × Int)),
      unmarkedKeys recipes v < fuel →
      Marked (Extracted.RecipeClosure._closure_visited fuel root recipes v) root
      ∧ ∀ k, Marked (Extracted.RecipeClosure._closure_visited fuel root recipes v) k →
          ¬ Marked v k →
          ChildrenMarked recipes
            (Extracted.RecipeClosure._closure_visited fuel root recipes v) k := by
  intro fuel
  induction fuel with
  | zero =>
    intro root recipes v hfuel
    exact absurd hfuel (Nat.not_lt_zero _)
  | succ fuel ihf =>
    intro root recipes v hfuel
    simp only [Extracted.RecipeClosure._closure_visited]
    by_cases hg : (decide ((Extracted.RecipeClosure._dictGetD v root 0) = 1)) = true
    · rw [if_pos hg]
      refine ⟨of_decide_eq_true hg, ?_⟩
      intro k hk hnk
      exact absurd hk hnk
    · rw [if_neg hg]
      have hroot : ¬ Extracted.RecipeClosure._dictGetD v root 0 = 1 := fun hc =>
        hg (decide_eq_true hc)
      cases hrcp : Extracted.RecipeClosure._dictGetD recipes root [] with
      | nil =>
        rw [List.foldl_nil]
        refine ⟨marked_dictSet_self v root, ?_⟩
        intro k hk hnk
        rcases marked_dictSet_inv v root k hk with rfl | hm
        · intro c q hcq
          rw [hrcp] at hcq
          exact absurd hcq (List.not_mem_nil)
        · exact absurd hm hnk
      | cons p ps =>
        obtain ⟨rl, hrl⟩ : keyIn recipes root :=
          keyIn_of_getD_ne recipes root [] (by rw [hrcp]; intro hc; cases hc)
        have hdec := unmarkedKeys_strict recipes v root rl hrl hroot
        have hlt : unmarkedKeys recipes (Extracted.RecipeClosure._dictSet v root 1)
            < fuel := by omega
        have hfold := foldl_closure_complete fuel recipes (fun r w => ihf r recipes w)
          (p :: ps) (Extracted.RecipeClosure._dictSet v root 1) hlt
        have hmsub : MSub (Extracted.RecipeClosure._dictSet v root 1)
            (List.foldl
              (fun visited _x =>
                Extracted.RecipeClosure._closure_visited fuel (_x.1) recipes visited)
              (Extracted.RecipeClosure._dictSet v root 1) (p :: ps)) :=
          foldl_closure_msub fuel recipes
            (fun r w => closure_visited_msub fuel r recipes w) (p :: ps) _
        refine ⟨hmsub root (marked_dictSet_self v root), ?_⟩
        intro k hk hnk
        by_cases hkr : k = root
        · subst hkr
          intro c q hcq
          rw [hrcp] at hcq
          exact hfold.1 (c, q) hcq
        · refine hfold.2 k hk ?_
          intro hm
          rcases marked_dictSet_inv v root k hm with h' | h'
          · exact hkr h'
          · exact hnk h'

/-- Roots-fold monotonicity at the wrapper seed. -/
private theorem roots_fold_msub (recipes : List (String × List (String × Int))) :
    ∀ (rs : List String) (v : List (String × Int)),
      MSub v (List.foldl
        (fun visited root => Extracted.RecipeClosure._closure_visited
          (Int.toNat ((Int.ofNat (List.length recipes)) + 1)) root recipes visited)
        v rs) := by
  intro rs
  induction rs with
  | nil => intro v k hk; exact hk
  | cons r rest ihl =>
    intro v
    rw [List.foldl_cons]
    intro k hk
    exact ihl _ k (closure_visited_msub _ r recipes v k hk)

/-- Roots fold at the wrapper seed: starting from a marked-closed dict, the
result marks every root and is marked-closed — the marked set is a fixpoint
containing the roots. -/
private theorem roots_fold_complete (recipes : List (String × List (String × Int))) :
    ∀ (rs : List String) (v : List (String × Int)),
      MarkedClosed recipes v →
      (∀ s ∈ rs, Marked
        (List.foldl
          (fun visited root => Extracted.RecipeClosure._closure_visited
            (Int.toNat ((Int.ofNat (List.length recipes)) + 1)) root recipes visited)
          v rs) s)
      ∧ MarkedClosed recipes
          (List.foldl
            (fun visited root => Extracted.RecipeClosure._closure_visited
              (Int.toNat ((Int.ofNat (List.length recipes)) + 1)) root recipes visited)
            v rs) := by
  intro rs
  induction rs with
  | nil =>
    intro v hcl
    exact ⟨fun s hs => absurd hs (List.not_mem_nil), hcl⟩
  | cons r rest ihl =>
    intro v hcl
    rw [List.foldl_cons]
    have hc := closure_visited_complete (Int.toNat ((Int.ofNat (List.length recipes)) + 1))
      r recipes v (eFuel_sufficient recipes v)
    have hmsub1 : MSub v (Extracted.RecipeClosure._closure_visited
        (Int.toNat ((Int.ofNat (List.length recipes)) + 1)) r recipes v) :=
      closure_visited_msub _ r recipes v
    have hcl1 : MarkedClosed recipes (Extracted.RecipeClosure._closure_visited
        (Int.toNat ((Int.ofNat (List.length recipes)) + 1)) r recipes v) := by
      intro k hk
      by_cases hkv : Marked v k
      · intro c q hcq
        exact hmsub1 c (hcl k hkv c q hcq)
      · exact hc.2 k hk hkv
    obtain ⟨hmarks, hclR⟩ := ihl _ hcl1
    refine ⟨?_, hclR⟩
    intro s hs
    rcases List.mem_cons.mp hs with rfl | hs'
    · exact roots_fold_msub recipes rest _ s hc.1
    · exact hmarks s hs'

/-- COMPLETENESS of the closure marking (P4c): through any injective
encoding, EVERY spec-`Reachable` item is marked in the visited dict the
extracted `recipe_closure_pure` builds at the wrapper seed `|recipes| + 1`
— the converse of `closure_visited_sound`, now universal. -/
theorem closure_visited_marks_reachable (f : Nat → String)
    (hf : ∀ {a b : Nat}, f a = f b → a = b)
    (es : List (Nat × List (Nat × Nat))) (roots : List Nat)
    {i : Nat} (hreach : Formal.RecipeClosure.Reachable (rOf es) roots i) :
    Marked
      (List.foldl
        (fun visited root => Extracted.RecipeClosure._closure_visited
          (Int.toNat ((Int.ofNat (List.length (encRecipes f es))) + 1)) root
          (encRecipes f es) visited)
        [] (roots.map f))
      (f i) := by
  have hnil : MarkedClosed (encRecipes f es) [] := by
    intro k hk
    exact absurd (show (0 : Int) = 1 from hk) (by decide)
  obtain ⟨hmarks, hclosed⟩ := roots_fold_complete (encRecipes f es) (roots.map f) [] hnil
  induction hreach with
  | root hm => exact hmarks _ (List.mem_map_of_mem hm)
  | @step item child hi hc ih =>
    obtain ⟨p, hp, hpc⟩ := List.mem_map.mp hc
    subst hpc
    have hmem : ((f p.1, Int.ofNat p.2) : String × Int)
        ∈ Extracted.RecipeClosure._dictGetD (encRecipes f es) (f item) [] := by
      rw [recipes_getD f hf es item]
      show ((f p.1, Int.ofNat p.2) : String × Int)
        ∈ (rOf es item).map (fun e => (f e.1, Int.ofNat e.2))
      exact List.mem_map_of_mem hp
    exact hclosed (f item) ih (f p.1) (Int.ofNat p.2) hmem

/-- COMPLETENESS of the extracted `recipe_closure_pure` outputs (P4c — the
formerly kernel-pinned direction, now universal): every `isCraftable` item
appears among the reported craftables and every `isNeeded` resource among
the reported needed resources — for EVERY encoded graph, drop table and
root set. -/
theorem recipe_closure_pure_complete (f : Nat → String)
    (hf : ∀ {a b : Nat}, f a = f b → a = b)
    (es : List (Nat × List (Nat × Nat))) (roots : List Nat)
    (ds : List (Nat × Nat)) :
    (∀ i, Formal.RecipeClosure.isCraftable (rOf es) roots i
      → f i ∈ (Extracted.RecipeClosure.recipe_closure_pure (roots.map f)
          (encRecipes f es) (encAssoc f f ds)).2)
    ∧ (∀ res, Formal.RecipeClosure.isNeeded (rOf es) roots ds res
      → f res ∈ (Extracted.RecipeClosure.recipe_closure_pure (roots.map f)
          (encRecipes f es) (encAssoc f f ds)).1) := by
  unfold Extracted.RecipeClosure.recipe_closure_pure
  simp only []
  constructor
  · rintro i ⟨hreach, hne⟩
    have hm := closure_visited_marks_reachable f hf es roots hreach
    obtain ⟨w, hw⟩ := marked_keyIn _ _ hm
    refine List.mem_map.mpr ⟨(f i, w), List.mem_filter.mpr ⟨hw, ?_⟩, rfl⟩
    show (decide ((Int.ofNat (List.length (Extracted.RecipeClosure._dictGetD
        (encRecipes f es) (f i) []))) > 0)) = true
    rw [recipes_getD f hf es i]
    cases hr : rOf es i with
    | nil => exact absurd hr hne
    | cons a as =>
      refine decide_eq_true ?_
      show (Int.ofNat (List.length (encRcp f (a :: as)))) > 0
      simp only [encRcp, encAssoc, List.length_map, List.length_cons,
        Int.ofNat_eq_natCast]
      omega
  · rintro res ⟨drop, hmemd, hreach⟩
    have hm := closure_visited_marks_reachable f hf es roots hreach
    refine List.mem_map.mpr ⟨(f res, f drop), List.mem_filter.mpr ⟨?_, ?_⟩, rfl⟩
    · show ((f res, f drop) : String × String) ∈ ds.map (fun e => (f e.1, f e.2))
      exact List.mem_map_of_mem hmemd
    · exact decide_eq_true hm

/-- EXACT SPEC of the extracted `recipe_closure_pure` — soundness and
completeness combined (the P3a-deferred direction now universal): through
any injective encoding, craftable-output membership is EXACTLY
`isCraftable` and needed-output membership EXACTLY `isNeeded`, for EVERY
graph, drop table and root set. -/
theorem recipe_closure_pure_spec (f : Nat → String)
    (hf : ∀ {a b : Nat}, f a = f b → a = b)
    (es : List (Nat × List (Nat × Nat))) (roots : List Nat)
    (ds : List (Nat × Nat)) :
    (∀ s, s ∈ (Extracted.RecipeClosure.recipe_closure_pure (roots.map f)
          (encRecipes f es) (encAssoc f f ds)).2
      ↔ ∃ i, f i = s ∧ Formal.RecipeClosure.isCraftable (rOf es) roots i)
    ∧ (∀ s, s ∈ (Extracted.RecipeClosure.recipe_closure_pure (roots.map f)
          (encRecipes f es) (encAssoc f f ds)).1
      ↔ ∃ res, f res = s ∧ Formal.RecipeClosure.isNeeded (rOf es) roots ds res) := by
  obtain ⟨hs2, hs1⟩ := recipe_closure_pure_sound f hf es roots ds
  obtain ⟨hc2, hc1⟩ := recipe_closure_pure_complete f hf es roots ds
  refine ⟨fun s => ⟨hs2 s, ?_⟩, fun s => ⟨hs1 s, ?_⟩⟩
  · rintro ⟨i, rfl, hcraft⟩
    exact hc2 i hcraft
  · rintro ⟨res, rfl, hneed⟩
    exact hc1 res hneed

/-! ### Quantity pins (kernel-evaluated): exact `_raw_units` outputs on the
registered mutation graphs — the numeric anchors the mutation suite cites
(diamond 31; cycle 6, where the dropped-visited-guard mutant yields 12).
The closure COMPLETENESS pins that used to live here (`closure_pin_*`) were
superseded by the universal `recipe_closure_pure_spec` above (P4c) and
dropped. -/

/-- Diamond: 0 ← {1 x2, 2 x3}; 1 ← 3 x5; 2 ← 3 x7; resource 100 drops 3. -/
private def pinRecipesDiamond : List (String × List (String × Int)) :=
  [("0", [("1", 2), ("2", 3)]), ("1", [("3", 5)]), ("2", [("3", 7)])]

private def pinRDiamond : Formal.RecipeClosure.Recipe := fun i =>
  if i = 0 then [(1, 2), (2, 3)] else if i = 1 then [(3, 5)]
  else if i = 2 then [(3, 7)] else []

/-- The diamond quantity math agrees end-to-end: 2·5 + 3·7 = 31 (all-`Y=1`). -/
theorem raw_units_pin_diamond :
    Extracted.RecipeClosure._raw_units 4 "0" pinRecipesDiamond [] []
      = Int.ofNat (Formal.RecipeClosure.rawUnits pinRDiamond (fun _ => 1) 4 0)
      ∧ Extracted.RecipeClosure._raw_units 4 "0" pinRecipesDiamond [] [] = 31 := by decide

/-- Cycle: 0 ← 1 x2; 1 ← 0 x3 (the registered visited-guard mutant diverges
here: dropping the `_raw_units` revisit short-circuit yields 12, not 6). -/
private def pinRecipesCycle : List (String × List (String × Int)) :=
  [("0", [("1", 2)]), ("1", [("0", 3)])]

private def pinRCycle : Formal.RecipeClosure.Recipe := fun i =>
  if i = 0 then [(1, 2)] else if i = 1 then [(0, 3)] else []

/-- Cyclic quantity math: units(0) = 2 · (3 · 1) = 6 on both sides. -/
theorem raw_units_pin_cycle :
    Extracted.RecipeClosure._raw_units 3 "0" pinRecipesCycle [] []
      = Int.ofNat (Formal.RecipeClosure.rawUnits pinRCycle (fun _ => 1) 3 0)
      ∧ Extracted.RecipeClosure._raw_units 3 "0" pinRecipesCycle [] [] = 6 := by decide

end Extracted.Bridges
