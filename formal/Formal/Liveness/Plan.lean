/-
  Formal.Liveness.Plan

  Phase 21a deliverable #2. Plans as lists of `ActionKind` tags plus a
  partial single-step semantics `applyActionKind`.

  ## Scope

  Per-kind semantics are defined ONLY for the 8 "trivial" firing means
  whose plan-existence lemma is in scope for Phase 21a:

    .rest, .wait, .claimPendingItem, .completeTask, .acceptTask,
    .taskExchange, .taskCancel, .buyBankExpansion

  All other 19 constructors fall through to a no-op default branch. This
  is NOT a semantic claim about those kinds — Phase 21b/c will replace
  the default with kind-specific semantics derived from the corresponding
  Phase-19 progress lemmas (e.g. `FightProgress.applyFightAction`,
  `GatherProgress.applyGatherAction`, etc., which already exist in
  `Formal/Liveness/{Fight,Gather,Deposit,Rest}Progress.lean`). Until
  then, the default no-op is correct EXACTLY for the in-scope lemmas,
  which only ever pattern-match on the 8 named kinds.

  ## Production source citations

  Each in-scope branch documents the production `apply()` method whose
  field updates it mirrors. Where production updates a field the Lean
  model doesn't carry (e.g. coordinates, cooldown), the model abstracts
  that away. Where production sets a string placeholder (e.g.
  `_PENDING_TASK`), the model lifts it to a Lean placeholder.

  ## Honest disclosure: acceptTask

  Production's `AcceptTaskAction.apply` (accept_task.py:32-42) sets
  `task_code = _PENDING_TASK` and `task_total = 1`. The REAL task assigned
  at execute-time depends on the server response — the planner-side apply
  is a placeholder so downstream goals can observe "I do have a task now."
  The Lean model mirrors this with `taskCode := some "__pending__"` and
  `taskTotal := 1` — the literal placeholder string and the placeholder
  total. Phase 21a's plan-existence lemma for `.acceptTask` proves only
  that the post-state's `acceptTaskFires` predicate (which checks
  `taskCode.isNone`) becomes `false`; it does NOT claim anything about
  the eventual task identity.

  ## Honest disclosure: buyBankExpansion

  Production adds 20 slots to `bank_capacity` (BANK_EXPANSION_SLOTS).
  Whether the post-state's `bankExpandFires` predicate becomes `false`
  depends on the pre-state's `bankItemsCount`. The plan-existence lemma
  is therefore conditional on a numeric precondition that 20 added slots
  suffice to drop the fill ratio below the 0.95 threshold.

  Liveness namespace — Mathlib axioms allowed; see
  `formal/Formal/Liveness/README.md`.
-/
import Formal.Liveness.Measure
import Formal.Liveness.PlanAction

set_option linter.dupNamespace false
set_option linter.unusedVariables false

namespace Formal.Liveness.Plan

open Formal.Liveness.Measure
open Formal.Liveness.PlanAction

/-- A plan is an ordered list of action kinds the planner emits. -/
abbrev Plan : Type := List ActionKind

/-- The placeholder task identifier production assigns on
    `AcceptTaskAction.apply` (accept_task.py:18, `_PENDING_TASK`). -/
def acceptTaskPlaceholderCode : String := "__pending__"

/-- Bank-expansion slot increment per buy (bank_expansion.py:22,
    `BANK_EXPANSION_SLOTS`). -/
def bankExpansionSlots : Nat := 20

/-- Single-step state transition for an `ActionKind`. Phase 21a defines
    semantics for the 8 trivial-firing kinds; all other kinds fall through
    to a no-op (see module docstring for rationale and Phase 21b/c plan). -/
def applyActionKind : ActionKind → State → State
  -- RestAction.apply (rest.py:23-24): hp := max_hp, cooldown reset (not modelled).
  | .rest, s => { s with hp := s.maxHp }
  -- WaitAction.apply (wait.py:34): identity.
  | .wait, s => s
  -- ClaimPendingItemAction.apply (claim.py:40+): pops first pending item;
  -- when only one is present, `pending_items` becomes empty. Lean model
  -- collapses the list to a Bool `pendingItemsNonempty`; the conservative
  -- single-action semantics flips it to `false`.
  | .claimPendingItem, s => { s with pendingItemsNonempty := false }
  -- CompleteTaskAction.apply (complete_task.py:30-41): clears
  -- task_code / task_type / task_progress / task_total. The Lean model
  -- represents an absent task by `taskCode := none`.
  | .completeTask, s => { s with taskCode := none, taskTotal := 0, taskProgress := 0 }
  -- AcceptTaskAction.apply (accept_task.py:32-42): assigns placeholder
  -- task. See "Honest disclosure: acceptTask" in the module docstring.
  | .acceptTask, s =>
      { s with taskCode := some acceptTaskPlaceholderCode,
               taskTotal := 1,
               taskProgress := 0 }
  -- TaskExchangeAction.apply (task_exchange.py:44+): consumes `min_coins`
  -- task coins from inventory, grants reward. The Lean model abstracts the
  -- coin counter via `taskCoinsTotal`; the conservative single-action
  -- semantics decrements by `taskExchangeMinCoins`. (Nat sub saturates.)
  | .taskExchange, s =>
      { s with taskCoinsTotal := s.taskCoinsTotal - s.taskExchangeMinCoins }
  -- TaskCancelAction.apply (task_cancel.py:35+): clears task; consumes
  -- one task coin. The Lean model has an OPAQUE Bool `taskCancelFires`
  -- which production resets after the cancel — the conservative
  -- single-action semantics flips it to `false`.
  | .taskCancel, s =>
      { s with taskCancelFires := false,
               taskCode := none,
               taskTotal := 0,
               taskProgress := 0 }
  -- BuyBankExpansionAction.apply (bank_expansion.py:39-54): adds 20 slots
  -- to bank_capacity, deducts gold cost.
  | .buyBankExpansion, s =>
      { s with bankCapacity := s.bankCapacity + bankExpansionSlots,
               gold := s.gold - s.nextExpansionCost }
  -- All other 19 kinds: no-op (see module docstring; Phase 21b/c will
  -- replace each with its specific semantics).
  | _, s => s

/-- Fold `applyActionKind` over a plan. -/
def applyPlan (p : Plan) (s : State) : State :=
  p.foldl (fun s a => applyActionKind a s) s

@[simp] theorem applyPlan_nil (s : State) : applyPlan [] s = s := rfl

@[simp] theorem applyPlan_cons (a : ActionKind) (p : Plan) (s : State) :
    applyPlan (a :: p) s = applyPlan p (applyActionKind a s) := by
  simp [applyPlan, List.foldl]

@[simp] theorem applyPlan_singleton (a : ActionKind) (s : State) :
    applyPlan [a] s = applyActionKind a s := by
  simp [applyPlan]

end Formal.Liveness.Plan
