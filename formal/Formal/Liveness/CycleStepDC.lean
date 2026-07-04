import Formal.Liveness.CycleStepD

/-! # CycleStepDC — the COMPUTABLE mirror of the defer-faithful cycle (Phase B2)

`cycleStepD` is noncomputable solely through LIV-001 (`xpToNextLevel`, consumed
by the `.fight` / `.completeTask` rollover branches of `applyActionKind`), so
the oracle cannot evaluate it for the Phase-B trace-lockstep differential
(`docs/PLAN_c2_composed_liveness.md`). This module supplies the mirror:

* `applyActionKindC (xpNext : Nat)` — a byte-for-byte clone of
  `Plan.applyActionKind` with the axiom occurrence replaced by the `xpNext`
  parameter (the live trace records the server's actual `max_xp`, so the
  harness feeds the REAL curve value the axiom abstracts).
* `applyActionKindC_eq` / `planForC_eq` / `cycleStepC_eq` / `cycleStepDC_eq` —
  kernel equality theorems, all `rfl`-shaped: the mirror and the model are
  DEFINITIONALLY the same function at the axiom's value. Any drift between the
  clone and the source breaks these theorems — the anti-drift guarantee is the
  kernel, not review.

Additive only; the equality theorems inherit LIV-001 (they mention
`xpToNextLevel`) — audited in `LivenessAudit.lean`. Liveness namespace. -/

set_option linter.dupNamespace false

namespace Formal.Liveness.CycleStepDC

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.PlanAction
open Formal.Liveness.TaskLifecyclePhase
open Formal.Liveness.Plan
open Formal.Liveness.CycleStep
open Formal.Liveness.InventoryDynamics
open Formal.Liveness.CycleStepD

