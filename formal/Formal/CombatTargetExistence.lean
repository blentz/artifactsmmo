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
(`winnableFarmTarget_eq_cascade`). Ruling C4-b then
deleted the windowed picker model (`pickBest`, `pickWinnable`, `inWindow`,
`pickWinnableWindowed` and their six theorems), its extraction and bridge:
`Liveness.GearTierLeveling` grounds the below-cap combat objective on the gear
objective instead. `Monster`, `WinnableFn` and `notOverleveled` stay — they are
the vocabulary of `WinnableAcrossBand`.

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

/-- A winnability (or XP-positivity) predicate over catalogue entries. -/
abbrev WinnableFn := Monster → Bool

/-! ## The suicide guard. -/

/-- The suicide-guard upper bound: at most `FIGHT_LEVEL_GAP_CEILING` (2)
levels above the character — `gear_objective._candidates`' level filter. -/
def notOverleveled (playerLevel : Int) (m : Monster) : Bool :=
  decide (m.level ≤ playerLevel + 2)

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
