-- @concept: gear-objective @property: termination, monotonicity, validity, dominance
/-
Formal model of the gear objective's pure core,
`src/artifactsmmo_cli/ai/gear_objective_core.py`
(spec docs/superpowers/specs/2026-10-18-global-gear-objective-design.md §2.3, §2.4).
The Python core is bound to these semantics by `formal/diff/test_gear_objective_diff.py`
(differential) and by the GEAR_OBJECTIVE_CORE_MUTATIONS group (unit-killed,
formal/diff/mutate.py).

Two pieces:

  * `layers` — the achievable set as a monotone fixed point grown in layers
    (§2.3). Layer 0 is `base`; each later layer is what `unlock` of the union so
    far adds; the walk stops at the first empty layer. Items are `Nat` ids drawn
    from a finite catalogue `cat`: a fresh item is a catalogue entry `unlock`
    reports and the union lacks. The Python core has no catalogue argument — its
    `unlock` returns only catalogue items, which is the precondition that makes
    the two agree (the differential draws `unlock` that way).
    Proven: the walk terminates within `cat.length + 1` layers
    (`layers_terminate`, by a well-founded measure, no fuel); every later layer
    is non-empty, unlocked by the union before it and disjoint from it
    (`layers_monotone`); and the final union is closed under `unlock` on the
    catalogue (`layers_fixed_point`).
  * `pieceKey` — the ascending order key for a missing target piece (§2.4
    step 2): `(layer, -(gain / price), -gain, slotRank)`, compared
    lexicographically by `keyLt` exactly like a Python tuple. Proven: a lower
    layer orders first whatever the gain and price (`layer_first`); within a
    layer the larger gain per price orders first (`ratio_orders`), then the
    larger gain (`gain_breaks_ratio_tie`), then the smaller slot rank
    (`slot_rank_breaks_tie`); `keyLt` is irreflexive (`keyLt_irrefl`). The
    Python core asserts `price > 0`; the order theorems need no price
    hypothesis because they hold for every `Rat`.
  * `objectiveHeld` — held exactly when nothing is missing (`held_iff_empty`).

Non-vacuity: every hypothesis is satisfiable — `layer_first` (`0 < 1`),
`ratio_orders`, `gain_breaks_ratio_tie` and `slot_rank_breaks_tie` are each
instantiated by a concrete `example` below, and `layers_monotone`'s split
hypothesis is met by the two-layer witness `layers_witness`.

Lean core only — no mathlib (mathlib is quarantined to Formal/Liveness/).
-/

namespace Formal.GearObjective

/-! ### The layered fixed point -/

/-- The catalogue items `unlock acc` reports that `acc` does not hold yet. -/
def fresh (cat : List Nat) (unlock : List Nat → List Nat) (acc : List Nat) : List Nat :=
  cat.filter (fun x => decide (x ∈ unlock acc) && !decide (x ∈ acc))

/-- The termination measure: catalogue items `acc` does not hold yet. -/
def remaining (cat acc : List Nat) : Nat :=
  (cat.filter (fun x => !decide (x ∈ acc))).length

theorem remaining_le (cat acc : List Nat) : remaining cat acc ≤ cat.length :=
  List.length_filter_le _ _

/-- Adding a non-empty fresh layer strictly shrinks what is left to unlock. -/
theorem remaining_lt (cat : List Nat) (unlock : List Nat → List Nat) (acc : List Nat)
    (h : fresh cat unlock acc ≠ []) :
    remaining cat (acc ++ fresh cat unlock acc) < remaining cat acc := by
  unfold remaining
  have hsub : cat.filter (fun x => !decide (x ∈ acc ++ fresh cat unlock acc))
      = (cat.filter (fun x => !decide (x ∈ acc))).filter
          (fun x => !decide (x ∈ acc ++ fresh cat unlock acc)) := by
    rw [List.filter_filter]
    apply List.filter_congr
    intro x _
    by_cases hx : x ∈ acc <;> simp [hx]
  rw [hsub, List.length_filter_lt_length_iff_exists]
  obtain ⟨y, hy⟩ := List.exists_mem_of_ne_nil _ h
  have hy' := hy
  simp only [fresh, List.mem_filter, Bool.and_eq_true, Bool.not_eq_true',
    decide_eq_false_iff_not, decide_eq_true_eq] at hy'
  refine ⟨y, ?_, ?_⟩
  · simp [List.mem_filter, hy'.1, hy'.2.2]
  · simp [hy]

/-- The layers after the first: grow `acc` by its fresh items until none remain. -/
def grow (cat : List Nat) (unlock : List Nat → List Nat) (acc : List Nat) : List (List Nat) :=
  if _h : fresh cat unlock acc = [] then []
  else fresh cat unlock acc :: grow cat unlock (acc ++ fresh cat unlock acc)
termination_by remaining cat acc
decreasing_by exact remaining_lt cat unlock acc (by assumption)

/-- All layers: `base` first, then every fresh layer. Mirrors Python
`achievable_layers`. -/
def layers (cat : List Nat) (unlock : List Nat → List Nat) (base : List Nat) : List (List Nat) :=
  base :: grow cat unlock base

