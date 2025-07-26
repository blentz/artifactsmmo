# ArtifactsMMO AI Player Implementation PRP

**Authors**: Requirements Analyst, System Architect  
**Using**: @sentient-agi-reasoning for enhanced reasoning  
**Target**: Complete AI Player application with CLI interface

## Goal
Build a comprehensive AI Player application that uses GOAP (Goal-Oriented Action Planning) to autonomously play ArtifactsMMO through the game's API. The system must intelligently progress characters from level 1 to maximum level while respecting all API constraints and cooldowns.

## Why
- **Business Value**: Demonstrates advanced AI game-playing capabilities and GOAP implementation
- **Integration**: Leverages existing GOAP library (`src/lib/goap.py`) and API client infrastructure  
- **Problems Solved**: Autonomous gameplay, intelligent decision-making, API rate limit compliance
- **Target Users**: Developers interested in AI gaming applications and GOAP implementations

## What
A CLI-controlled AI player that can create, manage, and autonomously operate characters in ArtifactsMMO until they reach maximum level, with comprehensive logging and caching systems.

### Success Criteria
- [ ] CLI can create, delete, and list characters via ArtifactsMMO API
- [ ] AI player can autonomously play from level 1 to maximum level (45)
- [ ] System respects all API cooldowns and rate limits
- [ ] Structured logging with configurable granularity levels
- [ ] Game data cached in YAML format using existing `yaml_data.py`
- [ ] Configuration data stored in YAML format in `config/` directory
- [ ] All actions use API as source of truth - no hardcoded game data
- [ ] Comprehensive test coverage with functional validation
- [ ] Full type safety with mypy strict mode compliance

## All Needed Context

### Documentation & References
```yaml
# MUST READ - Include these in your context window

- url: https://docs.artifactsmmo.com/
  why: Core game mechanics, API overview, rate limits, authentication
  critical: Every action corresponds to API endpoint, 45 level progression system

- url: https://api.artifactsmmo.com/docs/#/
  why: Complete OpenAPI specification, endpoint details, request/response schemas
  critical: Authentication patterns, cooldown handling, error codes

- file: src/lib/goap.py
  why: Existing GOAP implementation - World, Planner, Action_List classes
  critical: Uses A* pathfinding, state-based planning, action costs/effects

- file: src/lib/yaml_data.py
  why: YAML data persistence pattern - YamlData class implementation
  critical: Auto-creates files, handles loading/saving, debug logging

- file: src/lib/log.py
  why: Async logging pattern with QueueHandler/QueueListener
  critical: Must use async init_logger(), queue-based for performance

- file: src/lib/httpstatus.py
  why: Custom HTTP status codes for ArtifactsMMO API errors
  critical: Character cooldown (499), inventory full (497), etc.

- file: artifactsmmo-api-client/artifactsmmo_api_client/
  why: Generated API client with all endpoints and models
  critical: Uses attrs for data classes, httpx for HTTP, type annotations

- file: pyproject.toml
  why: Project configuration, dependencies, tool settings
  critical: Python 3.13, strict mypy, ruff linting, pytest setup

- file: docs/ARCHITECTURE.md
  why: Complete system architecture and component design
  critical: GOAP integration patterns, data flow, module structure

- docfile: claude_files/personas/requirements-analyst.md
  why: Requirements analysis approach and validation techniques

- docfile: claude_files/personas/system-architect.md  
  why: System design principles and architectural decisions
```

### Current Codebase Structure
```bash
artifactsmmo/
├── src/
│   └── lib/
│       ├── __init__.py
│       ├── goap.py              # GOAP implementation (World, Planner, Action_List)
│       ├── yaml_data.py         # YAML persistence (YamlData class)
│       ├── log.py               # Async logging setup
│       ├── httpstatus.py        # Custom HTTP status codes
│       ├── request_throttle.py  # Rate limiting utilities
│       └── throttled_transport.py
├── artifactsmmo-api-client/     # Generated API client
├── TOKEN                        # Authentication token file
├── pyproject.toml              # Python 3.13, mypy strict, ruff
├── tests/                      # Empty - need to establish patterns
└── docs/
    └── ARCHITECTURE.md         # Complete system design
```

