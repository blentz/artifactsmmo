# Product Requirements Prompt: Enhanced GoalManager System

## Executive Summary

The current GoalManager system in the ArtifactsMMO AI player is too rigid for effective gameplay. This PRP outlines a comprehensive enhancement to create an intelligent, data-driven goal management system that prioritizes XP collection through combat and crafting while leveraging game data for strategic decision-making.

## Problem Statement

### Current Limitations
- **Rigid Goal System**: Simple dictionary-based goals with basic priority scoring
- **Limited Game Data Integration**: Unused monster, item, resource, and map data for strategic decisions
- **No Goal Chain Support**: Lack of support for dependent goals and sub-goal requests
- **Basic Prioritization**: Simple integer priorities without weighted, multi-factor scoring
- **Missing Analysis Modules**: No level-appropriate monster targeting, gear evaluation, or crafting analysis

### Business Impact
The AI player's effectiveness is severely limited, resulting in errors, progression blocks, and poor strategic decision-making that prevents reliable advancement toward level 5 with appropriate gear.

## Solution Overview

Transform the GoalManager into an intelligent system with:
1. **Weighted Goal Selection** - Multi-factor scoring system prioritizing steady progression
2. **Goal Chain Architecture** - Dynamic sub-goal request system for dependency resolution
3. **Game Data Analysis Modules** - Strategic evaluation subsystems for level 5 progression
4. **Reliability-Focused Decision Making** - Error-free advancement toward level 5 with appropriate gear

## Data Source Requirements

### Mandatory Use of Cached Game Data
**ALL analysis and decision-making MUST use cached game data from the API client.** The system has access to complete, real-time game data through the CacheManager and must query this data for every decision.

**Available Cached Data Structures:**
```python
# From cache_manager.get_all_monsters()
List[GameMonster]: code, name, level, hp, attack_fire, attack_earth, attack_water, 
                   attack_air, res_fire, res_earth, res_water, res_air, min_gold, 
                   max_gold, drops

# From cache_manager.get_all_items()  
List[GameItem]: code, name, level, type, subtype, description, effects, craft, tradeable

# From cache_manager.get_all_resources()
List[GameResource]: code, name, skill, level, drops

# From cache_manager.get_all_maps()
List[GameMap]: name, skin, x, y, content (MapContent: type, code)

# From cache_manager.get_all_npcs()
List[GameNPC]: NPC trading and interaction data
```

### Required Data Query Examples
**Level-Appropriate Monster Selection:**
```python
# MUST filter real monster data - NO hardcoded monster names
appropriate_monsters = [
    monster for monster in game_data.monsters 
    if character.level - 1 <= monster.level <= character.level + 1
]
```

**Equipment Analysis:**
```python
# MUST query actual item database - NO hardcoded item codes
level_appropriate_gear = [
    item for item in game_data.items 
    if item.level <= 5 and item.type in EQUIPMENT_TYPES
]
```

**Crafting Recipe Analysis:**
```python
# MUST parse real craft data - NO simplified recipes
if item.craft:
    materials_needed = item.craft['materials']  # Real recipe data
    for material in materials_needed:
        # Find where this material can be obtained
        sources = [resource for resource in game_data.resources 
                  if material in resource.drops]
```

**Location Finding:**
```python
# MUST query actual map data - NO hardcoded coordinates
monster_locations = [
    game_map for game_map in game_data.maps 
    if game_map.content and game_map.content.type == "monster" 
    and game_map.content.code == target_monster.code
]
```

## Prohibited Approaches

### Absolutely Forbidden
- **No Hardcoding**: No hardcoded monster names, item codes, coordinates, or any game constants
- **No Task Simplification**: Must implement full functionality, not simplified or placeholder versions  
- **No Mocking**: No fake data, mock responses, or simulated game content
- **No "For Later"**: Everything must be fully implemented in the first pass
- **No Assumptions**: All decisions must be based on actual queried data

