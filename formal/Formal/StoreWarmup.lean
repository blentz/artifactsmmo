/-
Phase-7 Target F: pin the warm-up gates of `LearningStore`. The store's
median and success-rate aggregates both gate on `len(rows) >= 5` before
computing a value, returning a documented default below the gate. The pure
helpers `warmup_gated_median` and `warmup_gated_success_rate` were extracted
to `store_warmup_core.py`; this module models them and proves the gate
contracts.

The default below the gate is:
* `warmup_gated_median` → `None` (no estimate),
* `warmup_gated_success_rate` → `1.0` (treat unknown action as fully ok).

Above the gate the Python uses `statistics.median` (the lower-middle on even
counts) and the OK-fraction. Both are pinned at the gate boundary as cheap
regression-locks; the actual aggregate-correctness is left to the SQL test
suite (the gate is the load-bearing part of the contract).
-/

namespace Formal.StoreWarmup

/-- Production warm-up window. -/
def warmupMinSamples : Nat := 5

/-- `warmup_gated_median`: returns `none` when `samples.length < 5`, else
returns some median value. We don't model the median formula itself (the
SQL/statistics layer owns it) — we DO pin the gate. -/
def warmupGatedMedian (samples : List Int) (median : Int) : Option Int :=
  if samples.length < warmupMinSamples then none else some median

/-- The gate is exact: below the window the result is `none`. -/
theorem warmupGatedMedian_below_gate (samples : List Int) (median : Int)
    (h : samples.length < warmupMinSamples) :
    warmupGatedMedian samples median = none := by
  unfold warmupGatedMedian; simp [h]

/-- At-or-above the gate, the result is `some median`. -/
theorem warmupGatedMedian_at_or_above_gate (samples : List Int) (median : Int)
    (h : warmupMinSamples ≤ samples.length) :
    warmupGatedMedian samples median = some median := by
  unfold warmupGatedMedian
  have : ¬ samples.length < warmupMinSamples := by omega
  simp [this]

/-- Exactly at the boundary: 5 samples are accepted. -/
theorem warmupGatedMedian_boundary_witness :
    warmupGatedMedian [1, 2, 3, 4, 5] 3 = some 3 := by decide

/-- One below the boundary: 4 samples are refused. -/
theorem warmupGatedMedian_off_boundary_refused :
    warmupGatedMedian [1, 2, 3, 4] 3 = none := by decide

/-- Empty sample list refused (the strictest gate case). -/
theorem warmupGatedMedian_empty_refused (median : Int) :
    warmupGatedMedian [] median = none := by
  unfold warmupGatedMedian; simp [warmupMinSamples]

/-- `warmup_gated_success_rate`: returns `1.0` when below the gate, else
returns `ok_count / total`. We model with `Int` numerators/denominators
(matching `Rat` from the rest of the formal layer). -/
def warmupGatedSuccessRate (okCount total : Nat) : Rat :=
  if total < warmupMinSamples then 1 else (okCount : Rat) / (total : Rat)

/-- Below the gate ⇒ return 1 (the warm-up default). -/
theorem warmupGatedSuccessRate_below_gate (okCount total : Nat)
    (h : total < warmupMinSamples) :
    warmupGatedSuccessRate okCount total = 1 := by
  unfold warmupGatedSuccessRate; simp [h]

/-- At-or-above the gate ⇒ return `okCount / total`. -/
theorem warmupGatedSuccessRate_at_or_above_gate (okCount total : Nat)
    (h : warmupMinSamples ≤ total) :
    warmupGatedSuccessRate okCount total = (okCount : Rat) / (total : Rat) := by
  unfold warmupGatedSuccessRate
  have : ¬ total < warmupMinSamples := by omega
  simp [this]

/-- Result is always non-negative (the warm-up default is 1, every active
fraction is non-negative). -/
theorem warmupGatedSuccessRate_nonneg (okCount total : Nat) :
    0 ≤ warmupGatedSuccessRate okCount total := by
  unfold warmupGatedSuccessRate
  by_cases h : total < warmupMinSamples
  · simp [h]; decide
  · simp [h]
    rw [Rat.div_def]
    apply Rat.mul_nonneg
    · exact_mod_cast Nat.zero_le _
    · by_cases ht : total = 0
      · simp [ht]
      · apply Rat.le_of_lt
        apply Rat.inv_pos.mpr
        have : 0 < total := Nat.pos_of_ne_zero ht
        exact_mod_cast this

/-- Boundary witness: 5 samples, all ok ⇒ rate = (5 : Rat) / (5 : Rat). -/
theorem warmupGatedSuccessRate_boundary_all_ok :
    warmupGatedSuccessRate 5 5 = ((5 : Nat) : Rat) / ((5 : Nat) : Rat) := by
  unfold warmupGatedSuccessRate warmupMinSamples
  simp

/-- Boundary witness: 5 samples, none ok ⇒ rate = (0 : Rat) / (5 : Rat). -/
theorem warmupGatedSuccessRate_boundary_none_ok :
    warmupGatedSuccessRate 0 5 = ((0 : Nat) : Rat) / ((5 : Nat) : Rat) := by
  unfold warmupGatedSuccessRate warmupMinSamples
  simp

/-- One below the boundary: 4 samples ⇒ default 1. -/
theorem warmupGatedSuccessRate_off_boundary_default :
    warmupGatedSuccessRate 0 4 = 1 := by decide

/-- Empty samples ⇒ default 1 (strictest gate case). -/
theorem warmupGatedSuccessRate_empty_default :
    warmupGatedSuccessRate 0 0 = 1 := by decide

end Formal.StoreWarmup