### Desired Codebase Structure with Modular Design
```bash
artifactsmmo/
├── src/
│   ├── lib/                    # Existing utilities
│   │   ├── __init__.py
│   │   ├── goap.py            # GOAP planning algorithms
│   │   ├── yaml_data.py       # YAML persistence
│   │   ├── log.py             # Async logging
│   │   └── httpstatus.py      # Custom HTTP status codes
│   ├── cli/                    # Modular CLI interface
│   │   ├── __init__.py
│   │   ├── main.py            # Entry point with argument parsing
│   │   └── commands/          # Command implementations
│   │       ├── __init__.py
│   │       ├── character.py   # Character CRUD operations
│   │       ├── ai_player.py   # AI player control
│   │       └── diagnostics.py # GOAP planning diagnostics
│   ├── ai_player/             # Core AI player logic
│   │   ├── __init__.py
│   │   ├── ai_player.py       # Main AI orchestrator
│   │   ├── actions/           # Modular action system (one per file)
│   │   │   ├── __init__.py    # Action registry and discovery
│   │   │   ├── base_action.py # Abstract base class
│   │   │   ├── movement_action.py    # Movement and pathfinding
│   │   │   ├── combat_action.py      # Monster fighting
│   │   │   ├── gathering_action.py   # Resource collection
│   │   │   ├── crafting_action.py    # Item creation
│   │   │   ├── rest_action.py        # HP recovery
│   │   │   └── trading_action.py     # NPC interactions
│   │   ├── state/             # Type-safe state management
│   │   │   ├── __init__.py
│   │   │   ├── game_state.py  # GameState enum definitions
│   │   │   └── state_manager.py # State synchronization
│   │   ├── diagnostics/       # CLI diagnostic support
│   │   │   ├── __init__.py
│   │   │   ├── state_diagnostics.py   # State inspection
│   │   │   ├── action_diagnostics.py  # Action analysis
│   │   │   └── planning_diagnostics.py # GOAP visualization
│   │   ├── action_executor.py # API action execution
│   │   ├── goal_manager.py    # Dynamic goal selection
│   │   └── cooldown_manager.py # Cooldown tracking
│   └── game_data/             # API integration
│       ├── __init__.py
│       ├── api_client.py      # API client wrapper
│       ├── game_state.py      # Game state repository
│       └── cache_manager.py   # Game data caching
├── config/                    # YAML configuration
│   ├── ai_player.yaml        # AI behavior settings
│   ├── logging.yaml          # Logging configuration
│   └── goap_weights.yaml     # Action costs and weights
├── data/                     # YAML data cache
│   ├── characters/           # Per-character data
│   └── game_data/           # Cached game information
└── tests/                   # Comprehensive test suite
    ├── test_cli/
    │   ├── test_character_commands.py
    │   ├── test_ai_player_commands.py
    │   └── test_diagnostic_commands.py
    ├── test_ai_player/
    │   ├── test_actions/       # Individual action tests
    │   ├── test_state/         # State management tests
    │   ├── test_diagnostics/   # Diagnostic system tests
    │   └── test_integration/   # Full workflow tests
    ├── test_game_data/
    └── test_integration/
    └── fixtures/              # Test data and mock states
        ├── character_states/
        └── planning_scenarios/
```

### Known Gotchas & Library Quirks
```python
# CRITICAL: ArtifactsMMO API Requirements
# - Token authentication via Authorization header
# - Cooldowns MUST be respected - character locked until cooldown expires
# - Rate limiting enforced - respect HTTP 429 responses
# - API is source of truth - never hard-code game data

# CRITICAL: Python/Library Patterns in Codebase  
# - Uses Pydantic for data classes with validation and serialization
# - Async logging with QueueHandler pattern for performance
# - Type annotations required everywhere (mypy strict mode)
# - uv for both dependency AND virtualenv management, not pip/poetry/venv

# CRITICAL: GOAP Implementation Details
# - World contains multiple Planners, each with Action_List
# - Planner needs start_state, goal_state, and action_list
# - Actions have conditions (preconditions) and reactions (effects)
# - A* algorithm finds lowest-cost path to goal
# - Modular action system - one action per file for maintainability
# - GameState enum for type-safe state management (no string errors)

# CRITICAL: ArtifactsMMO Game Mechanics
# - Character progression: 45 levels, 8 skills (mining, woodcutting, etc.)
# - All actions have cooldowns - character locked during cooldown
# - HP can drop to 0 in combat - must rest to recover
# - Inventory has limited slots - must manage items
# - Equipment affects stats and capabilities

# CRITICAL: Debugging and Troubleshooting
# - CLI diagnostic commands essential for GOAP planning troubleshooting
# - Must be able to inspect state, actions, and planning process
# - Action modularity enables individual action testing and validation
```

