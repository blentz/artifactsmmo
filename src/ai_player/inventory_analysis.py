"""
Inventory Analysis

This module contains the ItemAnalyzer class for analyzing items to determine
their value and priority for inventory management decisions.
"""

from typing import Any

from .inventory_models import ItemInfo, ItemPriority
from .state.game_state import GameState


class ItemAnalyzer:
    """Analyzes items to determine their value and priority"""

    def __init__(self, economic_intelligence=None, task_manager=None):
        self.economic_intelligence = economic_intelligence
        self.task_manager = task_manager
        self.item_cache = {}

    def analyze_item_priority(self, item: ItemInfo, character_state: dict[GameState, Any]) -> ItemPriority:
        """Determine item priority based on current character state and goals.

        Parameters:
            item: ItemInfo object containing item details and metadata
            character_state: Dictionary with GameState enum keys and current values

        Return values:
            ItemPriority enum indicating item importance for current objectives

        This method analyzes an item's relevance to current character goals,
        active tasks, and progression needs to assign appropriate priority
        for inventory management and resource allocation decisions.
        """
        character_level = character_state.get(GameState.CHARACTER_LEVEL, 1)
        hp_current = character_state.get(GameState.HP_CURRENT, 100)
        hp_max = character_state.get(GameState.HP_MAX, 100)
        active_task = character_state.get(GameState.ACTIVE_TASK)

        # Critical priority items
        # 1. Equipment upgrades when no equipment equipped
        if item.type in ["weapon", "helmet", "body_armor", "leg_armor", "boots", "ring", "amulet"]:
            equipped_key = f"{item.type.upper()}_EQUIPPED"
            if item.type == "body_armor":
                equipped_key = "BODY_ARMOR_EQUIPPED"
            elif item.type == "leg_armor":
                equipped_key = "LEG_ARMOR_EQUIPPED"

            # Check if no equipment in this slot
            current_equipment = character_state.get(getattr(GameState, equipped_key, None))
            if current_equipment is None and item.level <= character_level + 5:
                return ItemPriority.CRITICAL

            # Equipment significantly better than current level
            if item.level > character_level + 10:
                return ItemPriority.HIGH

        # 2. Task-required items
        if self.task_manager and active_task:
            character_name = character_state.get("character_name", "")
            if self.is_item_needed_for_tasks(item.code, character_name):
                return ItemPriority.CRITICAL

        # High priority items
        # 1. Consumables when HP is low
        if item.consumable and item.type == "consumable":
            hp_percentage = (hp_current / hp_max) * 100 if hp_max > 0 else 100
            if hp_percentage < 50:  # Low HP threshold
                return ItemPriority.HIGH

        # 2. Valuable items (high market or base value)
        item_value = item.market_value or item.value
        if item_value >= 100:  # Valuable threshold
            return ItemPriority.HIGH

        # Junk items - very low value or way above character level
        if item_value < 5 or item.level > character_level + 20:
            return ItemPriority.JUNK

        # 3. Crafting materials needed for current goals
        if item.craftable or (item.type == "resource" and item.level <= character_level + 10):
            return ItemPriority.MEDIUM

        # Low priority - items that might be useful later
        if item.level <= character_level + 5 and item_value >= 10:
            return ItemPriority.LOW

        # Default to medium priority for unclassified items
        return ItemPriority.MEDIUM

    def calculate_item_utility(self, item: ItemInfo, character_state: dict[GameState, Any]) -> float:
        """Calculate utility score for item.

        Parameters:
            item: ItemInfo object containing item details and metadata
            character_state: Dictionary with GameState enum keys and current values

        Return values:
            Float representing item utility score (0.0 to 1.0)

        This method calculates a numerical utility score for an item based
        on its value for current tasks, economic potential, and character
        progression needs, enabling quantitative inventory optimization.
        """
        # Base utility score
        utility_score = 0.0

        # Get character information
        character_level = character_state.get(GameState.CHARACTER_LEVEL, 1)
        character_name = character_state.get("character_name", "")
        hp_current = character_state.get(GameState.HP_CURRENT, 100)
        hp_max = character_state.get(GameState.HP_MAX, 100)

        # 1. Task relevance (highest weight: 0.4)
        if self.is_item_needed_for_tasks(item.code, character_name):
            utility_score += 0.4

        # 2. Economic value (weight: 0.25)
        item_value = item.market_value or item.value
        # Normalize value to 0-1 scale (assuming max reasonable value of 1000)
        normalized_value = min(item_value / 1000.0, 1.0)
        utility_score += normalized_value * 0.25

        # 3. Level appropriateness (weight: 0.15)
        level_diff = abs(item.level - character_level)
        if level_diff <= 5:
            # Item is appropriate for current level
            level_score = 1.0 - (level_diff / 10.0)  # Higher score for closer levels
        elif item.level > character_level:
            # Future upgrade potential
            level_score = max(0.0, 0.5 - (level_diff - 5) / 20.0)
        else:
            # Outdated equipment
            level_score = max(0.0, 0.3 - (level_diff - 5) / 20.0)
        utility_score += level_score * 0.15

        # 4. Equipment upgrade potential (weight: 0.1)
        if self.is_item_equipment_upgrade(item, character_state):
            utility_score += 0.1

        # 5. Health utility for consumables (weight: 0.05)
        if item.consumable and item.type == "consumable":
            hp_percentage = (hp_current / hp_max) * 100 if hp_max > 0 else 100
            if hp_percentage < 75:  # More valuable when health is low
                health_urgency = (75 - hp_percentage) / 75.0
                utility_score += health_urgency * 0.05

        # 6. Crafting material value (weight: 0.05)
        if self.is_item_needed_for_crafting(item.code, character_state):
            utility_score += 0.05

        # Ensure score is within bounds
        return max(0.0, min(1.0, utility_score))

    def is_item_needed_for_tasks(self, item_code: str, character_name: str) -> bool:
        """Check if item is needed for active or available tasks.

        Parameters:
            item_code: Item identifier code to check requirements for
            character_name: Name of the character to check task requirements

        Return values:
            Boolean indicating whether item is required for character tasks

        This method checks if an item is required for the character's active
        tasks or upcoming task objectives, preventing accidental disposal
        of items needed for quest completion or progression.
        """
        if not self.task_manager:
            return False

        try:
            # Check if task manager has a method to check item requirements
            if hasattr(self.task_manager, 'is_item_needed_for_tasks'):
                return self.task_manager.is_item_needed_for_tasks(item_code, character_name)

            # Fallback: check if item is mentioned in active task data
            if hasattr(self.task_manager, 'get_active_task'):
                active_task = self.task_manager.get_active_task(character_name)
                if active_task and hasattr(active_task, 'requirements'):
                    # Check if item is in task requirements
                    for requirement in active_task.requirements:
                        if hasattr(requirement, 'code') and requirement.code == item_code:
                            return True
                        if hasattr(requirement, 'item') and requirement.item == item_code:
                            return True

            return False
        except Exception:
            # If task manager interaction fails, err on the side of caution
            return False

    def is_item_needed_for_crafting(self, item_code: str, character_state: dict[GameState, Any]) -> bool:
        """Check if item is needed for crafting progression"""
        # Check with economic intelligence if available
        if self.economic_intelligence and hasattr(self.economic_intelligence, 'is_item_needed_for_crafting'):
            try:
                return self.economic_intelligence.is_item_needed_for_crafting(item_code, character_state)
            except Exception:
                pass

        # Fallback: basic heuristics for common crafting materials
        crafting_materials = {
            # Common resource types that are typically used in crafting
            "copper_ore", "iron_ore", "gold_ore", "coal",
            "ash_wood", "spruce_wood", "birch_wood",
            "dead_fish", "shrimp", "trout", "salmon",
            "wolf_hair", "feather", "cowhide", "yellow_slimeball",
            # Common crafted materials
            "copper", "iron", "steel", "gold",
            "copper_ring", "iron_ring", "gold_ring",
            "wooden_staff", "iron_sword", "copper_sword"
        }

        # Check if item is a known crafting material
        if item_code in crafting_materials:
            return True

        # Check if item name/code suggests it's a resource
        if any(keyword in item_code.lower() for keyword in ["ore", "wood", "log", "hide", "bone", "feather", "scale"]):
            return True

        # Check character level - lower level characters need more basic materials
        character_level = character_state.get(GameState.CHARACTER_LEVEL, 1)
        if character_level < 10:
            # Low level characters benefit from most materials
            basic_materials = ["copper", "ash", "dead", "cowhide", "feather"]
            if any(material in item_code.lower() for material in basic_materials):
                return True

        return False

    def is_item_equipment_upgrade(self, item: ItemInfo, character_state: dict[GameState, Any]) -> bool:
        """Check if item is an equipment upgrade"""
        # Only check equipment types
        equipment_types = ["weapon", "helmet", "body_armor", "leg_armor", "boots", "ring", "amulet"]
        if item.type not in equipment_types:
            return False

        # Map item types to GameState equipment slots
        equipment_mapping = {
            "weapon": "WEAPON_EQUIPPED",
            "helmet": "HELMET_EQUIPPED",
            "body_armor": "BODY_ARMOR_EQUIPPED",
            "leg_armor": "LEG_ARMOR_EQUIPPED",
            "boots": "BOOTS_EQUIPPED",
            "ring": "RING1_EQUIPPED",  # Could also be RING2_EQUIPPED
            "amulet": "AMULET_EQUIPPED"
        }

        equipment_key = equipment_mapping.get(item.type)
        if not equipment_key:
            return False

        # Get currently equipped item
        try:
            current_equipment = character_state.get(getattr(GameState, equipment_key, None))
        except AttributeError:
            current_equipment = None

        # If no equipment in slot, any appropriate item is an upgrade
        if current_equipment is None:
            character_level = character_state.get(GameState.CHARACTER_LEVEL, 1)
            # Only consider upgrade if item level is reasonable for character
            return item.level <= character_level + 10

        # If current equipment exists, compare levels
        if hasattr(current_equipment, 'level'):
            current_level = current_equipment.level
        elif isinstance(current_equipment, dict):
            current_level = current_equipment.get('level', 0)
        else:
            # If we can't determine current level, assume any higher level item is better
            character_level = character_state.get(GameState.CHARACTER_LEVEL, 1)
            return item.level > character_level // 2  # Conservative estimate

        # Item is upgrade if it's higher level than current equipment
        # Also check that the upgrade isn't too far ahead for character level
        character_level = character_state.get(GameState.CHARACTER_LEVEL, 1)
        is_higher_level = item.level > current_level
        is_reasonable_level = item.level <= character_level + 10

        return is_higher_level and is_reasonable_level

    def calculate_opportunity_cost(self, item: ItemInfo, alternative_items: list[ItemInfo]) -> float:
        """Calculate opportunity cost of keeping item vs alternatives"""
        pass

    def get_item_market_data(self, item_code: str) -> dict[str, Any] | None:
        """Get current market data for item"""
        pass

    def predict_item_value_trend(self, item_code: str) -> str:
        """Predict if item value will rise, fall, or stay stable"""
        pass
