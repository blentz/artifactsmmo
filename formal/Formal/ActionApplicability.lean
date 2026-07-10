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

1. Specifies `fightApplicable` as a conjunction of 5 atomic conditions
   (mirrors Python `FightAction.is_applicable` in `actions/combat.py`
   exactly). The gear pre-filter (`best_eq >= monster_level - 1`) was
   REMOVED 2026-06-29 in lockstep with Python (commits 0cd5407b,
   5de3ce42) — it starved combat when no owned gear met the window.
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
  minFreeSlots  : Int
  xpPerKill     : Int       -- game_data.xp_per_kill(monster, playerLevel)
  dropFarm      : Bool := false
  -- Drop-farm variant (2026-07-06): a demand-serving goal may emit a fight
  -- whose sole purpose is the monster's DROPS (grey mob, zero xp) —
  -- GatherMaterialsGoal for recipe-closure drops (grey_farm_allowed policy)
  -- and, since 2026-07-08 (GAP-6), UpgradeEquipmentGoal for its own equip
  -- target's dropper. The flag bypasses ONLY the xpPositive lower gate;
  -- every structural gate (locations, inventory room, hp floor, level+2
  -- suicide guard) still applies. Mirrors Python FightAction.drop_farm.

/-- The composite predicate. Matches Python `FightAction.is_applicable`
term-by-term: locations, inventory room, hp floor, (drop-farm OR xp>0)
lower gate, level+2 suicide guard. The gear pre-filter
(`best_eq >= monster_level - 1`) was REMOVED 2026-06-29 in lockstep with
Python `is_applicable` (commits 0cd5407b, 5de3ce42): it starved combat when
no owned gear met the window. -/
def fightApplicable (i : FightInputs) : Bool :=
  i.hasLocations
    && hasInventoryRoom i.inventoryFree i.minFreeSlots
    && hpAboveFightFloor i.hp i.maxHp
    && (i.dropFarm || xpPositive i.xpPerKill)
    && monsterNotOverleveled i.playerLevel i.monsterLevel

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

/-- If the kill grants zero (or negative) XP and the fight is NOT a
drop-farm variant, the predicate is false. This is the NEW lower gate —
replaces `fightApplicable_false_of_underleveled_monster` (the old hard
window). A drop-farm fight (dropFarm = true) bypasses exactly this gate. -/
theorem fightApplicable_false_of_zero_xp (i : FightInputs)
    (h : i.xpPerKill ≤ 0) (hFarm : i.dropFarm = false) :
    fightApplicable i = false := by
  unfold fightApplicable xpPositive
  have : ¬ (i.xpPerKill > 0) := by omega
  simp [this, hFarm]

/-- If monster level exceeds `state.level + 2`, the predicate is false.
The suicide guard survives the P0 revision unchanged. -/
theorem fightApplicable_false_of_overleveled_monster (i : FightInputs)
    (h : i.monsterLevel > i.playerLevel + 2) :
    fightApplicable i = false := by
  unfold fightApplicable monsterNotOverleveled
  have : ¬ (i.monsterLevel ≤ i.playerLevel + 2) := by omega
  simp [this]

/-! ## Monotonicity. -/

