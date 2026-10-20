-- @concept: combat, cost @property: monotonicity, validity
/-
The seconds a fight costs, from its length (spec 2026-10-18 §2.9,
`src/artifactsmmo_cli/ai/fight_seconds_core.py`).

    fightSeconds = max(floor, turns × sTurn × (1 − h·haste))

## The model

A non-negative rational is an unreduced `(numerator, denominator)` pair compared
by cross-multiplication (`qle`), as `Formal.ConsumablePrice` does, so the model
never divides. `1 − h·haste` with `h = (hn, hd)` is `(hd − hn·haste) / hd`,
truncated at 0 by `Nat` subtraction: a haste that would remove the whole fight
leaves a raw time of 0, and the floor (never negative) wins, which is the
Python's `max` over a negative product.

## Theorems

* `floor_le` — never below the floor;
* `mono_turns` — more turns never cost fewer seconds;
* `anti_haste` — more haste never costs more seconds (`h ≥ 0` is the `Nat`
  domain).
-/

namespace Formal.FightSeconds

/-- A non-negative rational, `(numerator, denominator)`, unreduced. -/
abbrev Q := Nat × Nat

/-- `a ≤ b`, cross-multiplied. -/
def qle (a b : Q) : Prop := a.1 * b.2 ≤ b.1 * a.2

instance (a b : Q) : Decidable (qle a b) := inferInstanceAs (Decidable (_ ≤ _))

/-- The larger of two rationals, the second on a tie. -/
def qmax (a b : Q) : Q := if qle a b then b else a

/-- `turns × sTurn × (1 − h·haste)`, the hasted share truncated at 0. -/
def raw (turns sTurn h : Q) (haste : Nat) : Q :=
  (turns.1 * (sTurn.1 * (h.2 - h.1 * haste)), turns.2 * (sTurn.2 * h.2))

/-- A fight's seconds (see the module doc). -/
def fightSeconds (turns sTurn h : Q) (haste : Nat) (floor : Q) : Q :=
  qmax floor (raw turns sTurn h haste)

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

theorem le_qmax_left (a b : Q) : qle a (qmax a b) := by
  unfold qmax
  split
  · assumption
  · exact qle_refl a

theorem le_qmax_right (a b : Q) : qle b (qmax a b) := by
  unfold qmax
  split
  · exact qle_refl b
  · exact qle_of_not a b (by assumption)

/-- `qmax f` is monotone in its second argument, given a positive denominator
on the smaller side. -/
theorem qmax_mono (f a b : Q) (ha : 0 < a.2) (hab : qle a b) : qle (qmax f a) (qmax f b) := by
  unfold qmax
  by_cases hfa : qle f a
  · rw [if_pos hfa]
    by_cases hfb : qle f b
    · rw [if_pos hfb]; exact hab
    · exact absurd (qle_trans f a b ha hfa hab) hfb
  · rw [if_neg hfa]
    by_cases hfb : qle f b
    · rw [if_pos hfb]; exact hfb
    · rw [if_neg hfb]; exact qle_refl f

/-- Never below the floor. -/
theorem floor_le (turns sTurn h : Q) (haste : Nat) (floor : Q) :
    qle floor (fightSeconds turns sTurn h haste floor) :=
  le_qmax_left _ _

theorem raw_den_pos (turns sTurn h : Q) (haste : Nat) (ht : 0 < turns.2) (hs : 0 < sTurn.2)
    (hh : 0 < h.2) : 0 < (raw turns sTurn h haste).2 :=
  Nat.mul_pos ht (Nat.mul_pos hs hh)

/-- Scaling both sides of a cross-multiplied comparison by `k` and `d`. -/
theorem qle_scale (x1 x2 y1 y2 k d : Nat) (h : x1 * y2 ≤ y1 * x2) :
    qle (x1 * k, x2 * d) (y1 * k, y2 * d) := by
  unfold qle
  show x1 * k * (y2 * d) ≤ y1 * k * (x2 * d)
  calc x1 * k * (y2 * d) = (x1 * y2) * (k * d) := by
          rw [Nat.mul_assoc, Nat.mul_left_comm k, ← Nat.mul_assoc]
    _ ≤ (y1 * x2) * (k * d) := Nat.mul_le_mul_right _ h
    _ = y1 * k * (x2 * d) := by
          rw [Nat.mul_assoc, Nat.mul_left_comm x2, ← Nat.mul_assoc]

/-- More turns never cost fewer seconds. -/
theorem mono_turns (t1 t2 sTurn h : Q) (haste : Nat) (floor : Q)
    (h1 : 0 < t1.2) (hs : 0 < sTurn.2) (hh : 0 < h.2) (ht : qle t1 t2) :
    qle (fightSeconds t1 sTurn h haste floor) (fightSeconds t2 sTurn h haste floor) :=
  qmax_mono floor _ _ (raw_den_pos t1 sTurn h haste h1 hs hh) (qle_scale _ _ _ _ _ _ ht)

/-- More haste never costs more seconds. -/
theorem anti_haste (turns sTurn h : Q) (a1 a2 : Nat) (floor : Q)
    (ht : 0 < turns.2) (hs : 0 < sTurn.2) (hh : 0 < h.2) (ha : a1 ≤ a2) :
    qle (fightSeconds turns sTurn h a2 floor) (fightSeconds turns sTurn h a1 floor) := by
  apply qmax_mono floor _ _ (raw_den_pos turns sTurn h a2 ht hs hh)
  unfold raw qle
  show turns.1 * (sTurn.1 * (h.2 - h.1 * a2)) * (turns.2 * (sTurn.2 * h.2))
      ≤ turns.1 * (sTurn.1 * (h.2 - h.1 * a1)) * (turns.2 * (sTurn.2 * h.2))
  apply Nat.mul_le_mul_right
  apply Nat.mul_le_mul_left
  apply Nat.mul_le_mul_left
  exact Nat.sub_le_sub_left (Nat.mul_le_mul_left _ ha) _

end Formal.FightSeconds
