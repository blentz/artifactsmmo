-- @concept: liveness @property: safety, characterization
/-
Formal model of the pure decision boundary extracted from
`src/artifactsmmo_cli/ai/strategy_driver.py::objective_step_goal` (the
`ReachCharLevel` branch, lines 719-752) into
`src/artifactsmmo_cli/ai/objective_step_fight_core.py::objective_step_is_fight_pure`.

This is the production meaning of the Lean LIVENESS Bool `objectiveStepIsFight`
(`Formal/Liveness/Measure.lean`): whether the committed objective step is a
combat/char-leveling goal whose plan leads with Fight. It is the O5.4 perception
binding target — grounding the level-50 capstone's `CombatPersistent`/`hfair`
hypothesis (`Formal/Liveness/FightFairness.lean`) in the real StrategyArbiter
computation rather than asserting it.

PYTHON DECISION (`objective_step_is_fight_pure`):

  if not is_reach_char_level:   return False
  if not has_combat_monster:    return False
  bootstrap_gap = target - level
  items_task_active = (task_type == "items" and bool(task_code)
                       and task_total > 0 and task_progress < task_total)
  return not (bootstrap_gap > 4 and items_task_active)

FAITHFULNESS NOTES:

  * Nat subtraction. Python `bootstrap_gap = target - level` is `Int`; we model it
    with `Nat` truncating subtraction. The only use is the test `gap > 4`. When
    `target ≤ level` Python gives `gap ≤ 0` (not `> 4`) and `Nat` gives
    `target - level = 0` (not `> 4`) — they AGREE; and when `target > level + 4`
    both agree it is `> 4`. So `Nat` is exact for this predicate.

  * `bool(task_code)`. Python treats `None` and `""` as falsy. We model `task_code`
    as a `String` with the empty string standing for both; `taskCode ≠ ""` mirrors
    `bool(task_code)`. The differential harness encodes Python `None → ""`.

  * Honest slice (NOT a surrogate). The other `objective_step_goal` branches
    (`ObtainItem`, `ReachSkillLevel`) are by definition NOT combat-led and yield
    `objectiveStepIsFight = False`; modelling only the `ReachCharLevel` slice is the
    entire meaning of the Bool, not a stand-in for the whole routing function.

Lean core only — no mathlib. All conditions decidable (Nat order, String equality).
-/

namespace Formal.ObjectiveStepFight

/-- The pure decision boundary. Mirrors `objective_step_is_fight_pure`
component-for-component.

`isReachCharLevel` and `hasCombatMonster` are the routing gates; `target`/`level`
the char-level gap; `taskType`/`taskCode`/`taskTotal`/`taskProgress` the
items-task stand-down state. Returns `Bool` to match Python. -/
def objectiveStepIsFightPure (isReachCharLevel : Bool) (target level : Nat)
    (hasCombatMonster : Bool) (taskType taskCode : String)
    (taskTotal taskProgress : Nat) : Bool :=
  if ¬ isReachCharLevel then false
  else if ¬ hasCombatMonster then false
  else if target - level > 4
            ∧ taskType = "items" ∧ taskCode ≠ "" ∧ taskTotal > 0 ∧ taskProgress < taskTotal
       then false
  else true

/-- `itemsTaskActive` — the production items-task stand-down predicate, surfaced as
a definition so the role theorems read against it. -/
def itemsTaskActive (taskType taskCode : String) (taskTotal taskProgress : Nat) : Prop :=
  taskType = "items" ∧ taskCode ≠ "" ∧ taskTotal > 0 ∧ taskProgress < taskTotal

/-! ### Role theorems. -/

/-- (characterization) EXACT spec. Fires iff a combat objective is committed
(`ReachCharLevel` + combat monster) AND the long-haul items-task stand-down does
NOT apply. This is the anti-weakening contract pinned in `Contracts.lean`. -/
theorem fires_iff (isReachCharLevel hasCombatMonster : Bool)
    (target level taskTotal taskProgress : Nat) (taskType taskCode : String) :
    objectiveStepIsFightPure isReachCharLevel target level hasCombatMonster
        taskType taskCode taskTotal taskProgress = true
      ↔ (isReachCharLevel = true ∧ hasCombatMonster = true ∧
          ¬ (target - level > 4 ∧ itemsTaskActive taskType taskCode taskTotal taskProgress)) := by
  unfold objectiveStepIsFightPure itemsTaskActive
  by_cases h1 : isReachCharLevel = true
  · by_cases h2 : hasCombatMonster = true
    · by_cases h3 : target - level > 4
              ∧ taskType = "items" ∧ taskCode ≠ "" ∧ taskTotal > 0 ∧ taskProgress < taskTotal
      · simp [h1, h2, h3]
      · simp [h1, h2, h3]
    · simp [h1, h2]
  · simp [h1]

