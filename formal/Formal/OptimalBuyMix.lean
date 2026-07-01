-- @concept: potion-supply-economics @property: validity, safety
/-
Formal model of the pure largest-affordable-batch core extracted from
`src/artifactsmmo_cli/ai/optimal_buy_mix.py` (`optimal_buy_mix_pure`).

To craft `batch` runs of a recipe the bot must BUY, for each ingredient, the
shortfall between what the batch needs (`batch * need`) and what it already holds
(`held`), i.e. `max(0, batch*need - held)` units at that ingredient's price. The
total buy-cost is

    cost(batch) = Σ_i price_i · max(0, batch·need_i − held_i).

`optimalBuyMix` returns the largest `batch ≤ maxBatch` whose cost is affordable
(`≤ gold`), or 0 if even one run is unaffordable. The key fact making the Python
linear scan (which `break`s on the first unaffordable batch) correct is that
`cost` is MONOTONE NON-DECREASING in `batch` (`cost_mono`): a bigger batch never
costs less, so the affordable batches form a down-closed prefix and the largest
affordable batch equals the largest prefix-affordable batch. That monotonicity is
proven here and is exactly what justifies retiring the "drop the break" mutant in
`formal/diff/mutate.py` as a behaviour-preserving optimisation.

In Nat, truncated subtraction `b*n - h` IS `max(0, b*n - h)`, so the model is a
faithful float-free mirror. It is locked to the Python bit-for-bit by
`formal/diff/test_optimal_buy_mix_diff.py` through the `optimal_buy_mix` oracle
kind.
-/

namespace Formal.OptimalBuyMix

/-- Buy-cost of crafting `batch` runs: for each ingredient (parallel
`needs`/`held`/`prices` lists) buy the deficit `batch*need - held` — Nat truncated
subtraction, i.e. `max(0, …)` — at its price, and sum. Mismatched-length tails
contribute 0 (defensive; the differential always passes equal-length triples). -/
def cost : List Nat → List Nat → List Nat → Nat → Nat
  | n :: ns, h :: hs, p :: ps, b => p * (b * n - h) + cost ns hs ps b
  | [], _, _, _ => 0
  | _ :: _, [], _, _ => 0
  | _ :: _, _ :: _, [], _ => 0

/-- Cost of zero runs is zero: every deficit `0*n - h = 0`. -/
theorem cost_zero : ∀ (ns hs ps : List Nat), cost ns hs ps 0 = 0
  | n :: ns, h :: hs, p :: ps => by
      simp only [cost, Nat.zero_mul, Nat.zero_sub, Nat.mul_zero, cost_zero ns hs ps,
                 Nat.add_zero]
  | [], _, _ => by simp only [cost]
  | _ :: _, [], _ => by simp only [cost]
  | _ :: _, _ :: _, [] => by simp only [cost]

/-- `cost` is monotone non-decreasing in `batch`: a larger batch buys at least as
much of every ingredient, so it never costs less. This is the correctness witness
for the Python `break` (affordable batches are a down-closed prefix). -/
theorem cost_mono : ∀ (ns hs ps : List Nat) (b : Nat),
    cost ns hs ps b ≤ cost ns hs ps (b + 1)
  | n :: ns, h :: hs, p :: ps, b => by
      have ih := cost_mono ns hs ps b
      have hmul : b * n ≤ (b + 1) * n := Nat.mul_le_mul (Nat.le_succ b) (Nat.le_refl n)
      have hsub : b * n - h ≤ (b + 1) * n - h := Nat.sub_le_sub_right hmul h
      simp only [cost]
      exact Nat.add_le_add (Nat.mul_le_mul (Nat.le_refl p) hsub) ih
  | [], _, _, _ => by simp only [cost]; exact Nat.le_refl _
  | _ :: _, [], _, _ => by simp only [cost]; exact Nat.le_refl _
  | _ :: _, _ :: _, [], _ => by simp only [cost]; exact Nat.le_refl _

/-- Scan candidate batches downward from `fuel`, returning the largest `b` with
`1 ≤ b ≤ fuel` and `cost ≤ gold`; 0 if none is affordable. -/
def scanDown (ns hs ps : List Nat) (gold : Nat) : Nat → Nat
  | 0 => 0
  | b + 1 => if cost ns hs ps (b + 1) ≤ gold then b + 1
             else scanDown ns hs ps gold b

/-- Largest affordable batch `≤ maxBatch` (0 if even one run is unaffordable). -/
def optimalBuyMix (ns hs ps : List Nat) (gold maxBatch : Nat) : Nat :=
  scanDown ns hs ps gold maxBatch

/-- The returned batch is affordable: its cost is within budget. (At the 0
fall-through, `cost … 0 = 0 ≤ gold`.) -/
theorem result_feasible (ns hs ps : List Nat) (gold maxBatch : Nat) :
    cost ns hs ps (optimalBuyMix ns hs ps gold maxBatch) ≤ gold := by
  unfold optimalBuyMix
  induction maxBatch with
  | zero => simp only [scanDown]; rw [cost_zero]; exact Nat.zero_le _
  | succ b ih =>
      simp only [scanDown]
      split
      · rename_i hfit; exact hfit
      · exact ih

/-- One-past the result is unaffordable whenever the result was capped below
`maxBatch`: if `optimalBuyMix < maxBatch` then `cost (result + 1) > gold`. Together
with `result_feasible` and `cost_mono` this pins the result as THE largest
affordable batch. -/
theorem succ_infeasible (ns hs ps : List Nat) (gold maxBatch : Nat)
    (hlt : optimalBuyMix ns hs ps gold maxBatch < maxBatch) :
    gold < cost ns hs ps (optimalBuyMix ns hs ps gold maxBatch + 1) := by
  unfold optimalBuyMix at hlt ⊢
  revert hlt
  induction maxBatch with
  | zero => intro hlt; exact absurd hlt (Nat.not_lt_zero _)
  | succ b ih =>
      intro hlt
      by_cases hfit : cost ns hs ps (b + 1) ≤ gold
      · -- scanDown … (b+1) = b+1, so hlt : b+1 < b+1, contradiction
        simp only [scanDown, if_pos hfit] at hlt
        exact absurd hlt (Nat.lt_irrefl _)
      · -- scanDown … (b+1) = scanDown … b
        simp only [scanDown, if_neg hfit] at hlt ⊢
        have hgt : gold < cost ns hs ps (b + 1) := Nat.lt_of_not_le hfit
        have hle : scanDown ns hs ps gold b ≤ b := Nat.lt_succ_iff.mp hlt
        rcases Nat.lt_or_ge (scanDown ns hs ps gold b) b with hlt2 | hge2
        · exact ih hlt2
        · have heq : scanDown ns hs ps gold b = b := Nat.le_antisymm hle hge2
          rw [heq]; exact hgt

end Formal.OptimalBuyMix