## Implementation Blueprint

### Data Models and Structure
Create type-safe data models using Pydantic and GameState enum for validation:

```python
# src/ai_player/state/game_state.py
from enum import StrEnum
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, Union
from abc import ABC, abstractmethod

class GameState(StrEnum):
    """Global enum defining all possible game state keys.
    
    Using StrEnum ensures GOAP compatibility while providing type safety.
    CRITICAL: All state references must use this enum, never raw strings.
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
    
    # Skill progression states
    MINING_LEVEL = "mining_level"
    WOODCUTTING_LEVEL = "woodcutting_level"
    FISHING_LEVEL = "fishing_level"
    WEAPONCRAFTING_LEVEL = "weaponcrafting_level"
    
    # Equipment and inventory states
    WEAPON_EQUIPPED = "weapon_equipped"
    TOOL_EQUIPPED = "tool_equipped"
    INVENTORY_SPACE_AVAILABLE = "inventory_space_available"
    
    # Action availability states
    COOLDOWN_READY = "cooldown_ready"
    CAN_FIGHT = "can_fight"
    CAN_GATHER = "can_gather"
    CAN_CRAFT = "can_craft"

# src/ai_player/actions/base_action.py
class ActionResult(BaseModel):
    """Result of executing a GOAP action"""
    success: bool
    message: str
    state_changes: Dict[GameState, Any]
    cooldown_seconds: int = 0

class BaseAction(ABC):
    """Abstract base class for all modular GOAP actions"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique action identifier"""
        pass
    
    @property
    @abstractmethod
    def cost(self) -> int:
        """GOAP planning cost"""
        pass
    
    @abstractmethod
    def get_preconditions(self) -> Dict[GameState, Any]:
        """Required state conditions using GameState enum"""
        pass
    
    @abstractmethod
    def get_effects(self) -> Dict[GameState, Any]:
        """State changes using GameState enum"""
        pass
    
    @abstractmethod
    async def execute(self, character_name: str, current_state: Dict[GameState, Any]) -> ActionResult:
        """Execute action via API"""
        pass

# Example modular action implementation
class MovementAction(BaseAction):
    """Movement action using GameState enum for type safety"""
    
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

class CharacterGameState(BaseModel):
    """Character state using GameState enum keys for type safety"""
    model_config = ConfigDict(validate_assignment=True, extra='forbid')
    
    def to_goap_state(self) -> Dict[str, Any]:
        """Convert to GOAP state dict using enum values"""
        raw_dict = self.model_dump()
        return {GameState(k).value: (int(v) if isinstance(v, bool) else v) 
                for k, v in raw_dict.items() if k in [gs.value for gs in GameState]}
    
    @classmethod
    def from_api_character(cls, character: 'CharacterSchema') -> 'CharacterGameState':
        """Create from API response using GameState enum keys"""
        return cls(**{
            GameState.CHARACTER_LEVEL.value: character.level,
            GameState.CHARACTER_XP.value: character.xp,
            GameState.HP_CURRENT.value: character.hp,
            GameState.HP_MAX.value: character.max_hp,
            GameState.CURRENT_X.value: character.x,
            GameState.CURRENT_Y.value: character.y,
            GameState.COOLDOWN_READY.value: character.cooldown == 0,
            # ... (all other state mappings using enum)
        })
```

### Task Implementation Order

