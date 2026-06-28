-- @concept: items, gear @property: validity, dominance
import Formal.EquipValueAugmented
import Formal.PurposeRouting
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

/-! ### Combat & Gather purposes: `gear_value(Combat/Gather)` unifies the
per-monster scorers.

The Python `gear_value(Combat(...))` dispatches on `stats.type_`: the weapon slot
returns `weapon_score` (the `WScore` atom, which the Python weapon path further
augments with the non-tool bonus — `PurposeRouting.combatScore`), every other
(armor) slot returns `armor_score` (`AScore`); `gear_value(Gather(skill))`
returns `gather_score` (`PurposeRouting.gatherScore`). The defs below mirror that
dispatch over the existing `EquipmentScoring`/`PurposeRouting` score atoms, so the
four EquipmentScoring trio role theorems restate verbatim on the gear_value forms.

LAYERING: gear_value → scoring (one direction). The role theorems are the EXISTING
`EquipmentScoring.weapon_score_nonneg` / `GearPolicy.armor_score_nonneg` /
`EquipmentScoring.pickslot_score_optimal` /
`PurposeRouting.pickGatherSlot_score_optimal`, untouched; the restatements here
are corollaries that unfold to them. -/

open Formal.EquipmentScoring

/-- The `gear_value(Combat)` score atom, dispatched on whether the item fills the
weapon slot (Python `stats.type_ == "weapon"`): `WScore` against the monster's
resistance for the weapon slot, `AScore` against the monster's attack otherwise.
Mirrors `EquipmentScoring.WScore`/`AScore`. -/
def combatValue (isWeapon : Bool) (item : Item)
    (monsterAtk monsterRes : ElemStats) : Int :=
  if isWeapon then WScore item monsterRes else AScore item monsterAtk

/-- The `gear_value(Gather)` score atom: the signed per-skill effect the gather
picker minimizes (more negative = better). Mirrors `PurposeRouting.gatherScore`. -/
def gatherValue (skillEffect : Item → Int) (item : Item) : Int :=
  Formal.PurposeRouting.gatherScore skillEffect item

/-- `weapon_score_nonneg` restated on the `gear_value(Combat)` weapon form: the
weapon-slot combat value is `≥ 0` under nonneg per-element attacks and crit.
Unfolds to `EquipmentScoring.WScore`; discharged by the existing clamp theorem. -/
theorem combatValue_weapon_nonneg (item : Item) (monsterAtk monsterRes : ElemStats)
    (hatk : ∀ e ∈ elements, 0 ≤ elemGet item.attack e) (hcrit : 0 ≤ item.crit) :
    0 ≤ combatValue true item monsterAtk monsterRes := by
  unfold combatValue
  exact weapon_score_nonneg item monsterRes hatk hcrit

/-- `armor_score_nonneg` restated on the `gear_value(Combat)` armor form. Unfolds
to `EquipmentScoring.AScore`; discharged by `GearPolicy.armor_score_nonneg`. -/
theorem combatValue_armor_nonneg (item : Item) (monsterAtk monsterRes : ElemStats)
    (hAtk : ∀ e ∈ elements, 0 ≤ elemGet monsterAtk e)
    (hRes : ∀ e ∈ elements, 0 ≤ elemGet item.resistance e)
    (hUtil : 0 ≤ item.flatUtil) :
    0 ≤ combatValue false item monsterAtk monsterRes := by
  unfold combatValue
  exact Formal.GearPolicy.armor_score_nonneg item monsterAtk hAtk hRes hUtil

/-- `pickslot_score_optimal` restated on the `gear_value(Combat)` weapon form: the
weapon-slot argmax dominates every feasible candidate's combat value. The combat
purpose just instantiates the parametric `score` with `combatValue true`. -/
theorem combatValue_pickslot_optimal (playerLevel : Int)
    (monsterAtk monsterRes : ElemStats) (items : List Item) (c : Item) (cs : List Item)
    (hcand : candidates playerLevel items = c :: cs) :
    ∀ y ∈ candidates playerLevel items,
      combatValue true y monsterAtk monsterRes
        ≤ combatValue true
            (argmaxBy (fun i => combatValue true i monsterAtk monsterRes) c cs)
            monsterAtk monsterRes :=
  pickslot_score_optimal (fun i => combatValue true i monsterAtk monsterRes)
    playerLevel items c cs hcand

/-- `pickGatherSlot_score_optimal` restated on the `gear_value(Gather)` form: the
gather pick minimizes `gatherValue` over feasible candidates. Unfolds to
`PurposeRouting.gatherScore`; discharged by the existing optimality theorem. -/
theorem gatherValue_pickGatherSlot_optimal (skillEffect : Item → Int) (playerLevel : Int)
    (items : List Item) (picked : Item)
    (hPick : Formal.PurposeRouting.pickGatherSlot skillEffect playerLevel none items
              = some picked) :
    ∀ c ∈ candidates playerLevel items,
      gatherValue skillEffect picked ≤ gatherValue skillEffect c := by
  unfold gatherValue
  exact Formal.PurposeRouting.pickGatherSlot_score_optimal skillEffect playerLevel
    items picked hPick

/-! ### Alignment with `PurposeRouting`'s dispatch scores. -/

/-- Alignment: `PurposeRouting.combatScore` (the augmented Python `weapon_score`)
is exactly `2 * (weapon `gear_value(Combat)` atom) + nonToolBonus`. The `monsterAtk`
argument is irrelevant to the weapon branch. -/
theorem combatScore_eq_combatValue (monsterAtk monsterRes : ElemStats)
    (ci : Formal.PurposeRouting.CombatItem) :
    Formal.PurposeRouting.combatScore monsterRes ci
      = 2 * combatValue true ci.base monsterAtk monsterRes
          + Formal.PurposeRouting.nonToolBonus ci := by
  unfold combatValue Formal.PurposeRouting.combatScore
  rfl

/-- Alignment: the `gear_value(Gather)` atom IS `PurposeRouting.gatherScore`. -/
theorem gatherValue_eq_gatherScore (skillEffect : Item → Int) (item : Item) :
    gatherValue skillEffect item = Formal.PurposeRouting.gatherScore skillEffect item :=
  rfl

end Formal.GearValue
