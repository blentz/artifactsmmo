# ArtifactsMMO AI Player Architecture

## Overview

The ArtifactsMMO AI Player is an intelligent game client that uses Goal-Oriented Action Planning (GOAP) to autonomously play the ArtifactsMMO role-playing game. The system integrates the existing GOAP implementation (`src/lib/goap.py`) with the ArtifactsMMO API client to create an autonomous character that can progress from level 1 to maximum level through intelligent decision-making.

## Core Architecture

### System Components

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   CLI Interface │    │  AI Player Core  │    │  Game Data API  │
│                 │    │                  │    │                 │
│ • Character Mgmt│◄──►│ • GOAP Planner   │◄──►│ • API Client    │
│ • Commands      │    │ • Action Engine  │    │ • Game State    │
│ • Logging Ctrl  │    │ • State Manager  │    │ • Cooldowns     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │  Data Storage   │
                       │                 │
                       │ • YAML Cache    │
                       │ • Config Files  │
                       │ • Game Data     │
                       └─────────────────┘
```

### Component Details

#### 1. CLI Interface (`src/cli/`)
**Purpose**: User interaction, character management, and system diagnostics

**Modules**:
- `main.py` - Main CLI entry point with argument parsing
- `commands/` - Modular command implementations
  - `character.py` - Character CRUD operations  
  - `ai_player.py` - AI player control and monitoring
  - `diagnostics.py` - GOAP planning and state diagnostics

**Core Commands**:
- Character Management: `create-character`, `delete-character`, `list-characters`
- AI Player Control: `run-character`, `stop-character`, `status-character`
- Diagnostic Commands: `diagnose-state`, `diagnose-actions`, `diagnose-plan`, `test-planning`

**Diagnostic Features**:
```bash
# State inspection and validation
uv run python -m src.cli.main diagnose-state my_character
uv run python -m src.cli.main diagnose-state my_character --validate-enum

# Action analysis and troubleshooting  
uv run python -m src.cli.main diagnose-actions my_character --show-costs
uv run python -m src.cli.main diagnose-actions --list-all --show-preconditions

# GOAP planning visualization
uv run python -m src.cli.main diagnose-plan my_character --goal "level_up" --verbose
uv run python -m src.cli.main diagnose-plan my_character --goal "gather_resources" --show-steps

# Planning simulation and testing
uv run python -m src.cli.main test-planning --mock-state tests/fixtures/level_1_state.json
uv run python -m src.cli.main test-planning --start-level 1 --goal-level 2 --dry-run

# System configuration diagnostics
uv run python -m src.cli.main diagnose-weights --show-action-costs
uv run python -m src.cli.main diagnose-cooldowns my_character --monitor
```

**Responsibilities**:
- Character creation and deletion via API with validation
- Start/stop AI player instances with monitoring
- Configure logging levels (DEBUG, INFO, WARNING, ERROR)
- Display character status and statistics
- Provide deep introspection into GOAP planning process
- Enable troubleshooting of action preconditions and state management
- Support testing and simulation of planning scenarios

#### 2. AI Player Core (`src/ai_player/`)
**Purpose**: Intelligent game automation using Enhanced GOAP with recursive sub-goal support

**Key Modules**:
- `ai_player.py` - Main AI player orchestrator
- `actions/` - Modular GOAP action system with factory patterns
  - `base_action.py` - Abstract base class for all actions
  - `action_factory.py` - Factory for creating action instances
  - `rest_action_factory.py` - Factory for specialized rest actions
  - `movement_action.py` - Movement and pathfinding
  - `combat_action.py` - Monster fighting mechanics
  - `gathering_action.py` - Resource collection
  - `rest_action.py` - HP recovery with intelligent location selection
- `goals/` - Enhanced goal system with data-driven analysis
  - `base_goal.py` - Abstract base class for intelligent goals
  - `combat_goal.py` - Level-appropriate monster targeting
  - `crafting_goal.py` - Recipe analysis and material planning
  - `gathering_goal.py` - Resource collection optimization
  - `equipment_goal.py` - Gear upgrade evaluation
  - `movement_goal.py` - Strategic movement planning
  - `rest_goal.py` - HP recovery goal management
  - `sub_goal_request.py` - Sub-goal request models
- `analysis/` - Strategic game data analysis modules
  - `level_targeting.py` - Level-appropriate monster analysis
  - `crafting_analysis.py` - Recipe and material dependency analysis
  - `map_analysis.py` - Location finding and travel optimization
- `types/` - Type-safe models for GOAP integration
  - `goap_models.py` - Pydantic models for type-safe GOAP
  - `game_data.py` - Game data type definitions
- `state/` - Enhanced state management with recursive validation
  - `game_state.py` - GameState enum definitions
  - `character_game_state.py` - Character state Pydantic model
  - `state_manager.py` - State tracking with recursive sub-goal support
- `action_executor.py` - Enhanced API action execution with recursive sub-goal handling
- `goal_manager.py` - Intelligent goal selection with weighted analysis
- `goal_selector.py` - Goal selection and prioritization logic
- `exceptions.py` - Custom exceptions for error handling
- `diagnostics/` - Enhanced CLI diagnostic commands
  - `planning_diagnostics.py` - GOAP planning visualization and analysis

**Enhanced GOAP Integration**:
- Uses existing `src/lib/goap.py` with enhanced goal-driven planning
- Intelligent goal system with weighted selection and feasibility analysis
- Data-driven decision making using cached game data (monsters, items, maps)
- Recursive sub-goal architecture with factory patterns
- Type-safe GOAP models using Pydantic for state management
- Strategic analysis modules for level-appropriate targeting and crafting
- Sub-goal request system for dynamic dependency resolution

#### 3. Game Data Management (`src/game_data/`)
**Purpose**: API integration and game state caching

**Modules**:
- `api_client.py` - Wrapper around artifactsmmo-api-client
- `game_state.py` - Central game state repository
- `cooldown_manager.py` - Action timing and cooldown handling
- `cache_manager.py` - Game data caching using `src/lib/yaml_data.py`

#### 4. Data Storage
**Structure**:
```
data/
├── characters/          # Character-specific data
│   ├── {character_name}/
│   │   ├── state.yaml   # Current character state
│   │   ├── goals.yaml   # Active and completed goals
│   │   └── history.yaml # Action history and learning data
├── game_data/          # Cached game information
│   ├── items.yaml      # All game items
│   ├── monsters.yaml   # Monster data
│   ├── maps.yaml       # Map information
│   ├── resources.yaml  # Resource locations
│   └── npcs.yaml       # NPC information
└── cache_meta.yaml     # Cache metadata and timestamps

