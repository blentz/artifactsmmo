# Material Gathering Implementation

## Overview

This document describes the implementation of the complete material gathering chain for the `upgrade_weapon` goal, addressing the issue where the system would identify missing materials but fail to gather them.

## Problem

The original GOAP planning system would:
1. Correctly identify that materials (e.g., copper_ore) were insufficient
2. Fail to create a plan that includes gathering those materials
3. Skip directly from checking materials to verifying skills

## Solution

### 1. Enhanced GOAP Actions

Added a complete material gathering and transformation chain to `config/default_actions.yaml`:

#### Material Gathering Actions:
- **find_resources**: Locates required resources on the map
- **move_to_resource**: Moves character to resource location
- **gather_resources**: Gathers raw materials (e.g., copper_ore)

#### Material Transformation Actions:
- **find_workshop**: Locates appropriate workshop for transformation
- **move_to_workshop**: Moves character to workshop
- **transform_materials**: Transforms raw materials (ore → bars)
- **verify_material_sufficiency**: Confirms materials are now sufficient

### 2. State Management Updates

Updated `config/consolidated_state_defaults.yaml` to include:
- `location_context.resource_known`: Track if resource location is known
- `materials.transformation_complete`: Track transformation status
- `materials.ready_to_craft`: Indicate readiness for crafting

### 3. Action Configuration Changes

Key change in `check_material_availability`:
```yaml
reactions:
  materials:
    availability_checked: true
    # Don't set status here - let runtime determine if sufficient/insufficient
```

This allows the runtime to set material status to 'insufficient', triggering the gathering chain.

## Complete Action Chain

The enhanced system now creates a 9-action plan for `upgrade_weapon`:

1. **find_resources** - Find copper_ore location
2. **move_to_resource** - Move to resource
3. **gather_resources** - Gather copper_ore
4. **find_workshop** - Find smelting workshop
5. **move_to_workshop** - Move to workshop
6. **transform_materials** - Smelt ore → copper bars
7. **verify_material_sufficiency** - Confirm materials sufficient
8. **verify_skill_requirements** - Check crafting skills
9. **complete_equipment_upgrade** - Craft copper_dagger

## Testing

### Test Scripts Created:
- `test_full_crafting_chain.py` - Tests various material states
- `test_enhanced_crafting_chain.py` - Compares enhanced vs default actions
- `test_real_upgrade_flow.py` - Tests actual execution flow

### Test Results:
- GOAP planner successfully creates 9-action plans when materials are insufficient
- Actions properly chain from resource gathering through transformation to crafting
- System handles the complete copper_ore → copper_bar → copper_dagger chain

## Integration

The changes are fully integrated into the default configuration:
- No code changes required in the core system
- Purely configuration-driven through YAML
- Backward compatible with existing functionality
- Works with the metaprogramming action execution system

## Future Enhancements

Potential improvements:
1. Add support for multi-step material chains (e.g., items requiring multiple transformations)
2. Optimize gathering to collect exact quantities needed
3. Add support for alternative material sources
4. Implement material caching to avoid repeated gathering

## Usage

To use the enhanced material gathering:
1. System automatically detects insufficient materials during `check_material_availability`
2. GOAP planner creates appropriate gathering plan
3. Actions execute in sequence to gather, transform, and craft

No special configuration needed - it works automatically when materials are insufficient.