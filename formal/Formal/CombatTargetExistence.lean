-- @concept: combat, monsters @property: reachability, safety
import Formal.WinnableCascade

/-!
# Formal.CombatTargetExistence

**Composition-correctness model of combat-target selection.**

The grind target is the two-arm cascade `farm_target`
(`ai/gear_objective_context.py` → `winnable_cascade.winnable_farm_target_pure`):
the held PURSUE monsters-task's monster first, otherwise the gear objective's
`m*` while its `L*` is held, otherwise no target (spec 2026-10-18 §2.4: no
fight is chosen for XP while a piece of `L*` is missing).

Plan C Task 4 deleted the player's window-preferred winnable-monster pick
(`player._pick_winnable_monster`), the third arm of the old cascade.
`winnableFarmTarget` is mapped onto the shrunk cascade
(`winnableFarmTarget_eq_cascade`). The picker model below
(`pickWinnable` / `pickWinnableWindowed` / `pickBest` and their theorems,
bridged to `ai/combat_picker.pick_winnable_monster_pure`) has no production
caller now; it stays while `Liveness.GearTierLeveling` (and through it
`PerceptionRefresh` / `LevelFiftyReachableP`) grounds combat-target existence
on it, pending a ruling.

Theorems shipped here:

* `winnableFarmTarget_task_override` — when a PURSUE monsters-task is
  active, the cascade returns the task target.
* `winnableFarmTarget_falls_through_no_task` — with no task and a held
  `m*`, the cascade returns `m*`.
* `winnableFarmTarget_none_no_task` — with no task, `none` means there is
  no `m*` or its `L*` is not held.
* `winnableFarmTarget_eq_cascade` — under any code embedding, this model
  IS `Formal.WinnableCascade.winnableFarmTargetPure`.

Monsters are integer codes. Phase G3 of
`docs/PLAN_composition_correctness.md`.
-/

namespace Formal.CombatTargetExistence

/-! ## Abstract model. -/

/-- A monster catalog entry: integer code + level. -/
structure Monster where
  code  : Int
  level : Int
deriving Repr, DecidableEq

/-- A `Picker` is parametric in a winnability predicate. -/
abbrev WinnableFn := Monster → Bool

/-! ## The HIGHEST-LEVEL-WINNABLE picker, modeled in pure Lean.

Mirrored `player._pick_winnable_monster` (deleted, plan C Task 4): scan
monsters, keep the maximum-level entry whose winnability flag is true. Returns `none`
iff no monster is winnable. -/

/-- Scan a list, return the highest-level winnable monster (left-fold
with strict-improvement; ties keep the EARLIER candidate). -/
def pickBest (winnable : WinnableFn) : Option Monster → List Monster → Option Monster
  | acc, [] => acc
  | acc, m :: rest =>
      if winnable m then
        match acc with
        | none => pickBest winnable (some m) rest
        | some best =>
            if m.level > best.level
              then pickBest winnable (some m) rest
              else pickBest winnable (some best) rest
      else
        pickBest winnable acc rest

/-- Top-level entry point: pick from an empty accumulator. -/
def pickWinnable (winnable : WinnableFn) (monsters : List Monster) : Option Monster :=
  pickBest winnable none monsters

/-! ## Existence theorem.

If any monster in the list is winnable, the picker returns a `Some`. -/

theorem pickBest_some_of_acc_some
    (winnable : WinnableFn) (best : Monster) (xs : List Monster) :
    ∃ m, pickBest winnable (some best) xs = some m := by
  induction xs generalizing best with
  | nil => exact ⟨best, rfl⟩
  | cons m rest ih =>
    show ∃ k, pickBest winnable (some best) (m :: rest) = some k
    rw [show pickBest winnable (some best) (m :: rest) =
         (if winnable m then
            if m.level > best.level
              then pickBest winnable (some m) rest
              else pickBest winnable (some best) rest
          else pickBest winnable (some best) rest) from rfl]
    by_cases hWin : winnable m
    · rw [if_pos hWin]
      by_cases hLt : m.level > best.level
      · rw [if_pos hLt]
        exact ih m
      · rw [if_neg hLt]
        exact ih best
    · rw [if_neg hWin]
      exact ih best