config/
├── ai_player.yaml      # AI behavior configuration
├── logging.yaml        # Logging configuration
└── goap_weights.yaml   # Action cost weights for GOAP
```

## Enhanced GOAP System Integration

### Intelligent Goal System

The AI player uses an enhanced goal-driven system with data-driven analysis and recursive sub-goal support:

```python
# src/ai_player/goals/base_goal.py
from abc import ABC, abstractmethod
from ..state.character_game_state import CharacterGameState
from ..types.game_data import GameData
from ..types.goap_models import GOAPTargetState

class BaseGoal(ABC):
    """Abstract base class for all intelligent goals."""
    
    @abstractmethod
    def calculate_weight(self, character_state: CharacterGameState, game_data: GameData) -> float:
        """Calculate dynamic weight based on current conditions.
        
        Multi-factor scoring:
        - Necessity (40%): Required for progression
        - Feasibility (30%): Can be accomplished with current resources
        - Progression Value (20%): Contributes to level 5 with appropriate gear
        - Stability (10%): Reduces error potential
        """
        pass
    
    @abstractmethod
    def is_feasible(self, character_state: CharacterGameState, game_data: GameData) -> bool:
        """Check if goal can be pursued with current character state."""
        pass
    
    @abstractmethod
    def get_target_state(self, character_state: CharacterGameState, game_data: GameData) -> GOAPTargetState:
        """Generate GOAP target state for planning."""
        pass
    
    @abstractmethod
    def get_progression_value(self, character_state: CharacterGameState) -> float:
        """Calculate contribution to reaching level 5 with appropriate gear."""
        pass
```

### Strategic Analysis Modules

The system includes specialized analysis modules for data-driven decision making:

```python
# src/ai_player/analysis/level_targeting.py
from pydantic import BaseModel, Field

class MonsterTargetOption(BaseModel):
    """Pydantic model for monster targeting analysis results"""
    monster: GameMonster = Field(description="Target monster data")
    location: GameMap = Field(description="Monster location on map")
    efficiency_score: float = Field(ge=0.0, description="Calculated efficiency score")
    travel_distance: int = Field(ge=0, description="Manhattan distance to monster")
    xp_potential: int = Field(ge=0, description="Expected XP gain")
    gold_potential: float = Field(ge=0.0, description="Expected gold gain")

class MonsterTargetingResult(BaseModel):
    """Pydantic model for monster targeting analysis"""
    character_level: int = Field(ge=1, le=45, description="Character level used for analysis")
    available_targets: list[MonsterTargetOption] = Field(
        default_factory=list,
        description="Available monster targets sorted by efficiency"
    )
    best_target: MonsterTargetOption | None = Field(
        default=None,
        description="Highest efficiency target, if any available"
    )

class LevelAppropriateTargeting:
    def find_optimal_monsters(
        self, 
        character_level: int, 
        current_position: tuple[int, int],
        monsters: list[GameMonster],
        maps: list[GameMap]
    ) -> MonsterTargetingResult:
        """Find monsters within character_level ± 1 with efficiency scoring.
        
        Uses real GameMonster data:
        - Filter by monster.level in [character_level-1, character_level+1]
        - Score by XP potential, gold rewards, and travel distance
        - Cross-reference with map data for locations
        
        Returns:
            MonsterTargetingResult with sorted target options
        """
        pass
```

### Modular Action System with Factory Patterns

Actions are enhanced with factory patterns and sub-goal request capabilities:

```python
# src/ai_player/actions/base_action.py
from abc import ABC, abstractmethod
from typing import Dict, Any
from pydantic import BaseModel, Field
from ..state.game_state import GameState

class ActionResult(BaseModel):
    """Pydantic model for action execution results"""
    success: bool = Field(description="Whether action executed successfully")
    message: str = Field(description="Human-readable result message")
    state_changes: Dict[GameState, Any] = Field(
        default_factory=dict,
        description="State changes resulting from action execution"
    )
    cooldown_seconds: int = Field(ge=0, default=0, description="Cooldown duration in seconds")

