# Combat Assessment Implementation Plan

## Overview
Implement combat assessment features for the ArtifactsMMO CLI to help players make informed combat decisions.

## Requirements
1. Enhance `info monsters` command with `--compare CHARACTER` option
2. Add new `info monster <name>` command for specific monster details
3. Implement combat assessment logic with difficulty ratings
4. Add comprehensive tests

## Implementation Details

### 1. Combat Assessment Logic
- **Difficulty Rating System**:
  - Easy: Monster 2+ levels below character (🟢 Green)
  - Medium: Monster within 1 level of character (🟡 Yellow)
  - Hard: Monster 1-2 levels above character (🟠 Orange)
  - Deadly: Monster 3+ levels above character (🔴 Red)

- **Success Probability Calculation**:
  - Easy: 85-95% success
  - Medium: 65-85% success
  - Hard: 35-65% success
  - Deadly: 10-35% success

### 2. Helper Functions to Implement
- `_get_character_data(character_name)` - Fetch character stats
- `_calculate_difficulty_rating(char_level, monster_level)` - Determine difficulty
- `_calculate_success_probability(character, monster)` - Estimate success chance
- `_format_combat_analysis(character, monster)` - Format assessment output
- `_get_monster_drops(monster)` - Extract drop information

### 3. Enhanced Commands
- **`info monsters --compare CHARACTER`**: Show difficulty indicators for all monsters
- **`info monster <name> [--compare CHARACTER]`**: Detailed monster info with optional combat analysis

### 4. Output Features
- Color-coded difficulty indicators
- Success probability percentages
- HP and damage comparisons
- Drop information with risk/reward assessment
- Recommended character level

### 5. Testing Strategy
- Unit tests for combat assessment logic
- Integration tests for enhanced commands
- Mock character and monster data
- Edge case testing (missing data, API errors)

## Files to Modify
- `src/artifactsmmo_cli/commands/info.py` - Main implementation
- `tests/test_commands/test_info.py` - Test coverage

## Implementation Steps
1. Add combat assessment helper functions
2. Enhance existing `monsters` command
3. Add new `monster` command
4. Implement comprehensive tests
5. Validate functionality and edge cases