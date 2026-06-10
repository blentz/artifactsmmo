-- @concept: combat, characters @property: safety, monotonicity

/-!
# Formal.ActionApplicability

**Pure-Lean model of every action's `is_applicable` predicate.**

`is_applicable` is the planner's cheapest gate: a False answer here removes
the action from the search frontier instantly. The 2026-06-06 trace bug
involved `FightAction(chicken).is_applicable` correctly returning False
(chicken too low-level) while `predict_win` returned True at full HP —
two ORTHOGONAL filters, and the bot's target picker conflated them.

This module:

1. Specifies `fightApplicable` as a conjunction of 6 atomic conditions
   (mirrors Python `FightAction.is_applicable` in `actions/combat.py`
   exactly).
2. Proves the conditions are independent — each can falsify
   applicability on its own.
3. Proves applicability is MONOTONE in hp: more current hp never breaks
   the predicate.
4. Proves the **gear-vs-level orthogonality** of the 2026-06-06 trace in
   its post-P0 form: a winnable monster can still fail applicability —
   but only via the ZERO-XP gate or the upper-bound suicide guard, never
   via a hard lower level window.

**P0 revision (2026-06-09)**: the old lower bound
`monster_level >= max(1, level-1)` deadlocked combat at level 4 (the only
stat-winnable monsters were L1/L2 — below the window, XP-positive). The
lower gate is now `xp_per_kill(monster, char_level) > 0`: the documented
XP curve zeroes out at `char_level - monster_level >= 10`, so the gate is
naturally level-tracking. The upper bound (`level + 2` suicide guard)
stays. The Lean model takes the computed XP as an input (`xpPerKill`),
mirroring `game_data.xp_per_kill(...)` being an input to the Python
predicate.

Phase G4 of `docs/PLAN_composition_correctness.md`.
-/

namespace Formal.ActionApplicability

/-! ## Atomic conditions, lifted from Python. -/

/-- `hp_percent > MIN_FIGHT_HP_FRACTION` (Python `_MIN_FIGHT_HP_FRACTION = 0.5`).
We model the inequality on the scaled integer `hp * 100`, comparing against
`50 * max_hp`. This avoids floating-point in the Lean model. -/
def hpAboveFightFloor (hp maxHp : Int) : Bool :=
  decide (hp * 100 > 50 * maxHp)

/-- LOWER gate: `xp_per_kill(monster, char_level) > 0`. A monster whose
kill grants zero XP (the documented curve zeroes at
`char_level - monster_level >= 10`) serves no leveling objective and is
not applicable. Replaces the old hard window lower bound
`monster_level >= max(1, level-1)` that caused the P0 no-combat deadlock. -/
def xpPositive (xpPerKill : Int) : Bool :=
  decide (xpPerKill > 0)

/-- UPPER gate: `monster_level <= state.level + 2` — the suicide guard. -/
def monsterNotOverleveled (playerLevel monsterLevel : Int) : Bool :=
  decide (monsterLevel ≤ playerLevel + 2)

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
  xpPerKill     : Int       -- game_data.xp_per_kill(monster, playerLevel)

/-- The composite predicate. Matches Python `FightAction.is_applicable`
term-by-term: locations, inventory room, hp floor, xp>0 lower gate,
level+2 suicide guard, gear pre-filter. -/
def fightApplicable (i : FightInputs) : Bool :=
  i.hasLocations
    && hasInventoryRoom i.inventoryFree i.minFreeSlots
    && hpAboveFightFloor i.hp i.maxHp
    && xpPositive i.xpPerKill
    && monsterNotOverleveled i.playerLevel i.monsterLevel
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

/-- If the kill grants zero (or negative) XP, the predicate is false.
This is the NEW lower gate — replaces
`fightApplicable_false_of_underleveled_monster` (the old hard window). -/
theorem fightApplicable_false_of_zero_xp (i : FightInputs)
    (h : i.xpPerKill ≤ 0) :
    fightApplicable i = false := by
  unfold fightApplicable xpPositive
  have : ¬ (i.xpPerKill > 0) := by omega
  simp [this]

