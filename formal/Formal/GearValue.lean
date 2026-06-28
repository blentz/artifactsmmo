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

/-! ### Unified purpose-parameterized per-slot picker (Task 3, 2026-06-28).

The Python `loadout_picker.pick_loadout(purpose)` maximizes a SINGLE per-slot
benefit `_benefit(stats, purpose)`: `gear_value(stats, purpose)` for Combat and
Rank, and `-gear_value(stats, Gather skill)` for Gather (negate the signed gather
score so a bigger cooldown reduction is a bigger benefit). This section mirrors
that with ONE picker over ANY benefit function, and folds the previously-separate
`PurposeRouting.pickGatherSlot` *argmin* into the unified *argmax* via the proven
argmax/argmin duality — so no optimality content is lost. -/

/-- The per-task gear purpose, mirroring the Python `Combat`/`Rank`/`Gather`
value objects. `combat` carries the monster's attack/resistance and the slot's
weapon flag; `rank` carries the monster-independent per-item ruler (the genuine
`rankValue ∘ stats`, modeled as a per-item integer because the picker is
parametric in ANY per-item benefit — `rankValue`'s bit-identity to `equipValue`
is pinned separately by `rank_eq_equipValue`); `gather` carries the skill effect
the gather picker minimizes. -/
inductive Purpose where
  | combat (monsterAtk monsterRes : ElemStats) (isWeapon : Bool)
  | rank   (rankOf : Item → Int)
  | gather (skillEffect : Item → Int)

/-- The SINGLE per-slot benefit the unified picker MAXIMIZES (argmax), dispatched
on purpose. Combat/Rank use `gear_value` directly; Gather negates `gatherValue`
(`gear_value(Gather)`), so the gather argmin becomes a unified argmax. -/
def purposeBenefit : Purpose → Item → Int
  | .combat monsterAtk monsterRes isWeapon =>
      fun i => combatValue isWeapon i monsterAtk monsterRes
  | .rank rankOf => rankOf
  | .gather skillEffect => fun i => - gatherValue skillEffect i

/-- The unified purpose picker: the existing parametric `pickSlot` driven by the
purpose benefit. Combat callers, the Rank ranker, and the (folded-in) gather path
all route through this ONE picker. -/
def pickSlotForPurpose (p : Purpose) (playerLevel : Int)
    (current : Option Item) (items : List Item) : Option Item :=
  pickSlot (purposeBenefit p) playerLevel current items

/-- **Unified per-slot optimality, ∀ purpose**: the freshly-picked best maximizes
the purpose benefit over every feasible candidate. A direct instance of the
parametric `EquipmentScoring.pickslot_score_optimal` — the SAME proof now covers
Combat, Rank, and Gather. -/
theorem pickSlot_score_optimal_purpose (p : Purpose) (playerLevel : Int)
    (items : List Item) (c : Item) (cs : List Item)
    (hcand : candidates playerLevel items = c :: cs) :
    ∀ y ∈ candidates playerLevel items,
      purposeBenefit p y ≤ purposeBenefit p (argmaxBy (purposeBenefit p) c cs) :=
  pickslot_score_optimal (purposeBenefit p) playerLevel items c cs hcand

/-- Combat instance of the unified optimality (weapon OR armor slot): subsumes the
existing `combatValue_pickslot_optimal`. -/
theorem pickSlot_purpose_combat_optimal (monsterAtk monsterRes : ElemStats)
    (isWeapon : Bool) (playerLevel : Int) (items : List Item) (c : Item) (cs : List Item)
    (hcand : candidates playerLevel items = c :: cs) :
    ∀ y ∈ candidates playerLevel items,
      combatValue isWeapon y monsterAtk monsterRes
        ≤ combatValue isWeapon
            (argmaxBy (purposeBenefit (.combat monsterAtk monsterRes isWeapon)) c cs)
            monsterAtk monsterRes :=
  pickSlot_score_optimal_purpose (.combat monsterAtk monsterRes isWeapon)
    playerLevel items c cs hcand

/-- Rank instance of the unified optimality: the monster-independent ruler's
argmax dominates every feasible candidate. -/
theorem pickSlot_purpose_rank_optimal (rankOf : Item → Int) (playerLevel : Int)
    (items : List Item) (c : Item) (cs : List Item)
    (hcand : candidates playerLevel items = c :: cs) :
    ∀ y ∈ candidates playerLevel items,
      rankOf y ≤ rankOf (argmaxBy (purposeBenefit (.rank rankOf)) c cs) :=
  pickSlot_score_optimal_purpose (.rank rankOf) playerLevel items c cs hcand