### Examples of Prohibited Code
```python
# FORBIDDEN - hardcoded values
if monster_name == "chicken":  # NO!
    return True

# FORBIDDEN - simplified implementation  
def find_monsters():
    return ["chicken", "rat"]  # NO!

# FORBIDDEN - placeholder implementation
def analyze_crafting():
    # TODO: implement later  # NO!
    pass

# REQUIRED - data-driven implementation
def find_level_appropriate_monsters(character_level: int, monsters: List[GameMonster]):
    return [m for m in monsters if character_level - 1 <= m.level <= character_level + 1]
```

## Technical Requirements

### 1. Goal Class Hierarchy

**Base Goal Interface:**
```python
class BaseGoal(ABC):
    @abstractmethod
    def calculate_weight(self, character_state: CharacterGameState, game_data: Any) -> float:
        """Calculate dynamic weight based on current conditions"""
        pass
    
    @abstractmethod
    def is_feasible(self, character_state: CharacterGameState, game_data: Any) -> bool:
        """Check if goal can be pursued with current character state"""
        pass
    
    @abstractmethod
    def get_plan_steps(self, character_state: CharacterGameState, game_data: Any) -> List[BaseAction]:
        """Generate action sequence to achieve goal"""
        pass
    
    @abstractmethod
    def get_progression_value(self, character_state: CharacterGameState) -> float:
        """Calculate contribution to reaching level 5 with appropriate gear"""
        pass
```

**Specialized Goal Classes:**
- `CombatGoal`: Target level-appropriate monsters for XP toward level 5
- `CraftingGoal`: Create level-appropriate equipment and gain crafting XP
- `GatheringGoal`: Collect materials needed for crafting progression
- `EquipmentGoal`: Acquire and equip level-appropriate gear (level ≤ 5)

### 2. Goal Chain and Sub-Goal Request System

**Sub-Goal Request Architecture:**
```python
class SubGoalRequest:
    goal_type: str  # "move_to_location", "obtain_item", "reach_hp_threshold"
    parameters: Dict[str, Any]  # specific requirements for the sub-goal
    priority: int  # urgency level (1-10)
    requester: str  # identifier of the action/goal that requested this

class ActionResult:
    success: bool
    sub_goal_requests: List[SubGoalRequest] = []
    state_changes: Dict[str, Any] = {}
    error_message: Optional[str] = None

class BaseAction:
    def execute(self, character_state, game_data) -> ActionResult:
        # Check if action can be performed
        if not self.can_execute(character_state, game_data):
            # Return sub-goal request instead of failing
            return ActionResult(
                success=False,
                sub_goal_requests=[self.create_sub_goal_request(character_state, game_data)]
            )
        return self.perform_action(character_state, game_data)
```

**Goal Chain Planning:**
When actions discover dependencies at runtime, they request sub-goals. The GoalManager dynamically incorporates these sub-goals into the planning process, creating natural dependency resolution chains.

**Example Flow:**
1. Primary Goal: "Gain XP" → selects AttackAction
2. AttackAction discovers it's not at monster location
3. AttackAction returns SubGoalRequest("move_to_location", {target_monster: "chicken", coordinates: (1,2)})
4. GoalManager creates MoveGoal with target coordinates  
5. Final plan: [MoveAction(1,2), AttackAction()]

### 3. Analysis Modules

