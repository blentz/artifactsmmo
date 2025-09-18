# Pathfinding and Auto-Navigation Implementation Plan

## Overview
Implement pathfinding and auto-navigation commands for the ArtifactsMMO CLI to make movement more efficient.

## Requirements Analysis

### Commands to Implement
1. `action goto CHARACTER X Y` - Navigate to coordinates
2. `action goto CHARACTER bank` - Navigate to nearest bank
3. `action goto CHARACTER "task master"` - Navigate to nearest task master
4. `action goto CHARACTER copper` - Navigate to nearest copper resource
5. `action path CHARACTER X Y` - Show path without moving

### Features Required
- Calculate optimal path from current position to destination
- Execute moves automatically with cooldown handling
- Show progress during navigation
- Support named locations (NPCs, resources)
- Handle obstacles/invalid paths gracefully

## Technical Analysis

### Current Codebase Structure
- **action.py**: Contains move command, batch operations, cooldown handling
- **info.py**: Contains map API access, NPC location lookup
- **character.py**: Contains character info including current position (x, y)
- **Rich**: Used for progress display and formatting
- **API**: Simple grid coordinate system, no obstacles mentioned

### Key Insights
1. Game uses simple grid coordinates (x, y)
2. Existing move command handles single moves with cooldowns
3. Map API provides location data and content (NPCs, resources)
4. NPCs have known fallback locations in info.py
5. Rich progress bars already implemented for batch operations

## Implementation Plan

### Phase 1: Core Pathfinding Logic
Create pathfinding utilities in a new module:

```python
# src/artifactsmmo_cli/utils/pathfinding.py

@dataclass
class PathStep:
    x: int
    y: int

@dataclass
class PathResult:
    steps: list[PathStep]
    total_distance: int
    estimated_time: int  # seconds including cooldowns

def calculate_path(start_x: int, start_y: int, end_x: int, end_y: int) -> PathResult:
    """Calculate optimal path using Manhattan distance (no obstacles)."""

def get_character_position(character: str) -> tuple[int, int]:
    """Get current character position from API."""

def resolve_named_location(location_name: str, character_x: int, character_y: int) -> tuple[int, int]:
    """Resolve named locations like 'bank', 'task master', 'copper' to coordinates."""
```

### Phase 2: Location Resolution
Implement named location lookup:

```python
# Location resolution functions
def find_nearest_bank(character_x: int, character_y: int) -> tuple[int, int]:
def find_nearest_task_master(character_x: int, character_y: int) -> tuple[int, int]:
def find_nearest_resource(resource_name: str, character_x: int, character_y: int) -> tuple[int, int]:
```

Use existing map API and fallback to known locations from info.py.

### Phase 3: Navigation Commands
Add to action.py:

```python
@app.command("goto")
def goto_location(
    character: str = typer.Argument(..., help="Character name"),
    destination: str = typer.Argument(..., help="Destination (X Y coordinates or named location)"),
    wait_cooldown: bool = typer.Option(True, "--wait-cooldown", "-w", help="Wait for cooldowns between moves"),
    show_path: bool = typer.Option(False, "--show-path", "-p", help="Show path before moving"),
) -> None:

@app.command("path")
def show_path(
    character: str = typer.Argument(..., help="Character name"),
    destination: str = typer.Argument(..., help="Destination (X Y coordinates or named location)"),
) -> None:
```

### Phase 4: Navigation Execution
Implement auto-navigation with:
- Progress tracking using Rich
- Cooldown handling (wait or fail)
- Interrupt handling (Ctrl+C)
- Error recovery

### Phase 5: Testing
Create comprehensive tests:
- Unit tests for pathfinding algorithm
- Integration tests for commands
- Edge cases (invalid destinations, cooldowns, interrupts)

## Implementation Details

### Pathfinding Algorithm
Since no obstacles are mentioned, use simple Manhattan distance:
1. Calculate dx = abs(end_x - start_x)
2. Calculate dy = abs(end_y - start_y)
3. Generate step-by-step path moving one coordinate at a time
4. Optimize for shortest path (move diagonally when possible)

### Named Location Resolution
1. Try map API first for dynamic locations
2. Fall back to known locations from info.py
3. For resources, search map content for resource codes
4. Choose nearest location if multiple exist

### Progress Display
Reuse existing Rich progress patterns from batch operations:
- Show current step / total steps
- Show estimated time remaining
- Show current coordinates
- Allow interruption

### Error Handling
- Invalid destinations: Clear error message
- Character not found: Use existing validation
- API errors: Use existing error handling
- Cooldowns: Wait or fail based on user preference
- Interrupts: Clean exit with current position

## File Changes Required

### New Files
- `src/artifactsmmo_cli/utils/pathfinding.py` - Core pathfinding logic
- `tests/test_utils/test_pathfinding.py` - Pathfinding tests
- `tests/test_commands/test_pathfinding_commands.py` - Command tests

### Modified Files
- `src/artifactsmmo_cli/commands/action.py` - Add goto and path commands
- `src/artifactsmmo_cli/utils/__init__.py` - Export pathfinding utilities

## Success Criteria
1. All commands work as specified
2. Pathfinding is efficient and accurate
3. Named location resolution works for all specified types
4. Progress display is clear and informative
5. Error handling is robust
6. Tests achieve 100% coverage
7. No performance regressions

## Risk Mitigation
1. **API Rate Limits**: Add delays between moves, respect cooldowns
2. **Invalid Locations**: Validate destinations before starting navigation
3. **Long Paths**: Show estimated time, allow cancellation
4. **Network Issues**: Retry logic, graceful degradation
5. **Character State Changes**: Re-check position if moves fail

## Future Enhancements
1. Obstacle avoidance if game adds obstacles
2. Path optimization for multiple destinations
3. Waypoint system for complex routes
4. Auto-navigation scripts/macros
5. Path caching for common routes