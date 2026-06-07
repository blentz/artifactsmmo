-- @concept: core @property: monotonicity
/-
Formal model of the pure cores extracted from
`src/artifactsmmo_cli/ai/learning/scalarizer.py`
(`scalar_yield_pure` and `coins_spent_from_delta` in `scalar_core.py`).

`scalar_yield_pure` collapses a Yield into a single comparable scalar:

    scalar = char_xp * char_scalar * (level + 1)
           + Σ_skill skill_xp[s] * (relevant_w if s active else baseline_w)
           + gold / gold_per_xp
           + tasks_coins * coin_value / gold_per_xp

with the production constants char_scalar = 1.0, relevant_w = 2.0,
baseline_w = 0.2, gold_per_xp = 100.0.

EXACT-RATIONAL MODEL (over `Rat`, Lean core — no mathlib). The bot's real
`Yield` fields are NOT integers: `char_xp, gold, tasks_coins, skill_xp[*]` are
FRACTIONAL float AVERAGES of integer per-cycle deltas (`projections.py:117-123`,
`totals / n`), and `coin_value = total_value / total_coins_spent` is a fractional
ratio. We therefore model `scalarYieldQ` over the rationals, with the production
weights taken as EXACT rationals:

  * `charScale = 1`        (= char_scalar 1.0)
  * `baselineW = 1/5`      (= 0.2)
  * `relevantW = 2`        (= 2.0)
  * `goldUnit  = 1/100`    (= 1 / gold_per_xp 100); we MULTIPLY by `goldUnit`
    rather than dividing by 100, which is the same rational. The Python core
    divides by `gold_per_xp`; over the rationals `x / 100 = x * (1/100)` exactly.

So `scalarYieldQ ... = (the real float formula)` EXACTLY over rational inputs —
NO scaling, NO rounding, NO restriction to integers. The differential test feeds
exact `fractions.Fraction` inputs (fractional char_xp, skill_xp, gold,
tasks_coins, coin_value) and compares the Python pure core — invoked with
`Fraction` weights so every operation stays exact — against this `Rat` oracle
numerator/denominator EXACTLY. The fractional domain is thereby EXERCISED, not
rejected. **No live production caller exists** for `scalar_yield` /
`scalar_yield_pure` today (verified by `grep -rn 'scalar_yield' src/`: the only
callers are the unit-test and differential-test suites). The differential test
invokes the core with `Fraction` weights so every operation stays exact, and the
unit tests feed integer Yield fields (also exact). Byte-equivalence to this `Rat`
model therefore holds on every actual invocation. The pure core remains generic
in its weight parameters, so if a future production caller wires it in with
float constants, the float arithmetic for the production constants (0.2 = 1/5,
2.0, 1.0, 100.0) over fractional-average inputs would deviate from this exact
model only by IEEE 754 rounding; the proved order properties (monotonicities,
weight dominance) still hold to float precision, but bit-equivalence would
require lifting that caller to `Fraction` as well. The differential gap is
therefore CLOSED at every present-day invocation.

Every theorem below is a genuine order statement on the REAL fractional scalar
the bot compares: the formula is linear with positive coefficients, so the
proved monotonicities / weight-dominance / coin-inversion hold over all of `ℚ`.

