/-
Formal model of the PURE gear-taxonomy classification core from
`src/artifactsmmo_cli/ai/gear_taxonomy_core.py`.

Three pure functions over plain data:

* `is_combat_bearing(attack, resistance, hp_bonus, dmg, dmg_elements,
  critical_strike, initiative, lifesteal) -> bool` — the OR of the durable
  combat fields (Python truthiness: a non-empty map or a non-zero scalar).
* `is_consumable(effect_codes) -> bool` — any raw effect code in the consumable
  family (exact set + `boost_dmg_*` / `boost_res_*` prefixes).
* `combat_gear_types(rows) -> frozenset[str]` where each row is
  `(type, combat_bearing, consumable)` — the types that have a combat-bearing
  item AND no consumable item (the consumable axis CARVES the type out).

A row is modelled as `Row` (type : String, combatBearing/consumable : Bool).
The four role theorems pin the carving semantics:

* `combatGear_mem_iff`         — exact membership characterization.
* `combatGear_combat_mono`     — combat-monotone (false→true never removes).
* `combatGear_consumable_anti` — antitone in consumable (a consumable item only
  removes a type).
* `combatGear_subset_equippable` — every classified type is some row's type.

The `def`s are COMPUTABLE (they run in the oracle). Lean core only — no mathlib.

NOTE on the spec `def`: the brief wrote the filter predicate as
`fun t => ¬ cons.contains t`, but `List.filter` needs a `Bool` predicate, so we
use the (decidably) equivalent `fun t => decide (t ∉ cons)`; and we deduplicate
with `eraseDups` (the mathlib-free dedup used by `Formal.RecipeClosure`) rather
than `dedup`. Membership semantics are identical, so the theorem statements are
unchanged.
-/

namespace Formal.GearTaxonomy

/-! ### `is_combat_bearing` and `is_consumable`. -/

/-- Consumable-family exact effect codes (mirrors `_CONSUMABLE_EXACT`). -/
def consumableExact : List String :=
  ["heal", "restore", "splash_restore", "antipoison", "teleport", "boost_hp"]

/-- Consumable-family code prefixes (mirrors `_CONSUMABLE_PREFIX`). -/
def consumablePrefix : List String := ["boost_dmg_", "boost_res_"]

/-- True iff the item carries any DURABLE combat stat — the OR of the gear
combat fields. Maps (`attack`, `resistance`, `dmgElements`) are modelled as
association lists; their Python truthiness is "non-empty" (`!isEmpty`),
independent of the stored values. Scalars are non-zero. Mirrors
`gear_taxonomy_core.is_combat_bearing`. -/
def isCombatBearing (attack resistance dmgElements : List (String × Int))
    (hpBonus dmg criticalStrike initiative lifesteal : Int) : Bool :=
  !attack.isEmpty || !resistance.isEmpty || hpBonus != 0 || dmg != 0
    || !dmgElements.isEmpty || criticalStrike != 0 || initiative != 0
    || lifesteal != 0

/-- True iff any raw effect code is in the consumable family (exact set or one of
the two prefixes). Mirrors `gear_taxonomy_core.is_consumable`. -/
def isConsumable (effectCodes : List String) : Bool :=
  effectCodes.any (fun code =>
    consumableExact.contains code || consumablePrefix.any (fun p => p.isPrefixOf code))

/-! ### `combat_gear_types`. -/

/-- A classification row: an item's `type`, whether it is combat-bearing, and
whether it is consumable. -/
structure Row where
  type : String
  combatBearing : Bool
  consumable : Bool

/-- Types that are durable combat gear: those with a combat-bearing item AND no
consumable item. Mirrors `gear_taxonomy_core.combat_gear_types`. -/
def combatGearTypes (rows : List Row) : List String :=
  let combat := rows.filterMap (fun r => if r.combatBearing then some r.type else none)
  let cons := rows.filterMap (fun r => if r.consumable then some r.type else none)
  (combat.filter (fun t => !cons.contains t)).eraseDups

/-! ### Helper: membership in the per-flag type projection. -/

/-- `t` appears in the `filterMap` that keeps `r.type` for rows passing `pred`
IFF some row has `type = t` and passes `pred`. -/
theorem mem_typeProj (rows : List Row) (t : String) (pred : Row → Bool) :
    t ∈ rows.filterMap (fun r => if pred r then some r.type else none)
      ↔ ∃ r ∈ rows, r.type = t ∧ pred r = true := by
  rw [List.mem_filterMap]
  constructor
  · rintro ⟨r, hr, hf⟩
    refine ⟨r, hr, ?_⟩
    cases hp : pred r with
    | false => rw [hp] at hf; simp at hf
    | true => rw [hp] at hf; simp at hf; exact ⟨hf, rfl⟩
  · rintro ⟨r, hr, ht, hp⟩
    exact ⟨r, hr, by rw [hp, ht]; rfl⟩

/-! ### The four role theorems. -/

/-- (a) Membership characterization: a type is classified as durable combat gear
IFF it has a combat-bearing item AND no consumable item. -/
theorem combatGear_mem_iff (rows : List Row) (t : String) :
    t ∈ combatGearTypes rows ↔
      (∃ r ∈ rows, r.type = t ∧ r.combatBearing = true) ∧
      ¬ (∃ r ∈ rows, r.type = t ∧ r.consumable = true) := by
  unfold combatGearTypes
  rw [List.mem_eraseDups, List.mem_filter, Bool.not_eq_true', List.contains_eq_mem,
      decide_eq_false_iff_not, mem_typeProj rows t (·.combatBearing),
      mem_typeProj rows t (·.consumable)]

/-- (b) Combat-monotonicity: if every combat-witness in `rows` is preserved in
`rows'` and every consumable-witness in `rows'` reflects one in `rows`, then no
classified type is lost. Flipping a row's `combatBearing` false→true (with the
consumable side unchanged) never removes a type. -/
theorem combatGear_combat_mono (rows rows' : List Row)
    (h : ∀ t, (∃ r ∈ rows, r.type = t ∧ r.combatBearing = true) →
              (∃ r ∈ rows', r.type = t ∧ r.combatBearing = true))
    (hcons : ∀ t, (∃ r ∈ rows', r.type = t ∧ r.consumable = true) →
                  (∃ r ∈ rows, r.type = t ∧ r.consumable = true)) :
    ∀ t, t ∈ combatGearTypes rows → t ∈ combatGearTypes rows' := by
  intro t ht
  rw [combatGear_mem_iff] at ht ⊢
  obtain ⟨hcombat, hnotcons⟩ := ht
  refine ⟨h t hcombat, ?_⟩
  intro hcons'
  exact hnotcons (hcons t hcons')

/-- (c) Consumable-antitonicity: a classified type provably has NO consumable
item — adding a consumable item for that type can only remove it. -/
theorem combatGear_consumable_anti (rows : List Row) (t : String)
    (h : t ∈ combatGearTypes rows) :
    ¬ (∃ r ∈ rows, r.type = t ∧ r.consumable = true) := by
  rw [combatGear_mem_iff] at h
  exact h.2

/-- (d) Subset of equippable: every classified type appears as some row's type. -/
theorem combatGear_subset_equippable (rows : List Row) (t : String)
    (h : t ∈ combatGearTypes rows) : ∃ r ∈ rows, r.type = t := by
  rw [combatGear_mem_iff] at h
  obtain ⟨r, hr, ht, _⟩ := h.1
  exact ⟨r, hr, ht⟩

end Formal.GearTaxonomy
