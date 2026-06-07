-- @concept: core, planner @property: monotonicity, safety
/-
Formal model of the pure cores extracted from
`src/artifactsmmo_cli/ai/tiers/strategy_blend.py`
(`balancing` and `learned_blend`, extracted from
`StrategyEngine._balancing` / `StrategyEngine._learned_blend` in
`tiers/strategy.py`).

`balancing(leader, current)`:

    raw = 1 + BALANCE_K * (leader - current - BALANCE_THRESHOLD)
        = 1 + 0.25 * (leader - current - 2)
    result = max BALANCE_MIN (min BALANCE_MAX raw)
           = max 0.5 (min 2.0 raw)

`learned_blend(value, normalized, w)`:

    blend = (1 - w) * value + w * normalized

A convex combination over `w ∈ [0, 1]` (production caps `w ≤ 1/2` via
`blend_weight`, which is the same family).

## Models

* `balancing` over `Int`: SCALED BY 4. Production fields `leader, current` are
  integer levels in `state.skills.values()`, so the formula
  `1 + (1/4)*(leader - current - 2)` has denominator exactly 4. We model the
  multiplier-times-4: `scaled = 4 + (leader - current - 2)`, clamped to
  `[2, 8]` (= `[4 * 0.5, 4 * 2.0]`). The diff test compares
  `scaled / 4 == python_result` over `Fraction` for exact equality. Every
  proved bound/identity/monotonicity carries from the scaled `Int` model to
  the rational result by dividing by 4 > 0.

* `learned_blend` over `Rat`: the Python floats `0.25, 0.5, 2.0` are exact
  rationals, and the differential test feeds `Fraction` inputs for bit-exact
  agreement.

INPUT-DOMAIN REALITY:
* `leader, current` are skill levels ≥ 0 (game invariant; we don't need that
  here — the formula and clamp are total over all `Int`).
* `value` is the `_base_prior * _marginal * _balancing` product, ≥ 0 in
  production (priors / marginals / multipliers all ≥ 0); the convex bound
  doesn't depend on the sign.
* `normalized` is `min(1, max(0, char_xp/XP_RATE_REFERENCE)) ∈ [0, 1]` in
  production; the bound theorem only constrains `w ∈ [0, 1]`.
* `w` is `blend_weight(sample_count) ∈ [0, 1/2]` (production); the bound
  theorems are stated for `w ∈ [0, 1]` (a strictly weaker hypothesis).

Lean core only — no mathlib. `Int` order via `omega` / `Int.min`/`Int.max`
lemmas; `Rat` order via `Rat.add_le_add_*`, `Rat.mul_le_mul_of_nonneg_*`,
`Rat.mul_nonneg`, plus `grind`.
-/

namespace Formal.StrategyBlend

/-! ## (1) `balancing` over `Int`, scaled by 4. -/

/-- `BALANCE_THRESHOLD` (from `strategy_blend.py`). -/
def balanceThresh : Int := 2

/-- Scaled balanceMin = `4 * 0.5 = 2`. -/
def balanceMinScaled : Int := 2

/-- Scaled balanceMax = `4 * 2.0 = 8`. -/
def balanceMaxScaled : Int := 8

/-- `4 * raw = 4 + (leader - current - balanceThresh)`. The `+ 4` absorbs the
`+ 1` in `1 + 0.25*…`, scaled by 4. -/
def rawScaled (leader current : Int) : Int :=
  4 + (leader - current - balanceThresh)

/-- The scaled clamp. `balancing leader current = balancingScaled leader current / 4`
(in `Rat`); we prove every property at the `Int` level and the diff test does
the divide-by-4 round-trip exactly via `Fraction`. -/
def balancingScaled (leader current : Int) : Int :=
  max balanceMinScaled (min balanceMaxScaled (rawScaled leader current))

/-! ### Balancing intent theorems (scaled by 4). -/

/-- BAND LOWER BOUND (scaled): result ≥ 2 (= `4 * 0.5`). The outer `max`
absorbs every arbitrarily-low raw. -/
theorem balancingScaled_ge_min (leader current : Int) :
    balanceMinScaled ≤ balancingScaled leader current := by
  unfold balancingScaled
  exact Int.le_max_left _ _

