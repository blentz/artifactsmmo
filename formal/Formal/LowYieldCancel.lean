-- @concept: tasks @property: safety, monotonicity
/-
Formal model of the pure decision boundary extracted from
`src/artifactsmmo_cli/ai/learning/projections.py::low_yield_cancel_fires` into
`src/artifactsmmo_cli/ai/learning/low_yield_boundary.py::low_yield_fires_pure`.

PYTHON DECISION (`low_yield_fires_pure`):

  if not has_task:                            return False
  if farm_samples <= 0 or alt_samples <= 0:   return False
  if current_xp == 0 and alt_xp > 0:          return True     -- zero fast-path
  if confidence < min_confidence:             return False    -- margin gate
  return alt_xp >= current_xp * margin

EXACT-RATIONAL MODEL (`Rat`, Lean core — no mathlib). The Python `current_xp`,
`alt_xp` are `float` quotients (`reward_sum / sample_count`) and `confidence`
is `SkillXpCurve.confidence`, a rational fraction in `[0, 1]`. We model the
boundary over `Rat` so every operation is exact on fractional inputs; the
differential test feeds `fractions.Fraction` inputs to the Python pure core
and compares bit-exactly to this Rat oracle.

ZERO-FAST-PATH DISCLOSURE (intentional, not a defect):

  The fast-path `current_xp == 0 ∧ alt_xp > 0` BYPASSES the confidence gate.
  This is the documented design (`projections.py:380`, and the
  `TestGHCharXpFastCancel` test in `tests/test_ai/test_low_yield_cancel.py`
  which explicitly asserts: "Should fire immediately — no need to wait for
  confidence threshold"). The rationale is the Robby 347-fish gudgeon
  scenario: FarmItems char-XP averages exactly zero (XP only at
  CompleteTask), so any monster grind paying positive char-XP strictly
  dominates regardless of how few samples we have on the alternative. Zero is
  unimprovable; a single positive observation is enough information.

  We expose this asymmetry explicitly via
  `zero_fast_path_fires_with_low_confidence_witness`: a concrete state where
  `confidence < min_confidence` AND `alt_samples = 1` AND the rule fires.
  This is the contract, NOT a soundness defect.

PRODUCTION CONSTANTS: `LOW_YIELD_CONFIDENCE_THRESHOLD = 1/2`,
`LOW_YIELD_ALTERNATIVE_MARGIN = 3/2`.

Lean core only — no mathlib. Rat order via `Rat.mul_le_mul_of_nonneg_left`
and `grind` (core) for residual linear arithmetic; `decide` for Bool/Nat
boundaries.
-/

namespace Formal.LowYieldCancel

/-- The pure decision boundary. Mirrors `low_yield_fires_pure` component-for-component.

`hasTask`, `farmSamples`, `altSamples` are the shell-supplied gates;
`currentXp`, `altXp`, `confidence`, `margin`, `minConfidence` are the rational
arithmetic inputs. Returns `Bool` to match Python. -/
def lowYieldFiresPure (hasTask : Bool)
    (currentXp altXp confidence : Rat)
    (farmSamples altSamples : Nat)
    (margin minConfidence : Rat) : Bool :=
  if ¬ hasTask then false
  else if farmSamples = 0 ∨ altSamples = 0 then false
  else if currentXp = 0 ∧ altXp > 0 then true
  else if confidence < minConfidence then false
  else if altXp ≥ currentXp * margin then true else false

/-! ### Intent theorems. -/

/-- (a) No task held ⇒ never fires (unconditional). The shell's first guard. -/
theorem no_task_never_fires
    (currentXp altXp confidence margin minConfidence : Rat)
    (farmSamples altSamples : Nat) :
    lowYieldFiresPure false currentXp altXp confidence
        farmSamples altSamples margin minConfidence = false := by
  unfold lowYieldFiresPure
  simp

/-- Non-vacuity witness for `no_task_never_fires`: even when every other gate
trivially fires, `hasTask = false` blocks. -/
example :
    lowYieldFiresPure false 0 1000 1 10 10 (3/2) (1/2) = false :=
  no_task_never_fires (0 : Rat) (1000 : Rat) (1 : Rat) (3/2 : Rat) (1/2 : Rat) 10 10

/-- (b) No FarmItems samples ⇒ never fires. -/
theorem no_farm_samples_never_fires
    (currentXp altXp confidence margin minConfidence : Rat)
    (altSamples : Nat) :
    lowYieldFiresPure true currentXp altXp confidence
        0 altSamples margin minConfidence = false := by
  unfold lowYieldFiresPure
  simp

/-- (b′) No alt samples ⇒ never fires (symmetric). -/
theorem no_alt_samples_never_fires
    (currentXp altXp confidence margin minConfidence : Rat)
    (farmSamples : Nat) :
    lowYieldFiresPure true currentXp altXp confidence
        farmSamples 0 margin minConfidence = false := by
  unfold lowYieldFiresPure
  -- After `hasTask = true` and the sample-guard, second disjunct fires.
  by_cases hF : farmSamples = 0
  · simp [hF]
  · simp [hF]

/-- (b″) Combined: any sample side at zero blocks. -/
theorem no_samples_blocks
    (currentXp altXp confidence margin minConfidence : Rat)
    (farmSamples altSamples : Nat)
    (h : farmSamples = 0 ∨ altSamples = 0) :
    lowYieldFiresPure true currentXp altXp confidence
        farmSamples altSamples margin minConfidence = false := by
  rcases h with hF | hA
  · subst hF; exact no_farm_samples_never_fires currentXp altXp confidence margin minConfidence altSamples
  · subst hA; exact no_alt_samples_never_fires currentXp altXp confidence margin minConfidence farmSamples

/-- Non-vacuity for the sample gate: 0 alt samples blocks despite an
otherwise-firing zero-fast-path. -/
example :
    lowYieldFiresPure true 0 1000 1 5 0 (3/2) (1/2) = false :=
  no_alt_samples_never_fires (0 : Rat) (1000 : Rat) (1 : Rat) (3/2 : Rat) (1/2 : Rat) 5

/-- (c) Margin monotonicity in `altXp` (under all gates satisfied, positive
`currentXp`, confidence above threshold). Raising the alternative's char-XP
can only PRESERVE a fire — once fired, stays fired. -/
theorem fires_monotone_in_alt
    (currentXp alt alt' confidence margin minConfidence : Rat)
    (farmSamples altSamples : Nat)
    (hF : farmSamples ≠ 0) (hA : altSamples ≠ 0)
    (hCur : currentXp > 0)
    (hConf : confidence ≥ minConfidence)
    (hAA : alt ≤ alt')
    (h : lowYieldFiresPure true currentXp alt confidence
            farmSamples altSamples margin minConfidence = true) :
    lowYieldFiresPure true currentXp alt' confidence
        farmSamples altSamples margin minConfidence = true := by
  unfold lowYieldFiresPure at h ⊢
  have hFz : ¬ (farmSamples = 0 ∨ altSamples = 0) := by
    intro hor; rcases hor with hh | hh
    · exact hF hh
    · exact hA hh
  -- currentXp > 0 ⇒ currentXp ≠ 0, so the zero-fast-path doesn't trigger.
  have hcurne_zero : currentXp ≠ 0 := by
    intro hz; rw [hz] at hCur; exact absurd hCur (by grind)
  have hcurne : ¬ (currentXp = 0 ∧ alt > 0) := by
    intro ⟨hc, _⟩; exact hcurne_zero hc
  have hcurne' : ¬ (currentXp = 0 ∧ alt' > 0) := by
    intro ⟨hc, _⟩; exact hcurne_zero hc
  have hConf' : ¬ confidence < minConfidence := by grind
  simp [hFz, hcurne, hcurne', hConf'] at h ⊢
  -- h : (if alt ≥ currentXp * margin then true else false) = true.
  -- Extract the underlying ≥ from `h`.
  have hge : alt ≥ currentXp * margin := by
    by_cases hk : alt ≥ currentXp * margin
    · exact hk
    · simp [hk] at h
  have hge' : alt' ≥ currentXp * margin := Rat.le_trans hge hAA
  simp [hge']

/-- Non-vacuity for margin monotonicity: a concrete firing state. Threshold
`2 * 3/2 = 3`; alt = 6 ≥ 3. -/
example :
    lowYieldFiresPure true 2 6 1 5 5 (3/2) (1/2) = true := by
  unfold lowYieldFiresPure
  simp
  -- After simp the residual is `¬ 1 < 1/2 ∧ 2 * (3/2) ≤ 6`.
  refine ⟨?_, ?_⟩ <;> grind

/-- (d) ZERO-FAST-PATH SEMANTICS — DISCLOSURE THEOREM.

When `currentXp = 0` AND `altXp > 0`, the rule fires REGARDLESS of confidence
or sample counts (beyond the > 0 floor). The confidence gate is BYPASSED.
This is the documented production design. -/
theorem zero_fast_path_fires_unconditionally
    (altXp confidence margin minConfidence : Rat)
    (farmSamples altSamples : Nat)
    (hF : farmSamples ≠ 0) (hA : altSamples ≠ 0)
    (hAlt : altXp > 0) :
    lowYieldFiresPure true 0 altXp confidence
        farmSamples altSamples margin minConfidence = true := by
  unfold lowYieldFiresPure
  have hFz : ¬ (farmSamples = 0 ∨ altSamples = 0) := by
    intro hor; rcases hor with hh | hh
    · exact hF hh
    · exact hA hh
  simp [hFz, hAlt]

/-- (d′) CONCRETE WITNESS: the fast-path fires with confidence FAR BELOW the
0.5 threshold and only ONE alternative sample. Pins the bypass as intentional. -/
theorem zero_fast_path_fires_with_low_confidence_witness :
    lowYieldFiresPure true 0 1 0 1 1 (3/2) (1/2) = true := by
  unfold lowYieldFiresPure
  simp
  -- After simp the residual is `0 < 1 ∨ ...` — the zero-fast-path side suffices.
  left; grind

/-- (d″) AND the complement: with `currentXp = 0`, `altXp = 0`, the fast-path
does NOT fire (it requires `altXp > 0`). Pins the asymmetric boundary. -/
theorem zero_fast_path_blocked_when_alt_zero_and_low_confidence :
    lowYieldFiresPure true 0 0 0 5 5 (3/2) (1/2) = false := by
  unfold lowYieldFiresPure
  simp
  -- After simp residual is `0 < 1/2`.
  grind

/-- (e) MARGIN-GATE SOUNDNESS under positive `currentXp`. If the rule fires
under positive `currentXp`, then `altXp ≥ currentXp * margin`. The 1.5
production margin is sound: a fire implies the alternative is at least 1.5×
the current rate. -/
theorem positive_current_fires_implies_margin
    (currentXp altXp confidence margin minConfidence : Rat)
    (farmSamples altSamples : Nat)
    (hCur : currentXp > 0)
    (h : lowYieldFiresPure true currentXp altXp confidence
            farmSamples altSamples margin minConfidence = true) :
    altXp ≥ currentXp * margin := by
  unfold lowYieldFiresPure at h
  have hcurne_zero : currentXp ≠ 0 := by
    intro hz; rw [hz] at hCur; exact absurd hCur (by grind)
  by_cases hFz : farmSamples = 0 ∨ altSamples = 0
  · simp [hFz] at h
  · simp [hFz] at h
    have hcurne : ¬ (currentXp = 0 ∧ altXp > 0) := by
      intro ⟨hc, _⟩; exact hcurne_zero hc
    simp [hcurne] at h
    by_cases hConf : confidence < minConfidence
    · simp [hConf] at h
    · simp [hConf] at h
      by_cases hk : altXp ≥ currentXp * margin
      · exact hk
      · simp [hk] at h

/-- Non-vacuity for the margin soundness theorem: a fire at the exact 1.5
margin boundary really gives `alt ≥ current * 1.5`. -/
example : (3 : Rat) ≥ 2 * (3/2) := by grind

/-- (f) CONFIDENCE-GATE SOUNDNESS under positive `currentXp`. If the rule
fires AND `currentXp > 0`, then `confidence ≥ minConfidence`. The zero-fast-
path is the only exception. -/
theorem positive_current_fires_implies_confidence
    (currentXp altXp confidence margin minConfidence : Rat)
    (farmSamples altSamples : Nat)
    (hCur : currentXp > 0)
    (h : lowYieldFiresPure true currentXp altXp confidence
            farmSamples altSamples margin minConfidence = true) :
    confidence ≥ minConfidence := by
  unfold lowYieldFiresPure at h
  have hcurne_zero : currentXp ≠ 0 := by
    intro hz; rw [hz] at hCur; exact absurd hCur (by grind)
  by_cases hFz : farmSamples = 0 ∨ altSamples = 0
  · simp [hFz] at h
  · simp [hFz] at h
    have hcurne : ¬ (currentXp = 0 ∧ altXp > 0) := by
      intro ⟨hc, _⟩; exact hcurne_zero hc
    simp [hcurne] at h
    by_cases hConf : confidence < minConfidence
    · simp [hConf] at h
    · -- ¬ (confidence < minConfidence) over ℚ ⇒ confidence ≥ minConfidence.
      have : minConfidence ≤ confidence := by grind
      exact this

end Formal.LowYieldCancel
