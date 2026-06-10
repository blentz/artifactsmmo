-- @concept: resources @property: dominance, monotonicity, safety, totality
/-
Formal model of the bank-aware recipe shopping list extracted from
`src/artifactsmmo_cli/ai/shopping_list.py` (`shopping_list`, `_expand`,
`fully_covered_materials`).

`shopping_list(item, qty, recipes, owned)` recurses an item's recipe graph; at
each node it credits the held copies of THAT item (`owned`, = inventory + bank)
before expanding the sub-recipe, and stock at any level SHORT-CIRCUITS the
subtree below it. The NET result per item is the remaining acquisition work
after crediting holdings. The planner uses a 0-net item as "withdraw, don't
gather", pruning the gather subtree — so the proofs establish that the bank
credit never INCREASES work (dominance), is exactly accounted (reconstruction),
and is monotone in holdings.

CONSUME SEMANTICS (P2c, docs/PLAN_mechanical_extraction.md): the Python
`_expand` THREADS the `owned` dict through the recursion and CONSUMES stock as
it credits it — a unit of banked ore credited under one parent is NOT available
to a sibling branch. The pre-P2c hand model credited a CONSTANT `owned`
function at every node instead; the two agree on TREE recipes but the constant
model DOUBLE-CREDITS shared stock on DAG-shaped recipes (one raw material under
two parents — the shape real gear recipes have). Python's consume accounting is
the spec, so this model threads an `(owned, net)` state pair exactly like
`_expand` does. `formal/Formal/Extracted/Bridges.lean` proves the mechanically
extracted image (`Formal/Extracted/ShoppingList.lean`) equal to this model
UNIVERSALLY (`shopping_expand_bridge` / `shopping_list_bridge`).

The model shares the extracted encoding: items are `String` (pure payload, only
compared for equality), quantities are `Int`, and dicts are insertion-ordered
association lists with Python `dict.get`/`d[k]=v` semantics (`getD`/`setD`).
The recursion is FUEL-BOUNDED and structural on the fuel, mirroring the Python
`fuel` parameter seeded with `len(recipes) + 1` (unreachable on acyclic recipe
graphs).

The load-bearing per-node quantity is the DEFICIT — `deficit qty have = qty -
have` over `Nat` (truncated subtraction). The Python `used = min(have, qty);
deficit = qty - used` equals `qty - have` over `Nat` because `qty - min have
qty = qty - have`; over `Int` the node deficit `qty - min held qty` is
non-negative by construction. The per-node theorems are stated on this `Nat`
credit; the graph-level theorems are stated on `work` (the total raw gather
work a net list implies) via the reconstruction theorem `expand_eq_work`.

Lean core only — no mathlib (safety-module convention; arithmetic via `omega`,
structural recursion on the fuel).
-/

namespace Formal.ShoppingList

/-! ### Per-node credit: the `Nat.sub` deficit and its obligations. -/

/-- Per-node deficit: the remaining quantity after crediting `have` held copies
of an item needed in quantity `qty`. Mirrors Python
`used = min(have, qty); deficit = qty - used`, which equals `qty - have` over
`Nat` (truncated subtraction collapses the `min`). -/
def deficit (qty «have» : Nat) : Nat := qty - «have»

/-- The Python `used = min(have, qty)` credit equals `qty - deficit`: nothing is
over- or under-credited at a node (RECONSTRUCTION, per node):
`min have qty + deficit qty have = qty`. -/
theorem credit_plus_deficit (qty «have» : Nat) :
    min «have» qty + deficit qty «have» = qty := by
  unfold deficit; omega

/-- DOMINANCE (per node): the deficit never exceeds the uncredited requirement.
With `have = 0` (empty bank) the deficit is the full `qty`; any `have` only
reduces it. -/
theorem deficit_le_qty (qty «have» : Nat) : deficit qty «have» ≤ qty := by
  unfold deficit; omega

/-- MONOTONICITY (per node): more held copies ⇒ deficit non-increasing. -/
theorem deficit_antitone (qty h₁ h₂ : Nat) (hle : h₁ ≤ h₂) :
    deficit qty h₂ ≤ deficit qty h₁ := by
  unfold deficit; omega

/-- A 0 deficit is exactly "holdings fully cover the need" — the planner's
short-circuit / withdraw-don't-gather predicate (`fully_covered_materials`). -/
theorem deficit_zero_iff_covered (qty «have» : Nat) :
    deficit qty «have» = 0 ↔ qty ≤ «have» := by
  unfold deficit; omega

/-! ### The threaded-consume model: Python dict encoding. -/

/-- An insertion-ordered association list with Python dict semantics — the
shared encoding of the extracted model. -/
abbrev Dict (α : Type) := List (String × α)

/-- A recipe environment: item → its `{material: per_unit}` recipe. An item
absent (or with an empty recipe) is raw — the `recipes.get(item, {})` case. -/
abbrev Recipes := Dict (Dict Int)

