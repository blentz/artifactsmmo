-- @concept: items, gear @property: unified-ruler, decomposition
import Formal.EquipValueAugmented
/-!
# Formal.GearValue

**The unified gear value ruler core: `combatRaw` + `rankValue`.**

The Python `ai/gear_value_core.py` extracts the shared combat-signal atom
(`combat_raw`) and the monster-independent `Rank` ruler (`rank_value`) so the
`equip_value` ranker and `strategic_value` share ONE computation. This module
mirrors that core and pins it to the existing augmented-equip-value model:

* `combatRaw` is the genuine-combat slice of `rawSum` (drops the efficiency
  utility stats wisdom/prospecting/inventorySpace/haste).
* `rawSum_decomp` proves `rawSum = combatRaw + (the four efficiency stats)` —
  the decomposition that justifies the split.
* `rankValue` recomposes them as `2 * (combatRaw + efficiency) + nonToolBonus`
  and `rank_eq_equipValue` proves it is bit-identical to
  `EquipValueAugmented.equipValue` (so the 7 `equip_value` callers are
  unaffected when the Python `equip_value` delegates to `gear_value(_, Rank)`).
-/

namespace Formal.GearValue

open Formal.EquipValueAugmented

/-- The genuine-combat signal shared by the Rank ruler and strategic_value:
the combat slice of `rawSum` (attack, resistance, hp, dmg, crit, lifesteal,
combat-buff), excluding the efficiency utility stats. -/
def combatRaw (s : RawStats) : Int :=
  s.attack + s.resistance + s.hpRestore + s.hpBonus + s.dmg + s.crit
    + s.lifesteal + s.combatBuff

/-- The unified Rank ruler: `2 * (combatRaw + efficiency) + nonToolBonus`. -/
def rankValue (s : RawStats) (isTool : Bool) : Int :=
  2 * (combatRaw s + s.wisdom + s.prospecting + s.inventorySpace + s.haste)
    + nonToolBonus isTool

/-- `rawSum` splits into the combat signal plus the four efficiency stats. -/
theorem rawSum_decomp (s : RawStats) :
    rawSum s = combatRaw s + s.wisdom + s.prospecting + s.inventorySpace + s.haste := by
  unfold rawSum combatRaw
  omega

/-- The Rank ruler is bit-identical to the augmented `equipValue`. -/
theorem rank_eq_equipValue (s : RawStats) (isTool : Bool) :
    rankValue s isTool = equipValue s isTool := by
  unfold rankValue equipValue
  rw [rawSum_decomp]

end Formal.GearValue
