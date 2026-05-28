/-
Formal model of the pure cores extracted from
`src/artifactsmmo_cli/ai/tiers/objective_completion.py`
(`weighted_remaining_pure` and `is_complete_pure`).

These are the personality-weighted scalar of remaining work and the binary
"objective complete" predicate the strategy frontier ranks candidates by.

    weighted_remaining = Σ_i weights[i] * fractions[i]   (over the three
                                                          Tier-1 categories
                                                          char_level / skills / gear)
    is_complete        = (∀ i, fractions[i] = 0)

EXACT-RATIONAL MODEL (over `Rat`, Lean core — no mathlib). The production
fractions are floats in `[0, 1]` produced as integer-deficit / integer-target
ratios in `ObjectiveGap.gap` (`objective.py:102-106`); the personality weights
are floats returned by `Personality.category_weight` (`BalancedPersonality`
returns 1.0). Both are RATIONAL: the differential test feeds them as exact
`fractions.Fraction` values and the equivalence/monotonicity proved here holds
over all of `ℚ`. The model is generic — it does NOT hard-code arity = 3, but
mirrors the production via three-element tuples in the diff and via a list of
(weight, fraction) pairs here (the list form is what makes the bug-teeth
witness concrete and `decide`-able).

STRICT-POSITIVITY CONTRACT (the latent bug — see `personality.py` docstring):
the equivalence `weightedRemaining = 0 ↔ isComplete` holds IFF every weight is
strictly positive. With one zero weight, an INCOMPLETE objective whose only
non-zero fraction sits in the zeroed category scores 0 — wrongly indistinguishable
from complete. P1 ships only `BalancedPersonality` (all weights = 1.0 > 0),
so the bug is unreachable today. The bug-teeth theorem
`bug_teeth_witness` exhibits a concrete (weights,
fractions) pair that breaks the equivalence in the absence of positivity. A
future zero-weight personality would have to ship the contract guard (assert
or refactor); this Lean module is the proof obligation.

Lean core only — no mathlib. Rat order/identities via `Rat.mul_le_mul_of_nonneg_left`,
`Rat.add_nonneg`, `Rat.mul_nonneg`, and `grind` for the residual linear-arithmetic.
-/

namespace Formal.WeightedRemaining

/-- A pair of (weight, fraction) for a single category. -/
abbrev Term := Rat × Rat

/-- Σ_i weight_i * fraction_i. Mirrors `weighted_remaining_pure` exactly when
the term list is the three production categories `(char_level, skills, gear)`. -/
def weightedRemaining : List Term → Rat
  | [] => 0
  | (w, f) :: rest => w * f + weightedRemaining rest

/-- Every fraction is zero. Mirrors `is_complete_pure`. -/
def isComplete : List Term → Prop
  | [] => True
  | (_, f) :: rest => f = 0 ∧ isComplete rest

/-- Decidability of `isComplete` (the Python predicate is computable). -/
instance : ∀ ts : List Term, Decidable (isComplete ts)
  | [] => isTrue trivial
  | (_, f) :: rest =>
    match decEq f 0 with
    | isTrue hf =>
      match (instDecidableIsComplete rest) with
      | isTrue hr => isTrue ⟨hf, hr⟩
      | isFalse hr => isFalse (fun h => hr h.2)
    | isFalse hf => isFalse (fun h => hf h.1)

/-- Every weight in the term list is strictly positive. -/
def allWeightsPos : List Term → Prop
  | [] => True
  | (w, _) :: rest => 0 < w ∧ allWeightsPos rest

/-- Every fraction in the term list is non-negative. The production fractions
are deficit / target ratios with non-negative numerator and positive denominator
(`objective.py:102-106`), so this is a real game invariant. -/
def allFractionsNonneg : List Term → Prop
  | [] => True
  | (_, f) :: rest => 0 ≤ f ∧ allFractionsNonneg rest

/-! ### Intent theorems. -/

/-- Pins the exact recursive decomposition the Python computes (the model `=` the
Python arithmetic over the rationals). Any drift in `weighted_remaining_pure`
breaks the differential gate. -/
theorem weightedRemaining_cons (w f : Rat) (rest : List Term) :
    weightedRemaining ((w, f) :: rest) = w * f + weightedRemaining rest := rfl

theorem weightedRemaining_nil :
    weightedRemaining ([] : List Term) = 0 := rfl

/-- `isComplete` distributes over `cons`. -/
theorem isComplete_cons (w f : Rat) (rest : List Term) :
    isComplete ((w, f) :: rest) ↔ f = 0 ∧ isComplete rest := Iff.rfl