```yaml
Task 1: Core Infrastructure Setup
UPDATE pyproject.toml:
  - ADD: pydantic>=2.5.0, pydantic-settings dependencies
  - ENSURE: uv manages both dependencies and virtualenv
  - VALIDATE: All existing dependencies compatible with Pydantic

CREATE src/cli/__init__.py:
  - Empty module initialization

CREATE src/cli/main.py:
  - PATTERN: Use argparse for CLI with subcommands
  - COMMANDS: create-character, delete-character, list-characters, run-character
  - LOGGING: Add --log-level option (DEBUG, INFO, WARNING, ERROR)
  - AUTHENTICATION: Read TOKEN file, validate format using Pydantic

CREATE src/game_data/__init__.py:
  - Empty module initialization

CREATE src/game_data/api_client.py:
  - PATTERN: Wrap existing artifactsmmo_api_client with Pydantic models
  - AUTHENTICATION: Use TOKEN file for Authorization header with validation
  - ERROR HANDLING: Use custom HTTP status codes from httpstatus.py
  - RATE LIMITING: Implement retry logic with exponential backoff
  - VALIDATION: Use Pydantic for all request/response data

Task 2: Character Management Foundation  
CREATE src/cli/character_manager.py:
  - PATTERN: Mirror API client structure with sync/async methods
  - CREATE: character creation via characters/create endpoint
  - DELETE: character deletion via characters/delete endpoint  
  - LIST: get character list via my/characters endpoint
  - VALIDATION: Handle API errors gracefully with specific error messages

CREATE tests/test_cli/test_character_manager.py:
  - PATTERN: Use pytest with async support
  - MOCK: Mock API client responses
  - VALIDATE: Test all CRUD operations and error cases

Task 3: GameState Enum Foundation (CRITICAL FIRST)
CREATE src/ai_player/__init__.py:
  - Empty module initialization

CREATE src/ai_player/state/__init__.py:
  - Empty module initialization

CREATE src/ai_player/state/game_state.py:
  - CRITICAL: Define GameState StrEnum with ALL possible state keys
  - PATTERN: Use StrEnum for GOAP compatibility with type safety
  - VALIDATE: Include validation methods for state dict conversion
  - EXPORT: Make GameState enum available throughout the system
  - PREVENT: No raw strings allowed for state keys anywhere in codebase

CREATE src/ai_player/state/state_manager.py:
  - PATTERN: Use GameState enum for all state references
  - SYNC: Fetch character state from API regularly using enum keys
  - CONVERT: Transform API CharacterSchema to GameState enum dict
  - CACHE: Use yaml_data.py for temporary state storage with enum serialization
  - VALIDATION: Ensure all state keys exist in GameState enum

Task 4: Modular Action System Foundation
CREATE src/ai_player/actions/__init__.py:
  - PATTERN: Action registry system using importlib for discovery
  - REGISTER: Auto-discover all action modules and validate BaseAction interface
  - EXPORT: Provide get_all_actions() function for GOAP system
  - VALIDATE: Ensure all actions use GameState enum in preconditions/effects

CREATE src/ai_player/actions/base_action.py:
  - PATTERN: Abstract base class with strict GameState enum usage
  - ENFORCE: All preconditions/effects must use GameState enum keys
  - VALIDATE: ActionResult must include state_changes with enum keys
  - INTERFACE: Standardized execute() method with type safety

CREATE src/ai_player/actions/movement_action.py:
  - PATTERN: First concrete action implementation using GameState enum
  - IMPLEMENT: All BaseAction abstract methods with enum state references
  - TEST: Validate that action integrates properly with registry
  - EXAMPLE: Serves as template for other action implementations

Task 5: Core Actions Implementation (One Per File)
CREATE src/ai_player/actions/combat_action.py:
  - PATTERN: Use GameState enum for all state references
  - IMPLEMENT: Monster fighting with HP and location preconditions
  - API: Integration with action_fight_my_name_action_fight_post
  - VALIDATION: Ensure proper state changes using enum keys

CREATE src/ai_player/actions/gathering_action.py:
  - PATTERN: Resource collection using GameState enum
  - IMPLEMENT: Tool requirements and location preconditions
  - API: Integration with action_gathering_my_name_action_gathering_post
  - VALIDATION: Skill level and inventory space checks

CREATE src/ai_player/actions/rest_action.py:
  - PATTERN: HP recovery action using GameState enum
  - IMPLEMENT: HP threshold preconditions and recovery effects
  - API: Integration with action_rest_my_name_action_rest_post
  - VALIDATION: Safe location requirements

CREATE src/ai_player/actions/crafting_action.py:
  - PATTERN: Item creation using GameState enum
  - IMPLEMENT: Resource and skill level preconditions
  - API: Integration with action_crafting_my_name_action_crafting_post
  - VALIDATION: Inventory space and material requirements

CREATE src/ai_player/actions/trading_action.py:
  - PATTERN: NPC interaction using GameState enum
  - IMPLEMENT: Location and gold preconditions
  - API: Integration with NPC buy/sell endpoints
  - VALIDATION: Economic transaction validation

Task 6: GOAP Integration with Modular Actions
CREATE config/goap_weights.yaml:
  - PATTERN: Action costs using exact action names from modules
  - WEIGHTS: Define costs for each modular action type
  - GOALS: Priority weights for different objectives
  - VALIDATION: Ensure all action names match registry

UPDATE src/ai_player/goal_manager.py:
  - PATTERN: Use action registry to get available actions
  - INTEGRATE: Connect modular actions with GOAP planning
  - ENUM: Use GameState enum for all state references in planning
  - VALIDATION: Ensure goal states use valid GameState enum keys

Task 5: Action Execution Engine
CREATE src/ai_player/action_executor.py:
  - PATTERN: Use async/await for API calls
  - EXECUTE: Convert GOAP actions to API calls
  - COOLDOWN: Check and wait for cooldowns before execution
  - VALIDATE: Verify action success via API response
  - ERROR: Handle all ArtifactsMMO error codes appropriately

Task 6: Goal Management System
CREATE src/ai_player/goal_manager.py:
  - PATTERN: Use GOAP Planner from goap.py
  - GOALS: Dynamic goal selection based on character level/state
  - PLANNING: Generate action sequences using GOAP planner
  - ADAPT: Replan when goals complete or conditions change

Task 7: Main AI Player Orchestrator
CREATE src/ai_player/ai_player.py:
  - PATTERN: Use async event loop for main operation
  - ORCHESTRATE: Coordinate state management, planning, execution
  - LOOP: Main game loop with planning and execution cycles
  - SHUTDOWN: Graceful shutdown handling

Task 8: Data Caching System
CREATE src/game_data/cache_manager.py:
  - PATTERN: Use yaml_data.py for persistence with Pydantic serialization
  - CACHE: Store items, monsters, maps, resources, NPCs using Pydantic models
  - REFRESH: Update cache periodically with data validation
  - STRUCTURE: Organize in data/ directory as specified
  - VALIDATION: Use Pydantic models for all cached game data

CREATE data/ directory structure:
  - PATTERN: Follow ARCHITECTURE.md specification
  - ORGANIZE: characters/, game_data/ subdirectories
  - YAML: All data in YAML format using yaml_data.py with Pydantic model dumps
  - VALIDATION: Ensure cached data integrity with Pydantic model loading

Task 9: CLI Diagnostic Commands (Essential for Debugging)
CREATE src/cli/commands/__init__.py:
  - Empty module initialization

CREATE src/cli/commands/diagnostics.py:
  - PATTERN: Use GameState enum for all state validation
  - IMPLEMENT: diagnose-state command to show current character state
  - IMPLEMENT: diagnose-actions command to list available actions with costs
  - IMPLEMENT: diagnose-plan command to visualize GOAP planning process
  - IMPLEMENT: test-planning command for mock scenario testing
  - VALIDATION: Ensure all diagnostic output uses GameState enum names

CREATE src/ai_player/diagnostics/__init__.py:
  - Empty module initialization

CREATE src/ai_player/diagnostics/state_diagnostics.py:
  - PATTERN: GameState enum validation and inspection
  - IMPLEMENT: State consistency checking and enum validation
  - EXPORT: Functions for CLI diagnostic commands
  - VALIDATION: Detect invalid state keys not in GameState enum

CREATE src/ai_player/diagnostics/action_diagnostics.py:
  - PATTERN: Action registry inspection and validation
  - IMPLEMENT: Action precondition/effect analysis
  - EXPORT: Functions for CLI action debugging
  - VALIDATION: Ensure all actions use valid GameState enum keys

CREATE src/ai_player/diagnostics/planning_diagnostics.py:
  - PATTERN: GOAP planning process visualization
  - IMPLEMENT: Step-by-step planning analysis
  - EXPORT: Functions for CLI planning debugging
  - VALIDATION: Show state transitions using GameState enum

Task 10: CLI Command Integration
CREATE src/cli/commands/character.py:
  - PATTERN: Character CRUD operations with validation
  - IMPLEMENT: create-character, delete-character, list-characters
  - VALIDATION: Use Pydantic for input validation

CREATE src/cli/commands/ai_player.py:
  - PATTERN: AI player control and monitoring
  - IMPLEMENT: run-character, stop-character, status-character
  - INTEGRATION: Connect to modular action system and diagnostics
  - VALIDATION: Verify character state using GameState enum

UPDATE src/cli/main.py:
  - PATTERN: Import modular command implementations
  - INTEGRATE: Add diagnostic command subcommands
  - LOGGING: Configure logging based on CLI arguments
  - HELP: Provide comprehensive help for diagnostic commands

Task 11: Configuration Management
CREATE config/ai_player.yaml:
  - PATTERN: Follow ARCHITECTURE.md specification with Pydantic Settings
  - CONFIGURE: AI behavior, goal priorities, planning parameters
  - VALIDATION: Use Pydantic Settings for type-safe configuration loading
  - ACTIONS: Include configuration for modular action system

CREATE config/logging.yaml:
  - PATTERN: Use existing log.py async pattern
  - CONFIGURE: Log levels, handlers, formatters
  - INTEGRATION: Ensure compatibility with Pydantic logging
  - DIAGNOSTICS: Include logging configuration for diagnostic commands

Task 12: Comprehensive Testing with Modular Validation
CREATE tests/test_ai_player/test_actions/:
  - PATTERN: Individual action module testing
  - UNITTEST: Test each action class independently using GameState enum
  - VALIDATE: Ensure all actions use valid GameState enum keys
  - MOCK: Mock API responses for isolated action testing

CREATE tests/test_ai_player/test_state/:
  - PATTERN: GameState enum and state management testing
  - VALIDATE: Enum key validation and state conversion
  - UNITTEST: State manager with enum usage
  - INTEGRATION: API response to GameState enum conversion

CREATE tests/test_ai_player/test_diagnostics/:
  - PATTERN: Diagnostic system testing
  - UNITTEST: State diagnostics, action diagnostics, planning diagnostics
  - VALIDATE: Diagnostic output format and enum usage
  - INTEGRATION: CLI diagnostic command testing

CREATE tests/test_cli/test_diagnostic_commands.py:
  - PATTERN: CLI diagnostic command testing with GameState enum
  - UNITTEST: Each diagnostic command independently
  - VALIDATE: Correct enum usage in diagnostic output
  - INTEGRATION: End-to-end diagnostic workflows

CREATE tests/fixtures/:
  - PATTERN: Test data using GameState enum keys
  - CHARACTER_STATES: Mock character states with valid enum keys
  - PLANNING_SCENARIOS: GOAP planning test cases
  - VALIDATE: All fixture data uses GameState enum

Task 13: Final Integration and Validation
INTEGRATE all components:
  - ENTRY: Update pyproject.toml with CLI entry point
  - VALIDATE: Full system testing with GameState enum usage
  - DOCUMENT: Update any necessary documentation
  - DIAGNOSTICS: Verify all diagnostic commands work correctly
```

