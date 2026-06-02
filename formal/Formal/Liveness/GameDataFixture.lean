import Formal.Liveness.RecipeChainClosure
import Formal.Liveness.SkillGapClosure
import Formal.Liveness.TaskCompleteReachable
import Formal.Liveness.Measure
import Formal.Liveness.TaskLifecyclePhase
import Mathlib.Tactic

/-! # GameDataFixture — Phase 24

A concrete, hand-crafted fixture demonstrating that the Phase 23d-8
universal recipe-chain closure theorem produces a CONCRETE PLAN
when applied to a real-shaped game-data instance.

The fixture is a coherent miniature game world:
- 1 raw resource (iron_ore) gathered via mining skill.
- 1 intermediate craft (iron_bar from 2 iron_ore, weaponcrafting skill).
- 1 final craft (iron_sword from 1 iron_bar, weaponcrafting skill).

Items task: deliver 1 iron_sword. Concrete K-step plan:
  K_gather = 2 (iron_ore × 2)
  K_craft  = 2 (iron_bar + iron_sword)
  K_taskTrade = 1 (deliver iron_sword)
  K_total = 5.

**Scope honesty**: this is a MOCK fixture, not the live server game_data.
The full openapi-grounded fixture (~hundreds of recipes, items, monsters)
requires a server snapshot. The mock instantiates the universal claim
on a structurally-real dataset and demonstrates the proof's concrete
yield. A future phase can swap in the live snapshot once a stable
spec version is pinned.

NO new axioms. Pure instantiation of Phase 23d-8's universal theorem.
-/

namespace Formal.Liveness.GameDataFixture

open Formal.Liveness.Plan
open Formal.Liveness.PlanAction
open Formal.Liveness.Measure
open Formal.Liveness.TaskLifecyclePhase
open Formal.Liveness.TaskCompleteReachable
open Formal.Liveness.SkillGapClosure
open Formal.Liveness.RecipeChainClosure

/-! ## Fixture recipes -/

/-- `iron_ore` raw resource. Depth 0 = gathered, no crafting. -/
def ironOreRecipe : Recipe :=
  { output := "iron_ore"
    ingredients := []
    craftDepth := 0 }

/-- `iron_bar` intermediate. Recipe: 2 iron_ore → 1 iron_bar.
    Craft skill: weaponcrafting. -/
def ironBarRecipe : Recipe :=
  { output := "iron_bar"
    ingredients := [("iron_ore", 2)]
    craftDepth := 1 }

/-- `iron_sword` final item. Recipe: 1 iron_bar → 1 iron_sword.
    Craft skill: weaponcrafting. -/
def ironSwordRecipe : Recipe :=
  { output := "iron_sword"
    ingredients := [("iron_bar", 1)]
    craftDepth := 2 }

/-! ## Fixture invariants -/

/-- The recipes form an acyclic DAG: iron_ore (depth 0) ≺ iron_bar
    (depth 1) ≺ iron_sword (depth 2). -/
theorem fixture_dag_acyclic :
    ironOreRecipe.craftDepth < ironBarRecipe.craftDepth ∧
    ironBarRecipe.craftDepth < ironSwordRecipe.craftDepth := by
  refine ⟨?_, ?_⟩ <;> decide

/-- Concrete gather counts.
    - iron_ore: 0 ingredients (raw resource) → gatherCount = 0
                (gathering it produces 1 unit via a single .gather step).
    - iron_bar: 1 ingredient (iron_ore × 2) → gatherCount = 2.
    - iron_sword: 1 ingredient (iron_bar × 1) → gatherCount = 1. -/
theorem ironOreRecipe_gatherCount :
    ironOreRecipe.gatherCount = 0 := by rfl
theorem ironBarRecipe_gatherCount :
    ironBarRecipe.gatherCount = 2 := by rfl
theorem ironSwordRecipe_gatherCount :
    ironSwordRecipe.gatherCount = 1 := by rfl

/-- Concrete craft counts (1 per non-leaf recipe). -/
theorem ironOreRecipe_craftCount :
    ironOreRecipe.craftCount = 0 := by rfl
theorem ironBarRecipe_craftCount :
    ironBarRecipe.craftCount = 1 := by rfl
theorem ironSwordRecipe_craftCount :
    ironSwordRecipe.craftCount = 1 := by rfl

/-! ## Concrete plan witness -/

/-- A fixture State representing a fresh character with an iron_sword
    items task accepted, task_total = 1, no progress yet, no prerequisites
    satisfied (skill 0, no inventory). -/
def fixtureFreshState : State where
  level := 1
  xp := 0
  taskProgress := 0
  taskTotal := 1
  inventoryUsed := 0
  inventoryMax := 30
  hp := 100
  maxHp := 100
  taskType := some "items"
  taskCode := some "iron_sword"
  projectedSkillXpDelta := 0
  targetSkillXp := 0
  gold := 0
  bankAccessible := true
  bankUnlockMonsterPresent := false
  initialXp := 0
  unlockMonsterLevel := 0
  bankRequiredLevel := 0
  hasOverstockItems := false
  selectBankDepositsNonempty := false
  pendingItemsNonempty := false
  sellableInventoryNonempty := false
  taskCoinsTotal := 0
  taskExchangeMinCoins := 1
  lowYieldCancelFires := false
  taskCancelFires := false
  pursueTaskFires := false
  objectiveStepFires := false
  bankItemsKnown := false
  bankItemsCount := 0
  bankCapacity := 0
  nextExpansionCost := 1
  taskLifecyclePhase := .accepted
  actionsAttempted := 0
  craftableSlots := 0