/-- BAND UPPER BOUND (scaled): result ≤ 8 (= `4 * 2.0`). The inner `min`
clamps the raw down, and the outer `max` only PROMOTES values up to 2
(`balanceMinScaled = 2 < 8 = balanceMaxScaled`), so the bound survives. -/
theorem balancingScaled_le_max (leader current : Int) :
    balancingScaled leader current ≤ balanceMaxScaled := by
  unfold balancingScaled balanceMinScaled balanceMaxScaled rawScaled balanceThresh
  -- max 2 (min 8 r) ≤ 8
  have h2 : min (8 : Int) (4 + (leader - current - 2)) ≤ 8 :=
    Int.min_le_left _ _
  omega

/-- THRESHOLD IDENTITY: when `leader - current = balanceThresh` (= 2), the raw
multiplier is `1`, scaled to `4`. The clamp leaves `4` unchanged (since
`2 ≤ 4 ≤ 8`). This is the NEUTRAL baseline (NOT the leader=current case). -/
theorem balancingScaled_at_threshold (leader current : Int)
    (h : leader - current = balanceThresh) :
    balancingScaled leader current = 4 := by
  have h' : leader - current = 2 := by
    rw [h]; rfl
  unfold balancingScaled rawScaled balanceThresh balanceMinScaled balanceMaxScaled
  have hr : 4 + (leader - current - 2) = 4 := by omega
  rw [hr]
  decide

/-- LEADER = CURRENT CLAMP: when the queried skill is the leader (or any tied
position), the raw is `1 + (1/4)*(-2) = 1/2`, scaled to `2`. The clamp returns
EXACTLY `balanceMinScaled` (2). -/
theorem balancingScaled_at_equal_clamps_to_min (s : Int) :
    balancingScaled s s = balanceMinScaled := by
  unfold balancingScaled rawScaled balanceThresh balanceMinScaled balanceMaxScaled
  -- 4 + (s - s - 2) = 2. min 8 2 = 2. max 2 2 = 2.
  have hr : (4 : Int) + (s - s - 2) = 2 := by omega
  rw [hr]; decide