/-- `weightedRemaining` is non-negative when every weight ≥ 0 and every fraction ≥ 0
(the production invariant: deficit/target ratios are non-negative and personality
weights are non-negative). Each summand is a product of non-negatives. -/
theorem nonneg :
    ∀ (ts : List Term),
      (∀ t ∈ ts, 0 ≤ t.1) → (∀ t ∈ ts, 0 ≤ t.2) →
      0 ≤ weightedRemaining ts
  | [], _, _ => by simp [weightedRemaining]
  | (w, f) :: rest, hw, hf => by
      simp only [weightedRemaining]
      have h1 : 0 ≤ w * f :=
        Rat.mul_nonneg (hw (w, f) (by simp)) (hf (w, f) (by simp))
      have h2 : 0 ≤ weightedRemaining rest :=
        nonneg rest
          (fun t ht => hw t (by simp [ht]))
          (fun t ht => hf t (by simp [ht]))
      grind

/-- `isComplete` ⇒ `weightedRemaining = 0`. EVERY summand `w_i * 0 = 0`, no
positivity hypothesis on the weights needed — this direction of the equivalence
is unconditional. -/
theorem complete_imp_zero :
    ∀ (ts : List Term), isComplete ts → weightedRemaining ts = 0
  | [], _ => rfl
  | (w, f) :: rest, hc => by
      simp only [weightedRemaining]
      have hf : f = 0 := hc.1
      have hrest : weightedRemaining rest = 0 :=
        complete_imp_zero rest hc.2
      rw [hf, hrest]; grind

/-- THE positive-direction equivalence: under STRICT POSITIVITY of every weight
AND non-negativity of every fraction (both real production invariants — for
weights it's the contract; for fractions it's the deficit/target ratio shape),
`weightedRemaining = 0 ↔ isComplete`. The forward direction needs positivity
to convert a zero product `w*f = 0` to `f = 0` (without positivity, `w = 0`
absorbs an arbitrary `f`). -/
theorem zero_iff_complete_pos :
    ∀ (ts : List Term),
      allWeightsPos ts → allFractionsNonneg ts →
      (weightedRemaining ts = 0 ↔ isComplete ts)
  | [], _, _ => by simp [weightedRemaining, isComplete]
  | (w, f) :: rest, hpos, hnn => by
      simp only [weightedRemaining, isComplete]
      have hw : 0 < w := hpos.1
      have hf : 0 ≤ f := hnn.1
      have hrest_nn : 0 ≤ weightedRemaining rest :=
        nonneg rest
          (fun t ht => by
            -- weights non-negative on the rest (a fortiori from positivity).
            have := allWeightsPos_imp_nonneg rest hpos.2 t ht
            exact this)
          (fun t ht => allFractionsNonneg_imp rest hnn.2 t ht)
      have hw_nn : (0 : Rat) ≤ w := by grind
      have hwf_nn : 0 ≤ w * f := Rat.mul_nonneg hw_nn hf
      have ih :=
        zero_iff_complete_pos rest hpos.2 hnn.2
      constructor
      · intro hsum
        -- w*f + rest = 0 with both summands ≥ 0 ⇒ each summand = 0.
        have hwf_zero : w * f = 0 := by grind
        have hrest_zero : weightedRemaining rest = 0 := by grind
        -- w > 0 ∧ w*f = 0 ⇒ f = 0.
        have hf_zero : f = 0 := by
          rcases Rat.mul_eq_zero.mp hwf_zero with hw0 | hf0
          · exfalso; grind
          · exact hf0
        exact ⟨hf_zero, ih.mp hrest_zero⟩
      · intro hc
        have hf_zero : f = 0 := hc.1
        have hrest_zero : weightedRemaining rest = 0 := ih.mpr hc.2
        rw [hf_zero, hrest_zero]; grind
where
  /-- Strict positivity entails non-negativity, pointwise. -/
  allWeightsPos_imp_nonneg : ∀ (ts : List Term), allWeightsPos ts →
      ∀ t ∈ ts, 0 ≤ t.1
    | [], _, _, h => by simp at h
    | (w, _) :: rest, hpos, t, ht => by
        simp at ht
        rcases ht with heq | hmem
        · have h1 : (0 : Rat) < w := hpos.1
          have : t.1 = w := by grind
          grind
        · exact allWeightsPos_imp_nonneg rest hpos.2 t hmem
  /-- Pointwise extraction from `allFractionsNonneg`. -/
  allFractionsNonneg_imp : ∀ (ts : List Term), allFractionsNonneg ts →
      ∀ t ∈ ts, 0 ≤ t.2
    | [], _, _, h => by simp at h
    | (_, f) :: rest, hnn, t, ht => by
        simp at ht
        rcases ht with heq | hmem
        · subst heq; exact hnn.1
        · exact allFractionsNonneg_imp rest hnn.2 t hmem

