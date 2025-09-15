# Fix Crafting Goal Implementation Plan

## Problem Analysis

The current `CraftingGoal` implementation fails because it attempts to achieve multiple incompatible states simultaneously in a single GOAP target state. Crafting requires a sequential process that cannot be completed in one planning cycle.

### Current Issue
```python
# Current CraftingGoal.get_target_state() tries to achieve all of this at once:
{
    GameState.AT_WORKSHOP_LOCATION: True,        # Must be at workshop
    GameState.HAS_CRAFTING_MATERIALS: True,     # Must have all materials  
    GameState.CAN_CRAFT: True,                  # Must be able to craft
    GameState.CURRENT_X: 3,                     # Must be at specific coordinates
    GameState.CURRENT_Y: 1,                     
    GameState.GAINED_XP: True,                  # Must gain XP (outcome)
    GameState.INVENTORY_SPACE_AVAILABLE: True,  # Must have inventory space
    GameState.COOLDOWN_READY: True             # Must be ready for action
}
```

This is impossible because you cannot gather materials AND be at the workshop simultaneously.

## Example Case: Copper Legs Armor (17+ actions with cooldowns)

**Target**: Copper Legs Armor (level 5 gearcrafting)
**Materials**: 5x copper_bar + 2x feather
**Raw Materials**: 10x copper_ore (for copper_bars) + 2x feather (from chickens)

### Complete Action Sequence
1. Move to Copper Rocks (2,0) → **cooldown wait**
2-11. Gather copper_ore x10 → **cooldown wait after each**
12. Move to Mining Workshop (1,5) → **cooldown wait**
13. Craft copper_bar x5 → **cooldown wait**
14. Move to Chicken location (0,1) → **cooldown wait**  
15-16. Fight chickens x2 for feathers → **cooldown wait after each**
17. Move to Gearcrafting Workshop (3,1) → **cooldown wait**
18. Craft Copper Legs Armor → **cooldown wait**

**Total**: 18 actions + 18 cooldown waits = **36 execution cycles minimum**

## Solution Architecture

### 1. Convert CraftingGoal to Hierarchical Sub-Goal Generator

Replace the impossible single target state with sequential sub-goal requests:

```python
class CraftingGoal(BaseGoal):
    def get_target_state(self) -> GOAPTargetState:
        # Return minimal achievable state for recipe selection
        return GOAPTargetState(
            target_states={GameState.HAS_SELECTED_RECIPE: True},
            priority=7,
            timeout_seconds=60
        )
    
    def generate_sub_goal_requests(self) -> list[SubGoalRequest]:
        recipe = self._select_optimal_recipe()
        materials_needed = self._analyze_material_requirements(recipe)
        
        sub_goals = []
        
        # Phase 1: Gather each raw material
        for material_code, quantity in materials_needed.items():
            sub_goals.append(SubGoalRequest(
                goal_type="gather_material",
                parameters={
                    "material_code": material_code,
                    "quantity": quantity
                },
                priority=8,
                requester="CraftingGoal"
            ))
        
        # Phase 2: Move to workshop
        workshop_location = self._find_workshop_for_recipe(recipe)
        sub_goals.append(SubGoalRequest(
            goal_type="move_to_location", 
            parameters={
                "target_x": workshop_location.x,
                "target_y": workshop_location.y
            },
            priority=7,
            requester="CraftingGoal"
        ))
        
        # Phase 3: Execute crafting
        sub_goals.append(SubGoalRequest(
            goal_type="execute_craft",
            parameters={
                "recipe_code": recipe.code,
                "workshop_type": recipe.skill
            },
            priority=9,
            requester="CraftingGoal"
        ))
        
        return sub_goals
```

### 2. Create Specialized Sub-Goal Types

#### MaterialGatheringGoal
```python
class MaterialGatheringGoal(BaseGoal):
    def __init__(self, material_code: str, quantity: int):
        self.material_code = material_code
        self.quantity = quantity
    
    def get_target_state(self) -> GOAPTargetState:
        return GOAPTargetState(
            target_states={
                GameState.HAS_MATERIAL_{self.material_code.upper()}: True,
                GameState.INVENTORY_CONTAINS_{self.material_code.upper()}: self.quantity
            },
            priority=8,
            timeout_seconds=300
        )
```

#### WorkshopMovementGoal
```python
class WorkshopMovementGoal(BaseGoal):
    def __init__(self, workshop_x: int, workshop_y: int, workshop_type: str):
        self.workshop_x = workshop_x
        self.workshop_y = workshop_y
        self.workshop_type = workshop_type
    
    def get_target_state(self) -> GOAPTargetState:
        return GOAPTargetState(
            target_states={
                GameState.AT_WORKSHOP_LOCATION: True,
                GameState.CURRENT_X: self.workshop_x,
                GameState.CURRENT_Y: self.workshop_y,
                GameState.CAN_CRAFT: True
            },
            priority=7,
            timeout_seconds=120
        )
```

#### CraftExecutionGoal
```python
class CraftExecutionGoal(BaseGoal):
    def __init__(self, recipe_code: str, workshop_type: str):
        self.recipe_code = recipe_code
        self.workshop_type = workshop_type
    
    def get_target_state(self) -> GOAPTargetState:
        return GOAPTargetState(
            target_states={
                GameState.GAINED_XP: True,
                GameState.HAS_CRAFTED_ITEM: True,
                GameState.CRAFTING_COMPLETED: True
            },
            priority=9,
            timeout_seconds=60
        )
```

### 3. Enhance GameState Enum

Add new states for material tracking and crafting progress:

