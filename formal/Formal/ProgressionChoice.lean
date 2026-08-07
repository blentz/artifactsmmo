-- @concept: planner, progression @property: safety, totality
import Formal.Extracted.ProgressionChoice
/-! # ProgressionChoice — the unified progression objective `J`

Role theorems for the choice core specified in
`docs/spec_unified_objective/SPEC.md`. Proved DIRECTLY on the mechanically
extracted defs, so the objects proved about are the objects the differential
executes.

THE CONTRACT. The selector this replaces (`branch_pick_pure`) is a LEXICOGRAPHIC
pivot — gear-first until the band is adequate, then xp — whose switch condition is
never satisfiable against a 50-level catalogue. Measured: GEAR in 2950 of 2950
cycles, zero character levels in 13 hours. A lexicographic order returns one
extreme point of a Pareto front and can never return an interior trade-off. These
theorems pin the replacement: ONE total order on ONE currency, in which gear and
xp genuinely compete.

The order is carried by `sort_key`, an integer triple compared lexicographically,
so every theorem below is a statement about integers — no floats, and no
significance threshold (S-013).

Roles:
* `band_iff_*` — the three bands are exactly the spec's three cases, and
  unreachability is decided by the LEVEL FIELD ALONE (S-014). This is the one
  that matters most: an earlier draft had a second encoding (an infinity value)
  which could disagree with the level field.
* `finite_precedes_unreachable`, `nonfailed_precedes_failed` — cross-band
  precedence (S-006, S-012).
* `finite_orders_by_j` — inside the finite band, lower `J` wins (S-005).
* `unreachable_prefers_progress`, `unreachable_tie_prefers_cheaper` — inside the
  unreachable band, furthest progress then acquisition cost (S-006).
* `unreachable_ignores_cycles` — the void field cannot leak into the order. This
  is the theorem that would have caught the withdrawn S-009's failure mode, one
  layer down.
* `sort_key_total` — the key is a total preorder, so a ranking always exists and
  `choose` is total (S-001, S-007).

Core-only (no Mathlib). -/

namespace Formal.ProgressionChoice

open Extracted.ProgressionChoice

/-- Lexicographic order on the key triple — the order `rank_candidates` sorts by.
Ties fall through to the caller's stable-sort positional tie-break (S-008), which
is why this is a PREORDER and not an antisymmetric order: two candidates may share
a key and neither precedes the other. -/
def keyLe (a b : Int × Int × Int) : Prop :=
  a.1 < b.1 ∨ (a.1 = b.1 ∧ (a.2.1 < b.2.1 ∨ (a.2.1 = b.2.1 ∧ a.2.2 ≤ b.2.2)))

/-- `precedes` on candidates, via their keys. -/
def precedes (x y : ProgressionCandidate) : Prop :=
  keyLe (sort_key x) (sort_key y)

/-! ### Band classification (S-012, S-014) -/

/-- A FAILED candidate is in the FAILED band, whatever its level claims. -/
theorem band_iff_failed (c : ProgressionCandidate) (h : c.failed = true) :
    candidate_band c = _BAND_FAILED := by
  unfold candidate_band; rw [h]; rfl

/-- A non-FAILED candidate below the target is UNREACHABLE — decided by the level
    field alone, with no second encoding that could disagree (S-014). -/
theorem band_iff_unreachable (c : ProgressionCandidate)
    (hf : c.failed = false) (hl : c.reachable_level < TARGET_LEVEL) :
    candidate_band c = _BAND_UNREACHABLE := by
  unfold candidate_band; rw [hf]; simp [hl]

/-- A non-FAILED candidate at or above the target is FINITE. -/
theorem band_iff_finite (c : ProgressionCandidate)
    (hf : c.failed = false) (hl : ¬ (c.reachable_level < TARGET_LEVEL)) :
    candidate_band c = _BAND_FINITE := by
  unfold candidate_band; rw [hf]; simp [hl]

/-- The band is always one of exactly three values — the order below never meets
    a fourth case, so `sort_key`'s final `else` is genuinely the FAILED band. -/
theorem band_trichotomy (c : ProgressionCandidate) :
    candidate_band c = _BAND_FINITE ∨ candidate_band c = _BAND_UNREACHABLE
      ∨ candidate_band c = _BAND_FAILED := by
  unfold candidate_band
  by_cases hf : c.failed = true
  · rw [hf]; exact Or.inr (Or.inr rfl)
  · rw [Bool.not_eq_true] at hf
    rw [hf]
    by_cases hl : c.reachable_level < TARGET_LEVEL
    · simp [hl]
    · simp [hl]

/-- The band IS the key's first component — so cross-band precedence below is
    decided before any within-band figure is read. -/
theorem sort_key_finite (c : ProgressionCandidate)
    (h : candidate_band c = _BAND_FINITE) :
    sort_key c = (_BAND_FINITE, objective_j c, 0) := by
  unfold sort_key; rw [h]; simp

theorem sort_key_unreachable (c : ProgressionCandidate)
    (h : candidate_band c = _BAND_UNREACHABLE) :
    sort_key c = (_BAND_UNREACHABLE, TARGET_LEVEL - c.reachable_level, c.acquire_cost) := by
  unfold sort_key; rw [h]; simp [_BAND_UNREACHABLE, _BAND_FINITE]

theorem sort_key_failed (c : ProgressionCandidate)
    (h : candidate_band c = _BAND_FAILED) :
    sort_key c = (_BAND_FAILED, 0, 0) := by
  unfold sort_key; rw [h]; simp [_BAND_FAILED, _BAND_FINITE, _BAND_UNREACHABLE]

