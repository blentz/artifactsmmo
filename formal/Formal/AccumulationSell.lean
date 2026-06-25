/-
Formal model of `accumulation_steps` / `accumulation_excess` from
`src/artifactsmmo_cli/ai/accumulation_sell.py`.

The Python core is a ratio-driven, space-pressure-independent sell-down of
accumulated multiples. An item is over-accumulated when its held quantity is a
large multiple of its keep-cap (`useful_quantity_cap`); the bot sheds the
surplus down to the cap by selling, urgency rising geometrically (one step per
doubling of the ratio).

* `accumulation_steps(held, cap)` = the largest `k ≥ 0` with
  `eff_cap * 2**k ≤ held` (= floor(log2(held / eff_cap))), `eff_cap = max(cap,1)`;
  0 when `held < eff_cap`. Integer-exact doubling loop — no float.
* `accumulation_excess(held, cap)` = `held - max(cap,0)` when
  `held ≥ ACCUM_MULT * max(cap,1)` (the RATIO gate), else 0.
* `ACCUM_MULT = 5`, `SEVERE_STEPS = 5` (held ≥ cap*32 escalates the sell).

The Lean core is over `Nat` (held, cap are non-negative counts). `max cap 0 = cap`
over Nat, so the excess kept is exactly `cap`. The doubling loop is modeled as
fuel-bounded structural recursion seeded by `held` (the loop runs at most
log2(held) times, so `held` fuel is always adequate).

Lean core only — no mathlib. Integer arithmetic via `omega` / induction.
-/

namespace Formal.AccumulationSell

/-- Fire the accumulation sell when `held ≥ accMult * max(cap, 1)`
(mirrors `ACCUM_MULT = 5`). -/
def accMult : Nat := 5

/-- `accumulation_steps ≥ severeSteps` (held ≥ cap*32) escalates the sell above
the progression band (mirrors `SEVERE_STEPS = 5`). -/
def severeSteps : Nat := 5

/-- The doubling loop, fuel-bounded structural recursion. `bound` starts at
`eff_cap` and doubles each step the inequality holds; `fuel` (seeded by `held`)
bounds the iteration count. Returns the count of doublings. -/
def accumulationStepsFuel : Nat → Nat → Nat → Nat
  | 0, _, _ => 0
  | Nat.succ f, bound, held =>
      if bound * 2 ≤ held then 1 + accumulationStepsFuel f (bound * 2) held else 0

/-- `accumulation_steps`: floor(log2(held / max(cap,1))). 0 when held is below
`eff_cap = max(cap,1)`; otherwise the count of doublings of `eff_cap` that fit
under `held`. Fuel = `held` bounds the doubling loop. -/
def accumulationSteps (held cap : Nat) : Nat :=
  let effCap := max cap 1
  if held < effCap then 0 else accumulationStepsFuel held effCap held

/-- `accumulation_excess`: `held - cap` when `held ≥ accMult * max(cap,1)`
(the RATIO gate), else 0. Over `Nat`, `max cap 0 = cap`, so the kept amount is
exactly the true cap — a dominated item (cap 0) past the gate sells to 0, a kept
item (cap 1) sells to 1. -/
def accumulationExcess (held cap : Nat) : Nat :=
  let effCap := max cap 1
  if held < accMult * effCap then 0 else held - cap

/-- `below_gate_quiet`: below the ratio gate, the excess is exactly 0 (the bot
takes no accumulation sell action). -/
theorem below_gate_quiet (held cap : Nat) (h : held < accMult * max cap 1) :
    accumulationExcess held cap = 0 := by
  simp only [accumulationExcess]
  simp [h]

/-- `fires_implies_excess_positive`: once the ratio gate fires on a kept item
(`0 < cap`), the reported excess is strictly positive — the sell shed is real,
never junk. -/
theorem fires_implies_excess_positive (held cap : Nat)
    (hc : 0 < cap) (hf : accMult * max cap 1 ≤ held) :
    0 < accumulationExcess held cap := by
  have hmax : max cap 1 = cap := Nat.max_eq_left hc
  rw [hmax] at hf
  simp only [accumulationExcess]
  -- accMult = 5, so 5 * cap ≤ held; with 0 < cap, cap < held ⇒ held - cap > 0.
  have : ¬ held < accMult * max cap 1 := by
    rw [hmax]; omega
  simp only [this, if_false]
  unfold accMult at hf
  omega

/-- `excess_sells_down_to_cap`: on the fired branch, selling the excess leaves
EXACTLY `cap` held (the keep-cap). The shed converges to the cap. -/
theorem excess_sells_down_to_cap (held cap : Nat)
    (hf : accMult * max cap 1 ≤ held) :
    held - accumulationExcess held cap = cap := by
  simp only [accumulationExcess]
  have hge : accMult * max cap 1 ≤ held := hf
  have : ¬ held < accMult * max cap 1 := by omega
  simp only [this, if_false]
  -- cap ≤ held (from the gate: cap ≤ max cap 1 ≤ accMult*max cap 1 ≤ held).
  have hcap_le : cap ≤ held := by
    have h1 : cap ≤ max cap 1 := Nat.le_max_left cap 1
    have h2 : max cap 1 ≤ accMult * max cap 1 := by
      unfold accMult; omega
    omega
  omega

