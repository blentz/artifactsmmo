import Formal.PurposeRouting
import Formal.EquipValueAugmented
import Formal.Extracted.EquipmentScoring
import Formal.Extracted.EquipValue

/-!
# Extracted bridges, part 7 (P4b): the exact equipment-scoring cores.

P4a made `equipment/scoring.py` and `tiers/equip_value.py` exact-integer;
P4b extracts their pure cores (`weapon_score_raw_pure` / `weapon_score_pure`
/ `gather_score_pure` / `armor_score_pure` and `tool_value_pure`) and bridges
them to the hand models (the augmented `equip_value_pure` Rank core was retired
onto the unified `Formal.GearValue.rankValue` hand pin):

* `Formal.EquipmentScoring.WScore` / `AScore` — the hand models key elements
  by `Int` (fire/earth/water/air as 0..3) while the Python (and therefore
  the extracted image) keys them by `String`. The bridges are UNIVERSAL
  over an arbitrary INJECTIVE element embedding `enc : Int → String`
  (the CombatPicker code-embedding precedent): the extracted score over
  the encoded dicts equals the hand score over the original `ElemStats`,
  for EVERY item / monster profile. The production embedding
  (`fire ↦ "fire"`, ...) is one instance.
* `Formal.PurposeRouting.combatScore` — the augmented weapon score
  (`2 * WScore + nonToolBonus`); the `isTool` flag is the Python
  `subtype == "tool"` test, carried as a hypothesis.
* `Formal.PurposeRouting.gatherScore` — parametric in the per-item effect
  read; the extracted `gather_score_pure` IS that read, so the gather
  optimality contract is restated on the extracted def directly.
* `tool_value_pure` has no standalone hand model; its load-bearing content
  is the DUALITY with the gather score (`tool_value = |gather_score|`,
  and `= -gather_score` on the tool domain of non-positive effects), so
  maximizing the tool value is exactly minimizing the gather score.

Transferred hand theorems (the load-bearing contracts, restated on the
extracted defs): `weapon_score_nonneg` (THE clamp theorem),
`combatScore_strict_of_strict_wscore`, `combatScore_tiebreaks_nontool_over_tool`
(the fishing_net invariant), `pickslot_no_downgrade` (instantiated at the
extracted scores), and `pickGatherSlot_score_optimal`.

No sorry/admit, no new axioms; core-only (safety-module convention).
-/

namespace Extracted.Bridges

/-- Encode a hand `ElemStats` (Int element keys) into the extracted
String-keyed association dict, pointwise through `enc`. -/
def encElem (enc : Int → String) (s : Formal.EquipmentScoring.ElemStats) :
    List (String × Int) :=
  s.map (fun kv => (enc kv.1, kv.2))

/-- The extracted dict read over an encoded `ElemStats` IS the hand
`elemGet`, for any INJECTIVE element embedding (injectivity keeps distinct
element keys distinct through the encoding). -/
private theorem dictGetD_encElem (enc : Int → String)
    (hinj : ∀ a b : Int, enc a = enc b → a = b)
    (s : Formal.EquipmentScoring.ElemStats) (e : Int) :
    Extracted.EquipmentScoring._dictGetD (encElem enc s) (enc e) 0
      = Formal.EquipmentScoring.elemGet s e := by
  induction s with
  | nil => rfl
  | cons kv rest ih =>
    obtain ⟨k, v⟩ := kv
    by_cases h : k = e
    · subst h
      simp [encElem, Extracted.EquipmentScoring._dictGetD,
            Formal.EquipmentScoring.elemGet]
    · have henc : enc k ≠ enc e := fun hc => h (hinj _ _ hc)
      simp only [encElem, List.map_cons] at ih ⊢
      simp only [Extracted.EquipmentScoring._dictGetD,
                 Formal.EquipmentScoring.elemGet, List.find?_cons]
      rw [if_neg (by simpa using henc)]
      have hke : (k == e) = false := by simpa using h
      simp only [hke]
      exact ih

/-! ## scoring.py: weapon / armor / gather. -/