/-- THE BUG-TEETH theorem: WITHOUT the strict-positivity hypothesis, the
equivalence FAILS. Concretely: with one zero weight, that category's nonzero
fraction is absorbed and the other categories at zero produce a zero scalar on
an INCOMPLETE objective. Witness: weights `(0, 1, 1)` with fractions
`(1/2, 0, 0)` — `weightedRemaining = 0*1/2 + 1*0 + 1*0 = 0`, yet the first
fraction is `1/2 ≠ 0`, so `isComplete` is FALSE. This is the latent defect a
future zero-weight personality would expose; the production contract
(documented in `personality.py`) requires all weights > 0. -/
theorem bug_teeth_witness :
    ∃ (ts : List Term), weightedRemaining ts = 0 ∧ ¬ isComplete ts := by
  refine ⟨[((0 : Rat), (1/2 : Rat)), ((1 : Rat), (0 : Rat)), ((1 : Rat), (0 : Rat))], ?_, ?_⟩
  · simp [weightedRemaining]; grind
  · simp [isComplete]; grind

/-- The witness's WEIGHTS are non-negative (the zero weight is the degenerate
case that breaks the equivalence; it is NOT negative). Pins that the bug-teeth
example is not exploiting an arithmetic outlier. -/
example :
    let ts : List Term :=
      [((0 : Rat), (1/2 : Rat)), ((1 : Rat), (0 : Rat)), ((1 : Rat), (0 : Rat))]
    (∀ t ∈ ts, 0 ≤ t.1) ∧ (∀ t ∈ ts, 0 ≤ t.2) := by
  refine ⟨?_, ?_⟩ <;> intro t ht <;>
    (simp only [List.mem_cons, List.not_mem_nil, or_false] at ht;
     rcases ht with rfl | rfl | rfl) <;> grind

/-- MONOTONICITY in any fraction (the third intent property): if every weight is
non-negative, increasing one fraction non-decreases the scalar. Stated for the
head term; the analogous fact for any position follows by `cons` permutation. -/
theorem mono_head (w f f' : Rat) (rest : List Term)
    (hw : 0 ≤ w) (h : f ≤ f') :
    weightedRemaining ((w, f) :: rest) ≤ weightedRemaining ((w, f') :: rest) := by
  simp only [weightedRemaining]
  have : w * f ≤ w * f' := Rat.mul_le_mul_of_nonneg_left h hw
  grind

/-! ### Non-vacuity examples (genuine witnesses over the FRACTIONAL domain). -/

/-- `BalancedPersonality` on a partially-complete objective: weights = (1,1,1),
fractions = (1/5, 1/2, 0) gives `1/5 + 1/2 + 0 = 7/10`, non-zero so the gap is
not complete. Sanity-checks the model on a real production-shaped input. -/
example :
    weightedRemaining [((1 : Rat), (1/5 : Rat)), ((1 : Rat), (1/2 : Rat)),
                       ((1 : Rat), (0 : Rat))] = 7/10 := by
  simp [weightedRemaining]; grind

/-- `BalancedPersonality` on the COMPLETE objective: all fractions zero ⇒ the
scalar is zero, and `isComplete` holds. The positive-equivalence direction is
real on the witness. -/
example :
    let ts : List Term :=
      [((1 : Rat), (0 : Rat)), ((1 : Rat), (0 : Rat)), ((1 : Rat), (0 : Rat))]
    weightedRemaining ts = 0 ∧ isComplete ts := by
  refine ⟨?_, ?_⟩
  · simp [weightedRemaining]; grind
  · simp [isComplete]

/-- The skill-first personality shape (weights = 10 on skills, 1 elsewhere) is
STRICTLY POSITIVE — no bug-teeth here. Confirms the equivalence still holds
for non-uniform but positive weights. fractions = (0, 1/2, 0) gives 5. -/
example :
    let ts : List Term :=
      [((1 : Rat), (0 : Rat)), ((10 : Rat), (1/2 : Rat)), ((1 : Rat), (0 : Rat))]
    weightedRemaining ts = 5 ∧ ¬ isComplete ts := by
  refine ⟨?_, ?_⟩
  · simp [weightedRemaining]; grind
  · simp [isComplete]; grind

end Formal.WeightedRemaining