### Per-Task Pseudocode

```python
# Task 1: API Client Wrapper with Pydantic validation
from pydantic import BaseModel, Field, ValidationError

class TokenConfig(BaseModel):
    """Pydantic model for token validation"""
    token: str = Field(min_length=32, description="ArtifactsMMO API token")
    
    @classmethod
    def from_file(cls, token_file: str = "TOKEN") -> 'TokenConfig':
        token_value = Path(token_file).read_text().strip()
        return cls(token=token_value)

class APIClientWrapper:
    def __init__(self, token_file: str = "TOKEN"):
        # PATTERN: Use Pydantic for token validation
        try:
            self.token_config = TokenConfig.from_file(token_file)
        except ValidationError as e:
            raise ValueError(f"Invalid token format: {e}")
            
        self.client = AuthenticatedClient(
            base_url="https://api.artifactsmmo.com",
            token=self.token_config.token
        )
        # PATTERN: Use httpstatus.py for error handling
        self.status_codes = ArtifactsHTTPStatus
    
    async def create_character(self, name: str, skin: str) -> CharacterSchema:
        # CRITICAL: Handle rate limiting and cooldowns with Pydantic response validation
        response = await create_character_characters_create_post.asyncio(
            client=self.client,
            body=AddCharacterSchema(name=name, skin=skin)
        )
        if response.status_code == 429:  # Rate limited
            await self._handle_rate_limit(response)
        
        # PATTERN: Validate response with Pydantic if needed
        return response.parsed

# Task 4: GOAP Action Definition
def setup_goap_actions() -> Action_List:
    actions = Action_List()
    
    # PATTERN: Each action maps to API endpoint
    actions.add_condition("move_to_location", 
                         at_target_location=0, cooldown_ready=1)
    actions.add_reaction("move_to_location", 
                        at_target_location=1, cooldown_ready=0)
    actions.set_weight("move_to_location", 1)
    
    # CRITICAL: Fight action requires HP and correct location
    actions.add_condition("fight_monster",
                         at_monster_location=1, hp_sufficient=1, cooldown_ready=1)
    actions.add_reaction("fight_monster",
                        xp_gained=1, cooldown_ready=0)
    actions.set_weight("fight_monster", 3)
    
    return actions

# Task 7: Main AI Loop
async def ai_main_loop(character_name: str):
    state_manager = StateManager(character_name)
    goal_manager = GoalManager()
    executor = ActionExecutor()
    
    while not goal_manager.max_level_achieved():
        # PATTERN: Plan -> Execute -> Update cycle
        current_state = await state_manager.get_current_state()
        goal = goal_manager.select_next_goal(current_state)
        plan = goal_manager.plan_actions(current_state, goal)
        
        for action in plan:
            # CRITICAL: Always check cooldowns before execution
            await executor.wait_for_cooldown(character_name)
            result = await executor.execute_action(action)
            await state_manager.update_from_result(result)
            
            # PATTERN: Log at appropriate levels
            logger.info(f"Executed {action['name']}, cooldown: {result.cooldown}")
```