/-- The `(owned, net)` state pair `_expand` threads. -/
abbrev State := Dict Int × Dict Int

/-- Python `dict.get(k, default)`: first matching value, else the default. -/
def getD {α : Type} (m : Dict α) (k : String) (d : α) : α :=
  match m with
  | [] => d
  | (k', v) :: rest => if k' == k then v else getD rest k d

/-- Python `d[k] = v`: replace the first matching entry in place, else append —
every other entry is preserved, mirroring dict update semantics. -/
def setD {α : Type} (m : Dict α) (k : String) (v : α) : Dict α :=
  match m with
  | [] => [(k, v)]
  | (k', v') :: rest => if k' == k then (k', v) :: rest else (k', v') :: setD rest k v

/-- `getD` head hit: the first entry's key matches. -/
theorem getD_cons_self {α : Type} (a : String) (b d : α) (rest : Dict α) :
    getD ((a, b) :: rest) a d = b := by
  simp [getD]

/-- `getD` head miss: the first entry's key differs. -/
theorem getD_cons_ne {α : Type} (a k : String) (b d : α) (rest : Dict α)
    (h : a ≠ k) : getD ((a, b) :: rest) k d = getD rest k d := by
  simp [getD, h]

/-- `setD` head hit: replace the first entry in place. -/
theorem setD_cons_self {α : Type} (a : String) (b v : α) (rest : Dict α) :
    setD ((a, b) :: rest) a v = (a, v) :: rest := by
  simp [setD]

/-- `setD` head miss: keep the first entry, update the tail. -/
theorem setD_cons_ne {α : Type} (a k : String) (b v : α) (rest : Dict α)
    (h : a ≠ k) : setD ((a, b) :: rest) k v = (a, b) :: setD rest k v := by
  simp [setD, h]

