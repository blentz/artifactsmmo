-- @concept: bank @property: dominance, monotonicity, totality, safety
/-
Formal model of the pure bank-expansion firing decision extracted from
`src/artifactsmmo_cli/ai/bank_expansion_timing.py` (`should_expand_bank`).

ExpandBankGoal fires (buys a bank expansion) only when the bank is at or above a
rational fill threshold AND buying keeps gold at or above the reserve:

    fire  iff  (used*trigger_den ≥ capacity*trigger_num)  ∧  (gold - cost ≥ reserve)

The fill gate is an EXACT integer cross-multiply (the Python core computes
`used * trigger_den >= capacity * trigger_num`, never a float), so the proof is
about the real rational fill ratio, not a float surrogate. The reserve gate is the
SAFETY-HOLE fix: the pre-fix goal fired on bare `gold ≥ cost`, ignoring the reserve
and draining gold below it. We mirror the decision exactly over `Int` (the Python
`gold - cost` can go negative, so the model ranges over all integers; the `and` of
two decidable `≥` is `Decidable`).

Concrete TRUE-witness (non-vacuity anchor): used=96, capacity=100, gold=600,
cost=50, reserve=500, trigger=95/100 → both gates hold (96*100=9600 ≥ 100*95=9500,
600-50=550 ≥ 500), so the decision is `true`. See `expand_true_witness` below.

Lean core only — no mathlib. The decidable `≥` on `Int` and `omega`/`decide`
/`split`/`simp only [shouldExpandBank]` close every goal; the same core-only
convention as `Formal/CraftVsBuy.lean`.
-/

namespace Formal.BankExpansionTiming

/-- True iff the bank is at/above the rational fill threshold (exact integer
cross-multiply) AND buying keeps gold at/above the reserve. Mirrors the Python
`should_expand_bank`. -/
def shouldExpandBank (used capacity gold cost reserve triggerNum triggerDen : Int) : Bool :=
  decide (used * triggerDen ≥ capacity * triggerNum) && decide (gold - cost ≥ reserve)

/-- TOTALITY: the decision is always either `true` or `false` (no third outcome,
no stuck state). Trivial for `Bool`, stated for parity with the role matrix. -/
theorem expand_total (u c g k r tn td : Int) :
    shouldExpandBank u c g k r tn td = true ∨ shouldExpandBank u c g k r tn td = false := by
  cases shouldExpandBank u c g k r tn td
  · exact Or.inr rfl
  · exact Or.inl rfl

/-- DOMINANCE: the decision is `true` EXACTLY at the at-threshold-and-reserve-safe
condition (the precise firing condition — no over- or under-firing). -/
theorem expand_iff (u c g k r tn td : Int) :
    shouldExpandBank u c g k r tn td = true ↔
      (u * td ≥ c * tn ∧ g - k ≥ r) := by
  unfold shouldExpandBank
  simp only [Bool.and_eq_true, decide_eq_true_eq]

/-- SAFETY: whenever the expansion fires, the post-buy gold stays at or above the
reserve (`gold - cost ≥ reserve`) — buying never breaches the gold floor. This is
the SAFETY-HOLE the fix closes. -/
theorem expand_preserves_reserve (u c g k r tn td : Int)
    (h : shouldExpandBank u c g k r tn td = true) : g - k ≥ r := by
  rw [expand_iff] at h
  exact h.2

/-- Dominance corollary: an unaffordable buy (would drop gold below the reserve)
never fires. -/
theorem no_expand_when_unaffordable (u c g k r tn td : Int) (h : ¬ (g - k ≥ r)) :
    shouldExpandBank u c g k r tn td = false := by
  unfold shouldExpandBank
  simp only [Bool.and_eq_false_iff, decide_eq_false_iff_not]
  exact Or.inr h

/-- Dominance corollary: a bank below the fill threshold never fires. -/
theorem no_expand_when_below_threshold (u c g k r tn td : Int) (h : ¬ (u * td ≥ c * tn)) :
    shouldExpandBank u c g k r tn td = false := by
  unfold shouldExpandBank
  simp only [Bool.and_eq_false_iff, decide_eq_false_iff_not]
  exact Or.inl h

/-- MONOTONICITY in gold: if the expansion fires, raising the available gold keeps
it firing (more gold never flips an affordable purchase back to no-buy). -/
theorem expand_stable_under_more_gold (u c g g' k r tn td : Int)
    (hfire : shouldExpandBank u c g k r tn td = true) (hge : g ≤ g') :
    shouldExpandBank u c g' k r tn td = true := by
  rw [expand_iff] at hfire ⊢
  exact ⟨hfire.1, by omega⟩

/-- MONOTONICITY in fill: with a non-negative denominator, raising the used count
keeps the expansion firing (a fuller bank is at least as eligible). The
`0 ≤ triggerDen` precondition is supplied by the production trigger 95/100. -/
theorem expand_stable_under_more_fill (u u' c g k r tn td : Int)
    (htd : 0 ≤ td)
    (hfire : shouldExpandBank u c g k r tn td = true) (hge : u ≤ u') :
    shouldExpandBank u' c g k r tn td = true := by
  rw [expand_iff] at hfire ⊢
  refine ⟨?_, hfire.2⟩
  have hmul : u * td ≤ u' * td := Int.mul_le_mul_of_nonneg_right hge htd
  exact Int.le_trans hfire.1 hmul

/-- Concrete TRUE-witness (non-vacuity): the documented production-shaped instance
fires. used=96, capacity=100, gold=600, cost=50, reserve=500, trigger=95/100. -/
theorem expand_true_witness :
    shouldExpandBank 96 100 600 50 500 95 100 = true := by decide

end Formal.BankExpansionTiming
