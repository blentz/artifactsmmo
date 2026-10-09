-- @concept: consumables, cost @property: validity, monotonicity, totality
/-
The price of one consumable, in seconds (`docs/PLAN_consumable_utility.md`
increment 2, `src/artifactsmmo_cli/ai/consumable_price_core.py`).

USER 2026-10-09: "held stock (bag, bank, utility slots) is free. With none held,
its price is the cheaper of replacement time (make it: the acquisition walk) and
gold value (buy it) — the classic build/buy."

## The model

A non-negative rational is an unreduced `(numerator, denominator)` pair, and two
are compared by cross-multiplication (`qle`), as `Formal.LossRisk` does, so the
model never divides. `none` is an UNAVAILABLE side (+∞).

* `make` — the acquisition walk in seconds, `none` when there is no route;
* `buySeconds gold gpsNum gpsDen` — `gold / (gpsNum / gpsDen)` = `(gold × gpsDen,
  gpsNum)`, `none` when nobody sells for gold or the gold rate is 0 (the Python
  passes `gpsNum = 0` for any rate ≤ 0);
* `consumablePrice` — `(0, 1)` when anything is held, else the cheaper of the
  available sides (`make` on a tie, the Python `make <= buy` test).
-/

namespace Formal.ConsumablePrice

/-- A non-negative rational, `(numerator, denominator)`, unreduced. -/
abbrev Q := Nat × Nat

/-- `a ≤ b`, cross-multiplied. -/
def qle (a b : Q) : Prop := a.1 * b.2 ≤ b.1 * a.2

instance (a b : Q) : Decidable (qle a b) := inferInstanceAs (Decidable (_ ≤ _))

/-- The smaller of two rationals, the first on a tie. -/
def qmin (a b : Q) : Q := if qle a b then a else b

/-- `≤` with `none` as +∞. -/
def optLe : Option Q → Option Q → Prop
  | _, none => True
  | none, some _ => False
  | some a, some b => qle a b

/-- A present side has a positive denominator (a Python `Fraction` always does). -/
def posDen : Option Q → Prop
  | none => True
  | some a => 0 < a.2

/-- The cheaper available side; `none` only when neither is available. -/
def optMin : Option Q → Option Q → Option Q
  | none, b => b
  | some a, none => some a
  | some a, some b => some (qmin a b)

/-- The buy side in seconds: `gold` at a rate of `gpsNum / gpsDen` gold per second. -/
def buySeconds (gold : Option Nat) (gpsNum gpsDen : Nat) : Option Q :=
  match gold with
  | none => none
  | some g => if gpsNum = 0 then none else some (g * gpsDen, gpsNum)

/-- The price of one consumable (see the module doc). -/
def consumablePrice (held : Nat) (make : Option Q) (gold : Option Nat)
    (gpsNum gpsDen : Nat) : Option Q :=
  if 0 < held then some (0, 1) else optMin make (buySeconds gold gpsNum gpsDen)

/-- Gold prices with `none` (nobody sells) as +∞. -/
def goldLe : Option Nat → Option Nat → Prop
  | _, none => True
  | none, some _ => False
  | some a, some b => a ≤ b

/-! ## Order lemmas -/

theorem qle_refl (a : Q) : qle a a := Nat.le_refl _

theorem qle_of_not (a b : Q) (h : ¬ qle a b) : qle b a :=
  Nat.le_of_lt (Nat.lt_of_not_le h)

/-- Transitivity needs the MIDDLE denominator positive. -/
theorem qle_trans (a b c : Q) (hb : 0 < b.2) (hab : qle a b) (hbc : qle b c) : qle a c := by
  unfold qle at *
  apply Nat.le_of_mul_le_mul_right _ hb
  calc a.1 * c.2 * b.2 = (a.1 * b.2) * c.2 := by
          rw [Nat.mul_assoc, Nat.mul_comm c.2, ← Nat.mul_assoc]
    _ ≤ (b.1 * a.2) * c.2 := Nat.mul_le_mul_right _ hab
    _ = (b.1 * c.2) * a.2 := by
          rw [Nat.mul_assoc, Nat.mul_comm a.2, ← Nat.mul_assoc]
    _ ≤ (c.1 * b.2) * a.2 := Nat.mul_le_mul_right _ hbc
    _ = c.1 * a.2 * b.2 := by
          rw [Nat.mul_assoc, Nat.mul_comm b.2, ← Nat.mul_assoc]