/-- Reading through an update: the written key returns the new value, every
other key is untouched (the dict-update/read commutation every graph-level
proof reduces to). -/
theorem getD_setD {α : Type} (m : Dict α) (k k' : String) (v d : α) :
    getD (setD m k v) k' d = if k = k' then v else getD m k' d := by
  induction m with
  | nil =>
    show getD [(k, v)] k' d = if k = k' then v else d
    by_cases h : k = k'
    · subst h; rw [getD_cons_self, if_pos rfl]
    · rw [getD_cons_ne _ _ _ _ _ h, if_neg h]; rfl
  | cons kv rest ih =>
    obtain ⟨a, b⟩ := kv
    by_cases h1 : a = k
    · subst h1
      rw [setD_cons_self]
      by_cases h2 : a = k'
      · subst h2; rw [getD_cons_self, if_pos rfl]
      · rw [getD_cons_ne _ _ _ _ _ h2, if_neg h2, getD_cons_ne _ _ _ _ _ h2]
    · rw [setD_cons_ne _ _ _ _ _ h1]
      by_cases h2 : a = k'
      · subst h2
        rw [getD_cons_self, if_neg (fun hk => h1 hk.symm), getD_cons_self]
      · rw [getD_cons_ne _ _ _ _ _ h2, getD_cons_ne _ _ _ _ _ h2, ih]

/-! ### `expand`: the threaded-consume recursion (the Python `_expand`). -/

/-- One node of the recipe-graph expansion over the threaded `(owned, net)`
state: credit (and CONSUME) the held copies of `item`, record the net deficit,
and — only when the deficit is positive (the SHORT-CIRCUIT) — recurse into the
sub-recipe at `per_unit * deficit`. Out of fuel ⇒ state unchanged (the Python
`fuel <= 0` guard; unreachable on acyclic recipes at the `shoppingList`
seeding). Mirrors `_expand` statement-for-statement. -/
def expand : Nat → String → Int → Recipes → State → State
  | 0, _, _, _, state => state
  | fuel + 1, item, qty, recipes, state =>
    let owned := state.1
    let net := state.2
    let held := getD owned item 0
    let used := min held qty
    let owned := setD owned item (held - used)
    let deficit := qty - used
    let net := setD net item (getD net item 0 + deficit)
    if deficit ≤ 0 then (owned, net)
    else
      let recipe := getD recipes item []
      if recipe.length = 0 then (owned, net)
      else recipe.foldl (fun state mat => expand fuel mat.1 (mat.2 * deficit) recipes state)
        (owned, net)

/-- The net acquisition list for `qty` of `item` crediting (and consuming)
`owned` — the Python `shopping_list`, fuel seeded with `len(recipes) + 1`. -/
def shoppingList (item : String) (qty : Int) (recipes : Recipes) (owned : Dict Int) :
    Dict Int :=
  (expand (recipes.length + 1) item qty recipes (owned, [])).2

/-- Item codes in the net whose deficit is 0 — the planner's withdraw set
(the Python `fully_covered_materials`). -/
def fullyCoveredMaterials (item : String) (qty : Int) (recipes : Recipes)
    (owned : Dict Int) : List String :=
  ((shoppingList item qty recipes owned).filter (fun kv => kv.2 ≤ 0)).map Prod.fst

/-! ### Total raw gather work: the quantity the graph-level theorems bound.

`netSumRaw` is the net summed over RAW items (empty/absent recipe) — exactly
the gather work the planner's pruning leaves, and the quantity
`formal/diff/test_shopping_list_diff.py` compares. `work` recomputes it
directly over the threaded `owned` (no net), and `expand_eq_work` proves the
two accountings agree — the graph-level RECONSTRUCTION. -/

/-- The net summed over raw-leaf items (no recipe entry / empty recipe). -/
def netSumRaw (recipes : Recipes) : Dict Int → Int
  | [] => 0
  | (k, v) :: rest =>
    (if (getD recipes k []).length = 0 then v else 0) + netSumRaw recipes rest

/-- Spec-level raw gather work: threads (and consumes) `owned` exactly like
`expand`, returning `(owned', work added)` instead of recording a net. -/
def work : Nat → String → Int → Recipes → Dict Int → Dict Int × Int
  | 0, _, _, _, owned => (owned, 0)
  | fuel + 1, item, qty, recipes, owned =>
    let held := getD owned item 0
    let used := min held qty
    let owned := setD owned item (held - used)
    let deficit := qty - used
    if deficit ≤ 0 then (owned, 0)
    else
      let recipe := getD recipes item []
      if recipe.length = 0 then (owned, deficit)
      else recipe.foldl
        (fun acc mat =>
          ((work fuel mat.1 (mat.2 * deficit) recipes acc.1).1,
           acc.2 + (work fuel mat.1 (mat.2 * deficit) recipes acc.1).2))
        (owned, 0)

/-- `expand` at `fuel + 1`, zeta-expanded (the shape the proofs case on). -/
theorem expand_succ (fuel : Nat) (item : String) (qty : Int) (recipes : Recipes)
    (o n : Dict Int) :
    expand (fuel + 1) item qty recipes (o, n) =
      if qty - min (getD o item 0) qty ≤ 0 then
        (setD o item (getD o item 0 - min (getD o item 0) qty),
         setD n item (getD n item 0 + (qty - min (getD o item 0) qty)))
      else if (getD recipes item []).length = 0 then
        (setD o item (getD o item 0 - min (getD o item 0) qty),
         setD n item (getD n item 0 + (qty - min (getD o item 0) qty)))
      else
        (getD recipes item []).foldl
          (fun s mat =>
            expand fuel mat.1 (mat.2 * (qty - min (getD o item 0) qty)) recipes s)
          (setD o item (getD o item 0 - min (getD o item 0) qty),
           setD n item (getD n item 0 + (qty - min (getD o item 0) qty))) :=
  rfl

/-- `work` at `fuel + 1`, zeta-expanded (the shape the proofs case on). -/
theorem work_succ (fuel : Nat) (item : String) (qty : Int) (recipes : Recipes)
    (owned : Dict Int) :
    work (fuel + 1) item qty recipes owned =
      if qty - min (getD owned item 0) qty ≤ 0 then
        (setD owned item (getD owned item 0 - min (getD owned item 0) qty), 0)
      else if (getD recipes item []).length = 0 then
        (setD owned item (getD owned item 0 - min (getD owned item 0) qty),
         qty - min (getD owned item 0) qty)
      else
        (getD recipes item []).foldl
          (fun acc mat =>
            ((work fuel mat.1 (mat.2 * (qty - min (getD owned item 0) qty)) recipes acc.1).1,
             acc.2 +
               (work fuel mat.1 (mat.2 * (qty - min (getD owned item 0) qty)) recipes acc.1).2))
          (setD owned item (getD owned item 0 - min (getD owned item 0) qty), 0) :=
  rfl

/-- `netSumRaw` over a cons (the definitional unfolding the proofs rewrite). -/
theorem netSumRaw_cons (recipes : Recipes) (a : String) (b : Int) (rest : Dict Int) :
    netSumRaw recipes ((a, b) :: rest)
      = (if (getD recipes a []).length = 0 then b else 0) + netSumRaw recipes rest :=
  rfl

/-- Updating a net key shifts the raw-leaf total by exactly the value delta
(and only when the key is raw). -/
theorem netSumRaw_setD (recipes : Recipes) (n : Dict Int) (k : String) (v : Int) :
    netSumRaw recipes (setD n k v)
      = netSumRaw recipes n
        + (if (getD recipes k []).length = 0 then v - getD n k 0 else 0) := by
  induction n with
  | nil =>
    show netSumRaw recipes [(k, v)] = netSumRaw recipes [] + _
    rw [netSumRaw_cons]
    show _ + netSumRaw recipes [] = netSumRaw recipes [] + _
    by_cases hraw : (getD recipes k []).length = 0
    · rw [if_pos hraw, if_pos hraw]
      show v + 0 = 0 + (v - 0)
      omega
    · rw [if_neg hraw, if_neg hraw]
      omega
  | cons kv rest ih =>
    obtain ⟨a, b⟩ := kv
    by_cases h1 : a = k
    · subst h1
      rw [setD_cons_self, netSumRaw_cons, netSumRaw_cons, getD_cons_self]
      by_cases hraw : (getD recipes a []).length = 0
      · rw [if_pos hraw, if_pos hraw, if_pos hraw]; omega
      · rw [if_neg hraw, if_neg hraw, if_neg hraw]; omega
    · rw [setD_cons_ne _ _ _ _ _ h1, netSumRaw_cons, netSumRaw_cons, ih,
        getD_cons_ne _ _ _ _ _ h1]
      omega

/-! ### Pointwise dict orders: the simulation invariants. -/

/-- Pointwise holdings comparison: `o₁` holds no more than `o₂` of anything. -/
def OwnedLe (o₁ o₂ : Dict Int) : Prop := ∀ k, getD o₁ k 0 ≤ getD o₂ k 0

/-- All holdings are non-negative (the production invariant: counts of items). -/
def OwnedNonneg (o : Dict Int) : Prop := ∀ k, 0 ≤ getD o k 0

/-- All recipe per-unit quantities are non-negative (the production invariant:
a recipe never yields materials back). -/
def RecipesNonneg (recipes : Recipes) : Prop :=
  ∀ item, ∀ mat ∈ getD recipes item [], 0 ≤ mat.2

/-- Expanding a 0-quantity need is free: no work, holdings pointwise unchanged
(the credit consumes `min held 0 = 0`). -/
theorem work_zero (recipes : Recipes) (fuel : Nat) (item : String) (o : Dict Int)
    (ho : OwnedNonneg o) :
    (work fuel item 0 recipes o).2 = 0 ∧
      ∀ k, getD (work fuel item 0 recipes o).1 k 0 = getD o k 0 := by
  cases fuel with
  | zero => exact ⟨rfl, fun _ => rfl⟩
  | succ n =>
    rw [work_succ]
    rw [if_pos (show (0 : Int) - min (getD o item 0) 0 ≤ 0 by have := ho item; omega)]
    refine ⟨rfl, fun k => ?_⟩
    rw [getD_setD]
    by_cases hk : item = k
    · rw [if_pos hk, ← hk]
      have := ho item
      omega
    · rw [if_neg hk]

/-- THE SIMULATION (master) lemma: requesting no more with no fewer holdings
yields no more raw work, leaves pointwise no fewer holdings, and preserves
holdings non-negativity — the single induction `dominance`, `antitone_owned`
and `mono_qty` instantiate. Side 1 is the smaller request / richer bank. -/
theorem work_mono (recipes : Recipes) (hr : RecipesNonneg recipes) :
    ∀ (fuel : Nat) (item : String) (q₁ q₂ : Int) (o₁ o₂ : Dict Int),
      q₁ ≤ q₂ → OwnedLe o₂ o₁ → OwnedNonneg o₁ → OwnedNonneg o₂ →
      (work fuel item q₁ recipes o₁).2 ≤ (work fuel item q₂ recipes o₂).2 ∧
        OwnedLe (work fuel item q₂ recipes o₂).1 (work fuel item q₁ recipes o₁).1 ∧
        OwnedNonneg (work fuel item q₁ recipes o₁).1 ∧
        OwnedNonneg (work fuel item q₂ recipes o₂).1 := by
  intro fuel
  induction fuel with
  | zero =>
    intro item q₁ q₂ o₁ o₂ _ hle h₁ h₂
    exact ⟨Int.le_refl 0, hle, h₁, h₂⟩
  | succ n ih =>
    intro item q₁ q₂ o₁ o₂ hq hle h₁ h₂
    rw [work_succ, work_succ]
    have hh : getD o₂ item 0 ≤ getD o₁ item 0 := hle item
    -- Node facts: deficits ordered and non-negative, consumed holdings ordered.
    have hdle : q₁ - min (getD o₁ item 0) q₁ ≤ q₂ - min (getD o₂ item 0) q₂ := by omega
    have hd1nn : 0 ≤ q₁ - min (getD o₁ item 0) q₁ := by omega
    have hd2nn : 0 ≤ q₂ - min (getD o₂ item 0) q₂ := by omega
    have hle' : OwnedLe (setD o₂ item (getD o₂ item 0 - min (getD o₂ item 0) q₂))
        (setD o₁ item (getD o₁ item 0 - min (getD o₁ item 0) q₁)) := by
      intro k
      rw [getD_setD, getD_setD]
      by_cases hk : item = k
      · rw [if_pos hk, if_pos hk]; omega
      · rw [if_neg hk, if_neg hk]; exact hle k
    have h₁' : OwnedNonneg (setD o₁ item (getD o₁ item 0 - min (getD o₁ item 0) q₁)) := by
      intro k
      rw [getD_setD]
      by_cases hk : item = k
      · rw [if_pos hk]; have := h₁ item; omega
      · rw [if_neg hk]; exact h₁ k
    have h₂' : OwnedNonneg (setD o₂ item (getD o₂ item 0 - min (getD o₂ item 0) q₂)) := by
      intro k
      rw [getD_setD]
      by_cases hk : item = k
      · rw [if_pos hk]; have := h₂ item; omega
      · rw [if_neg hk]; exact h₂ k
    by_cases hc2 : q₂ - min (getD o₂ item 0) q₂ ≤ 0
    · -- Both sides fully covered: short-circuit on both.
      rw [if_pos (by omega : q₁ - min (getD o₁ item 0) q₁ ≤ 0), if_pos hc2]
      exact ⟨Int.le_refl 0, hle', h₁', h₂'⟩
    · rw [if_neg hc2]
      by_cases hc1 : q₁ - min (getD o₁ item 0) q₁ ≤ 0
      · -- ASYMMETRIC short-circuit: side 1 covered, side 2 still expands.
        rw [if_pos hc1]
        by_cases hlen : (getD recipes item []).length = 0
        · rw [if_pos hlen]
          exact ⟨by omega, hle', h₁', h₂'⟩
        · rw [if_neg hlen]
          -- Side 2's fold only adds work and only consumes holdings (progress).
          have prog : ∀ (mats : List (String × Int)), (∀ m ∈ mats, 0 ≤ m.2) →
              ∀ (acc : Dict Int × Int), OwnedNonneg acc.1 →
              acc.2 ≤ (mats.foldl
                  (fun acc mat =>
                    ((work n mat.1 (mat.2 * (q₂ - min (getD o₂ item 0) q₂)) recipes acc.1).1,
                     acc.2 + (work n mat.1 (mat.2 * (q₂ - min (getD o₂ item 0) q₂))
                       recipes acc.1).2)) acc).2 ∧
                OwnedLe (mats.foldl
                  (fun acc mat =>
                    ((work n mat.1 (mat.2 * (q₂ - min (getD o₂ item 0) q₂)) recipes acc.1).1,
                     acc.2 + (work n mat.1 (mat.2 * (q₂ - min (getD o₂ item 0) q₂))
                       recipes acc.1).2)) acc).1 acc.1 ∧
                OwnedNonneg (mats.foldl
                  (fun acc mat =>
                    ((work n mat.1 (mat.2 * (q₂ - min (getD o₂ item 0) q₂)) recipes acc.1).1,
                     acc.2 + (work n mat.1 (mat.2 * (q₂ - min (getD o₂ item 0) q₂))
                       recipes acc.1).2)) acc).1 := by
            intro mats
            induction mats with
            | nil => exact fun _ acc hacc => ⟨Int.le_refl _, fun _ => Int.le_refl _, hacc⟩
            | cons m rest ihm =>
              intro hmn acc hacc
              rw [List.foldl_cons]
              have hm0 : 0 ≤ m.2 := hmn m (List.mem_cons_self ..)
              have hq2 : (0 : Int) ≤ m.2 * (q₂ - min (getD o₂ item 0) q₂) :=
                Int.mul_nonneg hm0 hd2nn
              have hstep := ih m.1 0 (m.2 * (q₂ - min (getD o₂ item 0) q₂)) acc.1 acc.1
                hq2 (fun _ => Int.le_refl _) hacc hacc
              have hzero := work_zero recipes n m.1 acc.1 hacc
              have hr2 : 0 ≤ (work n m.1 (m.2 * (q₂ - min (getD o₂ item 0) q₂))
                  recipes acc.1).2 := by
                have := hstep.1; rw [hzero.1] at this; exact this
              have hown : OwnedLe (work n m.1 (m.2 * (q₂ - min (getD o₂ item 0) q₂))
                  recipes acc.1).1 acc.1 := by
                intro k
                have := hstep.2.1 k
                rw [hzero.2 k] at this
                exact this
              have hrest := ihm (fun x hx => hmn x (List.mem_cons_of_mem _ hx))
                ((work n m.1 (m.2 * (q₂ - min (getD o₂ item 0) q₂)) recipes acc.1).1,
                 acc.2 + (work n m.1 (m.2 * (q₂ - min (getD o₂ item 0) q₂)) recipes acc.1).2)
                hstep.2.2.2
              refine ⟨?_, fun k => Int.le_trans (hrest.2.1 k) (hown k), hrest.2.2⟩
              exact Int.le_trans (by omega) hrest.1
          have hfold := prog (getD recipes item []) (hr item)
            (setD o₂ item (getD o₂ item 0 - min (getD o₂ item 0) q₂), 0) h₂'
          exact ⟨hfold.1, fun k => Int.le_trans (hfold.2.1 k) (hle' k), h₁', hfold.2.2⟩
      · -- Both sides expand the same recipe.
        rw [if_neg hc1]
        by_cases hlen : (getD recipes item []).length = 0
        · rw [if_pos hlen, if_pos hlen]
          exact ⟨hdle, hle', h₁', h₂'⟩
        · rw [if_neg hlen, if_neg hlen]
          have par : ∀ (mats : List (String × Int)), (∀ m ∈ mats, 0 ≤ m.2) →
              ∀ (a₁ a₂ : Dict Int × Int), a₁.2 ≤ a₂.2 → OwnedLe a₂.1 a₁.1 →
              OwnedNonneg a₁.1 → OwnedNonneg a₂.1 →
              (mats.foldl
                  (fun acc mat =>
                    ((work n mat.1 (mat.2 * (q₁ - min (getD o₁ item 0) q₁)) recipes acc.1).1,
                     acc.2 + (work n mat.1 (mat.2 * (q₁ - min (getD o₁ item 0) q₁))
                       recipes acc.1).2)) a₁).2
                ≤ (mats.foldl
                  (fun acc mat =>
                    ((work n mat.1 (mat.2 * (q₂ - min (getD o₂ item 0) q₂)) recipes acc.1).1,
                     acc.2 + (work n mat.1 (mat.2 * (q₂ - min (getD o₂ item 0) q₂))
                       recipes acc.1).2)) a₂).2 ∧
              OwnedLe (mats.foldl
                  (fun acc mat =>
                    ((work n mat.1 (mat.2 * (q₂ - min (getD o₂ item 0) q₂)) recipes acc.1).1,
                     acc.2 + (work n mat.1 (mat.2 * (q₂ - min (getD o₂ item 0) q₂))
                       recipes acc.1).2)) a₂).1
                (mats.foldl
                  (fun acc mat =>
                    ((work n mat.1 (mat.2 * (q₁ - min (getD o₁ item 0) q₁)) recipes acc.1).1,
                     acc.2 + (work n mat.1 (mat.2 * (q₁ - min (getD o₁ item 0) q₁))
                       recipes acc.1).2)) a₁).1 ∧
              OwnedNonneg (mats.foldl
                  (fun acc mat =>
                    ((work n mat.1 (mat.2 * (q₁ - min (getD o₁ item 0) q₁)) recipes acc.1).1,
                     acc.2 + (work n mat.1 (mat.2 * (q₁ - min (getD o₁ item 0) q₁))
                       recipes acc.1).2)) a₁).1 ∧
              OwnedNonneg (mats.foldl
                  (fun acc mat =>
                    ((work n mat.1 (mat.2 * (q₂ - min (getD o₂ item 0) q₂)) recipes acc.1).1,
                     acc.2 + (work n mat.1 (mat.2 * (q₂ - min (getD o₂ item 0) q₂))
                       recipes acc.1).2)) a₂).1 := by
            intro mats
            induction mats with
            | nil => exact fun _ a₁ a₂ hw hle hn₁ hn₂ => ⟨hw, hle, hn₁, hn₂⟩
            | cons m rest ihm =>
              intro hmn a₁ a₂ hw hleacc hn₁ hn₂
              rw [List.foldl_cons, List.foldl_cons]
              have hm0 : 0 ≤ m.2 := hmn m (List.mem_cons_self ..)
              have hq' : m.2 * (q₁ - min (getD o₁ item 0) q₁)
                  ≤ m.2 * (q₂ - min (getD o₂ item 0) q₂) :=
                Int.mul_le_mul_of_nonneg_left hdle hm0
              have hstep := ih m.1 (m.2 * (q₁ - min (getD o₁ item 0) q₁))
                (m.2 * (q₂ - min (getD o₂ item 0) q₂)) a₁.1 a₂.1 hq' hleacc hn₁ hn₂
              exact ihm (fun x hx => hmn x (List.mem_cons_of_mem _ hx)) _ _
                (by have := hstep.1; omega) hstep.2.1 hstep.2.2.1 hstep.2.2.2
          exact par (getD recipes item []) (hr item)
            (setD o₁ item (getD o₁ item 0 - min (getD o₁ item 0) q₁), 0)
            (setD o₂ item (getD o₂ item 0 - min (getD o₂ item 0) q₂), 0)
            (Int.le_refl 0) hle' h₁' h₂'

/-! ### Reconstruction: the net's raw-leaf total IS the threaded work. -/

/-- RECONSTRUCTION (graph level): expanding a node adds exactly its threaded
raw work to the net's raw-leaf total, and consumes holdings identically — the
net is an exact account of the remaining gather work, never an over- or
under-statement. -/
theorem expand_eq_work (recipes : Recipes) :
    ∀ (fuel : Nat) (item : String) (qty : Int) (o n : Dict Int),
      (expand fuel item qty recipes (o, n)).1 = (work fuel item qty recipes o).1 ∧
        netSumRaw recipes (expand fuel item qty recipes (o, n)).2
          = netSumRaw recipes n + (work fuel item qty recipes o).2 := by
  intro fuel
  induction fuel with
  | zero =>
    intro item qty o n
    refine ⟨rfl, ?_⟩
    show netSumRaw recipes n = netSumRaw recipes n + 0
    omega
  | succ m ih =>
    intro item qty o n
    rw [expand_succ, work_succ]
    by_cases hc : qty - min (getD o item 0) qty ≤ 0
    · rw [if_pos hc, if_pos hc]
      refine ⟨rfl, ?_⟩
      rw [netSumRaw_setD]
      split <;> omega
    · rw [if_neg hc, if_neg hc]
      by_cases hlen : (getD recipes item []).length = 0
      · rw [if_pos hlen, if_pos hlen]
        refine ⟨rfl, ?_⟩
        rw [netSumRaw_setD, if_pos hlen]
        omega
      · rw [if_neg hlen, if_neg hlen]
        have key : ∀ (mats : List (String × Int)) (o' n' : Dict Int) (w : Int),
            ((mats.foldl
                (fun s mat => expand m mat.1 (mat.2 * (qty - min (getD o item 0) qty))
                  recipes s) (o', n')).1
              = (mats.foldl
                (fun acc mat =>
                  ((work m mat.1 (mat.2 * (qty - min (getD o item 0) qty)) recipes acc.1).1,
                   acc.2 + (work m mat.1 (mat.2 * (qty - min (getD o item 0) qty))
                     recipes acc.1).2)) (o', w)).1) ∧
            netSumRaw recipes (mats.foldl
                (fun s mat => expand m mat.1 (mat.2 * (qty - min (getD o item 0) qty))
                  recipes s) (o', n')).2
              = netSumRaw recipes n'
                + ((mats.foldl
                    (fun acc mat =>
                      ((work m mat.1 (mat.2 * (qty - min (getD o item 0) qty))
                          recipes acc.1).1,
                       acc.2 + (work m mat.1 (mat.2 * (qty - min (getD o item 0) qty))
                         recipes acc.1).2)) (o', w)).2 - w) := by
          intro mats
          induction mats with
          | nil =>
            intro o' n' w
            refine ⟨rfl, ?_⟩
            show netSumRaw recipes n' = netSumRaw recipes n' + (w - w)
            omega
          | cons mat rest ihm =>
            intro o' n' w
            simp only [List.foldl_cons]
            have hstep := ih mat.1 (mat.2 * (qty - min (getD o item 0) qty)) o' n'
            have heq : expand m mat.1 (mat.2 * (qty - min (getD o item 0) qty))
                recipes (o', n')
                = ((work m mat.1 (mat.2 * (qty - min (getD o item 0) qty)) recipes o').1,
                   (expand m mat.1 (mat.2 * (qty - min (getD o item 0) qty))
                     recipes (o', n')).2) := by
              rw [← hstep.1]
            rw [heq]
            have hrest := ihm
              (work m mat.1 (mat.2 * (qty - min (getD o item 0) qty)) recipes o').1
              (expand m mat.1 (mat.2 * (qty - min (getD o item 0) qty)) recipes (o', n')).2
              (w + (work m mat.1 (mat.2 * (qty - min (getD o item 0) qty)) recipes o').2)
            refine ⟨hrest.1, ?_⟩
            rw [hrest.2, hstep.2]
            omega
        have hfold := key (getD recipes item [])
          (setD o item (getD o item 0 - min (getD o item 0) qty))
          (setD n item (getD n item 0 + (qty - min (getD o item 0) qty))) 0
        refine ⟨hfold.1, ?_⟩
        rw [hfold.2, netSumRaw_setD, if_neg hlen]
        omega

/-- RECONSTRUCTION at the API level: the raw-leaf total of `shoppingList`'s
net IS the threaded raw work — the bank credit is exactly accounted. -/
theorem shoppingList_eq_work (item : String) (qty : Int) (recipes : Recipes)
    (owned : Dict Int) :
    netSumRaw recipes (shoppingList item qty recipes owned)
      = (work (recipes.length + 1) item qty recipes owned).2 := by
  unfold shoppingList
  have h := (expand_eq_work recipes (recipes.length + 1) item qty owned []).2
  simpa [netSumRaw] using h

/-! ### The graph-level obligations, re-proved under consume semantics. -/

/-- DOMINANCE (graph level): the bank-credited raw work is never larger than
the naive (no-holdings) requirement — crediting holdings at every node only
removes gather work, never adds it. The planner's bank-aware pruning is
therefore never MORE work than gathering everything. -/
theorem shoppingList_raw_le_naive (item : String) (qty : Int) (recipes : Recipes)
    (owned : Dict Int) (hr : RecipesNonneg recipes) (ho : OwnedNonneg owned) :
    netSumRaw recipes (shoppingList item qty recipes owned)
      ≤ netSumRaw recipes (shoppingList item qty recipes []) := by
  rw [shoppingList_eq_work, shoppingList_eq_work]
  exact (work_mono recipes hr (recipes.length + 1) item qty qty owned []
    (Int.le_refl qty) (fun k => ho k) ho (fun _ => Int.le_refl 0)).1

/-- MONOTONICITY in holdings (graph level): pointwise-more `owned` ⇒ the raw
work is non-increasing. More bank stock ⇒ net gather work non-increasing. -/
theorem shoppingList_raw_antitone_owned (item : String) (qty : Int)
    (recipes : Recipes) (o₁ o₂ : Dict Int) (hr : RecipesNonneg recipes)
    (hle : OwnedLe o₂ o₁) (h₁ : OwnedNonneg o₁) (h₂ : OwnedNonneg o₂) :
    netSumRaw recipes (shoppingList item qty recipes o₁)
      ≤ netSumRaw recipes (shoppingList item qty recipes o₂) := by
  rw [shoppingList_eq_work, shoppingList_eq_work]
  exact (work_mono recipes hr (recipes.length + 1) item qty qty o₁ o₂
    (Int.le_refl qty) hle h₁ h₂).1

/-- MONOTONICITY in requested quantity (graph level): needing more never costs
less work. -/
theorem shoppingList_raw_mono_qty (item : String) (q₁ q₂ : Int) (recipes : Recipes)
    (owned : Dict Int) (hr : RecipesNonneg recipes) (hq : q₁ ≤ q₂)
    (ho : OwnedNonneg owned) :
    netSumRaw recipes (shoppingList item q₁ recipes owned)
      ≤ netSumRaw recipes (shoppingList item q₂ recipes owned) := by
  rw [shoppingList_eq_work, shoppingList_eq_work]
  exact (work_mono recipes hr (recipes.length + 1) item q₁ q₂ owned owned
    hq (fun _ => Int.le_refl _) ho ho).1

/-- TOTALITY / honest baseline: with no holdings, a RAW item's net is exactly
`[(item, qty)]` — the gather-it-all amount the dominance bound is measured
against (rules out a vacuous bound). -/
theorem shoppingList_raw_no_holdings (item : String) (qty : Int) (recipes : Recipes)
    (hraw : (getD recipes item []).length = 0) (hq : 0 ≤ qty) :
    shoppingList item qty recipes [] = [(item, qty)] := by
  unfold shoppingList
  rw [expand_succ]
  rw [show getD ([] : Dict Int) item 0 = (0 : Int) from rfl,
    show min (0 : Int) qty = 0 by omega]
  by_cases hc : qty - (0 : Int) ≤ 0
  · rw [if_pos hc]
    show [(item, (0 : Int) + (qty - 0))] = [(item, qty)]
    rw [show (0 : Int) + (qty - 0) = qty by omega]
  · rw [if_neg hc, if_pos hraw]
    show [(item, (0 : Int) + (qty - 0))] = [(item, qty)]
    rw [show (0 : Int) + (qty - 0) = qty by omega]

/-- SHORT-CIRCUIT (the planner's withdraw-don't-gather decision): when holdings
fully cover the requested quantity, the net is the single `(item, 0)` entry —
the subtree below is never expanded, no matter what the recipe says. -/
theorem shoppingList_covered_singleton (item : String) (qty : Int) (recipes : Recipes)
    (owned : Dict Int) (hcov : qty ≤ getD owned item 0) :
    shoppingList item qty recipes owned = [(item, 0)] := by
  unfold shoppingList
  rw [expand_succ]
  rw [if_pos (show qty - min (getD owned item 0) qty ≤ 0 by omega)]
  show [(item, getD ([] : Dict Int) item 0 + (qty - min (getD owned item 0) qty))]
    = [(item, 0)]
  rw [show getD ([] : Dict Int) item 0 + (qty - min (getD owned item 0) qty) = 0 by
    show (0 : Int) + (qty - min (getD owned item 0) qty) = 0
    omega]

/-- SAFETY of the withdraw set: a fully-covered request yields exactly the item
itself as withdrawable — the pruning offers the withdraw and nothing else. -/
theorem fullyCovered_covered_singleton (item : String) (qty : Int) (recipes : Recipes)
    (owned : Dict Int) (hcov : qty ≤ getD owned item 0) :
    fullyCoveredMaterials item qty recipes owned = [item] := by
  unfold fullyCoveredMaterials
  rw [shoppingList_covered_singleton item qty recipes owned hcov]
  rfl

/-- DAG consume-accounting witness (the P2a model-fidelity finding, closed in
P2c): two gear parts share the same ore; 2 banked ore cover only ONE branch.
The pre-P2c constant-credit model credited the 2 ore under BOTH parents
(net ore 0); the consume model — like Python — leaves 2 ore of real work. -/
example :
    shoppingList "sword" 1
        [("sword", [("a", 1), ("b", 1)]), ("a", [("ore", 2)]), ("b", [("ore", 2)])]
        [("ore", 2)]
      = [("sword", 1), ("a", 1), ("ore", 2), ("b", 1)] := by
  decide

end Formal.ShoppingList
