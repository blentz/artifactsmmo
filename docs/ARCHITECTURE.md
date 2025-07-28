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
**Purpose**: Intelligent game automation using GOAP

**Key Modules**:
- `ai_player.py` - Main AI player orchestrator
- `actions/` - Modular GOAP action system (one action per file)
  - `base_action.py` - Abstract base class for all actions
  - `movement_action.py` - Movement and pathfinding
  - `combat_action.py` - Monster fighting mechanics
  - `gathering_action.py` - Resource collection
  - `crafting_action.py` - Item creation
  - `rest_action.py` - HP recovery
  - `trading_action.py` - NPC interactions
- `state/` - State management with type safety
  - `game_state.py` - GameState enum definitions
  - `state_manager.py` - Game state tracking and synchronization
- `action_executor.py` - API action execution with cooldown handling
- `goal_manager.py` - Dynamic goal selection based on character state
- `diagnostics/` - CLI diagnostic commands for troubleshooting
  - `state_diagnostics.py` - State inspection and validation
  - `action_diagnostics.py` - Action precondition/effect analysis
  - `planning_diagnostics.py` - GOAP planning visualization

**GOAP Integration**:
- Uses existing `src/lib/goap.py` for planning algorithms
- Modular action system with registry-based discovery
- Type-safe state management using GameState enum
- Maps GOAP actions to API client calls through action modules
- Handles preconditions and effects via standardized action interface

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

## GOAP System Integration

### Modular Action System

The AI player uses a modular action system where each action is defined in its own file:

```python
# src/ai_player/actions/base_action.py
from abc import ABC, abstractmethod
from typing import Dict, Any
from pydantic import BaseModel
from ..state.game_state import GameState

class ActionResult(BaseModel):
    success: bool
    message: str
    state_changes: Dict[GameState, Any]
    cooldown_seconds: int = 0

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
        """Required state conditions to execute this action"""
        pass
    
    @abstractmethod
    def get_effects(self) -> Dict[GameState, Any]:
        """State changes after successful execution"""
        pass
    
    @abstractmethod
    async def execute(self, character_name: str, current_state: Dict[GameState, Any]) -> ActionResult:
        """Execute the action via API call"""
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
        return {
            GameState.COOLDOWN_READY: True,
            GameState.AT_TARGET_LOCATION: False
        }
    
    def get_effects(self) -> Dict[GameState, Any]:
        return {
            GameState.CURRENT_X: self.target_x,
            GameState.CURRENT_Y: self.target_y,
            GameState.AT_TARGET_LOCATION: True,
            GameState.COOLDOWN_READY: False
        }
    
    async def execute(self, character_name: str, current_state: Dict[GameState, Any]) -> ActionResult:
        # Implementation using API client
        pass
```

### Goal Management

The system implements dynamic goal selection based on character progression:

1. **Early Game Goals** (Levels 1-10):
   - Gather basic resources
   - Craft starting equipment
   - Complete beginner tasks

2. **Mid Game Goals** (Levels 11-30):
   - Optimize skill progression
   - Economic activities (Grand Exchange)
   - Equipment upgrades

3. **Late Game Goals** (Levels 31-45):
   - Maximum level achievement
   - Rare item collection
   - Advanced crafting mastery

### Type-Safe State Management

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
        """Convert enum-keyed state dict to string-keyed dict for GOAP"""
        return {state.value: value for state, value in state_dict.items()}

class CharacterGameState(BaseModel):
    """Pydantic model for character state using GameState enum keys"""
    model_config = ConfigDict(validate_assignment=True, extra='forbid')
    
    def to_goap_state(self) -> Dict[str, Any]:
        """Convert to GOAP state dictionary using enum values"""
        raw_dict = self.model_dump()
        return {GameState(k).value: (int(v) if isinstance(v, bool) else v) 
                for k, v in raw_dict.items() if k in GameState}
    
    @classmethod
    def from_api_character(cls, character: 'CharacterSchema') -> 'CharacterGameState':
        """Create from API character response with validated state mapping"""
        return cls(**{
            GameState.CHARACTER_LEVEL.value: character.level,
            GameState.CHARACTER_XP.value: character.xp,
            GameState.CHARACTER_GOLD.value: character.gold,
            GameState.HP_CURRENT.value: character.hp,
            GameState.HP_MAX.value: character.max_hp,
            GameState.CURRENT_X.value: character.x,
            GameState.CURRENT_Y.value: character.y,
            GameState.MINING_LEVEL.value: character.mining_level,
            GameState.WOODCUTTING_LEVEL.value: character.woodcutting_level,
            GameState.FISHING_LEVEL.value: character.fishing_level,
            GameState.WEAPONCRAFTING_LEVEL.value: character.weaponcrafting_level,
            GameState.GEARCRAFTING_LEVEL.value: character.gearcrafting_level,
            GameState.JEWELRYCRAFTING_LEVEL.value: character.jewelrycrafting_level,
            GameState.COOKING_LEVEL.value: character.cooking_level,
            GameState.ALCHEMY_LEVEL.value: character.alchemy_level,
            GameState.INVENTORY_SPACE_AVAILABLE.value: character.inventory_max_items - len(character.inventory or []),
            GameState.COOLDOWN_READY.value: character.cooldown == 0,
            GameState.WEAPON_EQUIPPED.value: bool(character.weapon_slot),
            GameState.TOOL_EQUIPPED.value: bool(character.weapon_slot)
        })
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

### AI Behavior Configuration (`config/ai_player.yaml`)

```yaml
goals:
  priority_levels:
    survival: 10      # HP management, rest
    progression: 8    # XP and level advancement
    economic: 6       # Gold and trading
    exploration: 4    # Map discovery
    collection: 2     # Item gathering

planning:
  max_plan_depth: 10
  replan_interval: 300  # seconds
  emergency_replan_triggers:
    - low_hp
    - unexpected_location
    - api_error

actions:
  movement:
    pathfinding_algorithm: "a_star"
    avoid_monsters: true
  combat:
    min_hp_percentage: 0.3
    preferred_combat_level_range: [-2, +1]
  gathering:
    resource_priority:
      - "copper_ore"
      - "ash_wood" 
      - "gudgeon"
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