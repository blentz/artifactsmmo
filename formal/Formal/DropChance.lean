-- @concept: monsters, resources, cost @property: boundedness, monotonicity, validity
/-
The chance a drop lands, learned from observed drops (spec 2026-10-18 §2.8,
`src/artifactsmmo_cli/ai/drop_chance_core.py`).

    posterior = (1 + hits) / (apiRate + attempts)
    multiplier = max(1, 1 + k·P)
    chance = min(1, posterior × multiplier)
    units = chance × (minQ + maxQ) / 2
    k = max(0, Σ P·(hits·apiRate − attempts) / Σ attempts·P²)

## The model

A rational is an unreduced `(numerator, denominator)` pair of integers compared
by cross-multiplication (`qle`), so the model never divides; every denominator
it builds is positive under the theorems' hypotheses. `k` and `P` are integers
or rationals of either sign, as the Python takes them.

`fitK` is the Python's `fit_k` with the attempts cancelled: a sample's weighted
residual `w·P·(r − 1)` with `w = attempts` and `r = (hits / attempts)·apiRate`
is `P·(hits·apiRate − attempts)`, and its weighted square is `attempts·P²`. A
sample without attempts adds 0 to both (it has `hits ≤ attempts = 0`), which is
the Python dropping it. With no sample at a positive prospecting and positive
attempts the fit is 0.

## Theorems

* `posterior_in_unit` — the posterior is in (0, 1];
* `posterior_converges_hits` — more hits at fixed attempts never lower it;
* `multiplier_monotone` — the multiplier is monotone in P for k ≥ 0;
* `multiplier_ge_one` — the multiplier never lowers a chance;
* `chance_le_one` — the chance never exceeds 1;
* `units_le_mean` — one attempt yields at most the drop's mean quantity
  (`units = chance × (minQ + maxQ)/2`, `drop_chance_core.units_per_attempt`);
* `fitK_nonneg` — the fitted k is a rational ≥ 0 (positive denominator).
-/

namespace Formal.DropChance

/-- A rational, `(numerator, denominator)`, unreduced. -/
abbrev Q := Int × Int

/-- `a ≤ b`, cross-multiplied (sound for positive denominators). -/
def qle (a b : Q) : Prop := a.1 * b.2 ≤ b.1 * a.2

instance (a b : Q) : Decidable (qle a b) := inferInstanceAs (Decidable (_ ≤ _))

/-- The larger of two rationals, the second on a tie. -/
def qmax (a b : Q) : Q := if qle a b then b else a

/-- The smaller of two rationals, the first on a tie. -/
def qmin (a b : Q) : Q := if qle a b then a else b

def qmul (a b : Q) : Q := (a.1 * b.1, a.2 * b.2)

def one : Q := (1, 1)

/-- The Beta posterior mean: one hit in `apiRate` attempts, then the
observations. -/
def posterior (apiRate attempts hits : Nat) : Q :=
  (1 + (hits : Int), (apiRate : Int) + attempts)

/-- `max(1, 1 + k·P)`. -/
def multiplier (k : Q) (p : Int) : Q := qmax one (k.2 + k.1 * p, k.2)

/-- `min(1, posterior × multiplier)`. -/
def chance (apiRate attempts hits : Nat) (k : Q) (p : Int) : Q :=
  qmin one (qmul (posterior apiRate attempts hits) (multiplier k p))

/-- The expected units one attempt yields: `chance × (minQ + maxQ) / 2`
(`drop_chance_core.units_per_attempt`, ruling T16a). The ONE drop model every
consumer reads; its reciprocal is the expected attempts per unit the source
selectors rank by (`Formal.GatherSelection.attemptsPerUnit`). -/
def units (apiRate attempts hits : Nat) (k : Q) (p : Int) (minQ maxQ : Nat) : Q :=
  qmul (chance apiRate attempts hits k p) ((minQ : Int) + maxQ, 2)

/-- A fit sample: `(apiRate, prospecting, attempts, hits)`. -/
abbrev Sample := Nat × Int × Nat × Nat