/-- BRIDGE (universal over injective element embeddings): the extracted
`weapon_score_raw_pure` over the encoded element list and dicts equals the
hand `Formal.EquipmentScoring.WScore`, for EVERY item attack profile and
monster resistance profile. -/
theorem weapon_score_raw_bridge (enc : Int → String)
    (hinj : ∀ a b : Int, enc a = enc b → a = b)
    (item : Formal.EquipmentScoring.Item)
    (monsterRes : Formal.EquipmentScoring.ElemStats) :
    Extracted.EquipmentScoring.weapon_score_raw_pure
        (Formal.EquipmentScoring.elements.map enc)
        (encElem enc item.attack) item.crit (encElem enc monsterRes)
      = Formal.EquipmentScoring.WScore item monsterRes := by
  simp only [Extracted.EquipmentScoring.weapon_score_raw_pure,
             Formal.EquipmentScoring.WScore, Formal.EquipmentScoring.wTerm,
             Formal.EquipmentScoring.elements,
             List.map_cons, List.map_nil, List.foldl_cons, List.foldl_nil,
             List.sum_cons, List.sum_nil,
             dictGetD_encElem enc hinj,
             Int.zero_add, Int.add_zero, Int.add_assoc]

/-- BRIDGE (universal over injective element embeddings): the extracted
`armor_score_pure` equals the hand `Formal.EquipmentScoring.AScore` (no
clamp — armor scoring has none), for every profile. -/
theorem armor_score_bridge (enc : Int → String)
    (hinj : ∀ a b : Int, enc a = enc b → a = b)
    (item : Formal.EquipmentScoring.Item)
    (monsterAtk : Formal.EquipmentScoring.ElemStats)
    (hpBonus wisdom prospecting inventorySpace haste lifesteal combatBuff : Int)
    (hflat : item.flatUtil = hpBonus + wisdom + prospecting + inventorySpace + haste + lifesteal + combatBuff) :
    Extracted.EquipmentScoring.armor_score_pure
        (Formal.EquipmentScoring.elements.map enc)
        (encElem enc item.resistance) (encElem enc monsterAtk)
        hpBonus wisdom prospecting inventorySpace haste lifesteal combatBuff
      = Formal.EquipmentScoring.AScore item monsterAtk := by
  simp only [Extracted.EquipmentScoring.armor_score_pure,
             Formal.EquipmentScoring.AScore, Formal.EquipmentScoring.aTerm,
             Formal.EquipmentScoring.elements,
             List.map_cons, List.map_nil, List.foldl_cons, List.foldl_nil,
             List.sum_cons, List.sum_nil,
             dictGetD_encElem enc hinj,
             Int.zero_add, Int.add_zero, Int.add_assoc]
  omega

/-- BRIDGE: the extracted composite `weapon_score_pure` equals the hand
`Formal.PurposeRouting.combatScore` (`2 * WScore + nonToolBonus`) when the
`CombatItem`'s tool flag is the Python `subtype == "tool"` test. -/
theorem weapon_score_bridge (enc : Int → String)
    (hinj : ∀ a b : Int, enc a = enc b → a = b)
    (ci : Formal.PurposeRouting.CombatItem)
    (monsterRes : Formal.EquipmentScoring.ElemStats) (subtype : String)
    (hTool : ci.isTool = (subtype == "tool")) :
    Extracted.EquipmentScoring.weapon_score_pure
        (Formal.EquipmentScoring.elements.map enc)
        (encElem enc ci.base.attack) subtype ci.base.crit (encElem enc monsterRes)
      = Formal.PurposeRouting.combatScore monsterRes ci := by
  unfold Extracted.EquipmentScoring.weapon_score_pure
    Formal.PurposeRouting.combatScore Formal.PurposeRouting.nonToolBonus
  rw [weapon_score_raw_bridge enc hinj ci.base monsterRes, hTool]
  by_cases h : subtype = "tool" <;> simp [h]

/-- TRANSFERRED (THE clamp theorem, `weapon_score_nonneg`): the extracted
raw weapon score is nonnegative whenever every per-element attack is —
the `max(0, 100 - res)` clamp keeps a `res > 100` monster from flipping
the sign and preferring a strictly worse weapon. -/
theorem weapon_score_raw_nonneg_extracted (enc : Int → String)
    (hinj : ∀ a b : Int, enc a = enc b → a = b)
    (item : Formal.EquipmentScoring.Item)
    (monsterRes : Formal.EquipmentScoring.ElemStats)
    (hatk : ∀ e ∈ Formal.EquipmentScoring.elements,
        0 ≤ Formal.EquipmentScoring.elemGet item.attack e)
    (hcrit : 0 ≤ item.crit) :
    0 ≤ Extracted.EquipmentScoring.weapon_score_raw_pure
        (Formal.EquipmentScoring.elements.map enc)
        (encElem enc item.attack) item.crit (encElem enc monsterRes) := by
  rw [weapon_score_raw_bridge enc hinj item monsterRes]
  exact Formal.EquipmentScoring.weapon_score_nonneg item monsterRes hatk hcrit

