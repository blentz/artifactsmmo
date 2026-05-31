/-
  Formal.Liveness.Plan

  Phase 21a/b deliverable #2. Plans as lists of `ActionKind` tags plus a
  partial single-step semantics `applyActionKind`.

  ## Scope

  Per-kind semantics are defined for the 12 single-step firing means
  whose plan-existence lemma is in scope for Phases 21a + 21b:

    Phase 21a (8):
      .rest, .wait, .claimPendingItem, .completeTask, .acceptTask,
      .taskExchange, .taskCancel, .buyBankExpansion
    Phase 21b (added 4 new ActionKind branches; .taskCancel reused):
      .deleteItem, .depositAll, .npcSell  (+ .taskCancel reused for lowYieldCancel)

  All other 15 constructors fall through to a no-op default branch. This
  is NOT a semantic claim about those kinds — Phase 21c/d will replace
  the default with kind-specific semantics derived from the corresponding
  Phase-19 progress lemmas (e.g. `FightProgress.applyFightAction`,
  `GatherProgress.applyGatherAction`, etc., which already exist in
  `Formal/Liveness/{Fight,Gather,Deposit,Rest}Progress.lean`). Until
  then, the default no-op is correct EXACTLY for the in-scope lemmas,
  which only ever pattern-match on the 12 named kinds.

  ## Honest disclosure: minimal-modeling for Phase 21b kinds

  The four new branches (`.deleteItem`, `.depositAll`, `.npcSell`, plus
  reuse of `.taskCancel`) update ONLY the fields the corresponding firing
  predicate reads. Richer effects (inventory composition, NPC stock
  ledger, bank ledger updates, gold credited from sell) are deferred to
  later phases or out of Tier 3 scope. This is sufficient — and only
  sufficient — to flip the firing predicate of the targeted means to
  `false` in a single step.

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
    to a no-op (see module docstring for rationale and Phase 21b/c plan).

    `noncomputable` because Phase 21c's `.fight` branch references the
    axiomatic `xpToNextLevel` (AXIOM-ID LIV-001) for level rollover. -/