def applyActionKindC (xpNext : Nat) : ActionKind → State → State
  -- RestAction.apply (rest.py:23-24): hp := max_hp, cooldown reset (not modelled).
  | .rest, s => { s with hp := s.maxHp }
  -- WaitAction.apply (wait.py:34): identity.
  | .wait, s => s
  -- ClaimPendingItemAction.apply (claim.py:40+): pops first pending item;
  -- when only one is present, `pending_items` becomes empty. Lean model
  -- collapses the list to a Bool `pendingItemsNonempty`; the conservative
  -- single-action semantics flips it to `false`.
  | .claimPendingItem, s => { s with pendingItemsNonempty := false }
  -- CompleteTaskAction.apply (complete_task.py:46-59, see also
  -- TASK_COMPLETE_XP_ESTIMATE = 10 in complete_task.py:20): clears
  -- task_code / task_type / task_progress / task_total AND grants
  -- `taskCompleteXpEstimate = 10` xp (Phase 23c-3b, LIV-002). Lifecycle
  -- phase resets to `.none`.
  | .completeTask, s =>
      -- Item 1f: production server rolls level on completeTask reward
      -- (CompleteTaskAction.execute reads updated character schema with
      -- post-reward level). Lean model now mirrors this with the same
      -- rollover branch shape as .fight (Phase 21c).
      let willLevel : Bool :=
        decide (s.xp + taskCompleteXpEstimate ≥ xpNext)
        && decide (s.level < 50)
      let newLevel : Nat := if willLevel then s.level + 1 else s.level
      let newXp    : Nat := if willLevel then 0
                            else s.xp + taskCompleteXpEstimate
      { s with taskCode := none,
               taskTotal := 0,
               taskProgress := 0,
               taskLifecyclePhase := .none,
               level := newLevel,
               xp := newXp,
               -- Phase 23d-4: phase transitions to `.none` — reset counter.
               actionsAttempted := 0,
               -- Item 4d: credit task-completion gold reward.
               gold := s.gold + taskCompleteGoldEstimate }
  -- AcceptTaskAction.apply (accept_task.py:32-42): assigns placeholder
  -- task. See "Honest disclosure: acceptTask" in the module docstring.
  -- Phase 23c-3b: also sets `taskLifecyclePhase := .accepted` to match
  -- `deriveTaskLifecyclePhase (some "__pending__") 0 1 = .accepted`.
  | .acceptTask, s =>
      -- Item 1g-A2: pick the first code in `taskPool` not in
      -- `taskCodesSeen`; fall back to the placeholder when none fresh
      -- (legacy fixtures with empty pool keep the placeholder).
      let fresh : Option String := s.taskPool.find? (fun c => decide (¬ (c ∈ s.taskCodesSeen)))
      let newCode : String := fresh.getD acceptTaskPlaceholderCode
      { s with taskCode := some newCode,
               taskTotal := 1,
               taskProgress := 0,
               taskLifecyclePhase := .accepted }
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
      -- Item 1g-A2: push the cancelled code onto `taskCodesSeen` so the
      -- pigeonhole bound (cancels ≤ |taskPool|) holds along any cycleStep
      -- trajectory. When `taskCode = none` (cancel of an unaccepted task —
      -- shouldn't happen via productionLadder but defensively handled),
      -- leave the list unchanged.
      let newSeen : List String := match s.taskCode with
        | some c => c :: s.taskCodesSeen
        | none => s.taskCodesSeen
      { s with taskCancelFires := false,
               lowYieldCancelFires := false,
               pursueTaskFires := false,
               taskCode := none,
               taskTotal := 0,
               taskProgress := 0,
               taskLifecyclePhase := .none,
               -- Phase 23d-4: phase transitions to `.none` — reset counter.
               actionsAttempted := 0,
               taskCodesSeen := newSeen }
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
  | .npcSell, s =>
      -- Item 4d: credit sell-price gold; clear sellable flag.
      { s with sellableInventoryNonempty := false,
               gold := s.gold + npcSellGoldEstimate }
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
  --       `xpNext` threshold (and the level cap of 50 has
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
        decide (s.xp + 10 ≥ xpNext) && decide (s.level < 50)
      let newLevel : Nat := if willLevel then s.level + 1 else s.level
      let newXp    : Nat := if willLevel then 0 else s.xp + 10
      -- Phase 23d-4: bump actionsAttempted on a task-active state.
      let newAttempts : Nat :=
        if phaseActive s then s.actionsAttempted + 1 else s.actionsAttempted
      { s with level := newLevel,
               xp := newXp,
               bankAccessible := newBankAccessible,
               actionsAttempted := newAttempts }
  -- TaskTradeAction.apply (task_trade.py): delivers one or more units of
  -- the items-task item to the task NPC. The Lean model collapses a
  -- multi-trade delivery into a single step: it advances `taskProgress`
  -- to `taskTotal` (task complete) and resets the opaque
  -- `pursueTaskFires` Bool to `false`. Production firing predicate is
  -- the opaque `pursueTaskFires` (means.py:85-90, all gating folded in
  -- including `task_type == "items"` and progress < total); flipping it
  -- to `false` mirrors the post-delivery state where the task is fully
  -- satisfied (production would route to CompleteTaskGoal next cycle).
  --
  -- Honest disclosure: production may need multiple TaskTrade calls if
  -- the per-call delivery quantity is bounded by inventory; the Lean
  -- model does not track per-trade inventory deltas, so we collapse the
  -- chain into a single conservative step. Richer effects (inventory
  -- decrement of the task-item count, gold/coin reward credit) deferred
  -- — see module "Honest disclosure: minimal-modeling" note.
  | .taskTrade, s =>
      -- Phase 23d-5: advance taskProgress by 1 (NOT to taskTotal). Mirrors
      -- production `TaskTradeAction.apply` (task_trade.py:38-57) which advances
      -- `task_progress += quantity`; the Lean +1 collapse is a CONSERVATIVE
      -- under-step (production may deliver multiple units per call, so the
      -- Lean model requires ≥ taskTotal cycles to complete — an UPPER bound
      -- on what production needs). The phase recomputes from the new progress
      -- via `deriveTaskLifecyclePhase`:
      --   • if `taskProgress + 1 < taskTotal`: phase = .inProgress
      --   • if `taskProgress + 1 ≥ taskTotal` (and taskTotal > 0): phase = .complete
      -- Phase 23d-4: bump actionsAttempted on a task-active state.
      let newAttempts : Nat :=
        if phaseActive s then s.actionsAttempted + 1 else s.actionsAttempted
      let newProgress : Nat := s.taskProgress + 1
      let newPhase : TaskLifecyclePhase :=
        if s.taskTotal = 0 then s.taskLifecyclePhase
        else if newProgress ≥ s.taskTotal then .complete
        else .inProgress
      { s with pursueTaskFires := false,
               taskProgress := newProgress,
               taskLifecyclePhase := newPhase,
               actionsAttempted := newAttempts }
  -- Phase 21d-1 synthetic placeholder. See PlanAction.lean docstring
  -- "Phase 21d-1: synthetic `.objectiveStep` placeholder". The objective
  -- tier in production dispatches to a sub-goal whose plan is composed of
  -- ordinary Action subclasses (Fight, Move, Gather, …); we model the
  -- TIER's firing predicate `objectiveStepFires` (opaque Bool) being
  -- cleared by a single placeholder step. This is sufficient — and only
  -- sufficient — for the existential plan-existence claim at this
  -- abstraction level. Phase 22 (Cycle Loop) will compose the actual
  -- planner output through the sub-goal.
  | .objectiveStep, s => { s with objectiveStepFires := false }
  -- Phase 23d-7: .gather advances the projected skill-xp counter by 1.
  -- Mirrors production GatherAction.apply (gathering.py:52-83) which
  -- updates state.projected_skill_xp_delta[skill] += 1 when the gathered
  -- resource has a skill requirement. The Lean model carries a single
  -- scalar (projectedSkillXpDelta) per Phase-19c's design; advancing
  -- it by 1 per .gather suffices for the skill-gap closure proof
  -- (Phase 23d-7). All task fields are preserved (gather is task-
  -- agnostic; it never touches taskCode/Progress/Total or phase).
  | .gather, s =>
      -- Item 4a: also bump the inventory entry for the current gather
      -- target by 1. When gatherTarget is none, leave inventory unchanged
      -- (legacy fixtures default to none; only state populated by the
      -- perception layer carries the resource code).
      let newInv : List (String × Nat) :=
        match s.gatherTarget with
        | some code => (code, 1) :: s.inventoryItems
        | none => s.inventoryItems
      -- Item 4e: bump per-skill XP delta for gatherSkill. Legacy
      -- scalar projectedSkillXpDelta still advances for backward-compat.
      let newSkillXp : List (Skill × Nat) :=
        match s.gatherSkill with
        | some sk => (sk, 1) :: s.skillXpDelta
        | none => s.skillXpDelta
      { s with projectedSkillXpDelta := s.projectedSkillXpDelta + 1,
               inventoryItems := newInv,
               skillXpDelta := newSkillXp }
  -- Phase 23d-8: .craft advances the abstract craftableSlots counter
  -- by 1. Mirrors production CraftAction.apply (crafting.py:39+) which
  -- composes inventory updates (consume ingredients + produce output)
  -- + skill XP delta + task_progress for crafting tasks. The Lean
  -- abstraction collapses these to a single counter advance per .craft
  -- step (sufficient for recipe-chain closure proofs). All task fields
  -- are preserved.
  | .craft, s =>
      -- Item 4e: also bump per-skill XP delta for craftSkill.
      let newSkillXp : List (Skill × Nat) :=
        match s.craftSkill with
        | some sk => (sk, 1) :: s.skillXpDelta
        | none => s.skillXpDelta
      -- CRAFT_RELIEF post-condition: crafting consumes recipe inputs, so
      -- the production-side `craft_relief_candidates(...)` predicate
      -- becomes vacuously false until inventory rebuilds. The state-
      -- carried Bool is refreshed externally by the player snapshot;
      -- inside the apply we mirror that "predicate evaluates false
      -- immediately after the craft" by clearing the flag. This is what
      -- lets `extMeasureLt` strictly decrease on the craftReliefFlag
      -- slot, sealing CRAFT_RELIEF termination (CumulativeProgress.lean).
      -- CRAFT_POTIONS post-condition: the CraftPotions goal crafts the
      -- baseline utility-slot potion; once crafted the production
      -- `craft_potions_fires(...)` predicate becomes false (the slot is
      -- stocked). Cleared here alongside `craftReliefFires`, mirroring the
      -- same "predicate evaluates false immediately after the craft" pattern
      -- (planFor .craftPotions = [.craft]).
      { s with craftableSlots := s.craftableSlots + 1,
               skillXpDelta := newSkillXp,
               craftReliefFires := false,
               craftPotionsFires := false }
  -- Item 4b: .equip cons-prepends (slot, code) per equipTarget; no-op
  -- when equipTarget is none. Mirrors EquipAction.apply (equip.py:50+).
  | .equip, s =>
      let newEquip : List (String × String) :=
        match s.equipTarget with
        | some (slot, code) => (slot, code) :: s.equipment
        | none => s.equipment
      { s with equipment := newEquip }
  -- Item 4b: .unequip filters out the unequipTarget slot from equipment;
  -- no-op when unequipTarget is none. Mirrors UnequipAction.apply.
  | .unequip, s =>
      let newEquip : List (String × String) :=
        match s.unequipTarget with
        | some slot => s.equipment.filter (fun p => p.1 ≠ slot)
        | none => s.equipment
      { s with equipment := newEquip }
  -- Item 4b: .optimizeLoadout — production-side this runs a multi-step
  -- swap-in/swap-out for combat optimization. The single-step Lean
  -- mirror: when equipTarget = some (slot, code), apply equip semantics
  -- (cons-prepend). When unequipTarget = some slot, also filter. The
  -- result composes the swap.
  -- GEAR_REVIEW guard (guards.py:137) maps to the UpgradeEquipment goal,
  -- whose planner output is an OptimizeLoadout swap. We model the
  -- GEAR_REVIEW witness with `.optimizeLoadout`; in addition to the
  -- equipment swap, applying it clears the `gearReviewFires` latch
  -- (production: once the gear review materializes a swap the
  -- `gear_review_active` flag is cleared when no craftable upgrade
  -- remains — mirrored here as the conservative single-step clear, the
  -- same pattern as `.objectiveStep` clearing `objectiveStepFires`).
  | .optimizeLoadout, s =>
      let afterUnequip : List (String × String) :=
        match s.unequipTarget with
        | some slot => s.equipment.filter (fun p => p.1 ≠ slot)
        | none => s.equipment
      let newEquip : List (String × String) :=
        match s.equipTarget with
        | some (slot, code) => (slot, code) :: afterUnequip
        | none => afterUnequip
      { s with equipment := newEquip, gearReviewFires := false }
  -- Item 4c: .move teleports to moveTarget (single-step abstraction of
  -- production's multi-tile pathing). No-op when moveTarget is none.
  -- Mirrors MoveAction.apply (move.py:30+) at the post-step state.
  | .move, s =>
      match s.moveTarget with
      | some (tx, ty) => { s with posX := tx, posY := ty }
      | none => s
  -- Item 4c: .mapTransition uses the same moveTarget convention — the
  -- perception layer pre-resolves cross-map teleports into a (tx, ty)
  -- destination. Production's MapTransitionAction differs in side
  -- effects (cooldown, map id update) but Lean's abstract state only
  -- needs the position.
  | .mapTransition, s =>
      match s.moveTarget with
      | some (tx, ty) => { s with posX := tx, posY := ty }
      | none => s
  -- RecycleAction (recycle.py): consumes the surplus gear, clearing the
  -- recyclable-surplus signal (single-action semantics, like .npcSell clears
  -- sellable). Sufficient to flip `recycleSurplusFires` off post-recycle.
  | .recycle, s => { s with recyclableSurplusNonempty := false }
  -- WithdrawItemAction (withdraw_item.py) used by DRAIN_BANK_JUNK: pulls the
  -- over-cap bank junk into the bag, clearing the bank-junk signal (single-
  -- action semantics, like .recycle clears recyclable-surplus). Sufficient to
  -- flip `drainBankJunkFires` off post-withdraw — fire-and-lose.
  | .withdrawItem, s => { s with bankJunkNonempty := false }
  -- All other 4 kinds: no-op (see module docstring; future phases will
  -- replace each with its specific semantics).
  | _, s => s


/-- **Anti-drift kernel guarantee**: the clone IS `applyActionKind` at the
    axiom's value — definitionally, branch by branch. -/
theorem applyActionKindC_eq (a : ActionKind) (s : State) :
    applyActionKindC (xpToNextLevel s.level) a s = applyActionKind a s := by
  cases a <;> rfl

/-- Computable clone of `CycleStep.planFor` (which is marked noncomputable). -/
def planForC : MeansKind → State → Plan
  | .hpCritical       , _ => [.rest]
  | .restForCombat    , _ => [.rest]
  | .bankUnlock       , _ => [.fight]
  | .reachUnlockLevel , _ => [.fight]
  | .discardCritical  , _ => [.deleteItem]
  | .craftRelief      , _ => [.craft]
  | .recycleRelief    , _ => [.recycle]
  | .sellRelief       , _ => [.npcSell]
  | .depositFull      , _ => [.depositAll]
  | .discardHigh      , _ => [.deleteItem]
  | .gearReview       , _ => [.optimizeLoadout]
  | .craftPotions     , _ => [.craft]
  | .claimPending     , _ => [.claimPendingItem]
  | .completeTask     , _ => [.completeTask]
  | .sellPressured    , _ => [.npcSell]
  | .lowYieldCancel   , _ => [.taskCancel]
  | .taskCancel       , _ => [.taskCancel]
  | .objectiveStep    , s =>
      -- O5.2 (2026-06-16): a combat/char-leveling objective dispatches a
      -- Fight-led plan (production `ReachCharLevel` meta-goal + monster-task /
      -- combat objectives). When the objective step is a fight, the cycle
      -- FIGHTS (+10 char xp / rollover via `applyActionKind .fight`) — the
      -- model's faithful general leveling path. Otherwise the synthetic
      -- placeholder clears `objectiveStepFires` (legacy default: isFight=false).
      if s.objectiveStepIsFight then [.fight] else [.objectiveStep]
  | .pursueTask       , _ => [.taskTrade]
  | .acceptTask       , _ => [.acceptTask]
  | .taskExchange     , _ => [.taskExchange]
  | .maintainConsumables , _ => [.craft]  -- PLAN #6a: cook/brew a heal
  | .sellIdle         , _ => [.npcSell]
  | .recycleSurplus   , _ => [.recycle]
  | .drainBankJunk    , _ => [.withdrawItem]
  | .bankExpand       , _ => [.buyBankExpansion]
  | .wait             , _ => [.wait]


theorem planForC_eq (k : MeansKind) (s : State) : planForC k s = planFor k s := by
  cases k <;> rfl

/-- Computable clone of `cycleStep`. -/
def cycleStepC (xpNext : Nat) (s : State) : State :=
  match productionLadder s with
  | none => s
  | some k =>
    match planForC k s with
    | []     => s
    | a :: _ => applyActionKindC xpNext a s

theorem cycleStepC_eq (s : State) :
    cycleStepC (xpToNextLevel s.level) s = cycleStep s := by
  unfold cycleStepC cycleStep
  cases productionLadder s with
  | none => rfl
  | some k =>
    dsimp only
    rw [planForC_eq]
    cases planFor k s with
    | nil => rfl
    | cons a rest => exact applyActionKindC_eq a s

/-- Computable clone of `cycleStepD`. -/
def cycleStepDC (xpNext : Nat) (s : State) : State :=
  match productionLadder (perceptionRefreshD s) with
  | some k =>
      rearmOnMint k (perceptionRefreshD s)
        (partialClear k
          (pressureDeltaD k (perceptionRefreshD s) (cycleStepC xpNext (perceptionRefreshD s))))
  | none => cycleStepC xpNext (perceptionRefreshD s)

/-- **The Phase-B2 binding**: the computable defer-faithful cycle IS
    `cycleStepD` at the axiom's value. The oracle evaluates the left side;
    every capstone theorem speaks about the right side; this theorem is the
    bridge the trace-lockstep differential stands on. -/
theorem cycleStepDC_eq (s : State) :
    cycleStepDC (xpToNextLevel s.level) s = cycleStepD s := by
  unfold cycleStepDC cycleStepD
  have hx : xpToNextLevel s.level = xpToNextLevel (perceptionRefreshD s).level := by
    rw [perceptionRefreshD_level]
  cases productionLadder (perceptionRefreshD s) with
  | none => dsimp only; rw [hx, cycleStepC_eq]
  | some k => dsimp only; rw [hx, cycleStepC_eq]

end Formal.Liveness.CycleStepDC