#### Level-Appropriate Monster Targeting
```python
class LevelAppropriateTargeting:
    def find_optimal_monsters(
        self, 
        character_level: int, 
        current_position: Tuple[int, int],
        monsters: List[GameMonster],
        maps: List[GameMap]
    ) -> List[Tuple[GameMonster, GameMap, float]]:
        """
        Find monsters within character_level ± 1 with efficiency scoring.
        
        MUST query actual GameMonster data:
        - Filter by monster.level in [character_level-1, character_level+1]
        - Use monster.hp, monster.attack_*, monster.min_gold for scoring
        - Cross-reference monster.code with map.content.code for locations
        
        Returns: List of (monster, location, efficiency_score) tuples
        """
        # Filter level-appropriate monsters from real data
        appropriate_monsters = [
            monster for monster in monsters 
            if character_level - 1 <= monster.level <= character_level + 1
        ]
        
        # Find locations for each monster using real map data
        monster_locations = []
        for monster in appropriate_monsters:
            locations = [
                game_map for game_map in maps 
                if (game_map.content and 
                    game_map.content.type == "monster" and 
                    game_map.content.code == monster.code)
            ]
            
            for location in locations:
                # Calculate efficiency based on real monster stats
                distance = abs(location.x - current_position[0]) + abs(location.y - current_position[1])
                xp_potential = monster.level * 10  # Based on actual level
                gold_potential = (monster.min_gold + monster.max_gold) / 2
                efficiency = (xp_potential + gold_potential) / max(1, distance)
                
                monster_locations.append((monster, location, efficiency))
        
        return sorted(monster_locations, key=lambda x: x[2], reverse=True)
```

#### Crafting Analysis Module
```python
class CraftingAnalysisModule:
    def analyze_recipe(
        self, 
        recipe_code: str, 
        items: List[GameItem],
        character_state: CharacterGameState
    ) -> CraftingAnalysis:
        """
        Analyze crafting recipe for material requirements, XP rewards,
        and economic value using real GameItem.craft data.
        
        MUST parse actual craft data:
        - Query items list to find item with matching code
        - Parse item.craft dictionary for material requirements
        - Calculate total material costs from real drop rates
        """
        # Find the item using real data - NO hardcoding
        target_item = next((item for item in items if item.code == recipe_code), None)
        if not target_item or not target_item.craft:
            return CraftingAnalysis(feasible=False, reason="No recipe found")
        
        # Parse real crafting requirements
        craft_data = target_item.craft
        required_materials = craft_data.get('materials', [])
        required_skill_level = craft_data.get('level', 1)
        
        # Check if character can craft this
        skill_name = craft_data.get('skill', 'crafting')
        character_skill_level = getattr(character_state, f"{skill_name}_level", 1)
        
        if character_skill_level < required_skill_level:
            return CraftingAnalysis(
                feasible=False, 
                reason=f"Need {skill_name} level {required_skill_level}"
            )
        
        return CraftingAnalysis(
            feasible=True,
            materials_needed=required_materials,
            skill_required=skill_name,
            level_required=required_skill_level,
            result_item_level=target_item.level
        )
    
    def find_material_sources(
        self, 
        material_code: str,
        resources: List[GameResource],
        maps: List[GameMap]
    ) -> List[Tuple[GameMap, GameResource]]:
        """
        Find all locations where material can be gathered using real data.
        
        MUST query actual resource and map data:
        - Search resources list for items that drop the material
        - Cross-reference resource.code with map.content.code for locations
        """
        # Find resources that drop this material - NO hardcoding
        material_sources = []
        for resource in resources:
            if any(drop.get('code') == material_code for drop in resource.drops):
                # Find locations where this resource exists
                resource_locations = [
                    game_map for game_map in maps 
                    if (game_map.content and 
                        game_map.content.type == "resource" and 
                        game_map.content.code == resource.code)
                ]
                
                for location in resource_locations:
                    material_sources.append((location, resource))
        
        return material_sources
```

#### Map Analysis Module
```python
class MapAnalysisModule:
    def find_nearest_content(
        self,
        current_pos: Tuple[int, int],
        content_type: str,
        level_filter: Optional[int] = None
    ) -> List[Tuple[GameMap, float]]:
        """
        Find nearest locations with specified content type.
        Returns: List of (map, distance) sorted by proximity
        """
    
    def calculate_travel_efficiency(
        self,
        start_pos: Tuple[int, int],
        targets: List[Tuple[int, int]]
    ) -> Dict[Tuple[int, int], float]:
        """Calculate travel time and efficiency for multiple targets"""
```

### 4. Weighted Goal Selection System