/-- More current hp never breaks applicability (max_hp held fixed). -/
theorem fightApplicable_mono_in_hp (i : FightInputs) (hp' : Int)
    (hLe : i.hp ≤ hp')
    (hApp : fightApplicable i = true) :
    fightApplicable { i with hp := hp' } = true := by
  unfold fightApplicable at hApp
  simp only [Bool.and_eq_true] at hApp
  obtain ⟨⟨⟨⟨hLoc, hInv⟩, hHp⟩, hXp⟩, hLvl⟩ := hApp
  have hHp' : hpAboveFightFloor hp' i.maxHp = true := by
    unfold hpAboveFightFloor at hHp ⊢
    simp at hHp
    apply decide_eq_true
    have hMul : i.hp * 100 ≤ hp' * 100 :=
      Int.mul_le_mul_of_nonneg_right hLe (by decide)
    omega
  unfold fightApplicable
  simp only [Bool.and_eq_true]
  exact ⟨⟨⟨⟨hLoc, hInv⟩, hHp'⟩, hXp⟩, hLvl⟩

/-! ## Level-gate structure after the P0 revision.

The 2026-06-06 trace headline was: chicken passed winnability at hp=130
but failed FightAction.is_applicable (below the old hard window). The
2026-06-09 P0 deadlock showed that hard lower window starves combat
entirely when ALL winnable monsters sit below it. The revised contract:
the only structural level vetoes are ZERO XP (too far below — no
leveling value) and the `level + 2` suicide guard (too far above). -/

/-- A monster above the `level + 2` suicide guard has NO `fightApplicable`
no matter how full the bot's hp is. (The upper bound is *structural*, not
hp-recoverable — survives the P0 revision.) -/
theorem fightApplicable_false_above_level_window
    (i : FightInputs) (hp' : Int)
    (h : i.monsterLevel > i.playerLevel + 2) :
    fightApplicable { i with hp := hp' } = false := by
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
    (hZero : i.xpPerKill ≤ 0) (hFarm : i.dropFarm = false) :
    fightApplicable i = false ∧ winnable = winnable := by
  refine ⟨?_, rfl⟩
  exact fightApplicable_false_of_zero_xp i hZero hFarm

/-- Exact characterization of the predicate as a conjunction of the five
atomic conditions (the lower gate is now the drop-farm/xp disjunction).
Used to show the below-window case is now LIVE. -/
theorem fightApplicable_iff (i : FightInputs) :
    fightApplicable i = true ↔
      i.hasLocations = true ∧ i.inventoryFree ≥ i.minFreeSlots ∧
      i.hp * 100 > 50 * i.maxHp ∧ (i.dropFarm = true ∨ i.xpPerKill > 0) ∧
      i.monsterLevel ≤ i.playerLevel + 2 := by
  unfold fightApplicable hasInventoryRoom hpAboveFightFloor xpPositive
    monsterNotOverleveled
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
    (_hBelow : i.monsterLevel < max 1 (i.playerLevel - 1)) :
    fightApplicable i = true := by
  exact (fightApplicable_iff i).mpr ⟨hLoc, hInv, hHp, Or.inr hXp, hUp⟩

/-! ## Capability ⇒ structural applicability (the L50 fight-liveness seam). -/

/-- Capability ⇒ structural applicability: if the picker may return `m`
(winnable and within `[max(1,lvl-1), lvl+2]`) and the transient/spawn
preconditions hold, then `fightApplicable` is true. The "fight never
deadlocks given a winnable in-window target" seam for the L50 proof.

Hypotheses match the five surviving gates of the post-edit `fightApplicable`
exactly (gear pre-filter removed). They are JOINTLY SATISFIABLE — see
`winnable_inWindow_imp_fightApplicable_nonvacuous` below for a concrete
`FightInputs` meeting all five. -/
theorem winnable_inWindow_imp_fightApplicable
    (i : FightInputs)
    (hLoc : i.hasLocations = true)
    (hInv : hasInventoryRoom i.inventoryFree i.minFreeSlots = true)
    (hHp  : hpAboveFightFloor i.hp i.maxHp = true)
    (hWin : i.monsterLevel ≤ i.playerLevel + 2)
    (hXp  : xpPositive i.xpPerKill = true) :
    fightApplicable i = true := by
  unfold fightApplicable
  simp only [Bool.and_eq_true]
  refine ⟨⟨⟨⟨hLoc, hInv⟩, hHp⟩, ?_⟩, decide_eq_true hWin⟩
  simp [hXp]

/-- **Non-vacuity witness** for `winnable_inWindow_imp_fightApplicable`:
a concrete `FightInputs` that simultaneously satisfies all five hypotheses
(`hasLocations`, full inventory room, full HP, in-window, positive XP). This
kernel-checks that the consistency lemma's premises are jointly realizable,
so the lemma is NOT vacuously true. -/
theorem winnable_inWindow_imp_fightApplicable_nonvacuous :
    let i : FightInputs :=
      { hasLocations := true, inventoryFree := 1, hp := 100, maxHp := 100,
        playerLevel := 5, monsterLevel := 5, minFreeSlots := 1,
        xpPerKill := 10 }
    i.hasLocations = true
      ∧ hasInventoryRoom i.inventoryFree i.minFreeSlots = true
      ∧ hpAboveFightFloor i.hp i.maxHp = true
      ∧ i.monsterLevel ≤ i.playerLevel + 2
      ∧ xpPositive i.xpPerKill = true
      ∧ fightApplicable i = true := by
  refine ⟨rfl, by decide, by decide, by decide, by decide, ?_⟩
  decide

/-! ## Drop-farm bypass scope (2026-07-06).

The drop-farm variant exists so a DEMAND — a recipe material or, since
2026-07-08 (GAP-6), the emitting goal's own equip target — can hunt a grey
mob's drops (server drops loot regardless of xp). The bypass must be EXACTLY
the xp gate: every structural veto survives. -/

/-- With `dropFarm` set and zero xp, applicability reduces exactly to the
four structural gates — the bypass swallows nothing else. -/
theorem dropFarm_zero_xp_applicable_iff_structural (i : FightInputs)
    (hFarm : i.dropFarm = true) (_hZero : i.xpPerKill ≤ 0) :
    fightApplicable i = true ↔
      i.hasLocations = true ∧ i.inventoryFree ≥ i.minFreeSlots ∧
      i.hp * 100 > 50 * i.maxHp ∧ i.monsterLevel ≤ i.playerLevel + 2 := by
  rw [fightApplicable_iff]
  simp [hFarm]

/-- Structural veto survives the bypass: a drop-farm fight at or below the
hp floor is still inapplicable. (Same holds for locations / inventory /
suicide-guard via the unchanged `fightApplicable_false_of_*` lemmas, which
carry no xp hypothesis.) -/
theorem dropFarm_does_not_bypass_hp_floor (i : FightInputs)
    (h : i.hp * 100 ≤ 50 * i.maxHp) :
    fightApplicable i = false :=
  fightApplicable_false_of_low_hp i h

/-- Non-vacuity witness: a grey-mob drop-farm fight (zero xp, dropFarm set,
all structural gates satisfied) IS applicable — the live case this arm
exists for (L12 character hunting feathers from an L1 chicken). -/
theorem dropFarm_grey_mob_applicable_nonvacuous :
    let i : FightInputs :=
      { hasLocations := true, inventoryFree := 1, hp := 100, maxHp := 100,
        playerLevel := 12, monsterLevel := 1, minFreeSlots := 1,
        xpPerKill := 0, dropFarm := true }
    fightApplicable i = true := by
  decide

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
opaque flag, slot compatibility is decidable.

**HONESTY NOTE — slot-room gate lives in Python, deliberately omitted here
(slot-aware-inventory-room spec 2026-07-09, Task 5/8).** `EquipAction.
is_applicable` (Python `actions/equip.py`) carries a NET-slot-room gate:
equipping C into an occupied slot displaces the worn item O back into the
bag, so it needs `has_room(new_stacks, added_qty=0, slots_free, qty_free)`
where `new_stacks = max(0, O_needs_slot − C_frees_slot)` — the gate that
rejects the 20/20-slots-full "497-doomed equip" livelock (a held upgrade
whose displaced armor has nowhere to land). `equipApplicable` below models
ONLY ownership + slot-type compatibility and intentionally OMITS that slot
term: it is a partial proof-side sketch, NOT a differential mirror. Unlike
`fightApplicable` (which term-by-term mirrors Python and is exercised by the
liveness chain), `equipApplicable` is bound to no oracle and no
`formal/diff` value-lockstep — the Manifest carries only its
`#check equipApplicable_iff` proof-existence reference. Adding a
`hasSlotRoom` conjunct here would therefore be DEAD Lean (proven against
nothing). The slot gate's correctness is instead pinned in Python: the unit
gate (`actions/equip.py` + its tests) and the end-to-end livelock scenario
`tests/test_ai/scenarios/test_slot_exhaustion.py` (relief routed before the
doomed equip), plus the shared `InventoryRoom.hasRoom` core (mirrored in
`formal/Formal/InventoryRoom.lean`, differentially tested) that Python
`inventory_room.has_room` computes. Fight is NOT slot-gated in this fix
(its `hasInventoryRoom` term is the pre-existing QUANTITY floor,
`inventory_free ≥ 1`), so nothing changes there. -/

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