/-- `excess_monotone`: more held never reduces the reported excess — the shed is
monotone in the held quantity. -/
theorem excess_monotone (h1 h2 cap : Nat) (h : h1 ≤ h2) :
    accumulationExcess h1 cap ≤ accumulationExcess h2 cap := by
  simp only [accumulationExcess]
  by_cases g1 : h1 < accMult * max cap 1
  · -- h1 below gate ⇒ excess h1 = 0 ≤ anything
    simp only [g1, if_true]
    exact Nat.zero_le _
  · -- h1 fires ⇒ h2 fires too (gate monotone), both = held - cap.
    have g2 : ¬ h2 < accMult * max cap 1 := by omega
    simp only [g1, g2, if_false]
    omega

/-! ### `steps_threshold` — the geometric-severity escalation contract.

`severeSteps ≤ accumulationSteps held cap ⇒ max cap 1 * 32 ≤ held`: five
doublings means `held` is at least `2^5 = 32` times the effective cap. We prove
a fuel-induction helper first.

The helper is stated for `1 ≤ k` (a positive number of doublings). The base
case `k = 0` is intentionally excluded: `bound * 2^0 = bound ≤ held` is NOT
implied by `0 = accumulationStepsFuel …` (zero doublings says nothing about
`bound` vs `held`). The contract only ever needs `k = severeSteps = 5 ≥ 1`. -/

/-- Helper: when the fuel loop counts at least `k ≥ 1` doublings, the doubled
bound `bound * 2^k` still fits under `held`. By induction on the fuel; the first
firing supplies `bound * 2 ≤ held` and the IH handles the doubled bound. -/
theorem fuel_pow (f bound held k : Nat) (hk : 1 ≤ k)
    (h : k ≤ accumulationStepsFuel f bound held) :
    bound * 2 ^ k ≤ held := by
  induction f generalizing bound k with
  | zero =>
      -- fuel 0 ⇒ steps 0 ⇒ k ≤ 0, contradicting 1 ≤ k.
      simp only [accumulationStepsFuel] at h
      omega
  | succ f ih =>
      -- Unfold one fuel step. If the guard fails, steps = 0, contradicting 1 ≤ k.
      unfold accumulationStepsFuel at h
      by_cases hg : bound * 2 ≤ held
      · rw [if_pos hg] at h
        -- h : k ≤ 1 + accumulationStepsFuel f (bound*2) held
        -- k ≥ 1, so k = j + 1; peel one doubling.
        obtain ⟨j, rfl⟩ : ∃ j, k = j + 1 := ⟨k - 1, by omega⟩
        -- goal: bound * 2^(j+1) ≤ held; rewrite 2^(j+1) = 2^j * 2.
        rw [Nat.pow_succ, ← Nat.mul_assoc]
        -- goal: (bound * 2^j) ... rearrange to (bound * 2) * 2^j ≤ held.
        rw [Nat.mul_comm (bound * 2 ^ j) 2, ← Nat.mul_assoc, Nat.mul_comm 2 bound]
        -- goal: (bound * 2) * 2^j ≤ held.
        rcases Nat.eq_zero_or_pos j with hj0 | hjpos
        · -- j = 0: (bound*2) * 1 ≤ held, exactly the guard.
          subst hj0
          rw [Nat.pow_zero, Nat.mul_one]
          exact hg
        · -- j ≥ 1: apply IH on (bound*2) and j.
          have h' : j ≤ accumulationStepsFuel f (bound * 2) held := by omega
          exact ih (bound * 2) j hjpos h'
      · -- guard false ⇒ steps = 0 ⇒ k ≤ 0, contradicting 1 ≤ k.
        rw [if_neg hg] at h
        omega

/-- `steps_threshold`: reaching `severeSteps` (5) accumulation steps means the
held quantity is at least `32 = 2^5` times the effective cap — the geometric
severity that escalates the sell above the progression band. -/
theorem steps_threshold (held cap : Nat)
    (h : severeSteps ≤ accumulationSteps held cap) :
    max cap 1 * 32 ≤ held := by
  simp only [accumulationSteps] at h
  -- The `held < max cap 1` branch yields 0, contradicting severeSteps = 5 ≤ 0.
  by_cases hb : held < max cap 1
  · simp only [hb, if_true] at h
    unfold severeSteps at h
    omega
  · simp only [hb, if_false] at h
    -- severeSteps = 5 ≤ accumulationStepsFuel held (max cap 1) held
    unfold severeSteps at h
    have hk : (1 : Nat) ≤ 5 := by omega
    have hfp := fuel_pow held (max cap 1) held 5 hk h
    -- (max cap 1) * 2^5 = (max cap 1) * 32
    have h32 : (2 : Nat) ^ 5 = 32 := by decide
    rw [h32] at hfp
    exact hfp

end Formal.AccumulationSell
