-- @concept: items, gear @property: validity, dominance
import Formal.EquipValueAugmented
import Formal.PurposeRouting
/-!
# Formal.GearValue

**ONE gear ruler. `Rank` is `Combat` against a canonical adversary.**

The Python `ai/gear_value.gear_value(stats, purpose)` answers "which piece is
better" with a SINGLE algorithm — `weapon_score` for the weapon slot,
`armor_score` for every other slot — and the purposes differ only in what the
caller supplies. `Combat` is handed a real monster and a real wearer; `Rank` has
neither, so `gear_value_core.rank_adversary()` supplies the catalog-median one.
This module mirrors that:

* `combatValue` is the shared score atom (`WScore`/`AScore` dispatched on the
  weapon flag);
* `rankValue isWeapon item` is DEFINITIONALLY `combatValue` at the canonical
  adversary — `rankValue_eq_combatValue_canonical` is `rfl`, which is the whole
  content of "there is one algorithm";
* the two live orderings that forced the unification (`mushmush_jacket` over
  `adventurer_vest`, `fire_and_earth_amulet` over `life_amulet`) are discharged
  as kernel-checked arithmetic on the canonical adversary.

RETIRED: `rankValue` used to be a separate flat stat sum, `2 * (combatRaw +
wisdom + prospecting + inventorySpace + haste) + nonToolBonus`, pinned
bit-identical to `EquipValueAugmented.equipValue` by `rank_eq_equipValue`. Both
that definition and that theorem are GONE, not weakened: the Python function
they modelled (`gear_value_core.rank_value`) no longer exists, so keeping the
theorem would have told a false story about live code. `rankValue_eq_-
combatValue_canonical` is strictly stronger about the property that matters —
Rank cannot disagree with Combat because it IS Combat.

ALSO RETIRED: `combatRaw` (the flat 8-stat sum `attack + resistance + hpRestore
+ hpBonus + dmg + crit + lifesteal + combatBuff`) and `rawSum_decomp`. That
scalar was `StrategicValue`'s "how much combat is in this item" input, i.e. a
SECOND ruler living one layer up — free to disagree with this one about the same
slot, and guilty of the same 1:1 category error (a resistance PERCENTAGE added
to an HP amount) the Rank/Combat unification had just removed here. Both the
definition and the theorem are GONE, not weakened: the Python function they
modelled (`gear_value_core.combat_raw`) no longer exists. `rankCombat` /
`rankEfficiency` / `rankValue_decomp` below replace them with a strictly stronger
correspondence — the economics layer's combat input is not merely SHARED with
this ruler, it is one of the two terms this ruler is the sum of.
-/

namespace Formal.GearValue

open Formal.EquipValueAugmented

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
resistance for the weapon slot, `AScore` against the monster's attack, the
monster's resistance AND the WEARER's attack otherwise (armor is priced on both
halves of the swing — see `EquipmentScoring.AScore`).
Mirrors `EquipmentScoring.WScore`/`AScore`. -/
def combatValue (isWeapon : Bool) (item : Item)
    (monsterAtk monsterRes playerAtk : ElemStats) : Int :=
  if isWeapon then WScore item monsterRes
  else AScore item monsterAtk monsterRes playerAtk

/-! ### The canonical adversary: what makes `Rank` an INSTANCE of `Combat`.

Mirrors `ai/gear_value_core.rank_adversary()`. Every constant is the MEDIAN of
the pinned live catalog (`formal/sim/game_data_snapshot.json`, 58 monsters / 232
per-element resistance entries), re-derived from that file by
`tests/ai/test_gear_value_core.py` so a catalog shift fails the suite. -/

/-- Median TOTAL per-element attack over the 58 catalog monsters (min 4, max
1250), spread UNIFORMLY over the 4 elements: `135 / 4 = 33`.