/-- **Argmax/argmin duality** (the load-bearing fold): maximizing the negated
score selects exactly the `argminBy` item — the same leftmost-on-tie winner,
because the swap test `-score x > -score best` IS `score x < score best`. -/
theorem argmaxBy_neg_eq_argminBy (score : Item → Int) (best : Item) (xs : List Item) :
    argmaxBy (fun i => - score i) best xs
      = Formal.PurposeRouting.argminBy score best xs := by
  induction xs generalizing best with
  | nil => rfl
  | cons x xs ih =>
    simp only [argmaxBy, Formal.PurposeRouting.argminBy]
    by_cases h : score x < score best
    · rw [if_pos h, if_pos (show - score x > - score best by omega)]
      exact ih x
    · rw [if_neg h, if_neg (show ¬ (- score x > - score best) by omega)]
      exact ih best

/-- **Gather fold via duality** — optimality: the unified picker under the Gather
benefit (`-gatherValue`) MINIMIZES `gatherValue` over the feasible candidates,
recovering the `PurposeRouting.pickGatherSlot_score_optimal` content with no
optimality lost. -/
theorem pickSlot_purpose_gather_optimal (skillEffect : Item → Int) (playerLevel : Int)
    (items : List Item) (c : Item) (cs : List Item)
    (hcand : candidates playerLevel items = c :: cs) :
    ∀ y ∈ candidates playerLevel items,
      gatherValue skillEffect (argmaxBy (purposeBenefit (.gather skillEffect)) c cs)
        ≤ gatherValue skillEffect y := by
  intro y hy
  have h := pickSlot_score_optimal_purpose (.gather skillEffect) playerLevel items c cs hcand y hy
  have h' : - gatherValue skillEffect y
      ≤ - gatherValue skillEffect (argmaxBy (purposeBenefit (.gather skillEffect)) c cs) := h
  omega

/-- **Gather fold via duality** — picker identity: routing the Gather purpose
through the unified `pickSlotForPurpose` produces EXACTLY the dedicated
`PurposeRouting.pickGatherSlot` output, for any candidate list and current item.
The complete fold — the dead argmin picker is subsumed. -/
theorem pickSlotForPurpose_gather_eq (skillEffect : Item → Int) (playerLevel : Int)
    (current : Option Item) (items : List Item) :
    pickSlotForPurpose (.gather skillEffect) playerLevel current items
      = Formal.PurposeRouting.pickGatherSlot skillEffect playerLevel current items := by
  unfold pickSlotForPurpose pickSlot Formal.PurposeRouting.pickGatherSlot
  cases hC : candidates playerLevel items with
  | nil => rfl
  | cons c cs =>
    have hbest : argmaxBy (purposeBenefit (.gather skillEffect)) c cs
        = Formal.PurposeRouting.argminBy
            (Formal.PurposeRouting.gatherScore skillEffect) c cs :=
      argmaxBy_neg_eq_argminBy (Formal.PurposeRouting.gatherScore skillEffect) c cs
    simp only [hbest]
    cases current with
    | none => rfl
    | some cur =>
      simp only [purposeBenefit, gatherValue]
      by_cases h : Formal.PurposeRouting.gatherScore skillEffect
          (Formal.PurposeRouting.argminBy (Formal.PurposeRouting.gatherScore skillEffect) c cs)
          < Formal.PurposeRouting.gatherScore skillEffect cur
      · rw [if_pos h, if_pos (show - Formal.PurposeRouting.gatherScore skillEffect
            (Formal.PurposeRouting.argminBy (Formal.PurposeRouting.gatherScore skillEffect) c cs)
            > - Formal.PurposeRouting.gatherScore skillEffect cur by omega)]
      · rw [if_neg h, if_neg (show ¬ (- Formal.PurposeRouting.gatherScore skillEffect
            (Formal.PurposeRouting.argminBy (Formal.PurposeRouting.gatherScore skillEffect) c cs)
            > - Formal.PurposeRouting.gatherScore skillEffect cur) by omega)]

end Formal.GearValue