class BaseAction(ABC):
    """Abstract base class for all GOAP actions"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique action name"""
        pass
    
    @property
    @abstractmethod
    def cost(self) -> int:
        """GOAP cost for this action"""
        pass
    
    @abstractmethod
    def get_preconditions(self) -> Dict[GameState, Any]:
        """Required state conditions to execute this action using Pydantic-validated types"""
        pass
    
    @abstractmethod
    def get_effects(self) -> Dict[GameState, Any]:
        """State changes after successful execution using Pydantic-validated types"""
        pass
    
    @abstractmethod
    async def execute(self, character_name: str, current_state: CharacterGameState) -> ActionResult:
        """Execute the action via API call using Pydantic state model"""
        pass

# src/ai_player/actions/movement_action.py
class MovementAction(BaseAction):
    def __init__(self, target_x: int, target_y: int):
        self.target_x = target_x
        self.target_y = target_y
    
    @property
    def name(self) -> str:
        return f"move_to_{self.target_x}_{self.target_y}"
    
    @property
    def cost(self) -> int:
        return 1
    
    def get_preconditions(self) -> Dict[GameState, Any]:
        """Return preconditions for movement action"""
        return {
            GameState.COOLDOWN_READY: True,
            GameState.AT_TARGET_LOCATION: False
        }
    
    def get_effects(self) -> Dict[GameState, Any]:
        """Return effects of successful movement"""
        return {
            GameState.CURRENT_X: self.target_x,
            GameState.CURRENT_Y: self.target_y,
            GameState.AT_TARGET_LOCATION: True,
            GameState.COOLDOWN_READY: False
        }
    
    async def execute(self, character_name: str, current_state: CharacterGameState) -> ActionResult:
        """Execute movement action using Pydantic state model"""
        # Implementation using API client with type-safe state access
        pass
```

### Enhanced Goal Management with Recursive Sub-Goals

The system implements intelligent goal selection with data-driven analysis and recursive sub-goal support:

1. **Weighted Goal Selection**:
   - Multi-factor scoring (necessity, feasibility, progression, stability)
   - Real-time analysis using cached game data
   - Dynamic priority adjustment based on character state

2. **Goal Types**:
   - `CombatGoal`: Level-appropriate monster targeting for XP
   - `CraftingGoal`: Recipe analysis and material planning
   - `GatheringGoal`: Resource collection optimization
   - `EquipmentGoal`: Gear upgrade evaluation and acquisition
   - `MovementGoal`: Strategic movement and pathfinding
   - `RestGoal`: HP recovery with location intelligence

3. **Sub-Goal Architecture**:
   - Factory pattern for converting SubGoalRequest to Goal instances
   - Recursive execution with depth limits (max 10 levels)
   - Unified GOAP planning for both primary and sub-goals
   - State consistency validation during recursive execution

4. **Data-Driven Analysis**:
   - Level-appropriate monster filtering using real GameMonster data
   - Crafting recipe analysis with material dependency trees
   - Map analysis for optimal travel routes and resource locations
   - Equipment evaluation based on level requirements and stat benefits

### Enhanced Type-Safe State Management with Pydantic Models

The enhanced system uses Pydantic models for comprehensive type safety and validation:

```python
# src/ai_player/types/goap_models.py
class GOAPTargetState(BaseModel):
    """Type-safe replacement for dict[GameState, Any]"""
    target_states: dict[GameState, bool | int | float | str] = Field(
        default_factory=dict,
        description="Target state values indexed by GameState enum"
    )
    priority: int = Field(default=5, ge=1, le=10, description="Goal priority")
    timeout_seconds: int | None = Field(default=None, description="Max execution time")

class GOAPAction(BaseModel):
    """Type-safe replacement for dict-based action representation"""
    name: str = Field(description="Action name")
    action_type: str = Field(description="Action type for factory")
    parameters: dict[str, bool | int | float | str] = Field(
        default_factory=dict,
        description="Action parameters"
    )
    cost: int = Field(default=1, ge=0, description="GOAP cost")
    estimated_duration: float = Field(default=1.0, ge=0, description="Estimated seconds")
```

The GOAP planner uses a global GameState enum for type-safe state management:

```python
# src/ai_player/state/game_state.py
from enum import StrEnum
from typing import Dict, Any, Union

class GameState(StrEnum):
    """Global enum defining all possible game state keys.
    
    Using StrEnum ensures compatibility with GOAP library while providing
    type safety and IDE support for state names.
    """
    
    # Character progression states
    CHARACTER_NAME = "character_name"
    CHARACTER_LEVEL = "character_level"
    CHARACTER_XP = "character_xp"
    CHARACTER_GOLD = "character_gold"
    HP_CURRENT = "hp_current"
    HP_MAX = "hp_max"
    
    # Position and movement states
    CURRENT_X = "current_x"
    CURRENT_Y = "current_y"
    AT_TARGET_LOCATION = "at_target_location"
    AT_MONSTER_LOCATION = "at_monster_location"
    AT_RESOURCE_LOCATION = "at_resource_location"
    AT_NPC_LOCATION = "at_npc_location"
    AT_BANK_LOCATION = "at_bank_location"
    AT_GRAND_EXCHANGE = "at_grand_exchange"
    
    # Skill progression states
    MINING_LEVEL = "mining_level"
    WOODCUTTING_LEVEL = "woodcutting_level"
    FISHING_LEVEL = "fishing_level"
    WEAPONCRAFTING_LEVEL = "weaponcrafting_level"
    GEARCRAFTING_LEVEL = "gearcrafting_level"
    JEWELRYCRAFTING_LEVEL = "jewelrycrafting_level"
    COOKING_LEVEL = "cooking_level"
    ALCHEMY_LEVEL = "alchemy_level"
    
    # Equipment and inventory states
    WEAPON_EQUIPPED = "weapon_equipped"
    TOOL_EQUIPPED = "tool_equipped"
    INVENTORY_SPACE_AVAILABLE = "inventory_space_available"
    
    # Action availability states
    COOLDOWN_READY = "cooldown_ready"
    CAN_FIGHT = "can_fight"
    CAN_GATHER = "can_gather"
    CAN_CRAFT = "can_craft"
    
    @classmethod
    def validate_state_dict(cls, state_dict: Dict[str, Any]) -> Dict['GameState', Any]:
        """Validate and convert string keys to GameState enum values"""
        validated = {}
        for key, value in state_dict.items():
            try:
                enum_key = cls(key)
                validated[enum_key] = value
            except ValueError:
                raise ValueError(f"Invalid state key: {key}. Must be one of {list(cls)}")
        return validated
    
    @classmethod
    def to_goap_dict(cls, state_dict: Dict['GameState', Any]) -> Dict[str, Any]:
        """Convert enum-keyed state dict to string-keyed dict for GOAP
        
        Args:
            state_dict: Dictionary with GameState enum keys
            
        Returns:
            Dictionary with string keys for GOAP compatibility
        """
        validated_dict = {}
        for state, value in state_dict.items():
            if not isinstance(state, GameState):
                raise TypeError(f"All keys must be GameState enum values, got {type(state)}")
            validated_dict[state.value] = value
        return validated_dict

