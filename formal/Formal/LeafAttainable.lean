-- formal/Formal/LeafAttainable.lean
-- @concept: core, planner @property: validity, monotonicity
/-
Acquisition-leaf attainability, mirroring
`src/artifactsmmo_cli/ai/tiers/leaf_attainable_core.py::leaf_attainable_pure`
and the `leaf_ok` disjunction in `tiers/objective.py::is_attainable`.

A recipe-closure LEAF is attainable iff some acquisition source applies:
gatherable, dropped by a known-spawn monster, EARNED BY COMPLETING TASKS
(the C1 addition — e.g. `tasks_coin`), or buyable with an attainable currency.

Lean core only — no mathlib.
-/

namespace Formal.LeafAttainable

/-- The leaf-attainability decision: a 4-way disjunction over acquisition sources. -/
def leafAttainable (gatherable knownSpawnDrop taskEarnable buyable : Bool) : Bool :=
  gatherable || knownSpawnDrop || taskEarnable || buyable

/-- **VALIDITY.** The decision is exactly the disjunction of its sources. -/
theorem leafAttainable_iff_or (g d t b : Bool) :
    leafAttainable g d t b = (g || d || t || b) := rfl

/-- **TASK-SOURCE LOAD-BEARING.** An item earned by completing tasks is
attainable even when NO other source applies (the C1 fix: `tasks_coin`). A
mutant that drops the `taskEarnable` disjunct fails this. -/
theorem leafAttainable_task_earnable (g d b : Bool) :
    leafAttainable g d true b = true := by
  simp [leafAttainable]

/-- **MONOTONICITY.** Gaining the task-earnable source never makes an attainable
leaf un-attainable (each disjunct is positive). -/
theorem leafAttainable_monotone_task (g d t b : Bool) :
    leafAttainable g d t b = true → leafAttainable g d true b = true := by
  intro _; simp [leafAttainable]

/-! ### Non-vacuity witnesses. -/
-- No source ⇒ dead leaf (the pruned case is genuinely reachable).
example : leafAttainable false false false false = false := by decide
-- Each source alone suffices.
example : leafAttainable true false false false = true := by decide
example : leafAttainable false true false false = true := by decide
example : leafAttainable false false true false = true := by decide
example : leafAttainable false false false true = true := by decide

end Formal.LeafAttainable
