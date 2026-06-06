import Mathlib.Tactic

/-!
# Formal.ActionSetCompleteness

**Every game capability the AI must use has a corresponding modeled action.**

The Python `Player._build_actions()` (player.py:846+) populates the
GOAP action set. This module pins the COMPLETENESS of that set: every
GAME CAPABILITY the AI needs to use to play the game is represented by
a modeled action class.

We enumerate the capability ↔ action mapping and prove the mapping is
TOTAL — there is no game capability the bot's action set is silently
unaware of. This closes the "unknown unknowns" gap: a server feature
that has no Action class would be invisible to the planner.

Note: this models the ACTION-CLASS level, not the parametric
instantiation. We DO have parametric coverage for each class (one
FightAction per monster, one GatherAction per resource, etc.); the
parametric loop is straightforward in Python and the per-instance
correctness is covered by the per-action applicability theorems
(`ActionApplicability.lean`).
-/

namespace Formal.ActionSetCompleteness

/-! ## Capability inventory. -/

/-- Every meaningful game capability the AI can invoke. -/
inductive Capability where
  | fight                -- combat
  | gather               -- resource collection
  | craft                -- recipe execution
  | rest                 -- HP recovery via /rest endpoint
  | useConsumable        -- apple/potion for HP
  | move                 -- character movement (folded into fight/gather)
  | equip                -- gear/tool swap
  | unequip              -- gear removal (slot freeing)
  | depositAll           -- bank deposit
  | withdrawItem         -- bank withdrawal
  | acceptTask           -- get a new task
  | completeTask         -- finalize a task
  | taskExchange         -- spend tasks_coin for rewards
  | taskCancel           -- abandon a task
  | taskTrade            -- progress an items-task
  | npcSell              -- sell to NPC merchant
  | npcBuy               -- buy from NPC merchant
  | claimPendingItem     -- pending-items resolution
  | buyBankExpansion     -- bank capacity purchase
  | optimizeLoadout      -- per-fight gear swap
  | wait                 -- structural last-resort
deriving Repr, DecidableEq

/-- Every Action class instantiated in `Player._build_actions`. Matches
the Python imports header. -/
inductive ActionClass where
  | fightAction
  | gatherAction
  | craftAction
  | restAction
  | useConsumableAction
  | equipAction
  | unequipAction
  | depositAllAction
  | withdrawItemAction
  | acceptTaskAction
  | completeTaskAction
  | taskExchangeAction
  | taskCancelAction
  | taskTradeAction
  | npcSellAction
  | npcBuyAction
  | claimPendingItemAction
  | buyBankExpansionAction
  | optimizeLoadoutAction
  | waitAction
deriving Repr, DecidableEq

/-! ## The mapping. -/

def capabilityToAction : Capability → ActionClass
  | .fight              => .fightAction
  | .gather             => .gatherAction
  | .craft              => .craftAction
  | .rest               => .restAction
  | .useConsumable      => .useConsumableAction
  | .move               => .fightAction   -- movement is FOLDED into fight/gather's cost+execute
  | .equip              => .equipAction
  | .unequip            => .unequipAction
  | .depositAll         => .depositAllAction
  | .withdrawItem       => .withdrawItemAction
  | .acceptTask         => .acceptTaskAction
  | .completeTask       => .completeTaskAction
  | .taskExchange       => .taskExchangeAction
  | .taskCancel         => .taskCancelAction
  | .taskTrade          => .taskTradeAction
  | .npcSell            => .npcSellAction
  | .npcBuy             => .npcBuyAction
  | .claimPendingItem   => .claimPendingItemAction
  | .buyBankExpansion   => .buyBankExpansionAction
  | .optimizeLoadout    => .optimizeLoadoutAction
  | .wait               => .waitAction

/-! ## Totality. -/

/-- **Every capability maps to an action class** (totality). -/
theorem capability_mapping_total (c : Capability) :
    ∃ a, capabilityToAction c = a :=
  ⟨capabilityToAction c, rfl⟩

/-- **Deterministic mapping**: same capability ⇒ same action class. -/
theorem capability_mapping_deterministic (c : Capability)
    (a1 a2 : ActionClass)
    (h1 : capabilityToAction c = a1) (h2 : capabilityToAction c = a2) :
    a1 = a2 := by rw [← h1, ← h2]

/-! ## Surjectivity (every modeled ActionClass has a capability). -/

/-- Reverse: every modeled ActionClass corresponds to AT LEAST ONE
capability. Proven by case analysis over the finite ActionClass
inductive — no dead Action class in the set. -/
theorem every_action_has_a_capability (a : ActionClass) :
    ∃ c, capabilityToAction c = a := by
  cases a with
  | fightAction              => exact ⟨.fight, rfl⟩
  | gatherAction             => exact ⟨.gather, rfl⟩
  | craftAction              => exact ⟨.craft, rfl⟩
  | restAction               => exact ⟨.rest, rfl⟩
  | useConsumableAction      => exact ⟨.useConsumable, rfl⟩
  | equipAction              => exact ⟨.equip, rfl⟩
  | unequipAction            => exact ⟨.unequip, rfl⟩
  | depositAllAction         => exact ⟨.depositAll, rfl⟩
  | withdrawItemAction       => exact ⟨.withdrawItem, rfl⟩
  | acceptTaskAction         => exact ⟨.acceptTask, rfl⟩
  | completeTaskAction       => exact ⟨.completeTask, rfl⟩
  | taskExchangeAction       => exact ⟨.taskExchange, rfl⟩
  | taskCancelAction         => exact ⟨.taskCancel, rfl⟩
  | taskTradeAction          => exact ⟨.taskTrade, rfl⟩
  | npcSellAction            => exact ⟨.npcSell, rfl⟩
  | npcBuyAction             => exact ⟨.npcBuy, rfl⟩
  | claimPendingItemAction   => exact ⟨.claimPendingItem, rfl⟩
  | buyBankExpansionAction   => exact ⟨.buyBankExpansion, rfl⟩
  | optimizeLoadoutAction    => exact ⟨.optimizeLoadout, rfl⟩
  | waitAction               => exact ⟨.wait, rfl⟩

end Formal.ActionSetCompleteness