class CharacterGameState(BaseModel):
    """Enhanced Pydantic model for character state with comprehensive validation"""
    model_config = ConfigDict(validate_assignment=True, extra='forbid')
    
    # Character progression
    name: str = Field(description="Character name")
    level: int = Field(ge=1, le=45, description="Character level")
    xp: int = Field(ge=0, description="Experience points")
    max_xp: int = Field(ge=0, description="XP required for next level")
    gold: int = Field(ge=0, description="Gold amount")
    
    # Health and position
    hp: int = Field(ge=0, description="Current HP")
    max_hp: int = Field(ge=1, description="Maximum HP")
    x: int = Field(description="X coordinate")
    y: int = Field(description="Y coordinate")
    
    # Skill levels with validation
    mining_level: int = Field(ge=1, le=45, description="Mining skill level")
    woodcutting_level: int = Field(ge=1, le=45, description="Woodcutting skill level")
    fishing_level: int = Field(ge=1, le=45, description="Fishing skill level")
    weaponcrafting_level: int = Field(ge=1, le=45, description="Weaponcrafting skill level")
    gearcrafting_level: int = Field(ge=1, le=45, description="Gearcrafting skill level")
    jewelrycrafting_level: int = Field(ge=1, le=45, description="Jewelrycrafting skill level")
    cooking_level: int = Field(ge=1, le=45, description="Cooking skill level")
    alchemy_level: int = Field(ge=1, le=45, description="Alchemy skill level")
    
    def to_goap_state(self) -> Dict[str, Any]:
        """Convert to GOAP state dictionary with GameState enum validation
        
        Returns:
            Dictionary with string keys and validated values for GOAP planning
        """
        raw_dict = self.model_dump()
        goap_state = {}
        
        # Map character state fields to GameState enum values
        field_mapping = {
            'name': GameState.CHARACTER_NAME,
            'level': GameState.CHARACTER_LEVEL,
            'xp': GameState.CHARACTER_XP,
            'gold': GameState.CHARACTER_GOLD,
            'hp': GameState.HP_CURRENT,
            'max_hp': GameState.HP_MAX,
            'x': GameState.CURRENT_X,
            'y': GameState.CURRENT_Y,
            'mining_level': GameState.MINING_LEVEL,
            'woodcutting_level': GameState.WOODCUTTING_LEVEL,
            'fishing_level': GameState.FISHING_LEVEL,
            'weaponcrafting_level': GameState.WEAPONCRAFTING_LEVEL,
            'gearcrafting_level': GameState.GEARCRAFTING_LEVEL,
            'jewelrycrafting_level': GameState.JEWELRYCRAFTING_LEVEL,
            'cooking_level': GameState.COOKING_LEVEL,
            'alchemy_level': GameState.ALCHEMY_LEVEL
        }
        
        for field_name, game_state in field_mapping.items():
            if field_name in raw_dict:
                value = raw_dict[field_name]
                # Convert booleans to integers for GOAP compatibility
                goap_state[game_state.value] = int(value) if isinstance(value, bool) else value
        
        return goap_state
    
    @classmethod
    def from_api_character(cls, character: 'CharacterSchema') -> 'CharacterGameState':
        """Create from API character response with enhanced validation"""
        return cls(
            name=character.name,
            level=character.level,
            xp=character.xp,
            max_xp=character.max_xp,
            gold=character.gold,
            hp=character.hp,
            max_hp=character.max_hp,
            x=character.x,
            y=character.y,
            mining_level=character.mining_level,
            woodcutting_level=character.woodcutting_level,
            fishing_level=character.fishing_level,
            weaponcrafting_level=character.weaponcrafting_level,
            gearcrafting_level=character.gearcrafting_level,
            jewelrycrafting_level=character.jewelrycrafting_level,
            cooking_level=character.cooking_level,
            alchemy_level=character.alchemy_level
        )
```

## Sub-Goal Architecture

### Unified Sub-Goal Factory Pattern

The system implements a clean, unified architecture for sub-goal integration that eliminates converters and ensures the entire system uses the same facilities:

```python
# src/ai_player/goals/sub_goal_request.py
class SubGoalRequest(BaseModel):
    """Pydantic model for sub-goal requests with factory integration"""
    goal_type: str = Field(description="Type of sub-goal to create")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Sub-goal parameters")
    priority: int = Field(default=5, ge=1, le=10, description="Urgency level")
    requester: str = Field(description="Action/goal that requested this sub-goal")

