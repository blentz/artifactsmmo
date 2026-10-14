-- @concept: liveness @property: safety, liveness, validity
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
  return not (items_task_active(task_type, task_code, task_total, task_progress)
              and task_pays)

FAITHFULNESS NOTES:

  * `bool(task_code)`. Python treats `None` and `""` as falsy. We model `task_code`
    as a `String` with the empty string standing for both; `taskCode ≠ ""` mirrors
    `bool(task_code)`. The differential harness encodes Python `None → ""`.

  * Honest slice (NOT a surrogate). The other `objective_step_goal` branch
    (`ObtainItem`) is by definition NOT combat-led and yields
    `objectiveStepIsFight = False`; modelling only the `ReachCharLevel` slice is the
    entire meaning of the Bool, not a stand-in for the whole routing function.

Lean core only — no mathlib. All conditions decidable (Nat order, String equality).
-/

namespace Formal.ObjectiveStepFight

/-- `itemsTaskActive` — an items task is held and not yet complete
(`objective_step_fight_core.items_task_active`). -/
def itemsTaskActive (taskType taskCode : String) (taskTotal taskProgress : Nat) : Prop :=
  taskType = "items" ∧ taskCode ≠ "" ∧ taskTotal > 0 ∧ taskProgress < taskTotal

/-- The pure decision boundary. Mirrors `objective_step_is_fight_pure`
component-for-component: a committed `ReachCharLevel` with a combat monster is
Fight-led unless an items task is in progress AND it pays (spec 2026-10-14
items-task-pays). The level gap plays no part. -/
def objectiveStepIsFightPure (isReachCharLevel hasCombatMonster : Bool)
    (taskType taskCode : String) (taskTotal taskProgress : Nat) (taskPays : Bool) : Bool :=
  if ¬ isReachCharLevel then false
  else if ¬ hasCombatMonster then false
  else if (taskType = "items" ∧ taskCode ≠ "" ∧ taskTotal > 0 ∧ taskProgress < taskTotal)
            ∧ taskPays = true
       then false
  else true

/-! ### Role theorems. -/

/-- (characterization) EXACT spec, pinned in `Contracts.lean`. -/
theorem fires_iff (isReachCharLevel hasCombatMonster : Bool)
    (taskType taskCode : String) (taskTotal taskProgress : Nat) (taskPays : Bool) :
    objectiveStepIsFightPure isReachCharLevel hasCombatMonster taskType taskCode
        taskTotal taskProgress taskPays = true
      ↔ (isReachCharLevel = true ∧ hasCombatMonster = true ∧
          ¬ (itemsTaskActive taskType taskCode taskTotal taskProgress ∧ taskPays = true)) := by
  unfold objectiveStepIsFightPure itemsTaskActive
  by_cases h1 : isReachCharLevel = true
  · by_cases h2 : hasCombatMonster = true
    · by_cases h3 : (taskType = "items" ∧ taskCode ≠ "" ∧ taskTotal > 0 ∧ taskProgress < taskTotal)
              ∧ taskPays = true
      · simp [h1, h2, h3]
      · simp [h1, h2, h3]
    · simp [h1, h2]
  · simp [h1]

/-- (a) Not a `ReachCharLevel` step ⇒ never Fight-led. -/
theorem not_reach_char_level_never_fires (hasCombatMonster : Bool)
    (taskType taskCode : String) (taskTotal taskProgress : Nat) (taskPays : Bool) :
    objectiveStepIsFightPure false hasCombatMonster taskType taskCode taskTotal taskProgress
        taskPays = false := by
  simp [objectiveStepIsFightPure]

example : objectiveStepIsFightPure false true "" "" 0 0 false = false :=
  not_reach_char_level_never_fires true "" "" 0 0 false

/-- (b) No combat monster ⇒ never Fight-led. -/
theorem no_combat_monster_never_fires (taskType taskCode : String)
    (taskTotal taskProgress : Nat) (taskPays : Bool) :
    objectiveStepIsFightPure true false taskType taskCode taskTotal taskProgress taskPays
      = false := by
  simp [objectiveStepIsFightPure]

example : objectiveStepIsFightPure true false "" "" 0 0 false = false :=
  no_combat_monster_never_fires "" "" 0 0 false

/-- (c, LIVENESS) An UNPAID task never defers: a committed `ReachCharLevel` with a
combat monster is Fight-led whatever items task is held, when it does not pay.
Replaces the retired level-gap guarantee. -/
theorem unpaid_task_fires (taskType taskCode : String) (taskTotal taskProgress : Nat) :
    objectiveStepIsFightPure true true taskType taskCode taskTotal taskProgress false
      = true := by
  simp [objectiveStepIsFightPure]

example : objectiveStepIsFightPure true true "items" "t1" 5 2 false = true :=
  unpaid_task_fires "items" "t1" 5 2

/-- (d) No items task in progress ⇒ Fight-led, paying or not. -/
theorem no_items_task_fires (taskType taskCode : String) (taskTotal taskProgress : Nat)
    (taskPays : Bool) (hidle : ¬ itemsTaskActive taskType taskCode taskTotal taskProgress) :
    objectiveStepIsFightPure true true taskType taskCode taskTotal taskProgress taskPays
      = true := by
  unfold itemsTaskActive at hidle
  have hnot : ¬ ((taskType = "items" ∧ taskCode ≠ "" ∧ taskTotal > 0 ∧ taskProgress < taskTotal)
      ∧ taskPays = true) := fun h => hidle h.1
  simp [objectiveStepIsFightPure, hnot]

example : objectiveStepIsFightPure true true "monsters" "t1" 5 2 true = true :=
  no_items_task_fires "monsters" "t1" 5 2 true (by simp [itemsTaskActive])

/-- (e) Release: a COMPLETED items task never defers, paying or not. -/
theorem completed_task_fires (taskType taskCode : String) (taskTotal taskProgress : Nat)
    (taskPays : Bool) (hdone : taskProgress ≥ taskTotal) :
    objectiveStepIsFightPure true true taskType taskCode taskTotal taskProgress taskPays
      = true := by
  apply no_items_task_fires
  unfold itemsTaskActive
  rintro ⟨_, _, _, hlt⟩
  omega

example : objectiveStepIsFightPure true true "items" "t1" 5 5 true = true :=
  completed_task_fires "items" "t1" 5 5 true (by decide)

/-- Non-vacuity of the deferral branch: an active, PAYING items task defers. -/
example : objectiveStepIsFightPure true true "items" "t1" 5 2 true = false := by
  simp [objectiveStepIsFightPure]

end Formal.ObjectiveStepFight
