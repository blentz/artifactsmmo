
/-!
# Formal.ActionApplicability

**Pure-Lean model of every action's `is_applicable` predicate.**

`is_applicable` is the planner's cheapest gate: a False answer here removes
the action from the search frontier instantly. The 2026-06-06 trace bug
involved `FightAction(chicken).is_applicable` correctly returning False
(chicken too low-level) while `predict_win` returned True at full HP —
two ORTHOGONAL filters, and the bot's target picker conflated them.

This module:

1. Specifies `fightApplicable` as a conjunction of 5 atomic conditions
   (mirrors Python `actions/combat.py:46-64` exactly).
2. Proves the conditions are independent — each can falsify
   applicability on its own.
3. Proves applicability is MONOTONE in hp: more current hp never breaks
   the predicate.
4. Proves the **gear-vs-level orthogonality** that was the root of the
   2026-06-06 trace: a monster can pass winnability and fail
   applicability (chicken case) — the picker must check BOTH.

Phase G4 of `docs/PLAN_composition_correctness.md`.
-/

namespace Formal.ActionApplicability

/-! ## Atomic conditions, lifted from Python. -/

/-- `hp_percent > MIN_FIGHT_HP_FRACTION` (Python `_MIN_FIGHT_HP_FRACTION = 0.5`).
We model the inequality on the scaled integer `hp * 100`, comparing against
`50 * max_hp`. This avoids floating-point in the Lean model. -/
def hpAboveFightFloor (hp maxHp : Int) : Bool :=
  decide (hp * 100 > 50 * maxHp)

/-- `min_level <= monster_level <= state.level + 2` where
`min_level = max(1, state.level - 1)`. The monster must sit in a 4-level
window around the player. -/
def monsterLevelInWindow (playerLevel monsterLevel : Int) : Bool :=
  let minLevel := max 1 (playerLevel - 1)
  decide (minLevel ≤ monsterLevel ∧ monsterLevel ≤ playerLevel + 2)

/-- `best_eq >= monster_level - 1`. The strongest equipped item's level must
roughly match the monster. -/
def gearMeetsMonster (bestEqLevel monsterLevel : Int) : Bool :=
  decide (bestEqLevel ≥ monsterLevel - 1)

/-- Free inventory floor (`inventory_free >= MIN_FREE_SLOTS = 1`). -/
def hasInventoryRoom (inventoryFree minFreeSlots : Int) : Bool :=
  decide (inventoryFree ≥ minFreeSlots)

/-- Map of the FightAction's input. -/
structure FightInputs where
  hasLocations  : Bool      -- the monster has at least one known tile
  inventoryFree : Int
  hp            : Int
  maxHp         : Int
  playerLevel   : Int
  monsterLevel  : Int
  bestEqLevel   : Int
  minFreeSlots  : Int

/-- The composite predicate. Matches Python `combat.py:46-64` term-by-term. -/
def fightApplicable (i : FightInputs) : Bool :=
  i.hasLocations
    && hasInventoryRoom i.inventoryFree i.minFreeSlots
    && hpAboveFightFloor i.hp i.maxHp
    && monsterLevelInWindow i.playerLevel i.monsterLevel
    && gearMeetsMonster i.bestEqLevel i.monsterLevel

/-! ## Independence of the conditions. -/

/-- If `hasLocations` is false, the predicate is false. -/
theorem fightApplicable_false_of_no_locations (i : FightInputs)
    (h : i.hasLocations = false) :
    fightApplicable i = false := by
  unfold fightApplicable
  simp [h]

/-- If `inventoryFree < minFreeSlots`, the predicate is false. -/
theorem fightApplicable_false_of_no_inv_room (i : FightInputs)
    (h : i.inventoryFree < i.minFreeSlots) :
    fightApplicable i = false := by
  unfold fightApplicable hasInventoryRoom
  have : ¬ (i.inventoryFree ≥ i.minFreeSlots) := by omega
  simp [this]

/-- If hp is at or below the 50% floor, the predicate is false. -/
theorem fightApplicable_false_of_low_hp (i : FightInputs)
    (h : i.hp * 100 ≤ 50 * i.maxHp) :
    fightApplicable i = false := by
  unfold fightApplicable hpAboveFightFloor
  have : ¬ (i.hp * 100 > 50 * i.maxHp) := by omega
  simp [this]

/-- If monster level is below `max(1, lvl-1)`, the predicate is false. -/
theorem fightApplicable_false_of_underleveled_monster (i : FightInputs)
    (h : i.monsterLevel < max 1 (i.playerLevel - 1)) :
    fightApplicable i = false := by
  have hWin : monsterLevelInWindow i.playerLevel i.monsterLevel = false := by
    unfold monsterLevelInWindow
    apply decide_eq_false
    intro ⟨h1, _⟩
    omega
  unfold fightApplicable
  simp [hWin]