# src/ai_player/goal_manager.py
class GoalManager:
    def create_goal_from_sub_request(
        self, 
        sub_goal_request: SubGoalRequest, 
        context: GoalFactoryContext
    ) -> BaseGoal:
        """Factory method to convert SubGoalRequest to appropriate Goal instance.
        
        No converters needed - SubGoalRequest becomes Goal instances directly.
        Sub-goals use identical interfaces as regular goals.
        """
        if context.recursion_depth >= context.max_depth:
            raise MaxDepthExceededError(context.max_depth)
        
        if sub_goal_request.goal_type == "move_to_location":
            return MovementGoal(
                target_x=sub_goal_request.parameters["target_x"],
                target_y=sub_goal_request.parameters["target_y"]
            )
        elif sub_goal_request.goal_type == "reach_hp_threshold":
            return RestGoal(
                min_hp_percentage=sub_goal_request.parameters["min_hp_percentage"]
            )
        # Additional sub-goal types...
```

### Recursive Execution with Depth Limits

The ActionExecutor handles sub-goals with depth-limited recursion and state consistency validation:

```python
# src/ai_player/action_executor.py
class ActionExecutor:
    async def execute_action_with_subgoals(
        self, 
        action: BaseAction, 
        character_name: str, 
        current_state: CharacterGameState, 
        depth: int = 0
    ) -> ActionResult:
        """Execute action with recursive sub-goal handling."""
        
        # Depth limit protection
        if depth > self.max_subgoal_depth:
            raise MaxDepthExceededError(self.max_subgoal_depth)
        
        # Execute action using existing logic
        result = await self.execute_action(action, character_name, current_state)
        
        # Handle sub-goal requests recursively
        if not result.success and result.sub_goal_requests:
            for sub_goal_request in result.sub_goal_requests:
                # Use GoalManager factory to create Goal instance
                sub_goal = self.goal_manager.create_goal_from_sub_request(
                    sub_goal_request, context
                )
                
                # Get target state using same facility as regular goals
                target_state = sub_goal.get_target_state(context.character_state, context.game_data)
                
                # Use GOAP planning (same facility as regular goals)
                sub_plan = await self.goal_manager.plan_to_target_state(
                    context.character_state, target_state
                )
                
                # Execute sub-plan recursively
                if sub_plan.actions:
                    sub_result = await self.execute_plan_recursive(
                        sub_plan, character_name, depth + 1
                    )
                    
                    if sub_result.success:
                        # Refresh state and retry parent action
                        refreshed_state = await self.state_manager.refresh_state_for_parent_action(depth)
                        return await self.execute_action_with_subgoals(
                            action, character_name, refreshed_state, depth
                        )
        
        return result
```

## Strategic Analysis Modules

### Level-Appropriate Monster Targeting

The system includes intelligent monster selection based on character level and game data:

```python
# src/ai_player/analysis/level_targeting.py
class LevelAppropriateTargeting:
    def find_optimal_monsters(
        self, 
        character_level: int, 
        current_position: tuple[int, int],
        monsters: list[GameMonster],
        maps: list[GameMap]
    ) -> list[tuple[GameMonster, GameMap, float]]:
        """Find monsters within character_level ± 1 with efficiency scoring.
        
        Uses real GameMonster data:
        - Filter by monster.level in [character_level-1, character_level+1]
        - Score by XP potential, gold rewards, and travel distance
        - Cross-reference with map data for locations
        """
        # Filter level-appropriate monsters from real data
        appropriate_monsters = [
            monster for monster in monsters 
            if character_level - 1 <= monster.level <= character_level + 1
        ]
        
        # Find locations and calculate efficiency scores
        monster_locations = []
        for monster in appropriate_monsters:
            locations = [
                game_map for game_map in maps 
                if (game_map.content and 
                    game_map.content.type == "monster" and 
                    game_map.content.code == monster.code)
            ]
            
            for location in locations:
                distance = abs(location.x - current_position[0]) + abs(location.y - current_position[1])
                xp_potential = monster.level * 10
                gold_potential = (monster.min_gold + monster.max_gold) / 2
                efficiency = (xp_potential + gold_potential) / max(1, distance)
                
                monster_locations.append((monster, location, efficiency))
        
        return sorted(monster_locations, key=lambda x: x[2], reverse=True)