### Integration Points
```yaml
CLI_ENTRY:
  - add to: pyproject.toml
  - section: [project.scripts]  
  - command: "artifactsmmo-ai = 'src.cli.main:main'"

AUTHENTICATION:
  - file: TOKEN (already exists)
  - pattern: "Bearer {token}" in Authorization header
  - validation: Test with /my/characters endpoint

LOGGING:
  - pattern: Use existing src/lib/log.py async setup
  - configuration: config/logging.yaml for levels/handlers
  - format: Include character name, action type, timestamps

YAML_STORAGE:
  - data/: Use src/lib/yaml_data.py pattern
  - config/: Configuration files
  - structure: Match ARCHITECTURE.md specification
```

## Validation Loop

### Level 1: Syntax & Style with uv
```bash  
# CRITICAL: Run these FIRST - fix any errors before proceeding
# IMPORTANT: uv manages both dependencies and virtualenv automatically
uv sync                             # Ensure environment is up to date
uv run ruff check src/ --fix        # Auto-fix formatting/imports  
uv run mypy src/                    # Type checking (strict mode)
uv run ruff format src/             # Code formatting

# Expected: No errors. Mypy must pass in strict mode with Pydantic.
# If Pydantic import errors: uv add pydantic>=2.5.0
```

### Level 2: Unit Tests with Pydantic Validation
```python
# CREATE comprehensive test suite using pytest patterns with Pydantic
@pytest.mark.asyncio
async def test_character_creation():
    """Test character creation via API with Pydantic validation"""
    manager = CharacterManager()
    character = await manager.create_character("test_char", "men1")
    assert character.name == "test_char"
    assert character.level == 1
    
    # Test Pydantic model conversion
    game_state = CharacterGameState.from_api_character(character)
    assert game_state.character_level == 1
    assert game_state.cooldown_ready == True

@pytest.mark.asyncio 
async def test_goap_planning_with_pydantic():
    """Test GOAP action planning with Pydantic state models"""
    # Create Pydantic game state
    initial_state = CharacterGameState(
        x=0, y=0, character_level=1, character_xp=0,
        hp_current=100, hp_max=100,
        mining_level=1, woodcutting_level=1, fishing_level=1,
        weaponcrafting_level=1, gearcrafting_level=1, 
        jewelrycrafting_level=1, cooking_level=1, alchemy_level=1
    )
    
    planner = Planner("character_level", "at_location", "hp_current")
    planner.set_start_state(**initial_state.to_goap_state())
    planner.set_goal_state(character_level=2)
    actions = setup_goap_actions()
    planner.set_action_list(actions)
    plan = planner.calculate()
    assert len(plan) > 0
    assert plan[0]["name"] in ["move_to_location", "fight_monster"]

def test_cooldown_manager_pydantic():
    """Test cooldown tracking with Pydantic models"""
    manager = CooldownManager()
    
    # Create Pydantic cooldown info
    future_time = datetime.now() + timedelta(seconds=30)
    cooldown_data = Mock()
    cooldown_data.expiration = future_time
    cooldown_data.total_seconds = 30
    cooldown_data.remaining_seconds = 30
    cooldown_data.reason.value = "fight"
    
    manager.update_cooldown("test_char", cooldown_data)
    assert not manager.is_ready("test_char")
    assert manager.character_cooldowns["test_char"].time_remaining > 0

def test_ai_player_config_validation():
    """Test Pydantic configuration validation"""
    # Valid config
    config = AIPlayerConfig(
        survival_priority=10,
        progression_priority=8,
        min_hp_percentage=0.3
    )
    assert config.survival_priority == 10
    
    # Invalid config should raise ValidationError
    with pytest.raises(ValidationError):
        AIPlayerConfig(survival_priority=15)  # > 10 limit
```