/-- `Σ P·(hits·apiRate − attempts)`. -/
def numSum : List Sample → Int
  | [] => 0
  | (r, p, a, h) :: xs => p * ((h : Int) * r - a) + numSum xs

/-- `Σ attempts·P²`. -/
def denSum : List Sample → Int
  | [] => 0
  | (_, p, a, _) :: xs => (a : Int) * (p * p) + denSum xs

/-- Some sample has positive attempts at a positive prospecting. -/
def hasPos : List Sample → Bool
  | [] => false
  | (_, p, a, _) :: xs => (decide (0 < a) && decide (0 < p)) || hasPos xs

/-- The attempt-weighted least-squares slope through the origin, clamped at 0;
0 without a sample at a positive prospecting. -/
def fitK (s : List Sample) : Q :=
  if hasPos s then
    if numSum s ≤ 0 then (0, 1) else (numSum s, denSum s)
  else (0, 1)

theorem qle_refl (a : Q) : qle a a := Int.le_refl _

/-- The posterior is in (0, 1]: a positive numerator over a positive
denominator, at most 1. -/
theorem posterior_in_unit (apiRate attempts hits : Nat) (hr : 1 ≤ apiRate)
    (hh : hits ≤ attempts) :
    0 < (posterior apiRate attempts hits).1 ∧ 0 < (posterior apiRate attempts hits).2
      ∧ qle (posterior apiRate attempts hits) one := by
  unfold posterior qle one
  simp only [Int.mul_one, Int.one_mul]
  omega

/-- More hits at fixed attempts never lower the posterior. -/
theorem posterior_converges_hits (apiRate attempts h1 h2 : Nat) (hh : h1 ≤ h2) :
    qle (posterior apiRate attempts h1) (posterior apiRate attempts h2) := by
  unfold posterior qle
  exact Int.mul_le_mul_of_nonneg_right (by omega) (by omega)

/-- The multiplier never lowers a chance. -/
theorem multiplier_ge_one (k : Q) (p : Int) : qle one (multiplier k p) := by
  unfold multiplier qmax
  split
  · assumption
  · exact qle_refl one

/-- The multiplier is monotone in P for k ≥ 0 (a positive denominator). -/
theorem multiplier_monotone (k : Q) (p1 p2 : Int) (hk : 0 ≤ k.1) (hd : 0 < k.2)
    (hp : p1 ≤ p2) : qle (multiplier k p1) (multiplier k p2) := by
  have ht : k.1 * p1 ≤ k.1 * p2 := Int.mul_le_mul_of_nonneg_left hp hk
  have hm : (k.2 + k.1 * p1) * k.2 ≤ (k.2 + k.1 * p2) * k.2 :=
    Int.mul_le_mul_of_nonneg_right (by omega) (Int.le_of_lt hd)
  unfold multiplier qmax qle one at *
  simp only [Int.mul_one, Int.one_mul] at *
  split <;> split <;> simp only [Int.mul_one, Int.one_mul] at * <;> omega

/-- The chance never exceeds 1. -/
theorem chance_le_one (apiRate attempts hits : Nat) (k : Q) (p : Int) :
    qle (chance apiRate attempts hits k p) one := by
  unfold chance qmin
  split
  · exact qle_refl one
  · rename_i h
    unfold qle one at *
    simp only [Int.mul_one, Int.one_mul] at *
    omega

theorem sq_nonneg (p : Int) : 0 ≤ p * p := by
  rcases Int.le_total 0 p with h | h
  · exact Int.mul_nonneg h h
  · have hn : 0 ≤ -p := by omega
    have := Int.mul_nonneg hn hn
    rwa [Int.neg_mul_neg] at this

theorem denSum_nonneg (s : List Sample) : 0 ≤ denSum s := by
  induction s with
  | nil => exact Int.le_refl 0
  | cons x xs ih =>
    obtain ⟨_, p, a, _⟩ := x
    have := Int.mul_nonneg (Int.natCast_nonneg a) (sq_nonneg p)
    simp only [denSum]
    omega