/-- MONOTONE in `(leader - current)`: a wider gap never decreases the
multiplier. Both layers (`min`, `max`) preserve order; the raw step is also
monotone. Discharged by omega after pinning the min/max value semantics. -/
theorem balancingScaled_mono (leader current leader' current' : Int)
    (h : leader - current ≤ leader' - current') :
    balancingScaled leader current ≤ balancingScaled leader' current' := by
  unfold balancingScaled rawScaled balanceMinScaled balanceMaxScaled balanceThresh
  -- Prove the goal by establishing it via concrete value characterisation.
  -- Let a = 4 + (l - c - 2), b = 4 + (l' - c' - 2). Then a ≤ b by h.
  -- max 2 (min 8 a) is the clamp of a into [2, 8]; same for b. Clamp is monotone.
  -- We prove it directly: produce four lemmas and combine.
  have hab : 4 + (leader - current - 2) ≤ 4 + (leader' - current' - 2) := by omega
  -- Clamp upper-half (min 8 ·) is monotone:
  have hmin : min (8 : Int) (4 + (leader - current - 2))
            ≤ min (8 : Int) (4 + (leader' - current' - 2)) := by
    by_cases ha : (4 + (leader - current - 2) : Int) ≤ 8
    · -- a ≤ 8, so min 8 a = a
      rw [Int.min_eq_right ha]
      by_cases hb : (4 + (leader' - current' - 2) : Int) ≤ 8
      · rw [Int.min_eq_right hb]; exact hab
      · have hb : (8 : Int) < 4 + (leader' - current' - 2) := Int.not_le.mp hb; rw [Int.min_eq_left (Int.le_of_lt hb)]; omega
    · -- a > 8, so b ≥ a > 8, so both mins = 8.
      have ha : (8 : Int) < 4 + (leader - current - 2) := Int.not_le.mp ha
      rw [Int.min_eq_left (Int.le_of_lt ha)]
      have hb : (8 : Int) ≤ 4 + (leader' - current' - 2) := by omega
      rw [Int.min_eq_left hb]
      omega
  -- Clamp lower-half (max 2 ·) is monotone in the same way:
  by_cases ha : min (8 : Int) (4 + (leader - current - 2)) ≤ 2
  · -- max 2 (min 8 a) = 2 ≤ max 2 (...)
    rw [Int.max_eq_left ha]
    exact Int.le_max_left _ _
  · have ha : (2 : Int) < min 8 (4 + (leader - current - 2)) := Int.not_le.mp ha
    have ha' : (2 : Int) ≤ min 8 (4 + (leader - current - 2)) := Int.le_of_lt ha
    rw [Int.max_eq_right ha']
    have hb : (2 : Int) ≤ min 8 (4 + (leader' - current' - 2)) := Int.le_trans ha' hmin
    rw [Int.max_eq_right hb]
    exact hmin

/-! ## (2) `learnedBlend` over `Rat`. -/

/-- `(1 - w) * value + w * normalized`. -/
def learnedBlend (value normalized w : Rat) : Rat :=
  (1 - w) * value + w * normalized

/-! ### Learned-blend intent theorems. -/

/-- WARM-UP IDENTITY: `w = 0` ⇒ blend = value. With zero observed samples the
learning signal is fully ignored — the prior survives unchanged. -/
theorem learnedBlend_w_zero (value normalized : Rat) :
    learnedBlend value normalized 0 = value := by
  unfold learnedBlend; grind

/-- W = 1 IDENTITY: `w = 1` ⇒ blend = normalized. The far endpoint of the
convex combination. -/
theorem learnedBlend_w_one (value normalized : Rat) :
    learnedBlend value normalized 1 = normalized := by
  unfold learnedBlend; grind

/-- THE ANTI-PHASE-1 LOWER BOUND with `value ≤ normalized`: blend ≥ value.
A convex combination cannot drop below the lesser endpoint. -/
theorem learnedBlend_ge_value_when_le (value normalized w : Rat)
    (hw0 : 0 ≤ w) (hvn : value ≤ normalized) :
    value ≤ learnedBlend value normalized w := by
  unfold learnedBlend
  have hwn : w * value ≤ w * normalized := Rat.mul_le_mul_of_nonneg_left hvn hw0
  -- (1-w)*v + w*v = v ≤ (1-w)*v + w*n
  grind

/-- THE ANTI-PHASE-1 UPPER BOUND with `value ≤ normalized`: blend ≤ normalized.
A convex combination cannot rise above the greater endpoint. -/
theorem learnedBlend_le_normalized_when_le (value normalized w : Rat)
    (hw1 : w ≤ 1) (hvn : value ≤ normalized) :
    learnedBlend value normalized w ≤ normalized := by
  unfold learnedBlend
  have h1mw : 0 ≤ 1 - w := by grind
  have : (1 - w) * value ≤ (1 - w) * normalized :=
    Rat.mul_le_mul_of_nonneg_left hvn h1mw
  -- (1-w)*v + w*n ≤ (1-w)*n + w*n = n
  grind

/-- THE ANTI-PHASE-1 LOWER BOUND with `normalized ≤ value`: blend ≥ normalized.
Symmetric to `learnedBlend_ge_value_when_le`. -/
theorem learnedBlend_ge_normalized_when_ge (value normalized w : Rat)
    (hw1 : w ≤ 1) (hnv : normalized ≤ value) :
    normalized ≤ learnedBlend value normalized w := by
  unfold learnedBlend
  have h1mw : 0 ≤ 1 - w := by grind
  have : (1 - w) * normalized ≤ (1 - w) * value :=
    Rat.mul_le_mul_of_nonneg_left hnv h1mw
  grind

/-- THE ANTI-PHASE-1 UPPER BOUND with `normalized ≤ value`: blend ≤ value.
Symmetric to `learnedBlend_le_normalized_when_le`. -/
theorem learnedBlend_le_value_when_ge (value normalized w : Rat)
    (hw0 : 0 ≤ w) (hnv : normalized ≤ value) :
    learnedBlend value normalized w ≤ value := by
  unfold learnedBlend
  have hwn : w * normalized ≤ w * value := Rat.mul_le_mul_of_nonneg_left hnv hw0
  grind

/-- MONOTONE in `normalized` (given `w ≥ 0`): a stronger learning signal never
decreases the blend. -/
theorem learnedBlend_mono_normalized (value n n' w : Rat)
    (hw : 0 ≤ w) (h : n ≤ n') :
    learnedBlend value n w ≤ learnedBlend value n' w := by
  unfold learnedBlend
  have : w * n ≤ w * n' := Rat.mul_le_mul_of_nonneg_left h hw
  grind

/-- MONOTONE in `value` (given `w ≤ 1`): a stronger prior never decreases the
blend. -/
theorem learnedBlend_mono_value (v v' normalized w : Rat)
    (hw : w ≤ 1) (h : v ≤ v') :
    learnedBlend v normalized w ≤ learnedBlend v' normalized w := by
  unfold learnedBlend
  have h1mw : 0 ≤ 1 - w := by grind
  have : (1 - w) * v ≤ (1 - w) * v' := Rat.mul_le_mul_of_nonneg_left h h1mw
  grind

/-! ### Non-vacuity examples (genuine fractional witnesses). -/

/-- Threshold identity is non-vacuous: at leader=5, current=3 (gap=2), the
scaled multiplier IS exactly 4 (= 1 * 4). -/
example : balancingScaled 5 3 = 4 := balancingScaled_at_threshold 5 3 (by decide)

/-- At gap = 4 the scaled multiplier IS exactly 6 (= 4 + (5 - 1 - 2)), neither
clamped nor zero: a genuine non-vacuous mid-band value. -/
example : balancingScaled 5 1 = 6 := by
  unfold balancingScaled rawScaled balanceThresh balanceMinScaled balanceMaxScaled
  decide

/-- Extreme positive gap clamps EXACTLY to balanceMaxScaled (8). -/
example : balancingScaled 100 0 = balanceMaxScaled := by
  unfold balancingScaled rawScaled balanceThresh balanceMinScaled balanceMaxScaled
  decide

/-- leader = current = 3 clamps EXACTLY to balanceMinScaled (2). -/
example : balancingScaled 3 3 = balanceMinScaled := balancingScaled_at_equal_clamps_to_min 3

/-- A negative gap (queried skill ahead of the leader, e.g. leader=1, current=5,
gap=-4) clamps to balanceMinScaled — genuine over the negative input domain. -/
example : balancingScaled 1 5 = balanceMinScaled := by
  unfold balancingScaled rawScaled balanceThresh balanceMinScaled balanceMaxScaled
  decide

/-- Learned blend warm-up: w = 0 returns value EXACTLY, independent of
normalized — pinning the warm-up identity. -/
example : learnedBlend (3/10) (99/100) 0 = 3/10 := learnedBlend_w_zero _ _

/-- Learned blend at w = 1/4 over a fractional input domain: `(3/4)*(3/10) +
(1/4)*(8/10) = 9/40 + 8/40 = 17/40`. Both endpoints `3/10 = 12/40` and `8/10 =
32/40` are honoured by the convex bound. -/
example :
    learnedBlend (3/10) (8/10) (1/4) = 17/40 := by
  unfold learnedBlend; grind

/-- The convex bound is non-vacuous and STRICT at the midpoint: at w = 1/2,
the blend of 0 and 1 is 1/2, strictly between the endpoints. -/
example :
    learnedBlend 0 1 (1/2) = 1/2
    ∧ (0 : Rat) ≤ learnedBlend 0 1 (1/2) ∧ learnedBlend 0 1 (1/2) ≤ 1 := by
  refine ⟨?_, ?_, ?_⟩
  · unfold learnedBlend; grind
  · exact learnedBlend_ge_value_when_le 0 1 (1/2) (by grind) (by grind)
  · exact learnedBlend_le_normalized_when_le 0 1 (1/2) (by grind) (by grind)

/-- Monotonicity in `normalized` is non-vacuous: at w = 1/2, raising
normalized from 0 to 1 raises the blend from value/2 to (value + 1)/2. -/
example :
    learnedBlend (1/2) 0 (1/2) = 1/4 ∧ learnedBlend (1/2) 1 (1/2) = 3/4 := by
  refine ⟨?_, ?_⟩ <;> (unfold learnedBlend; grind)

end Formal.StrategyBlend