/-- TRANSFERRED (`combatScore_strict_of_strict_wscore`): any strict raw
WScore ordering survives the +0/+1 tiebreaker in the extracted composite
score — the `2 *` factor protects it, for ANY two subtypes. -/
theorem weapon_score_strict_extracted (enc : Int → String)
    (hinj : ∀ a b : Int, enc a = enc b → a = b)
    (a b : Formal.EquipmentScoring.Item)
    (monsterRes : Formal.EquipmentScoring.ElemStats) (subA subB : String)
    (hStrict : Formal.EquipmentScoring.WScore a monsterRes
      < Formal.EquipmentScoring.WScore b monsterRes) :
    Extracted.EquipmentScoring.weapon_score_pure
        (Formal.EquipmentScoring.elements.map enc)
        (encElem enc a.attack) subA a.crit (encElem enc monsterRes)
      < Extracted.EquipmentScoring.weapon_score_pure
        (Formal.EquipmentScoring.elements.map enc)
        (encElem enc b.attack) subB b.crit (encElem enc monsterRes) := by
  rw [weapon_score_bridge enc hinj ⟨a, subA == "tool"⟩ monsterRes subA rfl,
      weapon_score_bridge enc hinj ⟨b, subB == "tool"⟩ monsterRes subB rfl]
  exact Formal.PurposeRouting.combatScore_strict_of_strict_wscore
    ⟨a, subA == "tool"⟩ ⟨b, subB == "tool"⟩ monsterRes hStrict

/-- TRANSFERRED (`combatScore_tiebreaks_nontool_over_tool`, the fishing_net
invariant): on a raw WScore tie the non-tool weapon strictly outranks the
tool in the extracted composite score. -/
theorem weapon_score_tiebreak_extracted (enc : Int → String)
    (hinj : ∀ a b : Int, enc a = enc b → a = b)
    (toolItem nonToolItem : Formal.EquipmentScoring.Item)
    (monsterRes : Formal.EquipmentScoring.ElemStats)
    (subN : String) (hN : subN ≠ "tool")
    (hTie : Formal.EquipmentScoring.WScore toolItem monsterRes
      = Formal.EquipmentScoring.WScore nonToolItem monsterRes) :
    Extracted.EquipmentScoring.weapon_score_pure
        (Formal.EquipmentScoring.elements.map enc)
        (encElem enc toolItem.attack) "tool" toolItem.crit (encElem enc monsterRes)
      < Extracted.EquipmentScoring.weapon_score_pure
        (Formal.EquipmentScoring.elements.map enc)
        (encElem enc nonToolItem.attack) subN nonToolItem.crit
        (encElem enc monsterRes) := by
  rw [weapon_score_bridge enc hinj ⟨toolItem, true⟩ monsterRes "tool" (by simp),
      weapon_score_bridge enc hinj ⟨nonToolItem, false⟩ monsterRes subN
        (by simp [hN])]
  exact Formal.PurposeRouting.combatScore_tiebreaks_nontool_over_tool
    ⟨toolItem, true⟩ ⟨nonToolItem, false⟩ monsterRes rfl rfl hTie

/-- TRANSFERRED (`pickslot_no_downgrade` instantiated at the extracted raw
weapon score): the per-slot pick under the EXTRACTED score never downgrades
a filled slot. The hand pick theorems are parametric in the score; the
extracted def is a legal instance, so every pick contract holds for it. -/
theorem pickslot_no_downgrade_extracted (enc : Int → String)
    (monsterRes : Formal.EquipmentScoring.ElemStats) (playerLevel : Int)
    (cur : Formal.EquipmentScoring.Item)
    (items : List Formal.EquipmentScoring.Item) :
    ∃ r, Formal.EquipmentScoring.pickSlot
        (fun i => Extracted.EquipmentScoring.weapon_score_raw_pure
          (Formal.EquipmentScoring.elements.map enc)
          (encElem enc i.attack) i.crit (encElem enc monsterRes))
        playerLevel (some cur) items = some r ∧
      Extracted.EquipmentScoring.weapon_score_raw_pure
          (Formal.EquipmentScoring.elements.map enc)
          (encElem enc cur.attack) cur.crit (encElem enc monsterRes)
        ≤ Extracted.EquipmentScoring.weapon_score_raw_pure
          (Formal.EquipmentScoring.elements.map enc)
          (encElem enc r.attack) r.crit (encElem enc monsterRes) :=
  Formal.EquipmentScoring.pickslot_no_downgrade _ playerLevel cur items