/-- **The headline theorem**: if any monster in `xs` is winnable, the
picker returns SOME monster. The picker NEVER returns `none` when a
winnable target exists. -/
theorem pickWinnable_some_of_exists
    (winnable : WinnableFn) (xs : List Monster)
    (h : ∃ m ∈ xs, winnable m = true) :
    ∃ target, pickWinnable winnable xs = some target := by
  obtain ⟨m, hMem, hWin⟩ := h
  unfold pickWinnable
  induction xs with
  | nil => nomatch hMem
  | cons hd tl ih =>
    by_cases hHead : m = hd
    · -- m = hd: substitute m := hd; winnable hd via hWin.
      rw [hHead] at hWin
      show ∃ k, pickBest winnable none (hd :: tl) = some k
      rw [show pickBest winnable none (hd :: tl) =
           (if winnable hd then pickBest winnable (some hd) tl
                           else pickBest winnable none tl) from rfl]
      rw [if_pos hWin]
      exact pickBest_some_of_acc_some winnable hd tl
    · -- m ≠ hd: m is in tl, induct.
      have hTail : m ∈ tl := by
        cases hMem with
        | head => exact absurd rfl hHead
        | tail _ h => exact h
      show ∃ k, pickBest winnable none (hd :: tl) = some k
      rw [show pickBest winnable none (hd :: tl) =
           (if winnable hd then pickBest winnable (some hd) tl
                           else pickBest winnable none tl) from rfl]
      by_cases hHd : winnable hd
      · rw [if_pos hHd]
        exact pickBest_some_of_acc_some winnable hd tl
      · rw [if_neg hHd]
        exact ih hTail

/-! ## Empty / no-winnable corollary.

The picker returns `none` IFF no monster is winnable. (Soundness of
the existence claim — `none` is not a false-negative.) -/

theorem pickBest_none_iff_acc_none_and_none_winnable
    (winnable : WinnableFn) (xs : List Monster) :
    pickBest winnable none xs = none ↔ ∀ m ∈ xs, winnable m = false := by
  induction xs with
  | nil =>
    simp [pickBest]
  | cons hd tl ih =>
    constructor
    · -- ⇒
      intro hNone m hMem
      unfold pickBest at hNone
      by_cases hHd : winnable hd = true
      · rw [if_pos hHd] at hNone
        obtain ⟨k, hk⟩ := pickBest_some_of_acc_some winnable hd tl
        rw [hk] at hNone
        exact absurd hNone (by simp)
      · rw [if_neg hHd] at hNone
        cases hMem with
        | head => exact Bool.eq_false_iff.mpr hHd
        | tail _ hRest => exact (ih.mp hNone) m hRest
    · -- ⇐
      intro hAll
      unfold pickBest
      have hHd : winnable hd = false := hAll hd List.mem_cons_self
      rw [if_neg (by simp [hHd])]
      exact ih.mpr (fun m hm => hAll m (List.mem_cons_of_mem _ hm))

/-! ## Window-preferred picker with liveness fallback (P0 2026-06-09).

Mirrors `combat_picker.pick_winnable_monster_pure` (diff-locked by
`formal/diff/test_combat_picker_diff.py`). Since plan C Task 4 nothing in
production calls it; it is kept, with its theorems, because
`Liveness.GearTierLeveling` grounds the L50 chain on
`pickWinnableWindowed_some_of_winnable_xp_positive` (pending a ruling). -/

/-- The FightAction level window: `max(1, L-1) ≤ level ≤ L+2`. -/
def inWindow (playerLevel : Int) (m : Monster) : Bool :=
  decide (max 1 (playerLevel - 1) ≤ m.level ∧ m.level ≤ playerLevel + 2)

/-- The suicide-guard upper bound only (the fallback tier's level filter —
the lower bound is replaced by the xp>0 oracle). -/
def notOverleveled (playerLevel : Int) (m : Monster) : Bool :=
  decide (m.level ≤ playerLevel + 2)

/-- Window-preferred picker: try the window tier; when it is empty of
winnable monsters, fall back to the highest-level winnable monster with
positive XP under the suicide guard. -/
def pickWinnableWindowed (playerLevel : Int) (winnable xpPos : WinnableFn)
    (monsters : List Monster) : Option Monster :=
  match pickWinnable (fun m => winnable m && inWindow playerLevel m) monsters with
  | some best => some best
  | none =>
      pickWinnable
        (fun m => winnable m && xpPos m && notOverleveled playerLevel m) monsters

