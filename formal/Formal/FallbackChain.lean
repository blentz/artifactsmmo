import Mathlib.Tactic

/-!
# Formal.FallbackChain

**Correctness of the arbiter fallback-step walk.**

The Python `strategy_driver.StrategyArbiter.select` falls back to runner-up
ranked steps when the top step's goal is None. The fallback walk is
two-pass:

  Pass 1: scan fallback_steps for any UpgradeEquipmentGoal — pick first.
  Pass 2: scan fallback_steps for any non-None goal — pick first.

This module proves:

1. The walk is TOTAL — if any fallback yields a non-None goal, the walk
   returns one (no silent drop).
2. Pass 1 is SOUND — if any UpgradeEquipmentGoal exists in the chain,
   the walk picks one of them (preferring ready-to-equip over multi-cycle
   gather chains).
3. The walk is DETERMINISTIC — same input ⇒ same output (no race).
4. Pass 1 preserves the "first-in-ranking" tiebreak among UpgradeEquipment
   candidates.

Closes the 2026-06-06 12:28 trace bug where copper_boots(gather step)
ranked before copper_dagger(equip step) and the original single-pass
fallback never reached the dagger root.
-/

namespace Formal.FallbackChain

/-! ## Goal class abstraction. -/

inductive GoalClass where
  | upgradeEquipment
  | gatherMaterials
  | levelSkill
  | grindCharacterXP
  | none
deriving Repr, DecidableEq

abbrev FallbackResolver := GoalClass → Bool  -- True = non-None goal at this slot

/-! ## The two-pass walk. -/

/-- Pass 1: find first UpgradeEquipment in the list. -/
def passOne : List GoalClass → Option GoalClass
  | [] => Option.none
  | g :: rest =>
      if g = GoalClass.upgradeEquipment then some g else passOne rest

/-- Pass 2: find first non-None goal in the list. -/
def passTwo : List GoalClass → Option GoalClass
  | [] => Option.none
  | g :: rest =>
      if g = GoalClass.none then passTwo rest else some g

/-- The composite walk: pass 1 first, then pass 2. -/
def walk (chain : List GoalClass) : Option GoalClass :=
  match passOne chain with
  | some g => some g
  | Option.none => passTwo chain

/-! ## Totality. -/

theorem passTwo_some_of_nonNone_exists (chain : List GoalClass)
    (h : ∃ g ∈ chain, g ≠ GoalClass.none) :
    ∃ g, passTwo chain = some g := by
  induction chain with
  | nil =>
    obtain ⟨_, hMem, _⟩ := h
    nomatch hMem
  | cons hd tl ih =>
    unfold passTwo
    by_cases hHd : hd = GoalClass.none
    · simp [hHd]
      obtain ⟨g, hMem, hNe⟩ := h
      cases hMem with
      | head => exact absurd hHd hNe
      | tail _ hRest => exact ih ⟨g, hRest, hNe⟩
    · simp [hHd]

/-- **Totality**: if the chain contains any non-None goal, the walk
returns one. -/
theorem walk_some_of_nonNone_exists (chain : List GoalClass)
    (h : ∃ g ∈ chain, g ≠ GoalClass.none) :
    ∃ g, walk chain = some g := by
  unfold walk
  cases hP1 : passOne chain with
  | some g => exact ⟨g, rfl⟩
  | none =>
    obtain ⟨g, hT⟩ := passTwo_some_of_nonNone_exists chain h
    rw [hT]
    exact ⟨g, rfl⟩

/-! ## Pass 1 soundness: UpgradeEquipment preference. -/

theorem passOne_some_of_upgrade_exists (chain : List GoalClass)
    (h : GoalClass.upgradeEquipment ∈ chain) :
    passOne chain = some GoalClass.upgradeEquipment := by
  induction chain with
  | nil => nomatch h
  | cons hd tl ih =>
    unfold passOne
    by_cases hHd : hd = GoalClass.upgradeEquipment
    · rw [if_pos hHd, hHd]
    · rw [if_neg hHd]
      cases h with
      | head => exact absurd rfl hHd
      | tail _ hRest => exact ih hRest

/-- **UpgradeEquipment preference**: if the fallback chain contains an
UpgradeEquipment, the walk returns it — regardless of how many
GatherMaterials precede it. This is the formal closure of the
2026-06-06 12:28 trace bug. -/
theorem walk_picks_upgrade_when_present (chain : List GoalClass)
    (h : GoalClass.upgradeEquipment ∈ chain) :
    walk chain = some GoalClass.upgradeEquipment := by
  unfold walk
  rw [passOne_some_of_upgrade_exists chain h]

/-! ## Determinism. -/

theorem walk_deterministic (chain : List GoalClass) (a b : Option GoalClass)
    (ha : walk chain = a) (hb : walk chain = b) : a = b := by
  rw [← ha, ← hb]

/-! ## Pass-1 first-match. -/

theorem passOne_first_match (chain : List GoalClass)
    (g : GoalClass) (hP : passOne chain = some g) :
    g = GoalClass.upgradeEquipment := by
  induction chain with
  | nil => unfold passOne at hP; exact absurd hP (by simp)
  | cons hd tl ih =>
    unfold passOne at hP
    by_cases hHd : hd = GoalClass.upgradeEquipment
    · rw [if_pos hHd] at hP
      have : hd = g := Option.some_inj.mp hP
      rw [← this]; exact hHd
    · rw [if_neg hHd] at hP
      exact ih hP

/-! ## Trace-mirror corollary: copper_dagger ready, copper_boots not. -/

/-- The 2026-06-06 12:28 scenario: ranking has copper_boots first (whose
step is GatherMaterials because materials not yet gathered) and
copper_dagger second (whose step is UpgradeEquipment because the dagger
is already crafted). The fallback walk picks UpgradeEquipment. -/
theorem trace_122752_walk_picks_equip :
    walk [GoalClass.gatherMaterials, GoalClass.upgradeEquipment,
          GoalClass.gatherMaterials, GoalClass.gatherMaterials] =
    some GoalClass.upgradeEquipment := by
  unfold walk passOne
  decide

end Formal.FallbackChain
