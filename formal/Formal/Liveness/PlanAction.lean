/-
  Formal.Liveness.PlanAction

  Phase 21a deliverable #1. An `ActionKind` inductive that mirrors 1:1 the
  concrete `Action` subclasses in `src/artifactsmmo_cli/ai/actions/`.

  Production action set (27 concrete subclasses, enumerated from
  `grep -h '^class.*Action' src/artifactsmmo_cli/ai/actions/*.py | grep -v
  'ActionError\|ApiAction'` over commit b60e979, with the abstract base
  `Action(ABC)` excluded):

    1.  AcceptTaskAction         (accept_task.py)
    2.  BuyBankExpansionAction   (bank_expansion.py)
    3.  ClaimPendingItemAction   (claim.py)
    4.  CompleteTaskAction       (complete_task.py)
    5.  CraftAction              (crafting.py)
    6.  DeleteItemAction         (delete.py)
    7.  DepositAllAction         (deposit_all.py)
    8.  DepositGoldAction        (deposit_gold.py)
    9.  EquipAction              (equip.py)
    10. FightAction              (combat.py)
    11. GatherAction             (gathering.py)
    12. MapTransitionAction      (transition.py)
    13. MoveAction               (movement.py)
    14. MoveTo                   (movement_semantic.py)
    15. NpcBuyAction             (npc.py)
    16. NpcSellAction            (npc_sell.py)
    17. OptimizeLoadoutAction    (optimize_loadout.py)
    18. RecycleAction            (recycle.py)
    19. RestAction               (rest.py)
    20. TaskCancelAction         (task_cancel.py)
    21. TaskExchangeAction       (task_exchange.py)
    22. TaskTradeAction          (task_trade.py)
    23. UnequipAction            (unequip.py)
    24. UseConsumableAction      (consumable.py)
    25. WaitAction               (wait.py)
    26. WithdrawGoldAction       (withdraw_gold.py)
    27. WithdrawItemAction       (withdraw_item.py)

  ## Discrepancy with phase plan

  The phase plan's `PlanAction design` section enumerates 26 constructors
  and omits `moveTo`. Production has both `MoveAction` (raw coordinate
  move, `movement.py`) AND `MoveTo` (semantic move to a named target,
  `movement_semantic.py`); both subclass `Action` and both are emitted by
  the planner. Per the Phase 20a/b coarse-grain retraction lesson
  (`feedback_no_coarse_grain` in spirit: mirror the production action set
  faithfully, not a curated subset), this module includes BOTH as the 27
  constructors. The phase report flags the discrepancy.

  ## Scope of this module

  Constructors only — no arguments, no semantics. Plan-application
  semantics live in `Formal/Liveness/Plan.lean`; per-goal plan-existence
  lemmas live in `Formal/Liveness/PlanExists.lean`. The bare `ActionKind`
  tag suffices for Phase 21a's existential statements: "the planner CAN
  return some action of this kind." Phase 21b/c will refine deferred kinds
  (gather/craft/move/fight) with the parameter and semantic details needed
  for multi-step plan-construction proofs.

  ## Phase 21d-1: synthetic `.objectiveStep` placeholder

  `.objectiveStep` (28th constructor, added in Phase 21d-1) is a SYNTHETIC
  placeholder, NOT a production `Action` subclass. In production, the
  StrategyArbiter's objective tier dispatches to whatever sub-goal the
  current `chosen_step` materializes (strategy_driver.py:107-204); the
  resulting plan is composed of ordinary Action subclasses (Fight, Move,
  Gather, Craft, …). We add a single tag here so that
  `plan_exists_for_objectiveStep` can produce a single-element witness
  `[.objectiveStep]` whose `applyActionKind` semantics flip
  `objectiveStepFires := false`. The honest reading is "the objective tier
  IS plannable", with the actual planner composition deferred to Phase 22
  (Cycle Loop). The production action-class count (27) is preserved by
  excluding `.objectiveStep` from `productionActionKinds` below.

  Liveness namespace — Mathlib axioms allowed; see
  `formal/Formal/Liveness/README.md`.
-/

namespace Formal.Liveness.PlanAction

/-- 1:1 mirror of production's 27 `Action` subclasses in
    `src/artifactsmmo_cli/ai/actions/` (b60e979). Order matches the
    alphabetical enumeration in the module docstring for audit ease. -/
inductive ActionKind where
  | acceptTask
  | buyBankExpansion
  | claimPendingItem
  | completeTask
  | craft
  | deleteItem
  | depositAll
  | depositGold
  | equip
  | fight
  | gather
  | mapTransition
  | move
  | moveTo
  | npcBuy
  | npcSell
  | optimizeLoadout
  | recycle
  | rest
  | taskCancel
  | taskExchange
  | taskTrade
  | unequip
  | useConsumable
  | wait
  | withdrawGold
  | withdrawItem
  -- Phase 21d-1: synthetic placeholder, NOT a production `Action` subclass.
  -- See module docstring "Phase 21d-1: synthetic `.objectiveStep`
  -- placeholder" for the honest disclosure. Excluded from
  -- `productionActionKinds` to preserve the production count of 27.
  | objectiveStep
  deriving DecidableEq, Repr

/-- Enumeration of every `ActionKind` constructor, including the Phase
    21d-1 synthetic `.objectiveStep`. -/
def allActionKinds : List ActionKind :=
  [.acceptTask, .buyBankExpansion, .claimPendingItem, .completeTask,
   .craft, .deleteItem, .depositAll, .depositGold, .equip, .fight,
   .gather, .mapTransition, .move, .moveTo, .npcBuy, .npcSell,
   .optimizeLoadout, .recycle, .rest, .taskCancel, .taskExchange,
   .taskTrade, .unequip, .useConsumable, .wait, .withdrawGold,
   .withdrawItem, .objectiveStep]

/-- Enumeration of the production `Action` subclasses ONLY (27, matching
    `src/artifactsmmo_cli/ai/actions/` at commit b60e979). Excludes the
    Phase 21d-1 synthetic `.objectiveStep`. -/
def productionActionKinds : List ActionKind :=
  [.acceptTask, .buyBankExpansion, .claimPendingItem, .completeTask,
   .craft, .deleteItem, .depositAll, .depositGold, .equip, .fight,
   .gather, .mapTransition, .move, .moveTo, .npcBuy, .npcSell,
   .optimizeLoadout, .recycle, .rest, .taskCancel, .taskExchange,
   .taskTrade, .unequip, .useConsumable, .wait, .withdrawGold,
   .withdrawItem]

/-- Sanity: 28 constructors total (27 production + 1 synthetic). -/
example : allActionKinds.length = 28 := by decide

/-- Sanity: 27 production `Action` subclasses at commit b60e979. -/
example : productionActionKinds.length = 27 := by decide

end Formal.Liveness.PlanAction
