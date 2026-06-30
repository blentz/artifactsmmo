namespace Formal.MaxBatchFromHeld

/-- Fold the per-ingredient run-counts into their running minimum.
`acc` is seeded with the first ingredient's `held / need`, then every ingredient
(including the first, idempotently) drives `acc` down to `Nat.min acc (held / need)`.
The `need == 0` guard is defensive: real recipes have `need ≥ 1`, and the
differential samples `need ≥ 1`, so it never fires there. Mirrors the Python
`min(held[i] // needs[i] for i in range(len(needs)))`. -/
def runsFold : List (Nat × Nat) → Nat → Nat
  | [], acc => acc
  | (need, have_) :: rest, acc =>
      let r := if need == 0 then 0 else have_ / need
      runsFold rest (Nat.min acc r)

/-- Max crafts now: the min over ingredients of `held / need`, times the yield.
0 on the empty recipe, mirroring the Python `max_batch_from_held_pure`. -/
def maxBatchFromHeld (pairs : List (Nat × Nat)) (yieldPerCraft : Nat) : Nat :=
  match pairs with
  | [] => 0
  | (n0, h0) :: _ => (runsFold pairs (h0 / (if n0 == 0 then 1 else n0))) * yieldPerCraft

/-- Empty recipe ⇒ no batch, regardless of yield. -/
theorem batch_zero_on_empty (y : Nat) : maxBatchFromHeld [] y = 0 := by rfl

/-- The fold never raises the accumulator: it only takes minima. -/
theorem runsFold_le_acc (pairs : List (Nat × Nat)) (acc : Nat) :
    runsFold pairs acc ≤ acc := by
  induction pairs generalizing acc with
  | nil => exact Nat.le_refl acc
  | cons p rest ih =>
      obtain ⟨need, have_⟩ := p
      simp only [runsFold]
      exact Nat.le_trans (ih _) (Nat.min_le_left _ _)

/-- The batch is bounded by the first ingredient's run-count times the yield:
no recipe yields more potions than its scarcest-so-far ingredient permits. -/
theorem batch_le_first_bound (n0 h0 : Nat) (rest : List (Nat × Nat)) (y : Nat) :
    maxBatchFromHeld ((n0, h0) :: rest) y
      ≤ (h0 / (if n0 == 0 then 1 else n0)) * y := by
  simp only [maxBatchFromHeld]
  exact Nat.mul_le_mul_right _ (runsFold_le_acc _ _)

end Formal.MaxBatchFromHeld
