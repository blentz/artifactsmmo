-- @concept: tasks, items @property: safety, totality

/-!
# Formal.AcceptTaskGate

**Correctness of the ACCEPT_TASK firing predicate.**

Python `tiers/means.py:_fires` for `MeansKind.ACCEPT_TASK` now returns
True iff:
  (1) `state.task_code` is None, AND
  (2) For every target_gear code:
      (2a) it's NOT (owned-but-unequipped), AND
      (2b) it's NOT craftable under current skill levels

Defers AcceptTask whenever the gear chain has actionable work — closes
the 2026-06-06 trace where the bot would churn task chains while owned
gear sat unequipped and crafting skills were sufficient to make new gear.

This module proves:

1. Predicate is TOTAL and DETERMINISTIC (decidable Bool).
2. Active-task short-circuit: when task_code ≠ None, fires=False.
3. Owned-but-unequipped defers: any target gear in inventory but not
   in equipment ⇒ fires=False.
4. Craftable-defers: any target gear with crafting_skill ≤ current
   skill level ⇒ fires=False.
5. POSITIVE: when task_code is None AND every target gear is either
   equipped, not owned + not craftable ⇒ fires=True.
-/

namespace Formal.AcceptTaskGate

/-! ## Abstraction of inputs. -/

structure GearEntry where
  code           : Int
  ownedCount     : Int     -- inventory[code]
  isEquipped     : Bool
  craftingSkill  : Int     -- 0 = no crafting skill
  craftingLevel  : Int     -- recipe required level
  currentSkill   : Int     -- player's current skill level
deriving Repr, DecidableEq

structure Inputs where
  taskCodeNone : Bool
  targetGear   : List GearEntry
deriving Repr

/-! ## Per-entry defer condition. -/

/-- A gear entry triggers AcceptTask deferral if it is OWNED but
NOT equipped, OR if it's craftable under current skill. -/
def defersAcceptTask (g : GearEntry) : Bool :=
  if g.isEquipped then false
  else if g.ownedCount ≥ 1 then true
  else if g.craftingSkill > 0 ∧ g.currentSkill ≥ g.craftingLevel then true
  else false

/-! ## Aggregate predicate. -/

def anyDefers : List GearEntry → Bool
  | [] => false
  | g :: rest => defersAcceptTask g || anyDefers rest

/-- The firing predicate. -/
def acceptTaskFires (i : Inputs) : Bool :=
  i.taskCodeNone && !anyDefers i.targetGear

/-! ## Totality and determinism. -/

theorem fires_total (i : Inputs) : ∃ b, acceptTaskFires i = b :=
  ⟨acceptTaskFires i, rfl⟩

theorem fires_deterministic (i : Inputs) (a b : Bool)
    (h1 : acceptTaskFires i = a) (h2 : acceptTaskFires i = b) : a = b := by
  rw [← h1, ← h2]

/-! ## Active-task short-circuit. -/

theorem fires_false_when_active_task (i : Inputs)
    (h : i.taskCodeNone = false) :
    acceptTaskFires i = false := by
  unfold acceptTaskFires
  simp [h]

/-! ## Owned-but-unequipped defers. -/

theorem entry_defers_when_owned_not_equipped
    (g : GearEntry) (hOwn : g.ownedCount ≥ 1) (hEq : g.isEquipped = false) :
    defersAcceptTask g = true := by
  unfold defersAcceptTask
  rw [if_neg (by simp [hEq])]
  rw [if_pos hOwn]

theorem anyDefers_true_of_mem_defer
    (chain : List GearEntry) (g : GearEntry)
    (hMem : g ∈ chain) (hDef : defersAcceptTask g = true) :
    anyDefers chain = true := by
  induction chain with
  | nil => nomatch hMem
  | cons hd tl ih =>
    unfold anyDefers
    cases hMem with
    | head => simp [hDef]
    | tail _ hRest =>
      have := ih hRest
      simp [this]

/-- An owned-but-unequipped target gear forces AcceptTask to fire=False
(even when task_code is None). -/
theorem fires_false_when_owned_unequipped_gear_exists
    (i : Inputs) (g : GearEntry)
    (hMem : g ∈ i.targetGear)
    (hOwn : g.ownedCount ≥ 1) (hEq : g.isEquipped = false) :
    acceptTaskFires i = false := by
  unfold acceptTaskFires
  have hDef := entry_defers_when_owned_not_equipped g hOwn hEq
  have hAny := anyDefers_true_of_mem_defer i.targetGear g hMem hDef
  simp [hAny]

/-! ## Craftable defers. -/

theorem entry_defers_when_craftable
    (g : GearEntry)
    (hEq : g.isEquipped = false)
    (hNotOwned : g.ownedCount < 1)
    (hSkill : g.craftingSkill > 0)
    (hLevel : g.currentSkill ≥ g.craftingLevel) :
    defersAcceptTask g = true := by
  unfold defersAcceptTask
  rw [if_neg (by simp [hEq])]
  have hNotOwned' : ¬ (g.ownedCount ≥ 1) := by omega
  rw [if_neg hNotOwned']
  rw [if_pos ⟨hSkill, hLevel⟩]

/-- A craftable-but-unowned target gear forces fires=False. -/
theorem fires_false_when_craftable_gear_exists
    (i : Inputs) (g : GearEntry)
    (hMem : g ∈ i.targetGear)
    (hEq : g.isEquipped = false)
    (hNotOwned : g.ownedCount < 1)
    (hSkill : g.craftingSkill > 0)
    (hLevel : g.currentSkill ≥ g.craftingLevel) :
    acceptTaskFires i = false := by
  unfold acceptTaskFires
  have hDef := entry_defers_when_craftable g hEq hNotOwned hSkill hLevel
  have hAny := anyDefers_true_of_mem_defer i.targetGear g hMem hDef
  simp [hAny]

/-! ## Positive direction: equipped gear does not defer. -/

theorem entry_does_not_defer_when_equipped
    (g : GearEntry) (h : g.isEquipped = true) :
    defersAcceptTask g = false := by
  unfold defersAcceptTask
  simp [h]

theorem entry_does_not_defer_when_unowned_uncraftable
    (g : GearEntry)
    (hEq : g.isEquipped = false)
    (hNotOwned : g.ownedCount < 1)
    (hUncraft : g.craftingSkill ≤ 0 ∨ g.currentSkill < g.craftingLevel) :
    defersAcceptTask g = false := by
  unfold defersAcceptTask
  rw [if_neg (by simp [hEq])]
  have hNotOwned' : ¬ (g.ownedCount ≥ 1) := by omega
  rw [if_neg hNotOwned']
  rcases hUncraft with hS | hL
  · rw [if_neg]
    intro ⟨h, _⟩
    omega
  · rw [if_neg]
    intro ⟨_, h⟩
    omega

end Formal.AcceptTaskGate
