
/-!
# Formal.TaskTradeReadyPriority

**Correctness of the TaskTrade-ready PursueTask suppression rule.**

`strategy_driver.StrategyArbiter.select` now suppresses a fallback
`GatherMaterialsGoal(target=task_code)` when the player already holds
at least one unit of the task code. The suppression lets PursueTask's
TaskTrade fire instead of the multi-cycle gather chain.

Trace 2026-06-06 14:40 (cycles 25-26): task = items/copper_bar at
progress 20/21; inventory copper_bar = 1; fallback's
GatherMaterials(copper_bar, needed=8) for the gear-chain
ObtainItem(copper_boots) ran instead of PursueTask's TaskTrade. One
trade would complete the task; bot gathered MORE copper_ore for
armor while the held bar sat unused.

This module proves:

1. Suppression predicate is TOTAL and DETERMINISTIC.
2. SOUNDNESS: when all four conditions hold, suppress = true.
3. COMPLETENESS: when any condition fails, suppress = false.
4. Trace-mirror: the exact (prog=20/21, inv=1) scenario gives
   suppress = true.
-/

namespace Formal.TaskTradeReadyPriority

/-! ## Abstract state. -/

inductive TaskKind where
  | items
  | monsters
  | none
deriving Repr, DecidableEq

inductive MeansKind where
  | pursueTask
  | acceptTask
  | other
deriving Repr, DecidableEq

inductive StepGoalClass where
  | gatherMaterials  : (target : Int) → StepGoalClass
  | upgradeEquipment : StepGoalClass
  | none             : StepGoalClass
deriving Repr, DecidableEq

structure SimState where
  taskKind            : TaskKind
  taskCode            : Int
  inventoryTaskCode   : Int   -- count of taskCode held
  discretionary       : List MeansKind
  stepGoal            : StepGoalClass

/-! ## The suppression predicate. -/

def hasPursueTask (xs : List MeansKind) : Bool :=
  xs.any (fun m => m = MeansKind.pursueTask)

def isGatherTaskCode (g : StepGoalClass) (taskCode : Int) : Bool :=
  match g with
  | StepGoalClass.gatherMaterials t => decide (t = taskCode)
  | _ => false

/-- The full predicate: suppress when all four conditions hold. -/
def suppressFallback (s : SimState) : Bool :=
  hasPursueTask s.discretionary
    && (s.taskKind = TaskKind.items)
    && isGatherTaskCode s.stepGoal s.taskCode
    && decide (s.inventoryTaskCode ≥ 1)

/-! ## Totality + determinism. -/

theorem suppress_total (s : SimState) : ∃ b, suppressFallback s = b :=
  ⟨suppressFallback s, rfl⟩

theorem suppress_deterministic (s : SimState) (a b : Bool)
    (h1 : suppressFallback s = a) (h2 : suppressFallback s = b) : a = b := by
  rw [← h1, ← h2]

/-! ## Soundness: all four conditions ⇒ suppress = true. -/

theorem hasPursueTask_true_of_mem (xs : List MeansKind)
    (h : MeansKind.pursueTask ∈ xs) : hasPursueTask xs = true := by
  unfold hasPursueTask
  rw [List.any_eq_true]
  exact ⟨MeansKind.pursueTask, h, by decide⟩

theorem suppress_true_when_all_conditions_hold
    (s : SimState)
    (hPursue : MeansKind.pursueTask ∈ s.discretionary)
    (hItems : s.taskKind = TaskKind.items)
    (hMatch : ∃ t, s.stepGoal = StepGoalClass.gatherMaterials t ∧ t = s.taskCode)
    (hInHand : s.inventoryTaskCode ≥ 1) :
    suppressFallback s = true := by
  unfold suppressFallback
  have hP := hasPursueTask_true_of_mem s.discretionary hPursue
  obtain ⟨t, hG, hEq⟩ := hMatch
  have hGT : isGatherTaskCode s.stepGoal s.taskCode = true := by
    unfold isGatherTaskCode
    rw [hG]
    simp [hEq]
  simp [hP, hItems, hGT, hInHand]

/-! ## Completeness: any condition fails ⇒ suppress = false. -/

theorem suppress_false_when_no_pursue
    (s : SimState) (h : hasPursueTask s.discretionary = false) :
    suppressFallback s = false := by
  unfold suppressFallback
  simp [h]

theorem suppress_false_when_not_items
    (s : SimState) (h : s.taskKind ≠ TaskKind.items) :
    suppressFallback s = false := by
  unfold suppressFallback
  simp [h]

theorem suppress_false_when_inv_zero
    (s : SimState) (h : s.inventoryTaskCode < 1) :
    suppressFallback s = false := by
  unfold suppressFallback
  have hN : ¬ (s.inventoryTaskCode ≥ 1) := by omega
  simp [hN]

theorem suppress_false_when_step_not_gather_taskcode
    (s : SimState)
    (h : ∀ t, s.stepGoal = StepGoalClass.gatherMaterials t → t ≠ s.taskCode) :
    suppressFallback s = false := by
  unfold suppressFallback
  have hGF : isGatherTaskCode s.stepGoal s.taskCode = false := by
    unfold isGatherTaskCode
    cases hG : s.stepGoal with
    | gatherMaterials t =>
      have := h t hG
      simp [this]
    | upgradeEquipment => rfl
    | none => rfl
  simp [hGF]

/-! ## Trace-mirror: the exact 14:40 scenario. -/

/-- Robby's state at cycle 25-26 of session 14:40 collapses to this
literal. The suppression fires. -/
theorem trace_144020_suppress :
    suppressFallback {
      taskKind          := TaskKind.items
      taskCode          := 1   -- abstract for copper_bar
      inventoryTaskCode := 1
      discretionary     := [MeansKind.pursueTask]
      stepGoal          := StepGoalClass.gatherMaterials 1
    } = true := by
  unfold suppressFallback hasPursueTask isGatherTaskCode
  decide

end Formal.TaskTradeReadyPriority