```

### Crafting Analysis Module

Intelligent crafting analysis using real game data:

```python
# src/ai_player/analysis/crafting_analysis.py
class CraftingAnalysisModule:
    def analyze_recipe(
        self, 
        recipe_code: str, 
        items: list[GameItem],
        character_state: CharacterGameState
    ) -> CraftingAnalysis:
        """Analyze crafting recipe using real GameItem.craft data."""
        
        # Find item using real data - NO hardcoding
        target_item = next((item for item in items if item.code == recipe_code), None)
        if not target_item or not target_item.craft:
            return CraftingAnalysis(feasible=False, reason="No recipe found")
        
        # Parse real crafting requirements
        craft_data = target_item.craft
        required_materials = craft_data.get('materials', [])
        required_skill_level = craft_data.get('level', 1)
        skill_name = craft_data.get('skill', 'crafting')
        
        # Check character skill level using Pydantic model field mapping
        skill_level_mapping = {
            'mining': character_state.mining_level,
            'woodcutting': character_state.woodcutting_level,
            'fishing': character_state.fishing_level,
            'weaponcrafting': character_state.weaponcrafting_level,
            'gearcrafting': character_state.gearcrafting_level,
            'jewelrycrafting': character_state.jewelrycrafting_level,
            'cooking': character_state.cooking_level,
            'alchemy': character_state.alchemy_level
        }
        
        if skill_name not in skill_level_mapping:
            return CraftingAnalysis(
                feasible=False,
                reason=f"Unknown skill: {skill_name}"
            )
        
        character_skill_level = skill_level_mapping[skill_name]
        
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
```

### Map Analysis Module

Location finding and travel optimization:

```python
# src/ai_player/analysis/map_analysis.py
class MapAnalysisModule:
class MapLocationOption(BaseModel):
    """Pydantic model for map location analysis results"""
    map_location: GameMap = Field(description="Map location data")
    distance: float = Field(ge=0.0, description="Manhattan distance to location")
    content_level: int | None = Field(default=None, description="Content level if applicable")

class MapSearchResult(BaseModel):
    """Pydantic model for map search results"""
    content_type: str = Field(description="Type of content searched for")
    search_position: tuple[int, int] = Field(description="Position used as search origin")
    matching_locations: list[MapLocationOption] = Field(
        default_factory=list,
        description="Found locations sorted by distance"
    )
    nearest_location: MapLocationOption | None = Field(
        default=None,
        description="Closest matching location, if any found"
    )

class MapAnalysisModule:
    def find_nearest_content(
        self,
        current_pos: tuple[int, int],
        content_type: str,
        maps: list[GameMap],
        level_filter: int | None = None
    ) -> MapSearchResult:
        """Find nearest locations with specified content type.
        
        Returns: MapSearchResult with sorted location options
        """
        matching_maps = []
        for game_map in maps:
            if game_map.content and game_map.content.type == content_type:
                # Apply level filter if specified
                if level_filter is not None:
                    # Cross-reference with actual content data for level filtering
                    # Implementation depends on content type (monster, resource, etc.)
                    pass
                
                distance = abs(game_map.x - current_pos[0]) + abs(game_map.y - current_pos[1])
                matching_maps.append((game_map, distance))
        
        return sorted(matching_maps, key=lambda x: x[1])
```

## Exception Handling for Sub-Goal Architecture

Custom exceptions for robust error handling:

```python
# src/ai_player/exceptions.py
class SubGoalExecutionError(Exception):
    """Raised when sub-goal execution fails"""
    def __init__(self, depth: int, sub_goal_type: str, message: str):
        self.depth = depth
        self.sub_goal_type = sub_goal_type
        super().__init__(f"Sub-goal '{sub_goal_type}' failed at depth {depth}: {message}")

class MaxDepthExceededError(SubGoalExecutionError):
    """Raised when max recursion depth is exceeded"""
    def __init__(self, max_depth: int):
        super().__init__(max_depth, "depth_limit", f"Maximum recursion depth {max_depth} exceeded")

class StateConsistencyError(Exception):
    """Raised when state consistency validation fails during recursive execution"""
    def __init__(self, depth: int, message: str):
        self.depth = depth
        super().__init__(f"State consistency error at depth {depth}: {message}")
```

## API Integration Strategy

### API Client Wrapper

The system wraps the generated API client to provide:

1. **Authentication Management**: Token-based auth using the TOKEN file
2. **Error Handling**: Robust retry logic and error recovery
3. **Rate Limiting**: Respect API rate limits and cooldowns
4. **Response Processing**: Extract game state from API responses

## Model Boundary Enforcement

### Critical Architectural Rule: API Model Containment

The architecture enforces a strict boundary between external API client models and internal Pydantic models to maintain clean separation of concerns and prevent coupling.

```
┌─────────────────────────────────────────────────────────────────┐
│                     APPLICATION LAYERS                         │
│                  (Internal Pydantic Models ONLY)               │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ AI Player  │  │ CLI Layer   │  │    State Management     │  │
│  │    Core     │  │             │  │     Goal Planning       │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                    TRANSFORMATION BOUNDARY                     │
│              ⚠️  NO API CLIENT MODELS BEYOND THIS POINT ⚠️      │
├─────────────────────────────────────────────────────────────────┤
│                 API INTEGRATION LAYER                          │
│                                                                 │
│  ┌─────────────────────┐    ┌─────────────────────────────────┐ │
│  │   API Client        │    │       Cache Manager            │ │
│  │   Wrapper           │───▶│   (Receives Pydantic Only)     │ │
│  │ (Transforms Models) │    │                                │ │
│  └─────────────────────┘    └─────────────────────────────────┘ │
│              │                                                  │
│              ▼                                                  │
│  ┌─────────────────────┐                                       │
│  │ Generated API Client│                                       │
│  │ (External Models)   │                                       │
│  └─────────────────────┘                                       │
└─────────────────────────────────────────────────────────────────┘
```

### Model Transformation Rules

#### API Client Layer (`src/game_data/api_client.py`)
- **Input**: Raw API responses using generated client models (`ItemSchema`, `CharacterSchema`, etc.)
- **Output**: Internal Pydantic models exclusively (`GameItem`, `CharacterGameState`, etc.)
- **Responsibility**: Immediate transformation of all API responses to internal models
- **Enforcement**: NO API client models may escape this layer

#### All Other Layers
- **Models**: Internal Pydantic models exclusively
- **Serialization**: Use `model_dump()` method only
- **Data Flow**: Only receive pre-transformed Pydantic models
- **Enforcement**: API client models are FORBIDDEN beyond `api_client.py`

#### Benefits of Boundary Enforcement
1. **Decoupling**: Application logic independent of API client changes
2. **Type Safety**: Consistent Pydantic validation throughout application
3. **Maintainability**: Single transformation point for API model changes
4. **Testing**: Simplified mocking with uniform model types
5. **Serialization**: Unified `model_dump()` usage eliminates polymorphic patterns

#### Implementation Pattern
```python
# ✅ CORRECT: API Client Wrapper transforms immediately
class APIClientWrapper:
    async def get_character(self, name: str) -> CharacterGameState:
        api_response = await self._client.get_character(name)  # Returns CharacterSchema
        return CharacterGameState.from_api_character(api_response)  # Transform to Pydantic
    
    async def get_all_items(self) -> list[GameItem]:
        api_response = await self._client.get_all_items()  # Returns list[ItemSchema]
        return [GameItem.from_api_item(item) for item in api_response]  # Transform to Pydantic