/-! ## Concrete fixture instantiation -/

/-- **Concrete plan exists for the iron_sword items task**.

    Instantiates Phase 23d-8's universal `recipe_then_complete_reachable`
    against the fixture's `iron_sword` recipe and `fixtureFreshState`.
    Witnesses an explicit K_gather + K_craft + K_taskTrade plan that
    reaches `phase = .complete`.

    The exact K values for this fixture (modulo the recipe-chain
    abstraction in Phase 23d-8):
      K_gather = ironSwordRecipe.gatherCount = 1
      K_craft  = ironSwordRecipe.craftCount  = 1
      K_taskTrade = 1
    Total = 3 cycles to deliver one iron_sword (under the abstract
    counter model — production would need more cycles because each
    `.gather` only contributes 1 unit and each `.craft` only completes
    1 step). The proof's K is an EXISTENTIAL — sufficient to demonstrate
    the structural reachability claim. -/
theorem ironSword_task_completable :
    ∃ (K_gather K_craft K_taskTrade : Nat),
      (applyPlan
        ((List.replicate K_gather .gather)
          ++ (List.replicate K_craft .craft)
          ++ (List.replicate K_taskTrade .taskTrade))
        fixtureFreshState).taskLifecyclePhase = TaskLifecyclePhase.complete := by
  -- Apply the universal Phase 23d-8 theorem.
  apply recipe_then_complete_reachable ironSwordRecipe fixtureFreshState
  · -- taskCode is some
    decide
  · -- taskTotal > 0
    decide
  · -- taskProgress < taskTotal
    decide

/-- Concrete-witness restatement: explicit K values from the recipe shape. -/
theorem ironSword_task_completable_explicit :
    (applyPlan
      ((List.replicate ironSwordRecipe.gatherCount .gather)
        ++ (List.replicate ironSwordRecipe.craftCount .craft)
        ++ (List.replicate (fixtureFreshState.taskTotal - fixtureFreshState.taskProgress)
                            .taskTrade))
      fixtureFreshState).taskLifecyclePhase = TaskLifecyclePhase.complete := by
  -- This is the explicit-witness branch the Phase 23d-8 proof constructs.
  -- Direct application via the existential.
  have h := ironSword_task_completable
  -- Decompose the existential and pin to the canonical witness.
  -- (The Phase 23d-8 proof uses these exact K values; this corollary
  -- exposes them for downstream consumers.)
  -- Re-run the universal proof against the same recipe + state.
  exact (recipe_then_complete_reachable_with_explicit_K)
    ironSwordRecipe fixtureFreshState (by decide) (by decide) (by decide)
  where
    recipe_then_complete_reachable_with_explicit_K
        (r : Recipe) (s : State)
        (hCode : s.taskCode.isSome = true)
        (hTot : s.taskTotal > 0)
        (hLT : s.taskProgress < s.taskTotal) :
        (applyPlan
          ((List.replicate r.gatherCount .gather)
            ++ (List.replicate r.craftCount .craft)
            ++ (List.replicate (s.taskTotal - s.taskProgress) .taskTrade))
          s).taskLifecyclePhase = TaskLifecyclePhase.complete := by
      -- Extract the concrete K's from the universal theorem.
      -- The universal proof in RecipeChainClosure constructs exactly
      -- these witnesses, so we re-run its body with the same structure.
      set K_g := r.gatherCount with hKgDef
      set K_c := r.craftCount with hKcDef
      set K_t := s.taskTotal - s.taskProgress with hKtDef
      have hSplit :
          applyPlan
            (List.replicate K_g .gather ++ List.replicate K_c .craft
              ++ List.replicate K_t .taskTrade) s
            = applyPlan (List.replicate K_t .taskTrade)
                (applyPlan (List.replicate K_g .gather
                  ++ List.replicate K_c .craft) s) := by
        simp [applyPlan, List.foldl_append]
      rw [hSplit]
      set s' := applyPlan (List.replicate K_g .gather
                            ++ List.replicate K_c .craft) s with hsdef
      have hSplit2 :
          applyPlan (List.replicate K_g .gather ++ List.replicate K_c .craft) s
            = applyPlan (List.replicate K_c .craft)
                (applyPlan (List.replicate K_g .gather) s) := by
        simp [applyPlan, List.foldl_append]
      have hCode' : s'.taskCode.isSome = true := by
        rw [hsdef, hSplit2, replicate_craft_taskCode]
        rw [replicate_gather_taskCode]
        exact hCode
      have hProg' : s'.taskProgress = s.taskProgress := by
        rw [hsdef, hSplit2, replicate_craft_taskProgress]
        rw [replicate_gather_taskProgress]
      have hTot' : s'.taskTotal = s.taskTotal := by
        rw [hsdef, hSplit2, replicate_craft_taskTotal]
        rw [replicate_gather_taskTotal]
      have hTot'_pos : s'.taskTotal > 0 := by rw [hTot']; exact hTot
      have hLT' : s'.taskProgress < s'.taskTotal := by
        rw [hProg', hTot']; exact hLT
      have hKEq : K_t = s'.taskTotal - s'.taskProgress := by
        rw [hProg', hTot', hKtDef]
      rw [hKEq]
      exact taskComplete_reachable s' hCode' hTot'_pos hLT'

end Formal.Liveness.GameDataFixture
