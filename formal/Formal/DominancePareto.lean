-- @concept: equipment, selling @property: safety
/-
Formal model of `dominance_pareto.pareto_dominates` from
`src/artifactsmmo_cli/ai/dominance_pareto.py`.

Pareto-domination over a stat vector: a peer item DOMINATES an item when it is
`≥` the item componentwise (over the common prefix) AND strictly greater on at
least one component. Domination is the soundness gate for selling a strictly
worse piece of equipment: a piece is shed only when a peer beats it everywhere
and wins somewhere, so ties NEVER trigger a sale (EQUIPPABLE_KEEP keeps one).

* `geqAll peer item` = `peer ≥ item` on every shared index (`True` past the
  shorter list — the common-prefix convention).
* `gtSome peer item` = `peer > item` on at least one shared index (`False` on
  empty / no shared index).
* `paretoDominates peer item = geqAll peer item && gtSome peer item`.

Lean core only — no mathlib. Stat components are `Int` (a stat delta may be
negative). Componentwise reasoning by simultaneous induction on the two lists.
-/

namespace Formal.DominancePareto

/-- Mirror of `dominance_pareto.pareto_dominates`: `peer ≥ item` componentwise
    (over the common prefix) AND strictly greater somewhere. -/
def geqAll : List Int → List Int → Bool
  | p :: ps, i :: is => (decide (i ≤ p)) && geqAll ps is
  | _, _ => true

def gtSome : List Int → List Int → Bool
  | p :: ps, i :: is => (decide (i < p)) || gtSome ps is
  | _, _ => false

def paretoDominates (peer item : List Int) : Bool := geqAll peer item && gtSome peer item

/-- A dominating peer is ≥ the item at every common index — the keep is sound. -/
theorem pareto_implies_geq (peer item : List Int) (k : Nat)
    (hk : k < peer.length) (hk2 : k < item.length)
    (h : paretoDominates peer item = true) :
    item.get ⟨k, hk2⟩ ≤ peer.get ⟨k, hk⟩ := by
  -- Extract the geqAll conjunct, then induct on the two lists with the index.
  simp only [paretoDominates, Bool.and_eq_true] at h
  have hgeq : geqAll peer item = true := h.1
  clear h
  induction peer generalizing item k with
  | nil => exact absurd hk (by simp)
  | cons p ps ih =>
    cases item with
    | nil => exact absurd hk2 (by simp)
    | cons i is =>
      simp only [geqAll, Bool.and_eq_true, decide_eq_true_eq] at hgeq
      cases k with
      | zero =>
        simpa using hgeq.1
      | succ k' =>
        have hk' : k' < ps.length := by
          simp only [List.length_cons] at hk; omega
        have hk2' : k' < is.length := by
          simp only [List.length_cons] at hk2; omega
        have := ih is k' hk' hk2' hgeq.2
        simpa using this

/-- Domination requires a STRICT win somewhere — equal-everywhere peers do not
    dominate (ties keep one via EQUIPPABLE_KEEP). -/
theorem pareto_needs_strict (peer item : List Int)
    (h : paretoDominates peer item = true) :
    gtSome peer item = true := by
  simp [paretoDominates, Bool.and_eq_true] at h; exact h.2

/-- A vector never dominates itself (no piece sells itself). -/
theorem pareto_irreflexive (v : List Int) : paretoDominates v v = false := by
  have hgt : gtSome v v = false := by
    induction v with
    | nil => rfl
    | cons x xs ih =>
      simp only [gtSome, ih, Bool.or_false, decide_eq_false_iff_not]
      omega
  simp [paretoDominates, hgt]

end Formal.DominancePareto