/-- **The headline theorem (TRUE of production)**: if any monster is
winnable with positive XP under the suicide guard, the windowed picker
returns SOME target. The fallback tier makes this nearly definitional —
and it is exactly the claim the P0 deadlock violated (window-only picker
returned `none` while chicken/yellow_slime were winnable and XP-positive). -/
theorem pickWinnableWindowed_some_of_winnable_xp_positive
    (playerLevel : Int) (winnable xpPos : WinnableFn) (xs : List Monster)
    (h : ∃ m ∈ xs, winnable m = true ∧ xpPos m = true ∧
                   notOverleveled playerLevel m = true) :
    ∃ target, pickWinnableWindowed playerLevel winnable xpPos xs = some target := by
  unfold pickWinnableWindowed
  cases hWin : pickWinnable (fun m => winnable m && inWindow playerLevel m) xs with
  | some best => exact ⟨best, rfl⟩
  | none =>
      obtain ⟨m, hMem, hW, hX, hO⟩ := h
      have hFall :
          ∃ t, pickWinnable
            (fun m => winnable m && xpPos m && notOverleveled playerLevel m) xs
            = some t :=
        pickWinnable_some_of_exists _ xs ⟨m, hMem, by simp [hW, hX, hO]⟩
      obtain ⟨t, hT⟩ := hFall
      exact ⟨t, hT⟩

/-- When the window tier finds a winnable monster, the windowed picker
returns the window tier's answer (the fallback is never consulted). -/
theorem pickWinnableWindowed_prefers_window
    (playerLevel : Int) (winnable xpPos : WinnableFn) (xs : List Monster)
    (best : Monster)
    (hWin : pickWinnable (fun m => winnable m && inWindow playerLevel m) xs
            = some best) :
    pickWinnableWindowed playerLevel winnable xpPos xs = some best := by
  unfold pickWinnableWindowed
  rw [hWin]

/-- `none` is honest: the windowed picker returns `none` only when NO
monster is simultaneously winnable, XP-positive, and under the suicide
guard — a true combat deadlock. -/
theorem pickWinnableWindowed_none_implies_no_viable_target
    (playerLevel : Int) (winnable xpPos : WinnableFn) (xs : List Monster)
    (hNone : pickWinnableWindowed playerLevel winnable xpPos xs = none) :
    ∀ m ∈ xs, (winnable m && xpPos m && notOverleveled playerLevel m) = false := by
  unfold pickWinnableWindowed at hNone
  cases hWin : pickWinnable (fun m => winnable m && inWindow playerLevel m) xs with
  | some best => rw [hWin] at hNone; exact absurd hNone (by simp)
  | none =>
      rw [hWin] at hNone
      exact (pickBest_none_iff_acc_none_and_none_winnable _ xs).mp hNone

/-- Task-aligned cascade: if `taskTarget` is `some code`, return it
immediately (the task forces the target). Otherwise return the gear
objective's `m*` (`pathTarget`) when its `L*` is held (`pathHeld`), else
`none`. This mirrors `farm_target`. -/
def winnableFarmTarget
    (taskTarget pathTarget : Option Int) (pathHeld : Bool) : Option Int :=
  match taskTarget with
  | some t => some t
  | none =>
    match pathTarget, pathHeld with
    | some p, true => some p
    | _, _ => none

theorem winnableFarmTarget_task_override
    (taskCode : Int) (pathTarget : Option Int) (pathHeld : Bool) :
    winnableFarmTarget (some taskCode) pathTarget pathHeld = some taskCode := by
  unfold winnableFarmTarget
  rfl

theorem winnableFarmTarget_falls_through_no_task (m : Int) :
    winnableFarmTarget none (some m) true = some m := rfl

theorem winnableFarmTarget_none_no_task
    (pathTarget : Option Int) (pathHeld : Bool)
    (hNone : winnableFarmTarget none pathTarget pathHeld = none) :
    pathTarget = none ∨ pathHeld = false := by
  unfold winnableFarmTarget at hNone
  cases pathTarget with
  | none => exact Or.inl rfl
  | some p =>
    cases pathHeld with
    | false => exact Or.inr rfl
    | true => exact absurd hNone (by simp)

/-- The Int-coded model is the proved string cascade under any code
embedding `f`: codes are payload, never compared. -/
theorem winnableFarmTarget_eq_cascade (f : Int → String)
    (taskTarget pathTarget : Option Int) (pathHeld : Bool) :
    (winnableFarmTarget taskTarget pathTarget pathHeld).map f =
      Formal.WinnableCascade.winnableFarmTargetPure
        { taskMonster := taskTarget.map f, pathMonster := pathTarget.map f,
          pathWinnable := pathHeld } := by
  unfold winnableFarmTarget Formal.WinnableCascade.winnableFarmTargetPure
  cases taskTarget with
  | some t => rfl
  | none =>
    cases pathTarget with
    | none => cases pathHeld <;> rfl
    | some p => cases pathHeld <;> rfl

/-! Non-vacuity witnesses. -/

example : winnableFarmTarget none (some 7) true = some 7 := rfl
example : winnableFarmTarget none (some 7) false = none := rfl
example : winnableFarmTarget (some 3) (some 7) false = some 3 := rfl

end Formal.CombatTargetExistence
