# ArtifactsMMO CLI Implementation Plan

## Overview
Building a comprehensive CLI/TUI interface for ArtifactsMMO game with 77+ API endpoints.

## Current State Analysis
- ✅ Generated API client with 77 endpoints available
- ✅ TOKEN file exists for authentication
- ✅ Python 3.13 + uv project setup
- ❌ No CLI interface yet
- ❌ Missing CLI dependencies (typer, textual, rich)

## Implementation Tasks

### Phase 1: Core Infrastructure
1. **Update Dependencies** - Add typer[all], textual, rich, pydantic
2. **Project Structure** - Create src/artifactsmmo_cli/ hierarchy
3. **Configuration** - Token loading and API client config
4. **Client Manager** - Wrapper around generated API client
5. **Main Entry Point** - Typer app with command groups

### Phase 2: Command Groups
6. **Character Commands** - list, create, delete, select
7. **Action Commands** - move, fight, gather, rest, equip, use
8. **Bank Commands** - deposit/withdraw gold/items, list, expand
9. **Trading Commands** - Grand Exchange operations
10. **Crafting Commands** - craft, recipes, recycle
11. **Task Commands** - new, complete, exchange, trade, cancel
12. **Info Commands** - items, monsters, maps, resources, achievements
13. **Account Commands** - details, change-password, logs

### Phase 3: Enhancement & Testing
14. **Utilities** - Formatters, validators, helpers
15. **Error Handling** - Comprehensive API error handling
16. **Testing** - 100% coverage test suite
17. **TUI Interface** - Optional Textual-based interface
18. **Documentation** - CLI usage guide

## API Endpoint Mapping

### Character Management
- `character list` → `my_characters.get_my_characters_my_characters_get()`
- `character create` → `characters.create_character_characters_create_post()`
- `character delete` → `characters.delete_character_characters_delete_post()`

### Character Actions
- `action move` → `my_characters.action_move_my_name_action_move_post()`
- `action fight` → `my_characters.action_fight_my_name_action_fight_post()`
- `action gather` → `my_characters.action_gathering_my_name_action_gathering_post()`
- `action rest` → `my_characters.action_rest_my_name_action_rest_post()`
- `action equip` → `my_characters.action_equip_item_my_name_action_equip_post()`
- `action unequip` → `my_characters.action_unequip_item_my_name_action_unequip_post()`
- `action use` → `my_characters.action_use_item_my_name_action_use_post()`

### Bank Operations
- `bank deposit-gold` → `my_characters.action_deposit_bank_gold_my_name_action_bank_deposit_gold_post()`
- `bank withdraw-gold` → `my_characters.action_withdraw_bank_gold_my_name_action_bank_withdraw_gold_post()`
- `bank deposit-item` → `my_characters.action_deposit_bank_item_my_name_action_bank_deposit_item_post()`
- `bank withdraw-item` → `my_characters.action_withdraw_bank_item_my_name_action_bank_withdraw_item_post()`
- `bank list` → `my_account.get_bank_items_my_bank_items_get()`
- `bank expand` → `my_characters.action_buy_bank_expansion_my_name_action_bank_buy_expansion_post()`

## Key Design Decisions

### Command Structure
- Verb-noun pattern: `artifactsmmo <group> <action> [args]`
- Character name as first argument for character actions
- Global options: --token-file, --debug, --format

### Error Handling
- Specific exception types (no generic Exception catching)
- User-friendly error messages
- Cooldown handling for character actions
- API rate limiting awareness

### Authentication
- TOKEN file in project root (default)
- Optional ARTIFACTSMMO_TOKEN environment variable
- Bearer token authentication via httpx headers

### Output Formatting
- Rich library for colored/formatted output
- Table format for lists
- JSON format option for scripting
- Progress indicators for long operations

## Success Criteria
- [ ] All 77 API endpoints accessible via CLI
- [ ] Comprehensive help and auto-completion
- [ ] 100% test coverage
- [ ] Zero mypy/ruff errors
- [ ] User-friendly error handling
- [ ] Optional TUI interface working

## Next Steps
1. Update pyproject.toml with new dependencies
2. Create project structure
3. Implement core infrastructure
4. Build command groups systematically
5. Add comprehensive testing