INPUT-DOMAIN REALITY (Yield field types, from `learning/projections.py` +
`learning/models.py`):
  * `Yield.char_xp/gold/tasks_coins/skill_xp[*]` are FLOATS that are AVERAGES of
    integer per-cycle deltas — i.e. rationals. The `Rat` model is exact on them.
  * `gold` (delta_gold) CAN BE NEGATIVE: a cycle can spend gold (buy/exchange).
    char_xp and skill_xp deltas are non-negative in this game (XP only rises),
    and tasks_coins drop counts are non-negative — but the MODEL does not assume
    sign on the value inputs; it ranges over all `Rat`, so the diff test includes
    negatives where reachable (gold) and zeros everywhere.
  * `state.level` is a game character level, ALWAYS ≥ 1 (a new character is
    level 1; `from_character_schema` reads `char.level`, never below 1). The
    char-xp monotonicity theorem needs only `level + 1 ≥ 0`, which the `level ≥ 0`
    hypothesis (a fortiori true since level ≥ 1) supplies; we state `level ≥ 0`
    as the honest minimal precondition and justify it from the game invariant.
  * `coin_value` is `Σ value / Σ coins_spent` over exchanges with `coins_spent > 0`
    and non-negative item sell-back `value`, i.e. a ratio of non-negatives ⇒
    `coin_value ≥ 0`; the warm-up fallback DEFAULT_COIN_VALUE_GOLD = 5.0 ≥ 0 too.
    So `coinValue ≥ 0` is a real invariant — the coin monotonicity theorem uses it.

`coinsSpent` stays over `Int` (received / delta are integer inventory counts).

Lean core only — no mathlib. Rat order via `Rat.add_le_add_*`,
`Rat.mul_le_mul_of_nonneg_*`, `Rat.mul_nonneg`, `Rat.le_trans`, and `grind`
(core) for the residual linear-arithmetic / numeric goals; `omega` for Int.
-/

namespace Formal.Scalarizer

/-- A single skill summand: the weight selected for that skill (relevant or
baseline, as an exact rational) paired with its xp delta (a rational average). -/
abbrev SkillTerm := Rat × Rat

/-- Sum of `weight * xp` over the skill terms (mirrors the Python
`Σ skill_xp[s] * weight(s)` loop accumulator). -/
def skillSum : List SkillTerm → Rat
  | [] => 0
  | (w, xp) :: rest => w * xp + skillSum rest

/-- The rational scalar yield. All weight/scale factors are EXACT rationals (see
header); `goldUnit = 1/100` is the exact `1 / gold_per_xp`, so multiplying by it
equals the Python `/gold_per_xp`. Mirrors `scalar_yield_pure`
component-for-component over `ℚ`. -/
def scalarYield (charXp level : Rat) (skills : List SkillTerm)
    (gold tasksCoins coinValue : Rat)
    (charScale goldUnit : Rat) : Rat :=
  charXp * charScale * (level + 1)
    + skillSum skills
    + gold * goldUnit
    + tasksCoins * coinValue * goldUnit

/-- `coins_spent_from_delta`: the inventory delta inverts to coins spent. Counts
are integers, so this core stays over `Int`. -/
def coinsSpent (received delta : Int) : Int := received - delta

/-! ### Intent theorems. -/

/-- Pins the exact component decomposition the Python computes (the model `=` the
Python arithmetic over the rationals — no scaling). Any drift in
`scalar_yield_pure` breaks the differential gate. -/
theorem scalarYield_eq_components (charXp level : Rat) (skills : List SkillTerm)
    (gold tasksCoins coinValue charScale goldUnit : Rat) :
    scalarYield charXp level skills gold tasksCoins coinValue charScale goldUnit
      = charXp * charScale * (level + 1) + skillSum skills
        + gold * goldUnit + tasksCoins * coinValue * goldUnit := rfl

