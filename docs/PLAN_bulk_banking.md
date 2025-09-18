# Bulk Banking Operations Implementation Plan

## Overview
Add bulk banking operations to the ArtifactsMMO CLI for more efficient inventory management.

## Requirements Analysis

### Current Banking Structure
- Individual deposit/withdraw commands in `bank.py`
- Proper error handling and cooldown management
- Uses `SimpleItemSchema` for API calls
- Character inventory accessible via character API

### Item Structure
- Items have `type_` and `subtype` fields for categorization
- Inventory items have `code`, `quantity`, and `slot` properties
- Item types include: ore, wood, consumable, equipment, etc.

## Implementation Tasks

### 1. Core Helper Functions
- [ ] `get_character_inventory()` - Fetch character inventory
- [ ] `get_item_info()` - Get item details including type
- [ ] `categorize_items()` - Group items by type/subtype
- [ ] `execute_bulk_operation()` - Handle batch operations with progress

### 2. New Commands
- [ ] `bank deposit-all CHARACTER` - Deposit all items
- [ ] `bank withdraw-all CHARACTER ITEM_CODE` - Withdraw all of specific item
- [ ] `bank deposit-all CHARACTER --type TYPE` - Deposit by type
- [ ] `bank exchange CHARACTER` - Smart exchange operations

### 3. Features
- [ ] Rich progress bars for bulk operations
- [ ] Cooldown handling between operations
- [ ] Operation summaries with item counts
- [ ] Error handling with continue-on-error option
- [ ] Item type filtering (ore, wood, consumable, equipment)

### 4. Smart Exchange Logic
- [ ] Detect common resource types (ores, logs, etc.)
- [ ] Identify crafting materials vs resources
- [ ] Option to keep essential items (food, equipment)

### 5. Testing
- [ ] Unit tests for helper functions
- [ ] Integration tests for bulk commands
- [ ] Error handling tests
- [ ] Cooldown management tests

## Technical Approach

### Item Type Categories
```python
ITEM_CATEGORIES = {
    'resource': ['ore', 'wood', 'fish', 'mining', 'woodcutting', 'fishing'],
    'consumable': ['consumable', 'food'],
    'equipment': ['weapon', 'helmet', 'body_armor', 'leg_armor', 'boots', 'shield', 'amulet', 'ring'],
    'crafting': ['crafting_material', 'ingredient']
}
```

### Progress Tracking
- Use Rich Progress for visual feedback
- Track: items processed, successful operations, errors
- Show estimated time remaining

### Error Handling
- Continue on individual item errors
- Collect and report all errors at end
- Option to stop on first error

## Implementation Order
1. Helper functions for inventory and item management
2. Basic bulk deposit-all command
3. Type filtering functionality
4. Withdraw-all command
5. Smart exchange logic
6. Progress indicators and summaries
7. Comprehensive testing

## Success Criteria
- All bulk commands work reliably
- Proper cooldown handling
- Clear progress indication
- Comprehensive error reporting
- 100% test coverage