```python
class GoalWeightCalculator:
    def calculate_final_weight(
        self, 
        goal: BaseGoal, 
        character_state: CharacterGameState, 
        game_data: Any
    ) -> float:
        """
        Multi-factor weight calculation for steady progression:
        - Necessity (40%): Required for progression (HP critical, missing gear, level blocks)
        - Feasibility (30%): Can be accomplished with current resources/state
        - Progression Value (20%): Contributes to reaching level 5 with appropriate gear
        - Stability (10%): Reduces error potential and maintains steady progress
        """
        necessity = self._calculate_necessity(character_state)
        feasibility = self._calculate_feasibility(goal, character_state, game_data)
        progression = goal.get_progression_value(character_state)
        stability = 1.0 - goal.estimate_error_risk(character_state)  # Lower risk = higher stability
        
        return (necessity * 0.4 + feasibility * 0.3 + 
                progression * 0.2 + stability * 0.1)
```

## Implementation Plan

### Phase 1: Foundation (Priority: Critical)
1. **Create Goal Class Hierarchy** (`src/ai_player/goals/`)
   - `base_goal.py`: Abstract base class
   - `combat_goal.py`: Monster targeting and combat planning
   - `crafting_goal.py`: Recipe analysis and material planning
   - `gathering_goal.py`: Resource collection optimization
   - `equipment_goal.py`: Gear upgrade evaluation

### Phase 2: Analysis Modules (Priority: High)
2. **Level-Appropriate Monster Targeting** (`src/ai_player/analysis/level_targeting.py`)
   - Filter monsters by character level ± 1
   - Score by XP efficiency and travel distance
   - Consider combat difficulty and success probability

3. **Map Analysis Module** (`src/ai_player/analysis/map_analysis.py`)
   - Location finding for content types
   - Travel route optimization
   - Distance calculations and pathfinding efficiency

### Phase 3: Strategic Analysis (Priority: High)  
4. **Crafting Analysis Module** (`src/ai_player/analysis/crafting_analysis.py`)
   - Recipe requirement breakdown
   - Material dependency trees
   - Economic value and XP analysis

5. **Gear Evaluation Module** (`src/ai_player/analysis/gear_evaluation.py`)
   - Equipment stat comparison
   - Upgrade path identification
   - Combat effectiveness calculations

### Phase 4: Integration (Priority: High)
6. **Weighted Goal Selection** (`src/ai_player/goal_selector.py`)
   - Multi-factor weight calculation
   - Dynamic priority adjustment
   - Goal feasibility validation

7. **Enhanced GoalManager Integration**
   - Replace current goal selection logic
   - Integrate all analysis modules
   - Maintain backward compatibility with action system

## Success Metrics

### Primary Success Criteria
- **Level 5 Achievement**: Character reaches level 5 through steady XP progression
- **Level-Appropriate Gear**: All equipment slots filled with items having level requirement ≤ 5
- **Zero Critical Errors**: No crashes, infinite loops, or system failures during progression

### Secondary Metrics  
- **Steady Progress**: Non-zero advancement each session (XP gained, gear improved, materials gathered)
- **Goal Chain Resolution**: Successful sub-goal request handling and dependency resolution
- **Equipment Progression**: Systematic acquisition and equipping of level-appropriate gear

### Level 5 with Level-Appropriate Gear Requirements
Based on ArtifactsMMO game mechanics analysis:

**Character Progression:**
- Start: Level 1 character with basic equipment
- Target: Level 5 character with all equipment slots containing level ≤ 5 items
- Method: Combat XP from level-appropriate monsters (±1 level) and crafting XP

**Equipment Analysis:**
- **Slots Required**: weapon, helmet, chest_armor, leg_armor, boots, ring1, ring2, amulet
- **Level Constraint**: All equipped items must have `item.level ≤ 5`
- **Acquisition Methods**: 
  - Monster drops from defeated enemies
  - Crafted items using gathered materials
  - NPC purchases using accumulated gold