# ❌ INCORRECT: Passing API models to other layers
class CacheManager:
    def save_data(self, items: list[ItemSchema]):  # API model leaked!
        # This violates boundary enforcement
```

### Cooldown Management

Critical for game compliance and efficiency using Pydantic for data validation:

```python
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from typing import Dict, Optional
import asyncio

class CooldownInfo(BaseModel):
    """Pydantic model for cooldown information"""
    character_name: str
    expiration: datetime
    total_seconds: int = Field(ge=0)
    remaining_seconds: int = Field(ge=0)
    reason: str  # Action type that caused cooldown
    
    @property
    def is_ready(self) -> bool:
        """Check if cooldown has expired"""
        return datetime.now() >= self.expiration
    
    @property
    def time_remaining(self) -> float:
        """Get remaining cooldown time in seconds"""
        if self.is_ready:
            return 0.0
        return (self.expiration - datetime.now()).total_seconds()

class CooldownManager:
    """Manages character cooldowns with Pydantic validation"""
    
    def __init__(self):
        self.character_cooldowns: Dict[str, CooldownInfo] = {}
    
    def update_cooldown(self, character_name: str, cooldown_data: 'CooldownSchema') -> None:
        """Update cooldown from API response"""
        cooldown_info = CooldownInfo(
            character_name=character_name,
            expiration=cooldown_data.expiration,
            total_seconds=cooldown_data.total_seconds,
            remaining_seconds=cooldown_data.remaining_seconds,
            reason=cooldown_data.reason.value
        )
        self.character_cooldowns[character_name] = cooldown_info
    
    def is_ready(self, character_name: str) -> bool:
        """Check if character can perform actions"""
        if character_name not in self.character_cooldowns:
            return True
        return self.character_cooldowns[character_name].is_ready
    
    async def wait_for_cooldown(self, character_name: str) -> None:
        """Async wait until cooldown expires"""
        if not self.is_ready(character_name):
            cooldown = self.character_cooldowns[character_name]
            wait_time = cooldown.time_remaining
            self.logger.info(f"Waiting {wait_time:.1f}s for {cooldown.reason} cooldown")
            await asyncio.sleep(wait_time)
```

### Game State Synchronization

The AI player maintains authoritative game state by:

1. **API Response Processing**: Extract state from every API response
2. **Periodic State Refresh**: Fetch current character state regularly
3. **State Validation**: Verify local state matches API state
4. **Error Recovery**: Re-sync state after errors

## Logging Architecture

### Structured Logging Levels

- **DEBUG**: Detailed GOAP planning steps, API request/response details
- **INFO**: Character actions, goal transitions, significant events
- **WARNING**: Recoverable errors, unexpected conditions
- **ERROR**: Unrecoverable errors, system failures

### Log Message Format

```python
# Example log messages
logger.info("Character %s: Moving from (%d,%d) to (%d,%d)", char_name, old_x, old_y, new_x, new_y)
logger.debug("GOAP: Planning path from state %s to goal %s", current_state, goal_state) 
logger.warning("API rate limit hit, waiting %d seconds", wait_time)
logger.error("Failed to execute action %s: %s", action_name, error_msg)
```

### Log Aggregation

Logs are structured to support analysis and debugging:
- Action success/failure rates
- Goal completion times
- API response times
- Character progression metrics

## Implementation Roadmap

### Phase 1: Core Infrastructure
1. CLI interface with character management
2. API client wrapper with authentication
3. Basic GOAP action definitions
4. Game state management foundation

### Phase 2: Basic AI Player
1. Movement and exploration actions
2. Simple combat system
3. Resource gathering implementation
4. Cooldown handling

### Phase 3: Advanced Planning
1. Multi-step goal planning
2. Economic decision making
3. Equipment optimization
4. Skill progression strategies

### Phase 4: Optimization
1. Performance monitoring
2. Learning from gameplay patterns
3. Advanced goal prioritization
4. Multi-character coordination

## Configuration Management

### Enhanced AI Behavior Configuration (`config/ai_player.yaml`)

```yaml
# Enhanced Goal System Configuration
goals:
  # Weighted Goal Selection Factors
  weight_factors:
    necessity: 0.4     # Required for progression (HP critical, missing gear)
    feasibility: 0.3   # Can be accomplished with current resources
    progression: 0.2   # Contributes to reaching level 5 with appropriate gear
    stability: 0.1     # Reduces error potential and maintains steady progress
  
  # Goal Type Priorities
  type_priorities:
    combat: 9          # Level-appropriate monster targeting
    equipment: 8       # Gear upgrade evaluation
    rest: 10           # HP recovery (highest priority when needed)
    crafting: 7        # Recipe analysis and material planning
    gathering: 6       # Resource collection optimization
    movement: 5        # Strategic movement planning