/-- The band IS the key's first component — so cross-band precedence below is
    decided before any within-band figure is read. -/
theorem key_fst_is_band (c : ProgressionCandidate) :
    (sort_key c).1 = candidate_band c := by
  rcases band_trichotomy c with h | h | h
  · rw [sort_key_finite c h, h]
  · rw [sort_key_unreachable c h, h]
  · rw [sort_key_failed c h, h]

/-! ### Cross-band precedence (S-006, S-012) -/

/-- **S-006**: a candidate that can reach the objective beats one that cannot. -/
theorem finite_precedes_unreachable (x y : ProgressionCandidate)
    (hx : candidate_band x = _BAND_FINITE)
    (hy : candidate_band y = _BAND_UNREACHABLE) :
    precedes x y := by
  unfold precedes keyLe
  rw [key_fst_is_band, key_fst_is_band, hx, hy]
  exact Or.inl (by decide)

/-- **S-012**: a FAILED projection never outranks a usable candidate. A crash
    cannot masquerade as progress. -/
theorem nonfailed_precedes_failed (x y : ProgressionCandidate)
    (hx : ¬ (candidate_band x = _BAND_FAILED))
    (hy : candidate_band y = _BAND_FAILED) :
    precedes x y := by
  unfold precedes keyLe
  rw [key_fst_is_band, key_fst_is_band, hy]
  rcases band_trichotomy x with h | h | h
  · rw [h]; exact Or.inl (by decide)
  · rw [h]; exact Or.inl (by decide)
  · exact absurd h hx

/-! ### Within-band ordering -/

/-- **S-005**: inside the finite band, a strictly lower `J` strictly precedes.
    This is the whole objective in one line — gear and xp compared on one scale. -/
theorem finite_orders_by_j (x y : ProgressionCandidate)
    (hx : candidate_band x = _BAND_FINITE) (hy : candidate_band y = _BAND_FINITE)
    (hj : objective_j x < objective_j y) :
    precedes x y := by
  unfold precedes keyLe
  rw [sort_key_finite x hx, sort_key_finite y hy]
  exact Or.inr ⟨rfl, Or.inl hj⟩

/-- **S-006, first key**: inside the unreachable band, reaching a strictly higher
    level strictly precedes — whatever the costs. -/
theorem unreachable_prefers_progress (x y : ProgressionCandidate)
    (hx : candidate_band x = _BAND_UNREACHABLE)
    (hy : candidate_band y = _BAND_UNREACHABLE)
    (hl : y.reachable_level < x.reachable_level) :
    precedes x y := by
  unfold precedes keyLe
  rw [sort_key_unreachable x hx, sort_key_unreachable y hy]
  refine Or.inr ⟨rfl, Or.inl ?_⟩
  simp only []
  omega

/-- **S-006, second key**: at equal reachable level, a strictly cheaper
    acquisition strictly precedes. -/
theorem unreachable_tie_prefers_cheaper (x y : ProgressionCandidate)
    (hx : candidate_band x = _BAND_UNREACHABLE)
    (hy : candidate_band y = _BAND_UNREACHABLE)
    (hl : x.reachable_level = y.reachable_level)
    (hc : x.acquire_cost ≤ y.acquire_cost) :
    precedes x y := by
  unfold precedes keyLe
  rw [sort_key_unreachable x hx, sort_key_unreachable y hy]
  exact Or.inr ⟨rfl, Or.inr ⟨by rw [hl], hc⟩⟩

/-- **THE VOID-FIELD THEOREM (S-014)**: for an unreachable candidate the
    cycles-to-50 figure cannot influence the order at all — two candidates
    differing ONLY in that field get the identical key.

    S-014 declares that figure meaningless below the target, and this is what
    makes the declaration enforceable rather than aspirational. It is the same
    failure the withdrawn S-009 embodied one layer up: a clause that reads a field
    which carries no information in the band where it fires. -/
theorem unreachable_ignores_cycles (x y : ProgressionCandidate)
    (hx : candidate_band x = _BAND_UNREACHABLE)
    (hy : candidate_band y = _BAND_UNREACHABLE)
    (hlvl : x.reachable_level = y.reachable_level)
    (hcost : x.acquire_cost = y.acquire_cost) :
    sort_key x = sort_key y := by
  rw [sort_key_unreachable x hx, sort_key_unreachable y hy, hlvl, hcost]

/-- Likewise for FAILED: no field of a FAILED candidate reaches the order, so the
    core cannot rank one crash above another on meaningless data (S-012). -/
theorem failed_key_is_constant (x y : ProgressionCandidate)
    (hx : candidate_band x = _BAND_FAILED) (hy : candidate_band y = _BAND_FAILED) :
    sort_key x = sort_key y := by
  rw [sort_key_failed x hx, sort_key_failed y hy]

/-! ### Totality (S-001, S-007) -/

/-- **TOTALITY**: any two candidates are comparable, so a ranking always exists
    and `choose` never has to report "could not decide" on a non-empty input. -/
theorem sort_key_total (x y : ProgressionCandidate) :
    precedes x y ∨ precedes y x := by
  unfold precedes keyLe
  omega

/-- `precedes` is reflexive — needed for the sort to be well-defined on
    duplicates, which S-007 admits (the input is a sequence, not a set). -/
theorem precedes_refl (x : ProgressionCandidate) : precedes x x := by
  unfold precedes keyLe
  omega

end Formal.ProgressionChoice