**Progression Chain Example:**
1. Fight level 1-2 monsters for initial XP
2. Gather materials (wood, ore) for crafting level 2-3 equipment
3. Craft improved weapons/armor for better combat effectiveness
4. Fight stronger monsters (level 3-4) with improved gear
5. Continue cycle until level 5 with full level-appropriate equipment

## Implementation Constraints

### Data Dependency Validation
Every analysis module and goal class MUST include validation that ensures it receives and uses real game data:

```python
def validate_game_data(self, game_data: Any) -> None:
    """Validate that all required game data is present and non-empty."""
    if not game_data:
        raise ValueError("Game data cannot be None")
    
    if not hasattr(game_data, 'monsters') or not game_data.monsters:
        raise ValueError("Monster data is required and cannot be empty")
    
    if not hasattr(game_data, 'items') or not game_data.items:
        raise ValueError("Item data is required and cannot be empty")
    
    if not hasattr(game_data, 'maps') or not game_data.maps:
        raise ValueError("Map data is required and cannot be empty")
    
    # Validate data structure integrity
    for monster in game_data.monsters[:5]:  # Sample validation
        if not hasattr(monster, 'level') or not hasattr(monster, 'code'):
            raise ValueError(f"Invalid monster data structure: {monster}")
```

### Required Error Handling
All data queries must include comprehensive error handling for missing or invalid data:

```python
# REQUIRED - error handling for missing data
def find_level_appropriate_gear(self, items: List[GameItem]) -> List[GameItem]:
    if not items:
        raise ValueError("Cannot find gear: items list is empty")
    
    gear_items = [item for item in items if item.level <= 5 and item.type in EQUIPMENT_TYPES]
    
    if not gear_items:
        # This is valid - may be no level 5 gear available
        return []
    
    return gear_items
```

### Implementation Completeness Requirements
- **No Placeholder Functions**: Every method must have complete implementation
- **No Hardcoded Fallbacks**: Cannot use hardcoded data when API data is unavailable
- **No Simplified Logic**: Must implement full complexity as specified
- **Real Data Validation**: Must validate that queries return expected data structures

## Validation Gates

All validation commands must pass for implementation acceptance:

```bash
# Code Quality (zero warnings/errors required)
uv run ruff check --fix src/
uv run mypy src/

# Unit Tests (100% coverage requirement)
uv run pytest tests/ -v --cov=src --cov-report=term-missing --cov-fail-under=100

# Data Dependency Tests (verify real API data usage)
uv run pytest tests/test_data_dependencies/ -v

# Integration Tests (end-to-end goal execution)
uv run pytest tests/test_integration/ -v

# No Hardcoding Tests (scan for prohibited patterns)
uv run pytest tests/test_no_hardcoding/ -v
```

### Additional Validation Requirements
- **Data Source Verification**: Every analysis method must log which data sources were queried
- **Result Validation**: All returned data must be validated against expected schemas
- **Error Path Testing**: Every error condition must be tested with real scenarios
- **API Data Integration**: Tests must verify integration with actual cached game data

## Technical Context

### Key Files to Reference
- **Current GoalManager**: `src/ai_player/goal_manager.py:22-1243` (1200+ lines, needs comprehensive refactor)
- **API Client**: `src/game_data/api_client_wrapper.py:44-558` (game operations and data access)
- **Game Models**: `src/game_data/models.py` (GameMonster, GameItem, GameResource, GameMap structures)
- **Character State**: `src/ai_player/state/character_game_state.py` (current state representation)
- **Action System**: `src/ai_player/actions/` (existing action framework to integrate with)

### Game Mechanics Context
- **Combat**: Fight monsters at map locations for XP/gold/items
- **Crafting**: Create items from materials using recipes (provides skill XP)
- **Gathering**: Collect resources at specific map coordinates  
- **Equipment**: Equip items for stat bonuses affecting combat effectiveness
- **Level Requirements**: Monster levels determine XP efficiency (±1 level optimal)

