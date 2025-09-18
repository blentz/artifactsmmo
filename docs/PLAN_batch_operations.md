# Batch Operations Implementation Plan

## Overview
Implement batch operations functionality for the artifactsmmo CLI to allow users to repeat actions multiple times with cooldown handling.

## Requirements
1. Add a new `batch` subcommand to action.py that allows repeating actions
2. Support syntax like: `artifactsmmo action batch <character> <action> --times <n> [--wait-cooldown]`
3. Actions to support: gather, fight, rest, mine (basically any action that can be repeated)
4. Features:
   - Execute the action N times
   - Option to wait for cooldowns between actions (--wait-cooldown flag)
   - Show progress (e.g., "Executing action 3/10...")
   - Accumulate and display total results (total items gathered, XP gained, etc.)
   - Stop on error unless --continue-on-error flag is set
5. Use existing action implementations and formatters
6. Add comprehensive tests

## Technical Analysis
- Project uses Typer (not Click) for CLI
- Existing action pattern: validate → get API client → make API call → handle response → format output
- CLIResponse model handles success, error, and cooldown states
- Rich formatting is used extensively
- Comprehensive error handling with cooldown detection

## Implementation Steps

### 1. Core Batch Command Structure
- Add `batch` command to action.py
- Parameters:
  - `character`: Character name (required)
  - `action`: Action type (required) - choices: gather, fight, rest, mine
  - `--times`: Number of iterations (required)
  - `--wait-cooldown`: Wait for cooldowns between actions (flag)
  - `--continue-on-error`: Continue on error instead of stopping (flag)

### 2. Action Executor Functions
Create helper functions that can execute actions programmatically:
- `execute_gather_action(character: str) -> CLIResponse`
- `execute_fight_action(character: str) -> CLIResponse`
- `execute_rest_action(character: str) -> CLIResponse`
- `execute_mine_action(character: str) -> CLIResponse` (if mining exists)

### 3. Result Accumulation
Create data structures to track:
- Total XP gained
- Total gold gained
- Items collected (with quantities)
- Successful actions count
- Failed actions count
- Total time elapsed

### 4. Progress Display
- Use Rich progress bar
- Show current iteration (e.g., "3/10")
- Show current action status
- Display accumulated results in real-time

### 5. Cooldown Handling
- Detect cooldowns from CLIResponse
- If --wait-cooldown is set, sleep for cooldown duration
- Show countdown timer during wait
- If not set, stop execution on cooldown

### 6. Error Handling
- Stop on first error unless --continue-on-error is set
- Handle KeyboardInterrupt (Ctrl+C) gracefully
- Show partial results even if interrupted

### 7. Result Summary
Display final summary with:
- Total actions attempted/successful
- Total XP gained
- Total gold gained
- Items collected (grouped by type)
- Total time taken
- Average time per action

### 8. Testing
- Unit tests for each action executor
- Integration tests for batch command
- Test cooldown handling
- Test error scenarios
- Test interrupt handling

## File Changes
1. `src/artifactsmmo_cli/commands/action.py` - Add batch command and helper functions
2. `tests/test_commands/test_action.py` - Add comprehensive tests
3. Potentially add new utility functions if needed

## Implementation Notes
- Reuse existing action logic to avoid duplication
- Follow existing error handling patterns
- Use Rich for progress display and formatting
- Handle mining action if it exists in the API
- Ensure graceful handling of all edge cases