theorem qmin_le_left (a b : Q) : qle (qmin a b) a := by
  unfold qmin
  split
  · exact qle_refl a
  · exact qle_of_not a b (by assumption)

theorem qmin_le_right (a b : Q) : qle (qmin a b) b := by
  unfold qmin
  split
  · assumption
  · exact qle_refl b

theorem optMin_le_left (a b : Option Q) : optLe (optMin a b) a := by
  cases a with
  | none => trivial
  | some a =>
    cases b with
    | none => exact qle_refl a
    | some b => exact qmin_le_left a b

theorem optMin_le_right (a b : Option Q) : optLe (optMin a b) b := by
  cases b with
  | none => cases a <;> trivial
  | some b =>
    cases a with
    | none => exact qle_refl b
    | some a => exact qmin_le_right a b

/-- A cheaper FIRST side never raises the minimum. -/
theorem optMin_mono_left (a a' b : Option Q) (hpos : posDen a') (h : optLe a' a) :
    optLe (optMin a' b) (optMin a b) := by
  cases a with
  | none => exact optMin_le_right a' b
  | some a0 =>
    cases a' with
    | none => exact absurd h id
    | some a0' =>
      cases b with
      | none => exact h
      | some b0 =>
        show qle (qmin a0' b0) (qmin a0 b0)
        by_cases hab : qle a0 b0
        · rw [show qmin a0 b0 = a0 from if_pos hab]
          exact qle_trans _ a0' _ hpos (qmin_le_left a0' b0) h
        · rw [show qmin a0 b0 = b0 from if_neg hab]
          exact qmin_le_right a0' b0

/-- A cheaper SECOND side never raises the minimum. -/
theorem optMin_mono_right (a b b' : Option Q) (hpos : posDen b') (h : optLe b' b) :
    optLe (optMin a b') (optMin a b) := by
  cases b with
  | none =>
    cases a with
    | none => trivial
    | some a0 => exact optMin_le_left (some a0) b'
  | some b0 =>
    cases b' with
    | none => exact absurd h id
    | some b0' =>
      cases a with
      | none => exact h
      | some a0 =>
        show qle (qmin a0 b0') (qmin a0 b0)
        by_cases hab : qle a0 b0
        · rw [show qmin a0 b0 = a0 from if_pos hab]
          exact qmin_le_left a0 b0'
        · rw [show qmin a0 b0 = b0 from if_neg hab]
          exact qle_trans _ b0' _ hpos (qmin_le_right a0 b0') h

theorem buySeconds_posDen (gold : Option Nat) (n d : Nat) : posDen (buySeconds gold n d) := by
  cases gold with
  | none => trivial
  | some g =>
    by_cases hn : n = 0
    · simp [buySeconds, hn, posDen]
    · simp only [buySeconds, hn, if_false, posDen]
      omega

/-! ## Theorems -/

/-- HELD IS FREE: anything held prices at 0. -/
theorem held_free (held : Nat) (make : Option Q) (gold : Option Nat) (n d : Nat)
    (h : 0 < held) : consumablePrice held make gold n d = some (0, 1) := by
  simp [consumablePrice, h]

/-- NEVER DEARER THAN MAKING: the price is at most the make side. -/
theorem le_make (held : Nat) (make : Option Q) (gold : Option Nat) (n d : Nat) :
    optLe (consumablePrice held make gold n d) make := by
  unfold consumablePrice
  split
  · cases make with
    | none => trivial
    | some m => show 0 * m.2 ≤ m.1 * 1; simp
  · exact optMin_le_left _ _

/-- NEVER DEARER THAN BUYING: the price is at most the buy side. -/
theorem le_buy (held : Nat) (make : Option Q) (gold : Option Nat) (n d : Nat) :
    optLe (consumablePrice held make gold n d) (buySeconds gold n d) := by
  unfold consumablePrice
  split
  · cases buySeconds gold n d with
    | none => trivial
    | some b => show 0 * b.2 ≤ b.1 * 1; simp
  · exact optMin_le_right _ _

/-- THE PRICE IS ONE OF THE SIDES: free when held, else the make side or the buy
side itself (the minimum is attained, not merely bounded). -/
theorem price_mem (held : Nat) (make : Option Q) (gold : Option Nat) (n d : Nat) (r : Q)
    (h : consumablePrice held make gold n d = some r) :
    (0 < held ∧ r = (0, 1)) ∨ make = some r ∨ buySeconds gold n d = some r := by
  unfold consumablePrice at h
  by_cases hh : 0 < held
  · simp [hh] at h
    exact Or.inl ⟨hh, h.symm⟩
  · simp only [hh, if_false] at h
    cases make with
    | none => exact Or.inr (Or.inr h)
    | some m =>
      cases hb : buySeconds gold n d with
      | none => rw [hb] at h; exact Or.inr (Or.inl h)
      | some b =>
        rw [hb] at h
        simp only [optMin, Option.some.injEq] at h
        unfold qmin at h
        split at h
        · exact Or.inr (Or.inl (by rw [h]))
        · exact Or.inr (Or.inr (by rw [h]))

/-- UNPRICEABLE EXACTLY WHEN NOTHING SERVES: none held, no route, and no gold
seller at a positive gold rate. -/
theorem none_iff (held : Nat) (make : Option Q) (gold : Option Nat) (n d : Nat) :
    consumablePrice held make gold n d = none
      ↔ held = 0 ∧ make = none ∧ (gold = none ∨ n = 0) := by
  unfold consumablePrice
  by_cases hh : 0 < held
  · simp only [hh, if_true]
    constructor
    · intro h; cases h
    · intro h; omega
  · simp only [hh, if_false]
    have h0 : held = 0 := by omega
    cases make with
    | none =>
      cases gold with
      | none => simp [optMin, buySeconds, h0]
      | some g =>
        by_cases hn : n = 0
        · simp [optMin, buySeconds, hn, h0]
        · simp [optMin, buySeconds, hn]
    | some m =>
      constructor
      · intro h
        cases hb : buySeconds gold n d <;> rw [hb] at h <;> cases h
      · intro h; cases h.2.1

/-- A CHEAPER WAY TO MAKE IT NEVER RAISES THE PRICE. -/
theorem mono_make (held : Nat) (make make' : Option Q) (gold : Option Nat) (n d : Nat)
    (hpos : posDen make') (h : optLe make' make) :
    optLe (consumablePrice held make' gold n d) (consumablePrice held make gold n d) := by
  unfold consumablePrice
  split
  · exact qle_refl _
  · exact optMin_mono_left _ _ _ hpos h

/-- A CHEAPER GOLD PRICE NEVER RAISES THE PRICE. -/
theorem mono_gold (held : Nat) (make : Option Q) (gold gold' : Option Nat) (n d : Nat)
    (h : goldLe gold' gold) :
    optLe (consumablePrice held make gold' n d) (consumablePrice held make gold n d) := by
  unfold consumablePrice
  split
  · exact qle_refl _
  · apply optMin_mono_right _ _ _ (buySeconds_posDen gold' n d)
    cases gold with
    | none => cases buySeconds gold' n d <;> trivial
    | some g =>
      cases gold' with
      | none => exact absurd h id
      | some g' =>
        have hg : g' ≤ g := h
        unfold buySeconds
        by_cases hn : n = 0
        · simp [hn, optLe]
        · simp only [hn, if_false]
          show g' * d * n ≤ g * d * n
          exact Nat.mul_le_mul_right _ (Nat.mul_le_mul_right _ hg)

/-! ## Witnesses -/

-- Held: free whatever the sides.
example : consumablePrice 3 (some (90, 1)) (some 40) 1 2 = some (0, 1) := by decide
-- A 3-action walk (90 s) against 40 gold at 1/2 gold per second (80 s): buy.
example : consumablePrice 0 (some (90, 1)) (some 40) 1 2 = some (80, 1) := by decide
-- No grind target (rate 0): buying is unpriceable, making is the price.
example : consumablePrice 0 (some (90, 1)) (some 40) 0 1 = some (90, 1) := by decide
-- Nothing serves it.
example : consumablePrice 0 none none 1 2 = none := by decide

end Formal.ConsumablePrice