theorem grow_length_le (cat : List Nat) (unlock : List Nat → List Nat) (acc : List Nat) :
    (grow cat unlock acc).length ≤ remaining cat acc := by
  induction acc using (measure (remaining cat)).wf.induction with
  | h acc ih =>
    rw [grow]
    split
    · simp
    · rename_i h
      have hlt := remaining_lt cat unlock acc h
      have := ih (acc ++ fresh cat unlock acc) hlt
      simp only [List.length_cons]
      omega

/-- TERMINATION: the walk yields at most one layer per catalogue item, plus the base. -/
theorem layers_terminate (cat : List Nat) (unlock : List Nat → List Nat) (base : List Nat) :
    (layers cat unlock base).length ≤ cat.length + 1 := by
  have h1 := grow_length_le cat unlock base
  have h2 := remaining_le cat base
  simp only [layers, List.length_cons]
  omega

theorem grow_fixed_point (cat : List Nat) (unlock : List Nat → List Nat) (acc : List Nat) :
    ∀ x ∈ cat, x ∈ unlock (acc ++ (grow cat unlock acc).flatten) →
      x ∈ acc ++ (grow cat unlock acc).flatten := by
  induction acc using (measure (remaining cat)).wf.induction with
  | h acc ih =>
    rw [grow]
    split
    · rename_i h
      intro x hc hu
      simp only [List.flatten_nil, List.append_nil] at hu ⊢
      by_cases hx : x ∈ acc
      · exact hx
      · have : x ∈ fresh cat unlock acc := by
          simp [fresh, List.mem_filter, hc, hu, hx]
        rw [h] at this
        simp at this
    · rename_i h
      have hrec := ih (acc ++ fresh cat unlock acc) (remaining_lt cat unlock acc h)
      intro x hc hu
      simp only [List.flatten_cons, ← List.append_assoc] at hu ⊢
      exact hrec x hc hu

/-- FIXED POINT: the final union is closed under `unlock` on the catalogue. -/
theorem layers_fixed_point (cat : List Nat) (unlock : List Nat → List Nat) (base : List Nat) :
    ∀ x ∈ cat, x ∈ unlock (layers cat unlock base).flatten →
      x ∈ (layers cat unlock base).flatten := by
  simp only [layers, List.flatten_cons]
  exact grow_fixed_point cat unlock base

theorem grow_split (cat : List Nat) (unlock : List Nat → List Nat) (acc : List Nat) :
    ∀ (pre : List (List Nat)) (L : List Nat) (post : List (List Nat)),
      grow cat unlock acc = pre ++ L :: post →
      L ≠ [] ∧ ∀ x ∈ L, x ∈ cat ∧ x ∈ unlock (acc ++ pre.flatten) ∧ x ∉ acc ++ pre.flatten := by
  induction acc using (measure (remaining cat)).wf.induction with
  | h acc ih =>
    intro pre L post hsplit
    rw [grow] at hsplit
    split at hsplit
    · cases pre <;> simp at hsplit
    · rename_i h
      cases pre with
      | nil =>
        simp only [List.nil_append, List.cons.injEq] at hsplit
        obtain ⟨hL, _⟩ := hsplit
        subst hL
        refine ⟨h, ?_⟩
        intro x hx
        simp only [fresh, List.mem_filter, Bool.and_eq_true, Bool.not_eq_true',
          decide_eq_false_iff_not, decide_eq_true_eq] at hx
        simp [hx.1, hx.2.1, hx.2.2]
      | cons p pre' =>
        simp only [List.cons_append, List.cons.injEq] at hsplit
        obtain ⟨hp, hrest⟩ := hsplit
        subst hp
        have := ih (acc ++ fresh cat unlock acc) (remaining_lt cat unlock acc h) pre' L post hrest
        simp only [List.flatten_cons, ← List.append_assoc]
        exact this

/-- MONOTONE: every layer after the base is non-empty, unlocked by the union of
the layers before it, and disjoint from that union — the union strictly grows. -/
theorem layers_monotone (cat : List Nat) (unlock : List Nat → List Nat) (base : List Nat)
    (pre : List (List Nat)) (L : List Nat) (post : List (List Nat))
    (hpre : pre ≠ []) (hsplit : layers cat unlock base = pre ++ L :: post) :
    L ≠ [] ∧ ∀ x ∈ L, x ∈ cat ∧ x ∈ unlock pre.flatten ∧ x ∉ pre.flatten := by
  cases pre with
  | nil => exact absurd rfl hpre
  | cons p pre' =>
    simp only [layers, List.cons_append, List.cons.injEq] at hsplit
    obtain ⟨hp, hrest⟩ := hsplit
    subst hp
    simp only [List.flatten_cons]
    exact grow_split cat unlock base pre' L post hrest