```bash
# Run and iterate until passing with uv:
uv run pytest tests/ -v --tb=short
# If failing: Read error, understand root cause, fix code, re-run (never mock to pass)
# If Pydantic errors: Check model definitions and constraints
```

### Level 3: Integration Test with uv Environment
```bash
# CRITICAL: Test with real API (requires valid TOKEN) using uv
# uv automatically manages the virtualenv and dependencies

# Test character management
uv run python -m src.cli.main create-character test_integration_char men1
uv run python -m src.cli.main list-characters
uv run python -m src.cli.main delete-character test_integration_char

# Test AI player execution (short run)
uv run python -m src.cli.main run-character test_char --max-actions 10 --log-level DEBUG

# Expected: Character created, AI runs for 10 actions, logs show proper GOAP planning
# Pydantic validation should prevent invalid states and configurations
```

### Level 4: Full System Validation
```bash
# Create test character and run full AI loop
uv run python -m src.cli.main create-character ai_test_full men1
uv run python -m src.cli.main run-character ai_test_full --log-level INFO

# Monitor logs for:
# - Proper GOAP planning cycles
# - API cooldown compliance
# - Character progression (XP/level gains)
# - Error handling for API failures

# Cleanup
uv run python -m src.cli.main delete-character ai_test_full
```

