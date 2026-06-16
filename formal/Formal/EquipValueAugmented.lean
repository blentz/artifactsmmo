-- @concept: items, characters @property: dominance, monotonicity
/-!
# Formal.EquipValueAugmented

**Correctness of the augmented `equip_value` formula.**

The Python `tiers/equip_value.py:equip_value` now returns
  2 * (attack + resistance + hp_restore + hp_bonus + dmg + critical_strike)
  + nonToolBonus
where `nonToolBonus = 0 if subtype == "tool" else 1`.

The augmentation was forced by two trace bugs (2026-06-06 09:59 and
12:28): copper_boots(hp_bonus=10), copper_helmet(dmg=3,hp_bonus=20),
copper_dagger(crit=35) all scored equip_value ≤ 1 under the prior
formula (which summed only attack+resistance+hp_restore). Armor was
invisible to the ranker.

This module proves:

1. The composite raw signal is monotone non-decreasing in every
   modeled contributor (attack, resistance, hp_restore, hp_bonus,
   dmg, critical_strike). More of any positive stat never lowers the
   score.
2. The 2x factor protects every strict raw-signal inequality from
   the +0/+1 tiebreaker (same property as G2's `combatScore`).
3. Non-tool weapons strictly outrank equally-scored tools.
4. Zero-stat items score exactly 1 (non-tool) or 0 (tool).
-/

namespace Formal.EquipValueAugmented

/-! ## Composite raw signal. -/

structure RawStats where
  attack       : Int
  resistance   : Int
  hpRestore    : Int
  hpBonus      : Int
  dmg          : Int
  crit         : Int
  wisdom       : Int
  prospecting  : Int
deriving Repr, DecidableEq

def rawSum (s : RawStats) : Int :=
  s.attack + s.resistance + s.hpRestore + s.hpBonus + s.dmg + s.crit
    + s.wisdom + s.prospecting

def nonToolBonus (isTool : Bool) : Int := if isTool then 0 else 1

def equipValue (s : RawStats) (isTool : Bool) : Int :=
  2 * rawSum s + nonToolBonus isTool

/-! ## Monotonicity. -/

theorem nonToolBonus_nonneg (isTool : Bool) : 0 ≤ nonToolBonus isTool := by
  unfold nonToolBonus; split <;> decide

theorem nonToolBonus_le_one (isTool : Bool) : nonToolBonus isTool ≤ 1 := by
  unfold nonToolBonus; split <;> decide

theorem rawSum_mono_in_attack (s : RawStats) (a' : Int) (h : s.attack ≤ a') :
    rawSum s ≤ rawSum { s with attack := a' } := by
  unfold rawSum; simp; omega

theorem rawSum_mono_in_resistance (s : RawStats) (r' : Int) (h : s.resistance ≤ r') :
    rawSum s ≤ rawSum { s with resistance := r' } := by
  unfold rawSum; simp; omega

theorem rawSum_mono_in_hpBonus (s : RawStats) (h' : Int) (h : s.hpBonus ≤ h') :
    rawSum s ≤ rawSum { s with hpBonus := h' } := by
  unfold rawSum; simp; omega

theorem rawSum_mono_in_crit (s : RawStats) (c' : Int) (h : s.crit ≤ c') :
    rawSum s ≤ rawSum { s with crit := c' } := by
  unfold rawSum; simp; omega

theorem rawSum_mono_in_dmg (s : RawStats) (d' : Int) (h : s.dmg ≤ d') :
    rawSum s ≤ rawSum { s with dmg := d' } := by
  unfold rawSum; simp; omega

theorem rawSum_mono_in_wisdom (s : RawStats) (w' : Int) (h : s.wisdom ≤ w') :
    rawSum s ≤ rawSum { s with wisdom := w' } := by
  unfold rawSum; simp; omega

theorem rawSum_mono_in_prospecting (s : RawStats) (p' : Int) (h : s.prospecting ≤ p') :
    rawSum s ≤ rawSum { s with prospecting := p' } := by
  unfold rawSum; simp; omega

/-! ## Strict-order preservation. -/

/-- 2x factor preserves strict rawSum inequalities through the +0/+1
tiebreaker. Same property as `PurposeRouting.combatScore_strict_of_strict_wscore`. -/
theorem equipValue_strict_of_strict_raw
    (a b : RawStats) (aTool bTool : Bool)
    (hStrict : rawSum a < rawSum b) :
    equipValue a aTool < equipValue b bTool := by
  unfold equipValue
  have hA0 : 0 ≤ nonToolBonus aTool := nonToolBonus_nonneg aTool
  have hA1 : nonToolBonus aTool ≤ 1 := nonToolBonus_le_one aTool
  have hB0 : 0 ≤ nonToolBonus bTool := nonToolBonus_nonneg bTool
  have hB1 : nonToolBonus bTool ≤ 1 := nonToolBonus_le_one bTool
  omega

/-! ## Tie-break to non-tool. -/

/-- Equal raw scores, one is tool and the other not: non-tool strictly
outranks. Same property as
`PurposeRouting.combatScore_tiebreaks_nontool_over_tool`. -/
theorem equipValue_tiebreaks_nontool_over_tool
    (toolStats nonToolStats : RawStats)
    (hTie : rawSum toolStats = rawSum nonToolStats) :
    equipValue toolStats true < equipValue nonToolStats false := by
  unfold equipValue nonToolBonus
  rw [hTie]
  rw [if_pos rfl, if_neg (by decide)]
  omega

/-! ## Boundary values. -/

def zeroStats : RawStats :=
  { attack := 0, resistance := 0, hpRestore := 0,
    hpBonus := 0, dmg := 0, crit := 0, wisdom := 0, prospecting := 0 }

theorem rawSum_zero_at_zeroStats : rawSum zeroStats = 0 := by
  unfold rawSum zeroStats
  decide

/-- A zero-stat non-tool scores exactly 1 (the nonToolBonus floor). -/
theorem equipValue_nontool_zero_eq_one :
    equipValue zeroStats false = 1 := by
  unfold equipValue
  rw [rawSum_zero_at_zeroStats]
  unfold nonToolBonus
  decide

/-- A zero-stat tool scores exactly 0. -/
theorem equipValue_tool_zero_eq_zero :
    equipValue zeroStats true = 0 := by
  unfold equipValue
  rw [rawSum_zero_at_zeroStats]
  unfold nonToolBonus
  decide

/-! ## Trace-mirror theorems.

The actual values that bit the bot in trace 2026-06-06 12:28: -/

/-- copper_boots had hp_bonus=10, all else 0. raw=10, augmented=21. -/
theorem copper_boots_value :
    equipValue { attack := 0, resistance := 0, hpRestore := 0,
                 hpBonus := 10, dmg := 0, crit := 0, wisdom := 0, prospecting := 0 } false = 21 := by
  unfold equipValue rawSum nonToolBonus
  decide

/-- copper_helmet: hp_bonus=20, dmg=3. raw=23, augmented=47. -/
theorem copper_helmet_value :
    equipValue { attack := 0, resistance := 0, hpRestore := 0,
                 hpBonus := 20, dmg := 3, crit := 0, wisdom := 0, prospecting := 0 } false = 47 := by
  unfold equipValue rawSum nonToolBonus
  decide

/-- copper_dagger: attack=6 (air), crit=35. raw=41, augmented=83. -/
theorem copper_dagger_value :
    equipValue { attack := 6, resistance := 0, hpRestore := 0,
                 hpBonus := 0, dmg := 0, crit := 35, wisdom := 0, prospecting := 0 } false = 83 := by
  unfold equipValue rawSum nonToolBonus
  decide

/-- fishing_net: attack=5 (water), subtype=tool. raw=5, augmented=10. -/
theorem fishing_net_value :
    equipValue { attack := 5, resistance := 0, hpRestore := 0,
                 hpBonus := 0, dmg := 0, crit := 0, wisdom := 0, prospecting := 0 } true = 10 := by
  unfold equipValue rawSum nonToolBonus
  decide

/-- novice_guide artifact: hp 25, wisdom 25, prospecting 25, no combat stats.
raw=75, augmented=151. The trace bug: valued 0 before wisdom/prospecting were
modeled → discarded; now a high-value non-tool. -/
theorem novice_guide_value :
    equipValue { attack := 0, resistance := 0, hpRestore := 0,
                 hpBonus := 25, dmg := 0, crit := 0, wisdom := 25, prospecting := 25 } false = 151 := by
  unfold equipValue rawSum nonToolBonus
  decide

/-- copper_dagger strictly outranks fishing_net. The trace bug closure. -/
theorem copper_dagger_strictly_outranks_fishing_net :
    equipValue { attack := 5, resistance := 0, hpRestore := 0,
                 hpBonus := 0, dmg := 0, crit := 0, wisdom := 0, prospecting := 0 } true <
    equipValue { attack := 6, resistance := 0, hpRestore := 0,
                 hpBonus := 0, dmg := 0, crit := 35, wisdom := 0, prospecting := 0 } false := by
  unfold equipValue rawSum nonToolBonus
  decide

end Formal.EquipValueAugmented