/-- (a) Not a `ReachCharLevel` step ⇒ never Fight-led (unconditional). -/
theorem not_reach_char_level_never_fires (target level taskTotal taskProgress : Nat)
    (hasCombatMonster : Bool) (taskType taskCode : String) :
    objectiveStepIsFightPure false target level hasCombatMonster
        taskType taskCode taskTotal taskProgress = false := by
  unfold objectiveStepIsFightPure
  simp

/-- Non-vacuity witness for (a): even with a combat monster and no items task,
`isReachCharLevel = false` blocks. -/
example : objectiveStepIsFightPure false 50 3 true "" "" 0 0 = false :=
  not_reach_char_level_never_fires 50 3 0 0 true "" ""

/-- (b) No combat monster ⇒ never Fight-led. The model cannot claim a fight when
production has no target — the safety direction of the perception binding. -/
theorem no_combat_monster_never_fires (target level taskTotal taskProgress : Nat)
    (taskType taskCode : String) :
    objectiveStepIsFightPure true target level false taskType taskCode taskTotal taskProgress
      = false := by
  unfold objectiveStepIsFightPure
  simp

/-- Non-vacuity witness for (b): a committed `ReachCharLevel` with no items task
STILL does not fire when the combat monster is absent. -/
example : objectiveStepIsFightPure true 50 3 false "" "" 0 0 = false :=
  no_combat_monster_never_fires 50 3 0 0 "" ""

/-- (c, LIVENESS) Bootstrap guarantee. A committed `ReachCharLevel` with a combat
monster and a SMALL level gap (`target - level ≤ 4`) ALWAYS leads with Fight —
regardless of any active items task. This is the property the level-50 leveling
path relies on: the bootstrap char-level step breaks the no-combat livelock and
keeps the planner fighting while underleveled. -/
theorem bootstrap_always_fires (target level taskTotal taskProgress : Nat)
    (taskType taskCode : String) (hgap : target - level ≤ 4) :
    objectiveStepIsFightPure true target level true taskType taskCode taskTotal taskProgress
      = true := by
  have hg : ¬ (target - level > 4) := by omega
  simp [objectiveStepIsFightPure, hg]

/-- Non-vacuity witness for (c): gap of exactly 4 with an ACTIVE items task still
fires (the bootstrap path overrides the stand-down). -/
example : objectiveStepIsFightPure true 7 3 true "items" "t1" 5 2 = true :=
  bootstrap_always_fires 7 3 5 2 "items" "t1" (by decide)

/-- (d) Stand-down RELEASES at task completion. When `taskProgress ≥ taskTotal` the
items task is no longer active, so a committed `ReachCharLevel` with a combat
monster fires even on a long-haul gap — the deferral is temporary, not permanent. -/
theorem completed_task_fires (target level taskTotal taskProgress : Nat)
    (taskType taskCode : String) (hdone : taskProgress ≥ taskTotal) :
    objectiveStepIsFightPure true target level true taskType taskCode taskTotal taskProgress
      = true := by
  have hnot : ¬ (target - level > 4
      ∧ taskType = "items" ∧ taskCode ≠ "" ∧ taskTotal > 0 ∧ taskProgress < taskTotal) := by
    rintro ⟨_, _, _, _, hlt⟩; omega
  simp [objectiveStepIsFightPure, hnot]

/-- Non-vacuity witness for (d): a 47-level long-haul gap with a COMPLETED items
task fires (the stand-down has released). -/
example : objectiveStepIsFightPure true 50 3 true "items" "t1" 5 5 = true :=
  completed_task_fires 50 3 5 5 "items" "t1" (by decide)

end Formal.ObjectiveStepFight