## Final Validation Checklist
- [ ] All tests pass: `uv run pytest tests/ -v`
- [ ] No linting errors: `uv run ruff check src/`
- [ ] No type errors: `uv run mypy src/`
- [ ] CLI commands work: Character CRUD operations
- [ ] AI player runs: Autonomous gameplay for multiple actions
- [ ] Cooldowns respected: No API 499 errors in logs
- [ ] Data caching works: YAML files created in data/ directory
- [ ] Configuration loaded: Settings from config/ directory used
- [ ] Logging configurable: Different log levels produce appropriate output
- [ ] Error handling: Graceful failure for API errors
- [ ] Performance: System handles long-running gameplay sessions

---

## Anti-Patterns to Avoid
- ❌ Don't ignore cooldowns - API will return 499 and lock character
- ❌ Don't hardcode game data - always use API as source of truth
- ❌ Don't skip type annotations - mypy strict mode required
- ❌ Don't use sync functions for API calls - must be async
- ❌ Don't use attrs or dataclasses - use Pydantic for data validation and serialization
- ❌ Don't skip GOAP planning - system must use intelligent decision making
- ❌ Don't ignore rate limits - implement proper backoff strategies
- ❌ Don't mock tests to pass - fix underlying issues
- ❌ Don't bypass Pydantic validation - use model constraints for data integrity
- ❌ Don't use pip/poetry/venv - use uv for all dependency and environment management
- ❌ **Don't use raw strings for state keys** - ALWAYS use GameState enum for type safety
- ❌ **Don't put multiple actions in one file** - each action must be in its own module
- ❌ **Don't skip diagnostic commands** - essential for troubleshooting GOAP planning
- ❌ Don't bypass action registry - all actions must be discoverable via registry
- ❌ Don't create actions without using BaseAction interface - maintain consistency
- ❌ Don't reference state keys that don't exist in GameState enum - causes runtime errors

## Confidence Score: 9/10

This PRP provides exhaustive context for one-pass implementation success:
- ✅ Complete codebase analysis and existing patterns identified
- ✅ All necessary documentation URLs and references included  
- ✅ Detailed task breakdown in logical implementation order
- ✅ Specific code patterns and gotchas documented
- ✅ Comprehensive validation strategy with executable commands
- ✅ Integration requirements clearly specified
- ✅ Error handling and edge cases addressed

The only risk factor is the complexity of the GOAP integration with real-time API constraints, but the existing GOAP library and comprehensive API documentation mitigate this risk significantly.