### Data Structures Available
```python
# Monster data includes level, HP, damage, resistances, drops
GameMonster: code, name, level, hp, attack_*, res_*, min_gold, max_gold, drops

# Item data includes crafting recipes and stat effects  
GameItem: code, name, level, type, subtype, effects, craft, tradeable

# Resource data includes skill requirements and drop rates
GameResource: code, name, skill, level, drops

# Map data includes coordinates and content (monsters/resources)
GameMap: name, x, y, content (MapContent: type, code)
```

## Implementation Gotchas

### Critical Considerations
1. **API Data Dependency**: System cannot function without game data - no defaulting, fail with clear errors
2. **One Class Per File**: Follow project convention for clean organization
3. **Model Boundary Enforcement**: Transform API schemas to internal models at boundaries
4. **Cooldown Management**: Integrate with existing CooldownManager for action timing
5. **GOAP Integration**: New goals must convert to GOAP format for existing planner

### Common Pitfalls to Avoid
- **Infinite Loops**: Ensure goal feasibility checks prevent impossible goals
- **Resource Conflicts**: Handle concurrent resource requirements between goals
- **State Synchronization**: Keep character state consistent across goal evaluation
- **Error Cascading**: Implement robust error handling at each analysis layer

## Risk Mitigation

### Technical Risks
- **Performance Impact**: Goal calculation complexity could slow decision-making
  - *Mitigation*: Implement caching for expensive calculations, benchmark all analysis modules
- **Data Inconsistency**: Game API data could be malformed or incomplete  
  - *Mitigation*: Comprehensive validation and fallback mechanisms for all data access

### Implementation Risks
- **Integration Complexity**: Large refactor could break existing functionality
  - *Mitigation*: Incremental implementation with extensive testing at each phase
- **Over-Engineering**: Complex system could be harder to debug and maintain
  - *Mitigation*: Clear separation of concerns, comprehensive documentation

## Quality Assurance

### Testing Strategy
- **Unit Tests**: 100% coverage for all analysis modules and goal classes
- **Data Dependency Tests**: Verify all methods use real cached game data, not hardcoded values
- **Integration Tests**: Full goal selection and execution workflows with real API data
- **Edge Case Tests**: Empty game data, impossible goals, missing items/monsters
- **No-Hardcoding Tests**: Automated scanning for prohibited hardcoded values

### Code Quality Requirements
- All code must pass `ruff` linting with zero warnings
- All code must pass `mypy` type checking with zero errors  
- All methods must have comprehensive docstrings following project conventions
- All classes must follow one-class-per-file convention
- **Data Validation**: Every method must validate input data structures
- **Error Handling**: Comprehensive error handling for all API data scenarios

## Confidence Score: 9/10

This strengthened PRP provides comprehensive context for successful one-pass implementation with absolute clarity on data requirements. The analysis includes thorough codebase examination, specific success criteria (level 5 with appropriate gear), innovative goal chain architecture, and crystal-clear constraints on data usage.

**Critical Improvements from Strengthening Pass:**
- **Mandatory Real Data Usage**: Explicit requirements for cached API data in all analysis
- **Zero Hardcoding Policy**: Complete prohibition of hardcoded game constants  
- **Implementation Completeness**: No placeholders, simplifications, or "for later" allowed
- **Comprehensive Validation**: Data validation, error handling, and testing requirements
- **Concrete Examples**: Detailed code examples showing exact data structure usage

**Data-Driven Requirements:**
- All monster selection must filter `List[GameMonster]` by actual level values
- All crafting analysis must parse real `GameItem.craft` data structures  
- All location finding must query `List[GameMap]` with actual coordinates
- All equipment evaluation must use real `item.level` and `item.type` values

The AI agent implementing this PRP MUST use cached game data for every decision, with comprehensive error handling and validation. No shortcuts, simplifications, or hardcoded values are permitted. Use @sentient-agi-reasoning for complex design decisions while maintaining absolute adherence to data-driven implementation requirements.