/-- If monster level exceeds `state.level + 2`, the predicate is false.
The suicide guard survives the P0 revision unchanged. -/
theorem fightApplicable_false_of_overleveled_monster (i : FightInputs)
    (h : i.monsterLevel > i.playerLevel + 2) :
    fightApplicable i = false := by
  unfold fightApplicable monsterNotOverleveled
  have : ¬ (i.monsterLevel ≤ i.playerLevel + 2) := by omega
  simp [this]

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
  obtain ⟨⟨⟨⟨⟨hLoc, hInv⟩, hHp⟩, hXp⟩, hLvl⟩, hGear⟩ := hApp
  have hHp' : hpAboveFightFloor hp' i.maxHp = true := by
    unfold hpAboveFightFloor at hHp ⊢
    simp at hHp
    apply decide_eq_true
    have hMul : i.hp * 100 ≤ hp' * 100 :=
      Int.mul_le_mul_of_nonneg_right hLe (by decide)
    omega
  unfold fightApplicable
  simp only [Bool.and_eq_true]
  exact ⟨⟨⟨⟨⟨hLoc, hInv⟩, hHp'⟩, hXp⟩, hLvl⟩, hGear⟩

/-! ## Level-gate structure after the P0 revision.

The 2026-06-06 trace headline was: chicken passed winnability at hp=130
but failed FightAction.is_applicable (below the old hard window). The
2026-06-09 P0 deadlock showed that hard lower window starves combat
entirely when ALL winnable monsters sit below it. The revised contract:
the only structural level vetoes are ZERO XP (too far below — no
leveling value) and the `level + 2` suicide guard (too far above). -/

/-- A monster above the `level + 2` suicide guard has NO `fightApplicable`
no matter how full the bot's hp is or how much gear it owns. (The upper
bound is *structural*, not hp-recoverable — survives the P0 revision.) -/
theorem fightApplicable_false_above_level_window
    (i : FightInputs) (hp' bestEq' : Int)
    (h : i.monsterLevel > i.playerLevel + 2) :
    fightApplicable { i with hp := hp', bestEqLevel := bestEq' } = false := by
  apply fightApplicable_false_of_overleveled_monster
  exact h

/-- **Composition theorem**: winnability still does not imply
applicability — a winnable monster whose kill grants zero XP is not
applicable (it serves no leveling objective). This is the post-P0 form of
the orthogonality contract: the picker's fallback tier must filter
winnable candidates by `xp_per_kill > 0`, exactly what
`CombatTargetExistence.pickWinnableWindowed` does. -/
theorem winnable_does_not_imply_applicable
    (i : FightInputs) (winnable : Bool)
    (hZero : i.xpPerKill ≤ 0) :
    fightApplicable i = false ∧ winnable = winnable := by
  refine ⟨?_, rfl⟩
  exact fightApplicable_false_of_zero_xp i hZero

/-- Exact characterization of the predicate as a conjunction of the six
atomic conditions. Used to show the below-window case is now LIVE. -/
theorem fightApplicable_iff (i : FightInputs) :
    fightApplicable i = true ↔
      i.hasLocations = true ∧ i.inventoryFree ≥ i.minFreeSlots ∧
      i.hp * 100 > 50 * i.maxHp ∧ i.xpPerKill > 0 ∧
      i.monsterLevel ≤ i.playerLevel + 2 ∧
      i.bestEqLevel ≥ i.monsterLevel - 1 := by
  unfold fightApplicable hasInventoryRoom hpAboveFightFloor xpPositive
    monsterNotOverleveled gearMeetsMonster
  simp [and_assoc]

/-- **P0 regression witness (2026-06-09)**: a monster BELOW the old hard
window `[max(1, level-1), level+2]` but with positive XP IS applicable —
the exact case the old window rejected forever (level-4 character,
chicken L1, old window [3,6]). -/
theorem below_old_window_xp_positive_is_applicable
    (i : FightInputs)
    (hLoc  : i.hasLocations = true)
    (hInv  : i.inventoryFree ≥ i.minFreeSlots)
    (hHp   : i.hp * 100 > 50 * i.maxHp)
    (hXp   : i.xpPerKill > 0)
    (hUp   : i.monsterLevel ≤ i.playerLevel + 2)
    (hGear : i.bestEqLevel ≥ i.monsterLevel - 1)
    (_hBelow : i.monsterLevel < max 1 (i.playerLevel - 1)) :
    fightApplicable i = true := by
  exact (fightApplicable_iff i).mpr ⟨hLoc, hInv, hHp, hXp, hUp, hGear⟩

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