UNIFORM because a monster-independent ruler has no evidence for preferring one
element. The SAME magnitude is used for the reference WEARER's attack, making
the canonical duel SYMMETRIC — which is what fixes the defense-vs-offense
exchange rate without inventing a constant: with both sides at `m` per element,
`r`% resistance in every element stops `4*m*r/100` HP per turn and `r`% global
damage adds `0.01*r*4*m`, exactly equal (`rank_prices_resistance_and_damage_-
equally` below). -/
def rankReferenceAttack : Int := 33

/-- Median of the 232 catalog monster resistance entries (range -80..115). Zero
is the empirical centre AND leaves `AScore`'s `max 0 (100 - monRes)` offense
clamp at its maximum; a UNIFORM resistance is a pure scale factor on the offense
sum, so this choice moves offense-vs-defense only, never a within-term order. -/
def rankReferenceResistance : Int := 0

/-- The canonical adversary's (and reference wearer's) per-element attack. -/
def canonicalAttack : ElemStats := elements.map (fun e => (e, rankReferenceAttack))

/-- The canonical adversary's per-element resistance. -/
def canonicalResistance : ElemStats := elements.map (fun e => (e, rankReferenceResistance))

/-- The LIVE `ai/gear_value.gear_value(stats, purpose)` — the one gear ruler, at
whatever adversary the caller supplies. The weapon branch is the AUGMENTED
`PurposeRouting.combatScore` (`2 * WScore + nonToolBonus`), because that is what
the Python `weapon_score` returns and what carries the fishing_net tiebreak;
`combatValue` above is its RAW atom, related by `combatScore_eq_combatValue`. -/
def gearValue (isWeapon : Bool) (ci : Formal.PurposeRouting.CombatItem)
    (monsterAtk monsterRes playerAtk : ElemStats) : Int :=
  if isWeapon then Formal.PurposeRouting.combatScore monsterRes ci
  else AScore ci.base monsterAtk monsterRes playerAtk

/-- **The unified Rank ruler**: `gear_value(_, Rank)` IS `gear_value(_, Combat)`
against the canonical adversary. Mirrors the Python `gear_value`'s Rank branch,
which is literally `return gear_value(stats, rank_adversary())`. -/
def rankValue (isWeapon : Bool) (ci : Formal.PurposeRouting.CombatItem) : Int :=
  gearValue isWeapon ci canonicalAttack canonicalResistance canonicalAttack

/-- **ONE ALGORITHM** — the load-bearing statement of this whole unification:
Rank is not a second formula that has to be kept in agreement with Combat, it is
Combat with a particular adversary substituted, by definition. -/
theorem rankValue_eq_gearValue_canonical (isWeapon : Bool)
    (ci : Formal.PurposeRouting.CombatItem) :
    rankValue isWeapon ci
      = gearValue isWeapon ci canonicalAttack canonicalResistance canonicalAttack :=
  rfl

/-! #### The Rank ruler's own (COMBAT, EFFICIENCY) partition.

Mirrors the live `ai/gear_value.gear_components(stats, Rank)`. The economics
layer (`Formal.StrategicValue`, `tiers/pursuit_value`) consumes THESE two terms
rather than a scalar of its own, which is what makes "one scoring algorithm"
true of the acquisition path as well as the picker. -/

