/-
  Formal.Liveness.TaskLifecyclePhase

  Phase 23c-3b deliverable: Lean mirror of the production
  `TaskLifecyclePhase` enum and its `derive_task_lifecycle_phase` helper
  from `src/artifactsmmo_cli/ai/task_lifecycle.py`.

  ## Production source

  ```python
  class TaskLifecyclePhase(Enum):
      NONE = "none"
      ACCEPTED = "accepted"
      IN_PROGRESS = "in_progress"
      COMPLETE = "complete"

  def derive_task_lifecycle_phase(task_code, task_progress, task_total):
      if not task_code:
          return TaskLifecyclePhase.NONE
      if task_total <= 0:
          return TaskLifecyclePhase.NONE
      if task_progress >= task_total:
          return TaskLifecyclePhase.COMPLETE
      if task_progress == 0:
          return TaskLifecyclePhase.ACCEPTED
      return TaskLifecyclePhase.IN_PROGRESS
  ```

  The Lean mirror uses `Option String` for `taskCode`; "falsy" in Python
  collapses to `None`/empty-string both of which map to `.none` in Lean.
  Our `Option` model treats `none` and `some ""` both as "no task" via the
  explicit `taskCode = none ∨ taskCode = some ""` test.

  Liveness namespace — Mathlib axioms allowed; see
  `formal/Formal/Liveness/README.md`.
-/

namespace Formal.Liveness.TaskLifecyclePhase

/-- Lifecycle phase of the taskmaster task. 1:1 mirror of production's
    `TaskLifecyclePhase` enum. -/
inductive TaskLifecyclePhase where
  /-- No task accepted. -/
  | none
  /-- Task accepted, no progress yet (`task_progress == 0`). -/
  | accepted
  /-- Task in progress (`0 < task_progress < task_total`). -/
  | inProgress
  /-- Task ready for turn-in (`task_progress >= task_total`, `task_total > 0`). -/
  | complete
  deriving DecidableEq, Repr

/-- Derive the lifecycle phase from raw task fields. Mirrors
    `derive_task_lifecycle_phase` in `task_lifecycle.py`.

    Production treats `not task_code` as "no task"; we model that as
    `taskCode = none ∨ taskCode = some ""`. -/
def deriveTaskLifecyclePhase
    (taskCode : Option String) (taskProgress taskTotal : Nat) :
    TaskLifecyclePhase :=
  match taskCode with
  | none => .none
  | some s =>
      if s = "" then .none
      else if taskTotal = 0 then .none
      else if taskProgress ≥ taskTotal then .complete
      else if taskProgress = 0 then .accepted
      else .inProgress

end Formal.Liveness.TaskLifecyclePhase