# Sub-Goal Architecture Configuration
planning:
  max_subgoal_depth: 10           # Maximum recursive sub-goal depth
  enable_recursive_subgoals: true # Enable recursive sub-goal execution
  subgoal_timeout_seconds: 300    # Timeout for sub-goal execution
  replan_interval: 300            # seconds
  emergency_replan_triggers:
    - low_hp
    - unexpected_location
    - api_error
    - max_depth_exceeded

# Strategic Analysis Configuration
analysis:
  level_targeting:
    level_range: 1            # ±1 level for monster targeting
    efficiency_weight_xp: 0.6 # Weight for XP potential in efficiency calculation
    efficiency_weight_gold: 0.2 # Weight for gold potential
    efficiency_weight_distance: 0.2 # Weight for travel distance (inverted)
  
  crafting:
    max_material_depth: 5     # Maximum dependency tree depth for materials
    prioritize_xp_gain: true  # Prioritize recipes that give XP
    min_success_rate: 0.8     # Minimum success rate for crafting attempts
  
  equipment:
    max_level_filter: 5       # Only consider equipment with level <= 5
    stat_weight_damage: 0.4   # Weight for damage stats in evaluation
    stat_weight_defense: 0.3  # Weight for defense stats
    stat_weight_utility: 0.3  # Weight for utility stats (HP, etc.)

# Enhanced Action Configuration
actions:
  movement:
    pathfinding_algorithm: "manhattan"  # Manhattan distance for efficiency
    avoid_higher_level_monsters: true
    max_travel_distance: 20   # Maximum single-move distance
  
  combat:
    min_hp_percentage: 0.3
    preferred_level_range: [-1, +1]  # Character level ±1
    retreat_hp_threshold: 0.2 # HP threshold to trigger retreat
    max_combat_duration: 60   # Maximum seconds per combat
  
  gathering:
    prioritize_by_level: true # Prioritize resources appropriate for character level
    min_efficiency_score: 0.5 # Minimum efficiency to attempt gathering
  
  rest:
    preferred_rest_locations: # Preferred locations for resting (safer areas)
      - "bank"
      - "safe_zone"
    hp_recovery_threshold: 0.8 # HP percentage to stop resting

# Diagnostics and Monitoring
diagnostics:
  track_subgoal_depth: true    # Track recursive execution depth
  log_subgoal_chains: true     # Log sub-goal execution chains
  log_analysis_decisions: true # Log analysis module decisions
  performance_monitoring: true # Monitor goal selection performance
```

### GOAP Weights Configuration (`config/goap_weights.yaml`)

```yaml
action_costs:
  move_to_location: 1
  fight_monster: 3
  gather_resource: 2
  craft_item: 4
  rest_at_location: 1
  buy_from_npc: 2
  sell_to_npc: 2
  deposit_bank: 1
  withdraw_bank: 1
  equip_item: 1
  use_item: 2

goal_weights:
  reach_level: 100
  gather_resources: 50
  craft_equipment: 75
  complete_task: 80
  accumulate_gold: 30
```

## Development Environment

### Dependency Management with uv
```bash
# Project setup with uv (manages both dependencies and virtualenv)
uv sync                          # Install dependencies and create/activate venv
uv add pydantic                  # Add runtime dependency
uv add --dev pytest pytest-asyncio  # Add development dependency
uv run python -m src.cli.main   # Run commands in managed environment
uv run pytest                   # Run tests in managed environment
uv run mypy src/                 # Type checking in managed environment
```

### Required Dependencies
```toml
# pyproject.toml updates for Pydantic
[project]
dependencies = [
    "artifactsmmo-api-client",
    "pydantic>=2.5.0",
    "pydantic-settings",
    "httpx",
    "PyYAML",
]

[project.optional-dependencies]
dev = [
    "mypy",
    "pytest", 
    "pytest-asyncio",
    "pytest-cov",
    "ruff",
]
```

## Testing Strategy

### Unit Tests with Pydantic Validation
- GOAP action execution with type safety
- Pydantic model validation and serialization
- API client wrapper methods with proper error handling
- Configuration loading with Pydantic Settings

### Integration Tests  
- End-to-end character workflows with real API calls
- API error handling scenarios using custom HTTP status codes
- State synchronization verification with Pydantic models
- uv-managed test environment consistency

### Performance Tests
- Planning algorithm efficiency with large state spaces
- Memory usage under long runs with proper cleanup
- API rate limit handling with exponential backoff
- Cache effectiveness using YAML persistence

## Security Considerations

1. **Token Management**: Secure storage and handling of authentication tokens
2. **API Rate Limiting**: Respect game server limitations to avoid bans
3. **Error Handling**: Graceful degradation without exposing sensitive data
4. **Logging**: Avoid logging sensitive information like tokens or passwords

## Monitoring and Observability

### Metrics Collection
- Character progression rates
- Action success/failure ratios
- API response times
- Planning algorithm performance
- Goal completion statistics

### Health Checks
- API connectivity status
- Character state consistency
- Planning system responsiveness
- Cache data freshness

This architecture provides a robust foundation for an intelligent ArtifactsMMO AI player that can autonomously progress characters to maximum level while maintaining compliance with game mechanics and API constraints.