```python
class GameState(StrEnum):
    # Existing states...
    
    # Recipe selection states
    HAS_SELECTED_RECIPE = "has_selected_recipe"
    RECIPE_ANALYZED = "recipe_analyzed"
    
    # Material gathering states
    MATERIAL_GATHERING_IN_PROGRESS = "material_gathering_in_progress"
    HAS_MATERIAL_COPPER_ORE = "has_material_copper_ore"
    HAS_MATERIAL_FEATHER = "has_material_feather"
    HAS_MATERIAL_COPPER_BAR = "has_material_copper_bar"
    
    # Inventory tracking states  
    INVENTORY_CONTAINS_COPPER_ORE = "inventory_contains_copper_ore"
    INVENTORY_CONTAINS_FEATHER = "inventory_contains_feather"
    INVENTORY_CONTAINS_COPPER_BAR = "inventory_contains_copper_bar"
    
    # Crafting execution states
    CRAFTING_MATERIALS_READY = "crafting_materials_ready"
    HAS_CRAFTED_ITEM = "has_crafted_item"
    CRAFTING_COMPLETED = "crafting_completed"
```

### 4. Update Goal Manager Sub-Goal Factory

Extend the goal manager to handle new sub-goal types:

```python
class GoalManager:
    def create_goal_from_sub_request(self, sub_goal_request: SubGoalRequest) -> BaseGoal:
        if sub_goal_request.goal_type == "gather_material":
            return MaterialGatheringGoal(
                material_code=sub_goal_request.parameters["material_code"],
                quantity=sub_goal_request.parameters["quantity"]
            )
        elif sub_goal_request.goal_type == "move_to_workshop":
            return WorkshopMovementGoal(
                workshop_x=sub_goal_request.parameters["target_x"],
                workshop_y=sub_goal_request.parameters["target_y"],
                workshop_type=sub_goal_request.parameters.get("workshop_type", "unknown")
            )
        elif sub_goal_request.goal_type == "execute_craft":
            return CraftExecutionGoal(
                recipe_code=sub_goal_request.parameters["recipe_code"],
                workshop_type=sub_goal_request.parameters["workshop_type"]
            )
        # ... existing sub-goal types
```

### 5. Create CraftingAction for Final Execution

```python
class CraftingAction(BaseAction):
    def __init__(self, recipe_code: str, workshop_type: str):
        self.recipe_code = recipe_code
        self.workshop_type = workshop_type
    
    def get_preconditions(self) -> GOAPTargetState:
        return GOAPTargetState(
            target_states={
                GameState.COOLDOWN_READY: True,
                GameState.AT_WORKSHOP_LOCATION: True,
                GameState.CRAFTING_MATERIALS_READY: True,
                GameState.CAN_CRAFT: True
            }
        )
    
    def get_effects(self) -> GOAPTargetState:
        return GOAPTargetState(
            target_states={
                GameState.GAINED_XP: True,
                GameState.HAS_CRAFTED_ITEM: True,
                GameState.CRAFTING_COMPLETED: True,
                GameState.COOLDOWN_READY: False
            }
        )
```

### 6. Enhance State Manager for Material Tracking

Update the state manager to track inventory contents and material availability:

```python
class StateManager:
    def update_inventory_states(self, character_state: CharacterGameState) -> None:
        # Track specific materials in inventory
        inventory_counts = self._count_inventory_items(character_state.inventory)
        
        # Update material-specific states using direct enum access
        for material_code, count in inventory_counts.items():
            # Update inventory count states
            if material_code == "copper_ore":
                self.current_state[GameState.INVENTORY_CONTAINS_COPPER_ORE] = count
                self.current_state[GameState.HAS_MATERIAL_COPPER_ORE] = count > 0
            elif material_code == "feather":
                self.current_state[GameState.INVENTORY_CONTAINS_FEATHER] = count
                self.current_state[GameState.HAS_MATERIAL_FEATHER] = count > 0
            elif material_code == "copper_bar":
                self.current_state[GameState.INVENTORY_CONTAINS_COPPER_BAR] = count
                self.current_state[GameState.HAS_MATERIAL_COPPER_BAR] = count > 0
```

## Implementation Steps

### Phase 1: Core Infrastructure
1. **Update GameState enum** with new material and crafting states
2. **Create MaterialGatheringGoal** class with simple target states
3. **Create WorkshopMovementGoal** class for workshop navigation
4. **Create CraftExecutionGoal** class for final crafting step

### Phase 2: Action System Updates  
5. **Create CraftingAction** for actual recipe execution
6. **Update CraftingActionFactory** to generate recipe-specific actions
7. **Enhance StateManager** for inventory and material tracking

### Phase 3: Goal Integration
8. **Restructure CraftingGoal** to use sub-goal generation instead of complex target state
9. **Update GoalManager** sub-goal factory for new goal types
10. **Add material requirement analysis** to CraftingGoal

### Phase 4: Testing & Validation
11. **Test complete crafting sequence** with Copper Legs Armor example
12. **Validate cooldown handling** throughout the sequence
13. **Test inventory state management** and material tracking
14. **Ensure sub-goal execution order** is maintained

## Expected Outcome

After implementation, the crafting system will:

1. **Successfully plan and execute** complex crafting sequences like Copper Legs Armor
2. **Handle cooldown management** automatically between each action
3. **Track material gathering progress** through inventory states
4. **Use proper sub-goal decomposition** instead of impossible single-state targets
5. **Support any craftable recipe** through the same sub-goal architecture

The system will transform from attempting 1 impossible goal into executing 4-6 achievable sub-goals sequentially, each with 2-5 simple actions.