/-- A two-layer witness: `layers_monotone`'s split hypothesis is satisfiable. -/
theorem layers_witness :
    layers [0, 1] (fun acc => if 0 ∈ acc then [0, 1] else acc) [0] = [[0], [1]] := by
  have h1 : fresh [0, 1] (fun acc => if 0 ∈ acc then [0, 1] else acc) [0] = [1] := by decide
  have h2 : fresh [0, 1] (fun acc => if 0 ∈ acc then [0, 1] else acc) [0, 1] = [] := by decide
  unfold layers
  rw [grow, dif_neg (by rw [h1]; simp), h1]
  simp only [List.cons_append, List.nil_append]
  rw [grow, dif_pos h2]

example : ∃ pre L post, pre ≠ [] ∧
    layers [0, 1] (fun acc => if 0 ∈ acc then [0, 1] else acc) [0] = pre ++ L :: post :=
  ⟨[[0]], [1], [], by simp, by rw [layers_witness]; rfl⟩

/-! ### Missing-piece order -/

/-- `(layer, -(gain / price), -gain, slotRank)`. Mirrors Python `PieceKey`. -/
abbrev PieceKey := Nat × Rat × Rat × Int

/-- Mirrors Python `piece_order_key` (the `price > 0` assert lives in Python). -/
def pieceKey (layer : Nat) (gain price : Rat) (slotRank : Int) : PieceKey :=
  (layer, -(gain / price), -gain, slotRank)

/-- Strict lexicographic order, exactly Python's tuple `<`. -/
def keyLt (a b : PieceKey) : Bool :=
  decide (a.1 < b.1) || (decide (a.1 = b.1) &&
    (decide (a.2.1 < b.2.1) || (decide (a.2.1 = b.2.1) &&
      (decide (a.2.2.1 < b.2.2.1) || (decide (a.2.2.1 = b.2.2.1) &&
        decide (a.2.2.2 < b.2.2.2))))))

theorem keyLt_irrefl (a : PieceKey) : keyLt a a = false := by
  simp [keyLt, Rat.lt_irrefl]

/-- DEPENDENCY FIRST: a lower layer orders first whatever the gain and price. -/
theorem layer_first (l₁ l₂ : Nat) (g₁ p₁ g₂ p₂ : Rat) (s₁ s₂ : Int) (h : l₁ < l₂) :
    keyLt (pieceKey l₁ g₁ p₁ s₁) (pieceKey l₂ g₂ p₂ s₂) = true := by
  simp [keyLt, pieceKey, h]

/-- Within a layer, the larger gain per price orders first. -/
theorem ratio_orders (l : Nat) (g₁ p₁ g₂ p₂ : Rat) (s₁ s₂ : Int) (h : g₂ / p₂ < g₁ / p₁) :
    keyLt (pieceKey l g₁ p₁ s₁) (pieceKey l g₂ p₂ s₂) = true := by
  simp [keyLt, pieceKey, Rat.neg_lt_neg h]

/-- Equal gain per price: the larger gain orders first. -/
theorem gain_breaks_ratio_tie (l : Nat) (g₁ p₁ g₂ p₂ : Rat) (s₁ s₂ : Int)
    (hr : g₁ / p₁ = g₂ / p₂) (hg : g₂ < g₁) :
    keyLt (pieceKey l g₁ p₁ s₁) (pieceKey l g₂ p₂ s₂) = true := by
  simp [keyLt, pieceKey, hr, Rat.neg_lt_neg hg]

/-- Equal ratio and gain: the smaller slot rank orders first. -/
theorem slot_rank_breaks_tie (l : Nat) (g p₁ p₂ : Rat) (s₁ s₂ : Int)
    (hr : g / p₁ = g / p₂) (hs : s₁ < s₂) :
    keyLt (pieceKey l g p₁ s₁) (pieceKey l g p₂ s₂) = true := by
  simp [keyLt, pieceKey, hr, hs, Rat.lt_irrefl]

example : keyLt (pieceKey 0 1 100 0) (pieceKey 1 1000 1 0) = true :=
  layer_first 0 1 1 100 1000 1 0 0 (by decide)
example : keyLt (pieceKey 0 10 2 0) (pieceKey 0 10 5 0) = true :=
  ratio_orders 0 10 2 10 5 0 0 (by grind)
example : keyLt (pieceKey 0 4 2 0) (pieceKey 0 2 1 0) = true :=
  gain_breaks_ratio_tie 0 4 2 2 1 0 0 (by grind) (by grind)
example : keyLt (pieceKey 0 2 1 0) (pieceKey 0 2 1 3) = true :=
  slot_rank_breaks_tie 0 2 1 1 0 3 rfl (by decide)

/-- Sort piece ids ascending by key; `List.mergeSort` is stable, like Python
`sorted`, so equal keys keep their input order. -/
def pieceOrder (pieces : List (Nat × PieceKey)) : List Nat :=
  (pieces.mergeSort (fun a b => !keyLt b.2 a.2)).map Prod.fst

/-! ### Objective held -/

/-- Mirrors Python `objective_held`. -/
def objectiveHeld (missing : List Nat) : Bool := missing.isEmpty

theorem held_iff_empty (missing : List Nat) : objectiveHeld missing = true ↔ missing = [] := by
  simp [objectiveHeld]

end Formal.GearObjective