/-- The extracted gather score of an item with NO entry for the skill is 0
(the docstring contract: every gather tool beats a non-gathering item under
the argmin). -/
theorem gather_score_absent_zero (effs : List (String × Int)) (skill : String)
    (habs : ∀ kv ∈ effs, kv.1 ≠ skill) :
    Extracted.EquipmentScoring.gather_score_pure effs skill = 0 := by
  unfold Extracted.EquipmentScoring.gather_score_pure
  induction effs with
  | nil => rfl
  | cons kv rest ih =>
    obtain ⟨k, v⟩ := kv
    have hk : k ≠ skill := habs (k, v) List.mem_cons_self
    simp only [Extracted.EquipmentScoring._dictGetD]
    rw [if_neg (by simpa using hk)]
    exact ih (fun kv hkv => habs kv (List.mem_cons_of_mem _ hkv))

/-- TRANSFERRED (`pickGatherSlot_score_optimal`): the hand gather picker is
parametric in the per-item effect read; instantiated at the EXTRACTED
`gather_score_pure` (for any per-item effects encoding `effsOf`), the
picked tool minimizes the extracted gather score over every feasible
candidate. -/
theorem gather_pick_optimal_extracted
    (effsOf : Formal.EquipmentScoring.Item → List (String × Int))
    (skill : String) (playerLevel : Int)
    (items : List Formal.EquipmentScoring.Item)
    (picked : Formal.EquipmentScoring.Item)
    (hPick : Formal.PurposeRouting.pickGatherSlot
        (fun i => Extracted.EquipmentScoring.gather_score_pure (effsOf i) skill)
        playerLevel none items = some picked) :
    ∀ c ∈ Formal.EquipmentScoring.candidates playerLevel items,
      Extracted.EquipmentScoring.gather_score_pure (effsOf picked) skill
        ≤ Extracted.EquipmentScoring.gather_score_pure (effsOf c) skill := by
  have h := Formal.PurposeRouting.pickGatherSlot_score_optimal
    (fun i => Extracted.EquipmentScoring.gather_score_pure (effsOf i) skill)
    playerLevel items picked hPick
  simpa [Formal.PurposeRouting.gatherScore] using h

/-! ## equip_value.py: the tool duality.

The augmented composite Rank value (`equip_value_pure`) was retired when the
Python `equip_value` collapsed onto the unified `gear_value(_, Rank)` core; its
soundness now rides the HAND `Formal.GearValue.rankValue` / `rank_eq_equipValue`
pins (Contracts) + the `gear_value_core` differential, not a mechanical
extraction. Only the live `tool_value_pure` core remains extracted here. -/

/-- The two cores read dicts through their own emitted `_dictGetD` copies;
the copies have identical equations. -/
private theorem ev_dictGetD_eq {α : Type} (m : List (String × α))
    (k : String) (d : α) :
    Extracted.EquipValue._dictGetD m k d
      = Extracted.EquipmentScoring._dictGetD m k d := by
  induction m with
  | nil => rfl
  | cons kv rest ih =>
    obtain ⟨a, b⟩ := kv
    simp only [Extracted.EquipValue._dictGetD,
               Extracted.EquipmentScoring._dictGetD, ih]

/-- BRIDGE (cross-core duality, definitional): `tool_value_pure` is the
absolute value of the extracted gather score — the two pickers read the
SAME `skill_effects` entry. -/
theorem tool_value_abs_gather (effs : List (String × Int)) (skill : String) :
    Extracted.EquipValue.tool_value_pure effs skill
      = Extracted.EquipValue._intAbs
        (Extracted.EquipmentScoring.gather_score_pure effs skill) := by
  unfold Extracted.EquipValue.tool_value_pure
    Extracted.EquipmentScoring.gather_score_pure
  rw [ev_dictGetD_eq]

/-- TRANSFERRED duality: on the tool domain (the API encodes tool effects
as non-positive cooldown reductions) the tool value is the NEGATED gather
score — maximizing `tool_value` is exactly minimizing `gather_score`, so
the upgrade ranking and the gather picker agree on which tool is best. -/
theorem tool_value_neg_gather_on_tools (effs : List (String × Int))
    (skill : String)
    (h : Extracted.EquipmentScoring.gather_score_pure effs skill ≤ 0) :
    Extracted.EquipValue.tool_value_pure effs skill
      = - Extracted.EquipmentScoring.gather_score_pure effs skill := by
  rw [tool_value_abs_gather]
  unfold Extracted.EquipValue._intAbs
  rw [Int.ofNat_eq_natCast]
  omega

end Extracted.Bridges