/-- MONOTONICITY in char_xp (all else fixed): increasing char_xp never decreases
the scalar, GIVEN `level ≥ 0` (so `level + 1 ≥ 1 > 0`) and `charScale ≥ 0` (the
positive scale 1). `level ≥ 0` is a real game invariant (character level ≥ 1).
Higher char-xp yield ⇒ higher score — the scalar prefers earning character XP. -/
theorem scalarYield_mono_charxp (charXp charXp' level : Rat) (skills : List SkillTerm)
    (gold tasksCoins coinValue charScale goldUnit : Rat)
    (hlevel : 0 ≤ level) (hscale : 0 ≤ charScale) (h : charXp ≤ charXp') :
    scalarYield charXp level skills gold tasksCoins coinValue charScale goldUnit
      ≤ scalarYield charXp' level skills gold tasksCoins coinValue charScale goldUnit := by
  unfold scalarYield
  have hpos : 0 ≤ charScale * (level + 1) := Rat.mul_nonneg hscale (by grind)
  have hmul : charXp * charScale * (level + 1) ≤ charXp' * charScale * (level + 1) := by
    rw [Rat.mul_assoc, Rat.mul_assoc]
    exact Rat.mul_le_mul_of_nonneg_right h hpos
  grind

/-- MONOTONICITY in gold (all else fixed): given the positive `goldUnit` (1/100),
more gold never decreases the scalar. `gold` itself may be negative (spending),
but raising it still raises the score. -/
theorem scalarYield_mono_gold (charXp level : Rat) (skills : List SkillTerm)
    (gold gold' tasksCoins coinValue charScale goldUnit : Rat)
    (hunit : 0 ≤ goldUnit) (h : gold ≤ gold') :
    scalarYield charXp level skills gold tasksCoins coinValue charScale goldUnit
      ≤ scalarYield charXp level skills gold' tasksCoins coinValue charScale goldUnit := by
  unfold scalarYield
  have hmul : gold * goldUnit ≤ gold' * goldUnit :=
    Rat.mul_le_mul_of_nonneg_right h hunit
  grind

/-- MONOTONICITY in tasks_coins (all else fixed): given `coinValue ≥ 0` (a ratio
of non-negatives, DEFAULT 5 ≥ 0 — see header) and `goldUnit ≥ 0`, more coins
never decrease the scalar. -/
theorem scalarYield_mono_coins (charXp level : Rat) (skills : List SkillTerm)
    (gold tasksCoins tasksCoins' coinValue charScale goldUnit : Rat)
    (hcoin : 0 ≤ coinValue) (hunit : 0 ≤ goldUnit) (h : tasksCoins ≤ tasksCoins') :
    scalarYield charXp level skills gold tasksCoins coinValue charScale goldUnit
      ≤ scalarYield charXp level skills gold tasksCoins' coinValue charScale goldUnit := by
  unfold scalarYield
  have hcu : 0 ≤ coinValue * goldUnit := Rat.mul_nonneg hcoin hunit
  have hmul : tasksCoins * (coinValue * goldUnit) ≤ tasksCoins' * (coinValue * goldUnit) :=
    Rat.mul_le_mul_of_nonneg_right h hcu
  have e1 : tasksCoins * coinValue * goldUnit = tasksCoins * (coinValue * goldUnit) :=
    Rat.mul_assoc tasksCoins coinValue goldUnit
  have e2 : tasksCoins' * coinValue * goldUnit = tasksCoins' * (coinValue * goldUnit) :=
    Rat.mul_assoc tasksCoins' coinValue goldUnit
  grind

/-- MONOTONICITY in a single skill's xp, given that skill's weight ≥ 0 (both the
baseline 1/5 and relevant 2 weights are ≥ 0). Bumping one active skill's xp delta
(its weight fixed) never decreases the scalar. We isolate one term against the
rest of the list. -/
theorem skillSum_mono_one (w xp xp' : Rat) (rest : List SkillTerm)
    (hw : 0 ≤ w) (h : xp ≤ xp') :
    skillSum ((w, xp) :: rest) ≤ skillSum ((w, xp') :: rest) := by
  simp only [skillSum]
  have hmul : w * xp ≤ w * xp' := Rat.mul_le_mul_of_nonneg_left h hw
  grind

/-- WEIGHT DOMINANCE: the relevant-skill weight is ≥ the baseline weight
(2 ≥ 1/5), so one unit of an active-skill xp scores at least as much as one unit
of a baseline-skill xp. This is what makes the scalar prefer grinding the
task-relevant skill. Stated for any non-negative xp unit. -/
theorem relevant_weight_dominates (baselineW relevantW xp : Rat)
    (hle : baselineW ≤ relevantW) (hxp : 0 ≤ xp) :
    baselineW * xp ≤ relevantW * xp :=
  Rat.mul_le_mul_of_nonneg_right hle hxp

/-- COIN INVERSION: the recorded `delta = received - coins_spent` inverts back to
`delta` with NO sign error — `received - coinsSpent received delta = delta`.
Proves the derivation in `expected_coin_value_with_prices` is self-consistent. -/
theorem coinsSpent_inverts (received delta : Int) :
    received - coinsSpent received delta = delta := by
  unfold coinsSpent; omega

/-- The dual identity: `received - coinsSpent = delta` rearranges to the recorded
relation `coinsSpent = received - delta`. -/
theorem coinsSpent_eq (received delta : Int) :
    coinsSpent received delta = received - delta := rfl

/-! ### Non-vacuity examples (genuine witnesses over the FRACTIONAL domain). -/

/-- char-xp monotonicity is non-vacuous and STRICT at a reachable point: at level
1 (the minimum game level), scale 1, raising char_xp from 0 to 1 strictly raises
the scalar (by `1*1*(1+1) = 2`). The other inputs use the EXACT fractional
production unit `goldUnit = 1/100`. Includes the zero boundary. -/
example :
    scalarYield 0 1 [] 0 0 0 1 (1/100) = 0 ∧
    scalarYield 1 1 [] 0 0 0 1 (1/100) = 2 ∧
    scalarYield 0 1 [] 0 0 0 1 (1/100) < scalarYield 1 1 [] 0 0 0 1 (1/100) := by
  unfold scalarYield skillSum
  refine ⟨by grind, by grind, by grind⟩

/-- gold monotonicity non-vacuity over FRACTIONAL outputs: gold may be NEGATIVE
(spending). At the production `goldUnit = 1/100`, gold -3 scores -3/100 and gold
0 scores 0, a strict increase — a genuinely fractional scalar value. -/
example :
    scalarYield 0 1 [] (-3) 0 0 1 (1/100) = -3/100 ∧
    scalarYield 0 1 [] 0 0 0 1 (1/100) = 0 ∧
    scalarYield 0 1 [] (-3) 0 0 1 (1/100) < scalarYield 0 1 [] 0 0 0 1 (1/100) := by
  unfold scalarYield skillSum
  refine ⟨by grind, by grind, by grind⟩

/-- coin monotonicity non-vacuity at the DEFAULT coin value (5) with the
production `goldUnit = 1/100`: 0 coins score 0, 2 coins score `2*5*(1/100) =
1/10` — a genuinely fractional value the integer model could never produce. -/
example :
    scalarYield 0 1 [] 0 0 5 1 (1/100) = 0 ∧
    scalarYield 0 1 [] 0 2 5 1 (1/100) = 1/10 := by
  unfold scalarYield skillSum
  refine ⟨by grind, by grind⟩

/-- skill-weight dominance non-vacuity over FRACTIONAL xp: a fractional active
skill xp `1/3` at weight 2 scores `2/3`, vs baseline weight `1/5` scoring
`1/15` — and `1/5 ≤ 2`. A genuine fractional gap. -/
example :
    skillSum [((2 : Rat), 1/3)] = 2/3 ∧ skillSum [((1/5 : Rat), 1/3)] = 1/15 ∧
    (1/5 : Rat) * (1/3) ≤ 2 * (1/3) := by
  refine ⟨by simp only [skillSum]; grind, by simp only [skillSum]; grind, by grind⟩

/-- coin-inversion non-vacuity incl. zero and a negative recorded delta. -/
example :
    (10 - coinsSpent 10 4 = 4) ∧ (10 - coinsSpent 10 0 = 0)
      ∧ coinsSpent 3 5 = -2 := by
  refine ⟨coinsSpent_inverts 10 4, coinsSpent_inverts 10 0, by decide⟩

end Formal.Scalarizer