theorem denSum_pos (s : List Sample) (h : hasPos s = true) : 0 < denSum s := by
  induction s with
  | nil => simp [hasPos] at h
  | cons x xs ih =>
    obtain ⟨_, p, a, _⟩ := x
    have hsq := Int.mul_nonneg (Int.natCast_nonneg a) (sq_nonneg p)
    have hrest := denSum_nonneg xs
    simp only [hasPos, Bool.or_eq_true, Bool.and_eq_true, decide_eq_true_eq] at h
    simp only [denSum]
    rcases h with ⟨ha, hp⟩ | h
    · have := Int.mul_pos (Int.ofNat_lt.mpr ha) (Int.mul_pos hp hp)
      omega
    · have := ih h
      omega

/-- The fitted k is a rational ≥ 0 with a positive denominator. -/
theorem fitK_nonneg (s : List Sample) : 0 ≤ (fitK s).1 ∧ 0 < (fitK s).2 := by
  unfold fitK
  split
  · rename_i hpos
    split
    · exact ⟨Int.le_refl 0, by decide⟩
    · exact ⟨by omega, denSum_pos s hpos⟩
  · exact ⟨Int.le_refl 0, by decide⟩

/-- One attempt never yields more than the drop's mean quantity: the chance is
at most 1 (`chance_le_one`). -/
theorem units_le_mean (apiRate attempts hits : Nat) (k : Q) (p : Int) (minQ maxQ : Nat) :
    qle (units apiRate attempts hits k p minQ maxQ) ((minQ : Int) + maxQ, 2) := by
  have h := chance_le_one apiRate attempts hits k p
  unfold units qmul qle
  unfold qle one at h
  generalize chance apiRate attempts hits k p = c at h ⊢
  have hm : (0 : Int) ≤ ((minQ : Int) + maxQ) * 2 := by omega
  generalize (minQ : Int) + maxQ = m at hm ⊢
  simp only [Int.mul_one, Int.one_mul] at h
  have := Int.mul_le_mul_of_nonneg_right h hm
  calc c.1 * m * 2 = c.1 * (m * 2) := Int.mul_assoc _ _ _
    _ ≤ c.2 * (m * 2) := this
    _ = m * (c.2 * 2) := by rw [Int.mul_comm c.2, Int.mul_assoc, Int.mul_comm 2 c.2]

/-! ### Non-vacuity witnesses. -/
-- `posterior_in_unit`: the prior alone (rate 300, no attempts) and the live
-- trout_spot pearls (383 attempts, 2 hits) satisfy the hypotheses.
example : posterior 300 0 0 = (1, 300) := by decide
example : posterior 300 383 2 = (3, 683) := by decide
-- `posterior_converges_hits`: a hit strictly raises it.
example : ¬ qle (posterior 300 383 3) (posterior 300 383 2) := by decide
-- `multiplier_monotone`: k = 1/5 is non-negative and P 10 → 20 raises it, from 3 to 5.
example : multiplier (1, 5) 10 = (15, 5) := by decide
example : multiplier (1, 5) 20 = (25, 5) := by decide
-- A negative k·P is floored at 1.
example : multiplier (-1, 1) 5 = one := by decide
-- `chance_le_one`: a chance below 1 and one capped at it.
example : chance 300 0 0 (1, 5) 10 = (15, 1500) := by decide
example : chance 1 0 0 (1, 5) 10 = one := by decide
-- `units` / `units_le_mean`: the prior is one pearl in 300 gathers, and the live trout_spot
-- pearls (383 attempts, 2 hits) 3 in 683; a drop of 1 to 3 at 1 in 8 is 2/8.
example : units 300 0 0 (0, 1) 0 1 1 = (2, 600) := by decide
example : units 300 383 2 (0, 1) 0 1 1 = (6, 1366) := by decide
example : units 8 0 0 (0, 1) 0 1 3 = (4, 16) := by decide
-- `fitK_nonneg`: a positive slope (3000/30000 = 1/10), a clamped one, and none
-- without positive prospecting.
example : fitK [(300, 10, 100, 1), (100, 20, 50, 1)] = (3000, 30000) := by decide
example : fitK [(300, 10, 300, 0)] = (0, 1) := by decide
example : fitK [(300, -5, 300, 0)] = (0, 1) := by decide

end Formal.DropChance