/-- The Rank purpose's COMBAT term: `EquipmentScoring.ACombat` at the canonical
adversary on the armor branch, the whole augmented weapon score on the weapon
branch. `flatCombat` is the piece's `hp_restore + hp_bonus + lifesteal +
combatBuff`. -/
def rankCombat (isWeapon : Bool) (ci : Formal.PurposeRouting.CombatItem)
    (flatCombat : Int) : Int :=
  if isWeapon then Formal.PurposeRouting.combatScore canonicalResistance ci
  else ACombat ci.base canonicalAttack canonicalResistance canonicalAttack flatCombat

/-- The Rank purpose's EFFICIENCY term.

ZERO on the weapon branch, deliberately: `PurposeRouting.combatScore` is
`2 * WScore + nonToolBonus` and has no flat-utility block at all, so a weapon's
`wisdom`/`prospecting` are invisible to the RULER. Reporting 0 keeps
`rankValue_decomp` an exact identity instead of inventing a term the ruler does
not have. (Live blast radius: the four voidstone tools, 100 prospecting each,
and only as a tiebreak between weapons of identical `WScore`.) -/
def rankEfficiency (isWeapon : Bool)
    (wisdom prospecting inventorySpace haste : Int) : Int :=
  if isWeapon then 0 else AEfficiency wisdom prospecting inventorySpace haste

/-- **THE PARTITION, on the Rank purpose.** The ruler IS the sum of the two terms
the economics layer weighs — on BOTH branches, for every item. So the acquisition
score cannot contain a stat the ruler does not, cannot omit one the ruler has,
and cannot count one twice. -/
theorem rankValue_decomp (isWeapon : Bool)
    (ci : Formal.PurposeRouting.CombatItem)
    (flatCombat wisdom prospecting inventorySpace haste : Int)
    (hflat : ci.base.flatUtil
      = flatCombat + wisdom + prospecting + inventorySpace + haste) :
    rankValue isWeapon ci
      = rankCombat isWeapon ci flatCombat
        + rankEfficiency isWeapon wisdom prospecting inventorySpace haste := by
  unfold rankValue gearValue rankCombat rankEfficiency
  cases isWeapon with
  | true => simp
  | false =>
    simp only [if_false, Bool.false_eq_true]
    exact AScore_decomp ci.base canonicalAttack canonicalResistance canonicalAttack
      flatCombat wisdom prospecting inventorySpace haste hflat

/-- The armor branch of `gearValue` is exactly the raw `combatValue` atom the
picker optimality theorems are stated on, so nothing is lost by the augmentation
living only on the weapon side. -/
theorem gearValue_armor_eq_combatValue (ci : Formal.PurposeRouting.CombatItem)
    (monsterAtk monsterRes playerAtk : ElemStats) :
    gearValue false ci monsterAtk monsterRes playerAtk
      = combatValue false ci.base monsterAtk monsterRes playerAtk :=
  rfl

/-- The `gear_value(Gather)` score atom: the signed per-skill effect the gather
picker minimizes (more negative = better). Mirrors `PurposeRouting.gatherScore`. -/
def gatherValue (skillEffect : Item → Int) (item : Item) : Int :=
  Formal.PurposeRouting.gatherScore skillEffect item

/-- `weapon_score_nonneg` restated on the `gear_value(Combat)` weapon form: the
weapon-slot combat value is `≥ 0` under nonneg per-element attacks and crit.
Unfolds to `EquipmentScoring.WScore`; discharged by the existing clamp theorem. -/
theorem combatValue_weapon_nonneg (item : Item)
    (monsterAtk monsterRes playerAtk : ElemStats)
    (hatk : ∀ e ∈ elements, 0 ≤ elemGet item.attack e) (hcrit : 0 ≤ item.crit) :
    0 ≤ combatValue true item monsterAtk monsterRes playerAtk := by
  unfold combatValue
  exact weapon_score_nonneg item monsterRes hatk hcrit

/-- `armor_score_nonneg` restated on the `gear_value(Combat)` armor form. Unfolds
to `EquipmentScoring.AScore`; discharged by `GearPolicy.armor_score_nonneg`. -/
theorem combatValue_armor_nonneg (item : Item)
    (monsterAtk monsterRes playerAtk : ElemStats)
    (hAtk : ∀ e ∈ elements, 0 ≤ elemGet monsterAtk e)
    (hRes : ∀ e ∈ elements, 0 ≤ elemGet item.resistance e)
    (hUtil : 0 ≤ item.flatUtil)
    (hPAtk : ∀ e ∈ elements, 0 ≤ elemGet playerAtk e)
    (hDmg : 0 ≤ item.dmg)
    (hDmgElem : ∀ e ∈ elements, 0 ≤ elemGet item.dmgElem e)
    (hCrit : 0 ≤ item.crit) :
    0 ≤ combatValue false item monsterAtk monsterRes playerAtk := by
  unfold combatValue
  exact Formal.GearPolicy.armor_score_nonneg item monsterAtk monsterRes playerAtk
    hAtk hRes hUtil hPAtk hDmg hDmgElem hCrit

/-- Every value the canonical adversary carries is nonneg, so every `elemGet`
into it is — the one fact the Rank nonneg corollaries need about the adversary. -/
private theorem elemGet_nonneg_of_all {s : ElemStats} (h : ∀ kv ∈ s, 0 ≤ kv.2)
    (e : Int) : 0 ≤ elemGet s e := by
  unfold elemGet
  cases hf : s.find? (fun kv => kv.1 == e) with
  | none => exact Int.le_refl 0
  | some kv => exact h kv (List.mem_of_find?_eq_some hf)

theorem canonicalAttack_nonneg (e : Int) : 0 ≤ elemGet canonicalAttack e :=
  elemGet_nonneg_of_all
    (by unfold canonicalAttack rankReferenceAttack elements; decide) e

/-- Rank inherits `AScore`'s nonnegativity on the armor branch: the canonical
adversary's attack and resistance are nonneg, so the existing
`combatValue_armor_nonneg` discharges it with no new hypotheses about the
adversary. -/
theorem rankValue_armor_nonneg (ci : Formal.PurposeRouting.CombatItem)
    (hRes : ∀ e ∈ elements, 0 ≤ elemGet ci.base.resistance e)
    (hUtil : 0 ≤ ci.base.flatUtil)
    (hDmg : 0 ≤ ci.base.dmg)
    (hDmgElem : ∀ e ∈ elements, 0 ≤ elemGet ci.base.dmgElem e)
    (hCrit : 0 ≤ ci.base.crit) :
    0 ≤ rankValue false ci :=
  combatValue_armor_nonneg ci.base _ _ _ (fun e _ => canonicalAttack_nonneg e) hRes
    hUtil (fun e _ => canonicalAttack_nonneg e) hDmg hDmgElem hCrit

/-- Rank inherits `WScore`'s clamp nonnegativity on the weapon branch. -/
theorem rankValue_weapon_nonneg (ci : Formal.PurposeRouting.CombatItem)
    (hatk : ∀ e ∈ elements, 0 ≤ elemGet ci.base.attack e) (hcrit : 0 ≤ ci.base.crit) :
    0 ≤ rankValue true ci := by
  have h := combatValue_weapon_nonneg ci.base canonicalAttack canonicalResistance
    canonicalAttack hatk hcrit
  unfold rankValue gearValue Formal.PurposeRouting.combatScore
    Formal.PurposeRouting.nonToolBonus
  unfold combatValue at h
  simp only [if_true] at h ⊢
  cases ci.isTool <;> simp <;> omega

/-! #### The two live orderings the unification was required to fix.

Both are stated on `rankValue`, i.e. on the MONSTER-BLIND purpose — that is the
side that was still wrong. Stats are verbatim from `/v3/items`; `flatUtil` is the
piece's `hp_restore + hp_bonus + wisdom + prospecting + inventorySpace + haste +
lifesteal + combatBuff` sum, exactly as the Python adapter computes it. -/

/-- `mushmush_jacket`: hp_bonus 60 + wisdom 10 = flatUtil 70, dmg 10, crit 3. -/
def mushmushJacket : Formal.PurposeRouting.CombatItem :=
  { isTool := false, base :=
  { code := 0, level := 10, attack := [], resistance := [], crit := 3, fits := true,
    flatUtil := 70, dmg := 10 } }

/-- `adventurer_vest`: hp_bonus 60 + wisdom 20 = flatUtil 80, dmg 6, crit 0. -/
def adventurerVest : Formal.PurposeRouting.CombatItem :=
  { isTool := false, base :=
  { code := 1, level := 10, attack := [], resistance := [], crit := 0, fits := true,
    flatUtil := 80, dmg := 6 } }

/-- `life_amulet`: hp_bonus 30 = flatUtil 30, no damage percentages. -/
def lifeAmulet : Formal.PurposeRouting.CombatItem :=
  { isTool := false, base :=
  { code := 2, level := 15, attack := [], resistance := [], crit := 0, fits := true,
    flatUtil := 30 } }

/-- `fire_and_earth_amulet`: hp_bonus 20 = flatUtil 20, +5% fire and +5% earth. -/
def fireAndEarthAmulet : Formal.PurposeRouting.CombatItem :=
  { isTool := false, base :=
  { code := 3, level := 20, attack := [], resistance := [], crit := 0, fits := true,
    flatUtil := 20, dmgElem := [(0, 5), (1, 5)] } }

/-- **The owner's original complaint, closed on the Rank side.** The retired flat
sum scored the vest 173 to the jacket's 167 because it weighted 10 extra wisdom
the same as 4 points of global damage plus 3 points of crit. `AScore` had said
otherwise since 170ed8d8; Rank now says it too, because it IS `AScore`. -/
theorem rank_prefers_mushmush_jacket_over_adventurer_vest :
    rankValue false adventurerVest < rankValue false mushmushJacket := by
  decide +kernel

/-- **The 2026-08-04 equip loop, closed on the Rank side.** The acquisition path
scored `life_amulet` above `fire_and_earth_amulet` and equipped it; the combat
picker scored them 48000 to 6000 the other way and equipped it back, one API
request and one cooldown per leg, forever. Rank now agrees with the picker's
direction. -/
theorem rank_prefers_fire_and_earth_amulet_over_life_amulet :
    rankValue false lifeAmulet < rankValue false fireAndEarthAmulet := by
  decide +kernel

/-- The symmetric-duel calibration claim, checked: at the canonical adversary a
piece with `r`% resistance in EVERY element and a piece with `r`% GLOBAL damage
score identically. This is what makes the reference magnitude a pure
combat-vs-flat-utility knob rather than a hidden defense-vs-offense thumb. -/
theorem rank_prices_resistance_and_damage_equally (r : Int) :
    rankValue false ⟨{ code := 0, level := 0, attack := [], crit := 0, fits := true,
                       resistance := elements.map (fun e => (e, r)) }, false⟩
      = rankValue false ⟨{ code := 0, level := 0, attack := [], resistance := [],
                           crit := 0, fits := true, dmg := r }, false⟩ := by
  have hmax : max (0 : Int) 100 = 100 := by decide
  simp [rankValue, gearValue, AScore, aTerm, oTerm, wTerm, elements, elemGet,
        canonicalAttack, canonicalResistance, rankReferenceAttack,
        rankReferenceResistance, hmax]
  omega


/-- `pickslot_score_optimal` restated on the `gear_value(Combat)` weapon form: the
weapon-slot argmax dominates every feasible candidate's combat value. The combat
purpose just instantiates the parametric `score` with `combatValue true`. -/
theorem combatValue_pickslot_optimal (playerLevel : Int)
    (monsterAtk monsterRes playerAtk : ElemStats)
    (items : List Item) (c : Item) (cs : List Item)
    (hcand : candidates playerLevel items = c :: cs) :
    ∀ y ∈ candidates playerLevel items,
      combatValue true y monsterAtk monsterRes playerAtk
        ≤ combatValue true
            (argmaxBy (fun i => combatValue true i monsterAtk monsterRes playerAtk) c cs)
            monsterAtk monsterRes playerAtk :=
  pickslot_score_optimal (fun i => combatValue true i monsterAtk monsterRes playerAtk)
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
theorem combatScore_eq_combatValue (monsterAtk monsterRes playerAtk : ElemStats)
    (ci : Formal.PurposeRouting.CombatItem) :
    Formal.PurposeRouting.combatScore monsterRes ci
      = 2 * combatValue true ci.base monsterAtk monsterRes playerAtk
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
value objects. `combat` carries the monster's attack/resistance, the FIGHTER's own
per-element attack (which `AScore` needs to price a piece's damage-%), and the
slot's weapon flag; `rank` carries the monster-independent per-item ruler (the genuine
`rankValue ∘ stats`, modeled as a per-item integer because the picker is
parametric in ANY per-item benefit — `rankValue`'s identity to the canonical `combatValue`
is pinned separately by `rankValue_eq_combatValue_canonical`); `gather` carries the skill effect
the gather picker minimizes. -/
inductive Purpose where
  | combat (monsterAtk monsterRes playerAtk : ElemStats) (isWeapon : Bool)
  | rank   (rankOf : Item → Int)
  | gather (skillEffect : Item → Int)

/-- The SINGLE per-slot benefit the unified picker MAXIMIZES (argmax), dispatched
on purpose. Combat/Rank use `gear_value` directly; Gather negates `gatherValue`
(`gear_value(Gather)`), so the gather argmin becomes a unified argmax.

The utility-fill arm is `200 * flatUtil`, which `EquipmentScoring.AScore_no_monster`
proves IS `AScore i [] [] []` — the live `_benefit` computes it as
`armor_score(stats, {}, {}, {})`, on the same `200 *` scale as every other armor
score, so the two stay bit-identical. -/
def purposeBenefit : Purpose → Item → Int
  | .combat monsterAtk monsterRes playerAtk isWeapon =>
      fun i => combatValue isWeapon i monsterAtk monsterRes playerAtk
  | .rank rankOf => rankOf
  | .gather skillEffect =>
      fun i => if i.isUtilityFill then 200 * i.flatUtil
               else - gatherValue skillEffect i

/-- On a NON-utility-fill item the Gather benefit is exactly `-gatherValue` (the
`else` arm) — the atom that lets the gather folds reduce to the dedicated
`gatherScore` argmin/optimality without touching the utility-fill artifacts. -/
theorem purposeBenefit_gather_nonfill (skillEffect : Item → Int) (i : Item)
    (h : i.isUtilityFill = false) :
    purposeBenefit (.gather skillEffect) i = - gatherValue skillEffect i := by
  simp only [purposeBenefit, h, Bool.false_eq_true, if_false]

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
theorem pickSlot_purpose_combat_optimal (monsterAtk monsterRes playerAtk : ElemStats)
    (isWeapon : Bool) (playerLevel : Int) (items : List Item) (c : Item) (cs : List Item)
    (hcand : candidates playerLevel items = c :: cs) :
    ∀ y ∈ candidates playerLevel items,
      combatValue isWeapon y monsterAtk monsterRes playerAtk
        ≤ combatValue isWeapon
            (argmaxBy (purposeBenefit (.combat monsterAtk monsterRes playerAtk isWeapon)) c cs)
            monsterAtk monsterRes playerAtk :=
  pickSlot_score_optimal_purpose (.combat monsterAtk monsterRes playerAtk isWeapon)
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

/-- **Gather fold via duality** — optimality: on the pure gather-tool sub-world
(NO candidate is a `isUtilityFill` artifact, so every candidate's Gather benefit
is `-gatherValue`), the unified picker under the Gather benefit MINIMIZES
`gatherValue` over the feasible candidates, recovering the
`PurposeRouting.pickGatherSlot_score_optimal` content with no optimality lost.

The `hNoFill` hypothesis is NON-VACUOUS: every non-artifact item defaults
`isUtilityFill = false` (weapons/tools — exactly the gather-tool scenario this
theorem governs). The utility-fill artifact case is instead covered directly by
the generic `pickSlot_score_optimal_purpose` (its benefit IS the flat utility). -/
theorem pickSlot_purpose_gather_optimal (skillEffect : Item → Int) (playerLevel : Int)
    (items : List Item) (c : Item) (cs : List Item)
    (hcand : candidates playerLevel items = c :: cs)
    (hNoFill : ∀ i ∈ candidates playerLevel items, i.isUtilityFill = false) :
    ∀ y ∈ candidates playerLevel items,
      gatherValue skillEffect (argmaxBy (purposeBenefit (.gather skillEffect)) c cs)
        ≤ gatherValue skillEffect y := by
  intro y hy
  have h := pickSlot_score_optimal_purpose (.gather skillEffect) playerLevel items c cs hcand y hy
  have hbest_mem : argmaxBy (purposeBenefit (.gather skillEffect)) c cs
      ∈ candidates playerLevel items := by
    rw [hcand]; exact argmaxBy_mem _ c cs
  have hyf : y.isUtilityFill = false := hNoFill y hy
  have hbf : (argmaxBy (purposeBenefit (.gather skillEffect)) c cs).isUtilityFill = false :=
    hNoFill _ hbest_mem
  have ey := purposeBenefit_gather_nonfill skillEffect y hyf
  have eb := purposeBenefit_gather_nonfill skillEffect
    (argmaxBy (purposeBenefit (.gather skillEffect)) c cs) hbf
  rw [ey, eb] at h
  omega

/-- **Gather fold via duality** — picker identity: on the pure gather-tool
sub-world (no candidate AND no current item is a `isUtilityFill` artifact),
routing the Gather purpose through the unified `pickSlotForPurpose` produces
EXACTLY the dedicated `PurposeRouting.pickGatherSlot` output. The complete fold —
the dead argmin picker is subsumed. The hypotheses are NON-VACUOUS: every
non-artifact item (weapons/tools) defaults `isUtilityFill = false`, which is
precisely the gather-tool picking this identity governs. When a utility-fill
artifact IS present the two pickers legitimately DIVERGE (the unified picker
equips the flat-utility artifact; the dedicated argmin does not), so the identity
holds only where the utility-fill semantics are inert. -/
theorem pickSlotForPurpose_gather_eq (skillEffect : Item → Int) (playerLevel : Int)
    (current : Option Item) (items : List Item)
    (hNoFill : ∀ i ∈ candidates playerLevel items, i.isUtilityFill = false)
    (hCurNoFill : ∀ cur, current = some cur → cur.isUtilityFill = false) :
    pickSlotForPurpose (.gather skillEffect) playerLevel current items
      = Formal.PurposeRouting.pickGatherSlot skillEffect playerLevel current items := by
  unfold pickSlotForPurpose pickSlot Formal.PurposeRouting.pickGatherSlot
  cases hC : candidates playerLevel items with
  | nil => rfl
  | cons c cs =>
    -- On the non-fill candidate list, the Gather benefit is exactly `-gatherScore`,
    -- so the unified argmax equals the argmax of the negated score, which the
    -- proven duality folds to the dedicated `argminBy gatherScore`.
    have hcongr : argmaxBy (purposeBenefit (.gather skillEffect)) c cs
        = argmaxBy (fun i => - Formal.PurposeRouting.gatherScore skillEffect i) c cs := by
      apply argmaxBy_congr
      intro i hi
      have hif : i.isUtilityFill = false := hNoFill i (by rw [hC]; exact hi)
      rw [purposeBenefit_gather_nonfill skillEffect i hif, gatherValue]
    have hbest : argmaxBy (purposeBenefit (.gather skillEffect)) c cs
        = Formal.PurposeRouting.argminBy
            (Formal.PurposeRouting.gatherScore skillEffect) c cs := by
      rw [hcongr]
      exact argmaxBy_neg_eq_argminBy (Formal.PurposeRouting.gatherScore skillEffect) c cs
    simp only [hbest]
    cases current with
    | none => rfl
    | some cur =>
      have hcf : cur.isUtilityFill = false := hCurNoFill cur rfl
      -- `argminBy gatherScore` over the non-fill list is itself non-fill, so BOTH
      -- benefit reads reduce to `-gatherScore` and the comparison matches exactly.
      have hbf : (Formal.PurposeRouting.argminBy
          (Formal.PurposeRouting.gatherScore skillEffect) c cs).isUtilityFill = false :=
        hNoFill _ (by
          rw [hC]; exact Formal.PurposeRouting.argminBy_mem
            (Formal.PurposeRouting.gatherScore skillEffect) c cs)
      have ecur := purposeBenefit_gather_nonfill skillEffect cur hcf
      have ebest := purposeBenefit_gather_nonfill skillEffect
        (Formal.PurposeRouting.argminBy (Formal.PurposeRouting.gatherScore skillEffect) c cs) hbf
      rw [gatherValue] at ecur ebest
      dsimp only
      rw [ecur, ebest]
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