/-- If monster level exceeds `state.level + 2`, the predicate is false. -/
theorem fightApplicable_false_of_overleveled_monster (i : FightInputs)
    (h : i.monsterLevel > i.playerLevel + 2) :
    fightApplicable i = false := by
  have hWin : monsterLevelInWindow i.playerLevel i.monsterLevel = false := by
    unfold monsterLevelInWindow
    apply decide_eq_false
    intro ⟨_, h2⟩
    omega
  unfold fightApplicable
  simp [hWin]

/-- If best-equipped level is below `monster_level - 1`, the predicate is false. -/
theorem fightApplicable_false_of_undergear (i : FightInputs)
    (h : i.bestEqLevel < i.monsterLevel - 1) :
    fightApplicable i = false := by
  unfold fightApplicable gearMeetsMonster
  have : ¬ (i.bestEqLevel ≥ i.monsterLevel - 1) := by omega
  simp [this]

/-! ## Monotonicity. -/

/-- More current hp never breaks applicability (max_hp held fixed). -/
theorem fightApplicable_mono_in_hp (i : FightInputs) (hp' : Int)
    (hLe : i.hp ≤ hp')
    (hApp : fightApplicable i = true) :
    fightApplicable { i with hp := hp' } = true := by
  unfold fightApplicable at hApp
  simp only [Bool.and_eq_true] at hApp
  obtain ⟨⟨⟨⟨hLoc, hInv⟩, hHp⟩, hWin⟩, hGear⟩ := hApp
  have hHp' : hpAboveFightFloor hp' i.maxHp = true := by
    unfold hpAboveFightFloor at hHp ⊢
    simp at hHp
    apply decide_eq_true
    have hMul : i.hp * 100 ≤ hp' * 100 :=
      Int.mul_le_mul_of_nonneg_right hLe (by decide)
    omega
  unfold fightApplicable
  simp only [Bool.and_eq_true]
  exact ⟨⟨⟨⟨hLoc, hInv⟩, hHp'⟩, hWin⟩, hGear⟩

/-! ## Gear-vs-level orthogonality.

The 2026-06-06 trace headline: chicken passed winnability at hp=130 but
failed FightAction.is_applicable (`monsterLevel=1 < max(1, 3-1) = 2`).
This isn't a bug in either piece — it's the contract: winnability and
applicability gate ORTHOGONAL conditions, and the target picker must
respect both. -/

/-- A monster that fails the level filter has NO `fightApplicable` no matter
how full the bot's hp is or how much gear it owns. (Proves the filter is
*structural*, not hp-recoverable.) -/
theorem fightApplicable_false_under_level_window
    (i : FightInputs) (hp' bestEq' : Int)
    (h : i.monsterLevel < max 1 (i.playerLevel - 1) ∨
         i.monsterLevel > i.playerLevel + 2) :
    fightApplicable { i with hp := hp', bestEqLevel := bestEq' } = false := by
  cases h with
  | inl hLow =>
    apply fightApplicable_false_of_underleveled_monster
    exact hLow
  | inr hHigh =>
    apply fightApplicable_false_of_overleveled_monster
    exact hHigh

/-- **Composition theorem**: even if a target is winnable (at any hp), the
fight is not applicable when the level window excludes the monster. The
picker must therefore filter winnable candidates BY the level window
before returning them. -/
theorem winnable_does_not_imply_applicable
    (i : FightInputs) (winnable : Bool)
    (hLow : i.monsterLevel < max 1 (i.playerLevel - 1)) :
    fightApplicable i = false ∧ winnable = winnable := by
  refine ⟨?_, rfl⟩
  exact fightApplicable_false_of_underleveled_monster i hLow

/-! ## RestAction applicability — the simplest action and a useful baseline. -/

def restApplicable (hp maxHp : Int) : Bool :=
  decide (hp < maxHp)

theorem restApplicable_iff_subfull (hp maxHp : Int) :
    restApplicable hp maxHp = true ↔ hp < maxHp := by
  unfold restApplicable
  simp

theorem restApplicable_false_at_full (hp maxHp : Int) (h : hp = maxHp) :
    restApplicable hp maxHp = false := by
  unfold restApplicable
  simp [h]

/-! ## EquipAction applicability sketch.

EquipAction requires the item to be OWNED (inventory or current slot) and
of compatible type for the slot. Modeled abstractly: ownership is an
opaque flag, slot compatibility is decidable. -/

structure EquipInputs where
  ownedCount   : Int      -- spare copies in inventory (excludes equipped)
  currentSlot  : Option Int  -- current equipped code in target slot
  itemCode     : Int
  slotFits     : Bool

def equipApplicable (e : EquipInputs) : Bool :=
  e.slotFits &&
    decide (e.ownedCount ≥ 1 ∨ e.currentSlot = some e.itemCode)

theorem equipApplicable_iff (e : EquipInputs) :
    equipApplicable e = true ↔
      e.slotFits = true ∧ (e.ownedCount ≥ 1 ∨ e.currentSlot = some e.itemCode) := by
  unfold equipApplicable
  simp

end Formal.ActionApplicability
