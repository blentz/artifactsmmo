"""
State Parameters Registry

Centralized registry for ALL state parameters used throughout the system.
This eliminates hardcoded parameter strings and ensures naming consistency.

Following DRY principle - all parameter names defined once, used everywhere.
Following KISS principle - simple dotted naming convention.
"""

from typing import Set


class StateParameters:
    """
    Centralized registry for all state parameters.
    
    All parameter names use dotted notation to preserve semantic grouping
    without the complexity of nested data structures.
    
    Design Decisions:
    - Dotted naming preserves hierarchical meaning (equipment_status.selected_item)
    - Flat storage eliminates sync issues between systems
    - Constants prevent typos and enable IDE auto-completion
    - Comprehensive coverage ensures no hardcoded strings elsewhere
    """
    
    # Target Item Parameters
    TARGET_ITEM = "target.item"
    TARGET_SLOT = "target.slot"
    TARGET_RECIPE = "target.recipe"
    
    # Equipment Status Parameters
    EQUIPMENT_UPGRADE_STATUS = "equipment_status.upgrade_status"
    EQUIPMENT_GAPS_ANALYZED = "equipment_status.gaps_analyzed"
    EQUIPMENT_ITEM_CRAFTED = "equipment_status.item_crafted"
    EQUIPMENT_EQUIPPED = "equipment_status.equipped"
    EQUIPMENT_HAS_TARGET_SLOT = "equipment_status.has_target_slot"
    EQUIPMENT_HAS_WEAPON = "equipment_status.has_weapon"
    # API-duplicate equipment parameters removed - use character API for current equipment state
    
    # Character Status Parameters
    CHARACTER_ALIVE = "character_status.alive"
    CHARACTER_LEVEL = "character_status.level"
    CHARACTER_HP = "character_status.hp"
    CHARACTER_MAX_HP = "character_status.max_hp"
    CHARACTER_PREVIOUS_HP = "character_status.previous_hp"
    CHARACTER_COOLDOWN_ACTIVE = "character_status.cooldown_active"
    CHARACTER_COOLDOWN_HANDLED = "character_status.cooldown_handled"
    CHARACTER_SAFE = "character_status.safe"
    CHARACTER_XP_PERCENTAGE = "character_status.xp_percentage"
    CHARACTER_NAME = "character_status.name"
    
    # Location Context Parameters - removed redundant, use CHARACTER_X/Y, TARGET_X/Y, API data
    
    # Materials Parameters - minimal set, use knowledge base for lookups
    MATERIALS_STATUS = "materials.status"
    MATERIALS_GATHERED = "materials.gathered"
    # Duplicate materials parameters removed - use TARGET_RECIPE + knowledge base for all material lookups
    
    # Equipment gap analysis and slot selection parameters
    EQUIPMENT_GAP_ANALYSIS = "equipment.gap_analysis"
    SLOT_SELECTION_REASONING = "slot.selection_reasoning"
    
    # Combat context parameters - moved to Combat Context Parameters section
    
    # Workflow and subgoal parameters
    WORKFLOW_STEP = "workflow.step"
    
    # Action configuration parameters (flattened from action_config)
    ACTION_MAX_WEAPONS_TO_EVALUATE = "action.max.weapons.to.evaluate"
    ACTION_MAX_WEAPON_LEVEL_ABOVE_CHARACTER = "action.max.weapon.level.above.character"
    ACTION_MAX_WEAPON_LEVEL_BELOW_CHARACTER = "action.max.weapon.level.below.character"
    ACTION_WEAPON_STAT_WEIGHTS = "action.weapon.stat.weights"
    ACTION_CRAFTABILITY_SCORING = "action.craftability.scoring"
    ACTION_MAX_SKILL_CHECK_WEAPON_LEVEL = "action.max.skill.check.weapon.level"
    ACTION_MAX_SKILL_BLOCKED_CHECKS = "action.max.skill.blocked.checks"
    ACTION_BASIC_WEAPON_CODES = "action.basic.weapon.codes"
    ACTION_MAX_BASIC_WEAPON_LEVEL = "action.max.basic.weapon.level"
    
    
    # Legacy parameters with underscores converted to dots
    TRANSFORMATIONS_NEEDED = "transformations.needed"
    CHARACTER_X = "character.x"
    CHARACTER_Y = "character.y"
    ANALYSIS_RADIUS = "analysis.radius"
    MATERIAL_ANALYSIS = "material.analysis"
    SEARCH_RADIUS = "search.radius"
    LEVEL_RANGE = "level.range"
    TARGET_MONSTER = "target.monster"
    TARGET_X = "target.x"
    TARGET_Y = "target.y"
    ITEM_CODE = "item.code"
    TRANSFORMATIONS_COMPLETED = "transformations.completed"
    EQUIPMENT_TYPES = "equipment.types"
    CONFIG_DATA = "config.data"
    SUFFICIENT_MATERIALS = "sufficient.materials"
    TOTAL_REQUIREMENTS = "total.requirements"
    WORKSHOP_REQUIREMENTS = "workshop.requirements"
    CURRENT_GATHERING_GOAL = "current.gathering.goal"
    EQUIPMENT_STATUS = "equipment.status"
    SELECTED_RECIPE = "selected.recipe"
    UPGRADE_STATUS = "upgrade.status"
    REQUIRED_ITEMS = "required.items"
    QUANTITY = "item.quantity"
    REQUIRED_CRAFT_SKILL = "required.craft.skill"
    REQUIRED_CRAFT_LEVEL = "required.craft.level"
    REQUIRED_WORKSHOP_TYPE = "required.workshop.type"
    TARGET_CRAFT_SKILL = "target.craft.skill"
    TARGET_MATERIAL = "target.material"
    QUANTITY_NEEDED = "quantity.needed"
    LAST_TRANSFORMATION = "last.transformation"
    VERIFICATION_RESULTS = "verification.results"
    CURRENT_TRANSFORMATION_INDEX = "current.transformation.index"

    # Combat Context Parameters
    COMBAT_STATUS = "combat_context.status"
    COMBAT_TARGET = "combat_context.target"
    # COMBAT_LOCATION removed - use knowledge_base.get_combat_location(context) helper
    COMBAT_RECENT_WIN_RATE = "combat_context.recent_win_rate"
    COMBAT_LOW_WIN_RATE = "combat_context.low_win_rate"
    COMBAT_RECENT_LOSSES = "combat_context.recent_losses"
    COMBAT_RECENT_WINS = "combat_context.recent_wins"
    COMBAT_PRE_COMBAT_HP = "combat_context.pre_combat_hp"
    
    # Goal Progress Parameters
    GOAL_CURRENT_GOAL = "goal_progress.current_goal"
    GOAL_PHASE = "goal_progress.phase"
    GOAL_STEPS_COMPLETED = "goal_progress.steps_completed"
    GOAL_TOTAL_STEPS = "goal_progress.total_steps"
    GOAL_BLOCKED_BY = "goal_progress.blocked_by"
    GOAL_MONSTERS_HUNTED = "goal_progress.monsters_hunted"
    
    # Resource Availability Parameters
    RESOURCE_AVAILABILITY_MONSTERS = "resource_availability.monsters"
    RESOURCE_AVAILABILITY_RESOURCES = "resource_availability.resources"
    # RESOURCE_AT_RESOURCE_LOCATION removed - use knowledge_base.is_at_resource_location(context) helper
    RESOURCE_CODE = "resource_availability.code"
    RESOURCE_NAME = "resource_availability.name"
    
    # Skill Requirements Parameters
    SKILL_REQUIREMENTS_VERIFIED = "skill_requirements.verified"
    SKILL_REQUIREMENTS_SUFFICIENT = "skill_requirements.sufficient"
    
    # Skill Status Parameters
    SKILL_STATUS_CHECKED = "skill_status.checked"
    SKILL_STATUS_SUFFICIENT = "skill_status.sufficient"
    
    # Skills Parameters (dynamic - base template)
    SKILLS_DEFAULT_LEVEL = "skills._default_skill.level"
    SKILLS_DEFAULT_REQUIRED = "skills._default_skill.required"
    SKILLS_DEFAULT_XP = "skills._default_skill.xp"
    
    # Workshop Status Parameters
    WORKSHOP_DISCOVERED = "workshop_status.discovered"
    WORKSHOP_LOCATIONS = "workshop_status.locations"
    # WORKSHOP_AT_WORKSHOP removed - use knowledge_base.is_at_workshop(context) helper
    WORKSHOP_TYPE = "workshop_status.type"
    WORKSHOP_CODE = "workshop_status.code"
    # WORKSHOP_X/Y removed - use knowledge_base.get_workshop_locations() + TARGET_X/Y for movement
    WORKSHOP_REQUIREMENTS = "workshop_status.requirements"
    
    # Inventory Parameters
    INVENTORY_UPDATED = "inventory.updated"
    
    
    # Healing Context Parameters
    HEALING_NEEDED = "healing_context.healing_needed"
    HEALING_STATUS = "healing_context.healing_status"
    HEALING_METHOD = "healing_context.healing_method"
    
    @classmethod
    def get_all_parameters(cls) -> Set[str]:
        """
        Get all registered parameter names.
        
        Returns:
            Set of all parameter constant values
        """
        return {
            value for key, value in cls.__dict__.items()
            if isinstance(value, str) and not key.startswith('_')
        }
    
    @classmethod
    def validate_parameter(cls, param: str) -> bool:
        """
        Validate that a parameter is registered.
        
        Args:
            param: Parameter name to validate
            
        Returns:
            True if parameter is registered, False otherwise
        """
        return param in cls.get_all_parameters()
    
    @classmethod
    def get_parameters_by_category(cls, category: str) -> Set[str]:
        """
        Get parameters by category prefix.
        
        Args:
            category: Category prefix (e.g., 'equipment_status', 'character_status')
            
        Returns:
            Set of parameters matching the category
        """
        return {
            param for param in cls.get_all_parameters()
            if param.startswith(f"{category}.")
        }