noncomputable def applyActionKind : ActionKind → State → State
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
  -- one task coin. The Lean model has OPAQUE Bools `taskCancelFires`,
  -- `lowYieldCancelFires`, and `pursueTaskFires` which production resets
  -- after the cancel (no task ⇒ none of these can fire) — the
  -- conservative single-action semantics flips all three to `false`.
  -- Phase 21b: also covers `.lowYieldCancel` whose firing predicate
  -- reads `s.lowYieldCancelFires`.
  | .taskCancel, s =>
      { s with taskCancelFires := false,
               lowYieldCancelFires := false,
               pursueTaskFires := false,
               taskCode := none,
               taskTotal := 0,
               taskProgress := 0 }
  -- BuyBankExpansionAction.apply (bank_expansion.py:39-54): adds 20 slots
  -- to bank_capacity, deducts gold cost.
  | .buyBankExpansion, s =>
      { s with bankCapacity := s.bankCapacity + bankExpansionSlots,
               gold := s.gold - s.nextExpansionCost }
  -- DeleteItemAction.apply (delete.py): removes an overstock item from
  -- inventory. The Lean model abstracts inventory composition via the
  -- Bool `hasOverstockItems`; the conservative single-action semantics
  -- flips it to `false` (the deleted item WAS the overstock, so after
  -- delete the overstock is gone). Sufficient to clear
  -- `discardCriticalFires` and `discardHighFires`. Richer effects (item
  -- composition, inventoryUsed decrement) deferred — see module
  -- "Honest disclosure: minimal-modeling" note.
  | .deleteItem, s => { s with hasOverstockItems := false }
  -- DepositAllAction.apply (deposit_all.py): deposits the curated
  -- non-keep-set into the bank. The Lean model abstracts the selection
  -- via the Bool `selectBankDepositsNonempty`; the conservative
  -- single-action semantics flips it to `false` (everything that would
  -- have been deposited has been). Sufficient to clear
  -- `depositFullFires`. Richer effects (bank ledger, inventoryUsed
  -- update for the deposited subset) deferred — see module
  -- "Honest disclosure: minimal-modeling" note.
  | .depositAll, s => { s with selectBankDepositsNonempty := false }
  -- NpcSellAction.apply (npc_sell.py): sells the curated sellable
  -- inventory subset to an NPC merchant. The Lean model abstracts the
  -- selection via the Bool `sellableInventoryNonempty`; the conservative
  -- single-action semantics flips it to `false` (post-sell nothing
  -- sellable remains). Sufficient to clear `sellPressuredFires` and
  -- `sellIdleFires`. Richer effects (gold credit, inventoryUsed
  -- decrement, NPC stock) deferred — see module "Honest disclosure:
  -- minimal-modeling" note.
  | .npcSell, s => { s with sellableInventoryNonempty := false }
  -- FightAction.apply (combat.py:apply): xp += 10, hp damage (irrelevant
  -- to firing predicates), task_progress += 1 if matches monster-task.
  -- Phase 21c adds two extensions for the two Fight-firing means
  -- (`bankUnlock`, `reachUnlockLevel`):
  --
  --   (a) BANK-UNLOCK FLIP: when the pre-state satisfies the production
  --       `bankUnlockFires` predicate (bank-unlock monster present, bank
  --       not yet accessible, xp under initial-xp budget, character level
  --       sufficient for the unlock monster), the fight resolves the
  --       achievement and the server flips `bank_accessible := True`.
  --       In production the perception layer integrates this on the next
  --       refresh; here we model it as a single-step effect of `.fight`,
  --       guarded by the firing-predicate conditions so non-unlock fights
  --       (regular monster grinds) DO NOT flip bank access.
  --
  --   (b) LEVEL ROLLOVER: when the +10 xp grant would cross the
  --       `xpToNextLevel s.level` threshold (and the level cap of 50 has
  --       not been hit), the level advances and xp resets to 0. This
  --       mirrors what the perception layer would integrate from the
  --       server's `/v3/my/{name}/action/fight` response. Phase 19b's
  --       `fightApply` deliberately omits this (its scope was the
  --       perception-invariant strict-progress lemma); Phase 21c's
  --       `applyActionKind .fight` adds it because plan-existence for
  --       `reachUnlockLevel` requires the planner-side projection to
  --       reach `bankRequiredLevel` after a bounded fight sequence.
  --
  -- Honest disclosure: this `.fight` apply does NOT model loot,
  -- inventory deltas, cooldown, or position — none enter the firing
  -- predicates targeted in Phase 21c. The bank-unlock flip is also a
  -- model commitment that production's server-side achievement WILL
  -- flip `bank_accessible` on a single successful unlock fight (true
  -- per the game's documented mechanic; the perception layer's
  -- subsequent refresh observes the flipped flag).
  | .fight, s =>
      let unlockMonsterReady : Bool :=
        s.bankUnlockMonsterPresent
        && !s.bankAccessible
        && decide (s.xp ≤ s.initialXp)
        && (decide (s.unlockMonsterLevel = 0)
            || decide (s.level + 1 ≥ s.unlockMonsterLevel))
      let newBankAccessible : Bool :=
        if unlockMonsterReady then true else s.bankAccessible
      let willLevel : Bool :=
        decide (s.xp + 10 ≥ xpToNextLevel s.level) && decide (s.level < 50)
      let newLevel : Nat := if willLevel then s.level + 1 else s.level
      let newXp    : Nat := if willLevel then 0 else s.xp + 10
      { s with level := newLevel,
               xp := newXp,
               bankAccessible := newBankAccessible }
  -- All other 14 kinds: no-op (see module docstring; Phase 21d will
  -- replace each with its specific semantics).
  | _, s => s

/-- Fold `applyActionKind` over a plan. `noncomputable` for the same
    reason as `applyActionKind` (Phase 21c xp/level axiom). -/
noncomputable def applyPlan (p : Plan) (s : State) : State :=
  p.foldl (fun s a => applyActionKind a s) s

@[simp] theorem applyPlan_nil (s : State) : applyPlan [] s = s := rfl

@[simp] theorem applyPlan_cons (a : ActionKind) (p : Plan) (s : State) :
    applyPlan (a :: p) s = applyPlan p (applyActionKind a s) := by
  simp [applyPlan, List.foldl]

@[simp] theorem applyPlan_singleton (a : ActionKind) (s : State) :
    applyPlan [a] s = applyActionKind a s := by
  simp [applyPlan]

end Formal.Liveness.Plan
