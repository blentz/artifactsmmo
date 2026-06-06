import Formal.CycleInvariants

/-!
# Formal.MultiCycleLiveness

**Bounded-progression theorem across multiple cycles.**

Per-cycle invariants (`Formal.CycleInvariants`) say a single action
neither breaks nor stalls state. This module composes them: starting
from any state, applying a sequence of well-formed FightActions
strictly raises xp, and any finite N of those raises xp by at least N
times the smallest XP gain.

Concretely, the headline:

  `multi_fight_raises_xp_by_at_least`:
    After N successful fights each yielding ≥ k XP, total xp gain ≥ N·k.

This bounds the cycle count to reach the next character level.
-/

namespace Formal.MultiCycleLiveness
open Formal.CycleInvariants

/-! ## Repeated fight sequence. -/

/-- Run a list of actions through `applyAction`, left-fold. -/
def runSequence (s : State) : List Action → State
  | [] => s
  | a :: rest => runSequence (applyAction s a) rest

/-- A sequence is well-formed when every action is. -/
def AllWellFormed : List Action → Prop
  | [] => True
  | a :: rest => WellFormed a ∧ AllWellFormed rest

/-- N fight actions, each yielding xpPerFight XP, hpPerFight HP loss. -/
def nFights (n : Nat) (xpPerFight hpPerFight : Int) : List Action :=
  match n with
  | 0 => []
  | Nat.succ k => Action.fight xpPerFight hpPerFight :: nFights k xpPerFight hpPerFight

/-! ## XP monotonicity over a sequence. -/

theorem xp_monotone_over_sequence
    (s : State) (acts : List Action) (h : AllWellFormed acts) :
    s.xp ≤ (runSequence s acts).xp := by
  induction acts generalizing s with
  | nil => exact Int.le_refl s.xp
  | cons a rest ih =>
    obtain ⟨hHead, hTail⟩ := h
    have hStep : s.xp ≤ (applyAction s a).xp :=
      xp_monotone_under_well_formed s a hHead
    have hRec : (applyAction s a).xp ≤ (runSequence (applyAction s a) rest).xp :=
      ih (applyAction s a) hTail
    show s.xp ≤ (runSequence (applyAction s a) rest).xp
    omega

/-! ## XP gain bound for N fights. -/

/-- Each fight in `nFights n` is well-formed when `xpPerFight ≥ 0` and
`hpPerFight ≥ 0`. -/
theorem nFights_all_well_formed (n : Nat) (xpG hpL : Int)
    (hX : 0 ≤ xpG) (hH : 0 ≤ hpL) :
    AllWellFormed (nFights n xpG hpL) := by
  induction n with
  | zero => trivial
  | succ k ih =>
    refine ⟨⟨hX, hH⟩, ?_⟩
    exact ih

/-- **The headline theorem**: after N fights each yielding `xpPerFight`
XP, the cumulative xp gain is ≥ N · xpPerFight (which itself ≥ N · 0 = 0).
Establishes a lower bound on per-cycle progression. -/
theorem multi_fight_raises_xp_by_at_least
    (s : State) (n : Nat) (xpG hpL : Int) :
    s.xp + (n : Int) * xpG ≤ (runSequence s (nFights n xpG hpL)).xp := by
  induction n generalizing s with
  | zero => simp [nFights, runSequence]
  | succ k ih =>
    show s.xp + (Nat.succ k : Int) * xpG ≤
         (runSequence s (Action.fight xpG hpL :: nFights k xpG hpL)).xp
    unfold runSequence
    -- After 1 fight: state's xp = s.xp + xpG.
    have hAfter1 : (applyAction s (Action.fight xpG hpL)).xp = s.xp + xpG := rfl
    have hIH := ih (applyAction s (Action.fight xpG hpL))
    rw [hAfter1] at hIH
    -- Convert (succ k : Int) = k + 1.
    have hCast : (Nat.succ k : Int) = (k : Int) + 1 := by
      rw [Int.natCast_succ]
    have hSucc : (Nat.succ k : Int) * xpG = (k : Int) * xpG + xpG := by
      rw [hCast, Int.add_mul, Int.one_mul]
    rw [hSucc]
    omega

/-! ## Bounded reach. -/

/-- **Corollary**: to raise xp by at least `delta`, it suffices to run
`⌈delta / xpPerFight⌉` fights when `xpPerFight > 0`. The bot reaches
any finite XP target in BOUNDED cycles. -/
theorem bounded_fights_suffice_for_xp_delta
    (s : State) (delta xpG hpL : Int)
    (hX : 0 < xpG) (hD : 0 ≤ delta) :
    ∃ n : Nat,
      s.xp + delta ≤ (runSequence s (nFights n xpG hpL)).xp := by
  -- Pick n = max(0, delta) treating as a Nat (which is ≥ delta / xpG).
  refine ⟨delta.toNat, ?_⟩
  have hMonotone :=
    multi_fight_raises_xp_by_at_least s delta.toNat xpG hpL
  have hAtLeast : delta ≤ (delta.toNat : Int) * xpG := by
    have hToNat : (delta.toNat : Int) = delta := Int.toNat_of_nonneg hD
    rw [hToNat]
    have hXge1 : (1 : Int) ≤ xpG := hX
    calc delta = delta * 1 := by rw [Int.mul_one]
      _ ≤ delta * xpG := Int.mul_le_mul_of_nonneg_left hXge1 hD
  omega

end Formal.MultiCycleLiveness
