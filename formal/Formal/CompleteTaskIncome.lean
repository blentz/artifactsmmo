-- formal/Formal/CompleteTaskIncome.lean
-- @concept: core, tasks @property: monotonicity
/-
Coin-income model for `CompleteTaskAction.apply`
(`src/artifactsmmo_cli/ai/actions/complete_task.py`) and its pure core
`src/artifactsmmo_cli/ai/actions/complete_task_core.py::complete_task_apply_pure`.

Completing a task mints the task's `tasks_coin` reward into inventory. Like
`NpcBuyInventory` (which models the load-bearing SLOT count and leaves per-key
bookkeeping to the differential test), this models the load-bearing TASKS_COIN
COUNT: `applyComplete coins reward = coins + reward`. The headline contract is
MONOTONICITY: a reward ≥ 1 strictly raises the coin count — so a funding plan
that repeatedly completes tasks makes monotone progress toward `tasks_coin ≥ N`
(the C3 termination argument rests on this).

The reward ≥ 1 floor is enforced on the Python side
(`GameData.task_coin_reward` returns the API per-task amount or the conservative
`min` ≥ 1); the differential test feeds rewards ≥ 1.

Lean core only — no mathlib. Nat arithmetic via `omega`.
-/

namespace Formal.CompleteTaskIncome

/-- Mint `reward` tasks_coin: the post-completion coin count. -/
def applyComplete (coins reward : Nat) : Nat := coins + reward

/-- **VALIDITY.** The coin count after completion is exactly before + reward. -/
theorem applyComplete_adds (coins reward : Nat) :
    applyComplete coins reward = coins + reward := rfl

/-- **MONOTONICITY.** A reward of at least 1 STRICTLY raises the coin count —
the load-bearing progress fact for funding-plan termination. -/
theorem applyComplete_monotone (coins reward : Nat) (h : 1 ≤ reward) :
    coins < applyComplete coins reward := by
  simp [applyComplete]; omega

/-! ### Non-vacuity witnesses. -/
-- A reward of 1 (the floor) already increases the count: monotonicity is not vacuous.
example : applyComplete 0 1 = 1 := by decide
example : applyComplete 5 3 = 8 := by decide
-- The monotonicity hypothesis is satisfiable (reward = 1).
example : (0 : Nat) < applyComplete 0 1 := by decide

end Formal.CompleteTaskIncome
