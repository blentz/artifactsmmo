"""
Equipment Goal Implementation

This module implements intelligent equipment acquisition and management goals that
acquire and equip level-appropriate gear (level ≤ 5) using data-driven item analysis
and strategic equipment evaluation without hardcoded item codes or stat values.
"""

from typing import Any

from ..analysis.map_analysis import MapAnalysisModule
from ..state.character_game_state import CharacterGameState
from ..state.game_state import GameState
from src.game_data.game_data import GameData
from ..types.goap_models import GOAPTargetState
from .base_goal import BaseGoal
from .sub_goal_request import SubGoalRequest


class EquipmentGoal(BaseGoal):
    """Intelligent equipment goal for level-appropriate gear acquisition.

    This goal implements strategic equipment management using data-driven analysis
    to acquire and equip level-appropriate gear (item.level ≤ 5) for optimal
    character progression and combat effectiveness.
    """

    def __init__(self, target_slot: str | None = None, max_item_level: int = 5):
        """Initialize equipment goal with optional target specification.

        Parameters:
            target_slot: Optional specific equipment slot to focus on
            max_item_level: Maximum item level to consider (default 5 for progression goal)
        """
        self.target_slot = target_slot
        self.max_item_level = max_item_level
        self.map_analysis = MapAnalysisModule()

        # Define equipment slots for level 5 progression goal
        self.equipment_slots = {
            "weapon": "weapon_slot",
            "helmet": "helmet_slot",
            "body_armor": "body_armor_slot",
            "leg_armor": "leg_armor_slot",
            "boots": "boots_slot",
            "ring1": "ring1_slot",
            "ring2": "ring2_slot",
            "amulet": "amulet_slot",
        }

    def calculate_weight(self, character_state: CharacterGameState, game_data: GameData) -> float:
        """Calculate equipment goal weight using multi-factor scoring.

        This method implements the PRP requirement for weighted scoring:
        - Necessity (40%): Equipment gaps that hinder progression
        - Feasibility (30%): Items available and accessible to character
        - Progression Value (20%): Direct contribution to level 5 with appropriate gear
        - Stability (10%): Low error risk with predictable equipment upgrades
        """
        self.validate_game_data(game_data)

        # Calculate necessity (40% weight)
        necessity = self._calculate_equipment_necessity(character_state, game_data)

        # Calculate feasibility (30% weight)
        feasibility = self._calculate_equipment_feasibility(character_state, game_data)

        # Calculate progression value (20% weight)
        progression = self.get_progression_value(character_state, game_data)

        # Calculate stability (10% weight) - equipment upgrades are generally stable
        stability = 0.85  # High stability - equipment acquisition has predictable outcomes

        # Combine factors with PRP-specified weights
        final_weight = necessity * 0.4 + feasibility * 0.3 + progression * 0.2 + stability * 0.1

        return min(10.0, final_weight * 10.0)  # Scale to 0-10 range

    def is_feasible(self, character_state: CharacterGameState, game_data: GameData) -> bool:
        """Check if equipment goal can be pursued with current character state."""
        self.validate_game_data(game_data)

        # Check if there are level-appropriate equipment upgrades available
        available_upgrades = self._find_available_equipment_upgrades(character_state, game_data)

        return len(available_upgrades) > 0

    def get_target_state(self, character_state: CharacterGameState, game_data: GameData) -> GOAPTargetState:
        """Return GOAP target state for equipment goal.

        This method defines the desired state conditions for successful equipment acquisition:
        1. Character must have optimal equipment for their level
        2. Equipment must be properly equipped in appropriate slots
        3. Equipment must be level-appropriate (≤ max_item_level)
        4. Character combat effectiveness must be improved
        """
        self.validate_game_data(game_data)

        # Find optimal equipment upgrade
        target_equipment = self._select_optimal_equipment_upgrade(character_state, game_data)
        if not target_equipment:
            # Return empty target state if no equipment upgrades needed
            return GOAPTargetState(target_states={}, priority=1, timeout_seconds=None)

        # Define target state conditions for equipment success
        target_states = {
            # Must have better equipment equipped
            GameState.READY_FOR_UPGRADE: False,  # Should no longer need upgrades
            GameState.HAS_REQUIRED_ITEMS: True,  # Must have the target equipment
            # Equipment-specific states based on target slot
            GameState.WEAPON_EQUIPPED: True,
            GameState.HELMET_EQUIPPED: True,
            GameState.BODY_ARMOR_EQUIPPED: True,
            GameState.LEG_ARMOR_EQUIPPED: True,
            GameState.BOOTS_EQUIPPED: True,
            GameState.RING1_EQUIPPED: True,
            GameState.RING2_EQUIPPED: True,
            GameState.AMULET_EQUIPPED: True,
            # Inventory management
            GameState.INVENTORY_SPACE_AVAILABLE: True,
            # Action readiness
            GameState.COOLDOWN_READY: True,
        }

        return GOAPTargetState(
            target_states=target_states,
            priority=5,  # Medium priority - supports other goals
            timeout_seconds=1800,  # 30 minute timeout for equipment acquisition chains
        )

    def get_progression_value(self, character_state: CharacterGameState, game_data: GameData) -> float:
        """Calculate contribution to reaching level 5 with appropriate gear."""
        # Equipment directly contributes to the primary success criteria:
        # "Level 5 with all equipment slots filled with level ≤ 5 items"

        current_level = character_state.level
        equipment_coverage = self._calculate_equipment_coverage(character_state)

        # High progression value - equipment is core to the success criteria
        base_progression = 0.8

        # Higher value if character is close to level 5 but lacks equipment
        if current_level >= 4 and equipment_coverage < 0.7:
            return 0.9

        # Moderate value if character needs equipment for current level
        level_appropriate_coverage = self._calculate_level_appropriate_coverage(character_state, game_data)
        coverage_factor = 1.0 - level_appropriate_coverage

        return min(1.0, base_progression + coverage_factor * 0.2)

    def estimate_error_risk(self, character_state: CharacterGameState) -> float:
        """Estimate equipment-specific error risk."""
        # Equipment acquisition generally has low error risk
        base_risk = 0.15

        # Increase risk if character lacks gold for purchases
        gold_risk = 0.0
        if character_state.gold < 100:  # Arbitrary threshold
            gold_risk += 0.1

        # Increase risk if inventory is nearly full
        inventory_risk = 0.0
        if hasattr(character_state, "inventory_space_count") and character_state.inventory_space_count < 3:
            inventory_risk += 0.15

        return min(1.0, base_risk + gold_risk + inventory_risk)

    def generate_sub_goal_requests(
        self, character_state: CharacterGameState, game_data: GameData
    ) -> list[SubGoalRequest]:
        """Generate sub-goal requests for equipment acquisition dependencies."""
        sub_goals: list[SubGoalRequest] = []

        # Find target equipment
        target_equipment = self._select_optimal_equipment_upgrade(character_state, game_data)
        if not target_equipment:
            return sub_goals

        item, acquisition_method = target_equipment

        # Generate sub-goals based on acquisition method
        if acquisition_method == "monster_drop":
            # Find monsters that drop this item
            dropping_monsters = self._find_monsters_dropping_item(item.code, game_data)
            if dropping_monsters:
                # Request combat for item acquisition
                monster, _ = dropping_monsters[0]
                sub_goals.append(
                    SubGoalRequest(
                        goal_type="combat_for_item",
                        parameters={"target_monster": monster.code, "target_item": item.code},
                        priority=7,
                        requester="EquipmentGoal",
                        reason=f"Fight {monster.name} for {item.name}",
                    )
                )

        elif acquisition_method == "crafting":
            # Request crafting for this item
            sub_goals.append(
                SubGoalRequest(
                    goal_type="craft_item",
                    parameters={"item_code": item.code},
                    priority=6,
                    requester="EquipmentGoal",
                    reason=f"Craft {item.name} for equipment upgrade",
                )
            )

        elif acquisition_method == "npc_purchase":
            # Find NPC that sells this item
            selling_npcs = self._find_npcs_selling_item(item.code, game_data)
            if selling_npcs:
                npc = selling_npcs[0]
                # Request movement to NPC location
                npc_locations = self.map_analysis.find_content_by_code("npc", npc.code, game_data.maps)
                if npc_locations:
                    target_npc_location = npc_locations[0]
                    sub_goals.append(
                        SubGoalRequest.move_to_location(
                            target_npc_location.x,
                            target_npc_location.y,
                            "EquipmentGoal",
                            f"Move to {npc.name} to buy {item.name}",
                        )
                    )

        # Request inventory space if needed
        if hasattr(character_state, "inventory_space_count") and character_state.inventory_space_count < 2:
            sub_goals.append(
                SubGoalRequest(
                    goal_type="manage_inventory",
                    parameters={"required_space": 2},
                    priority=5,
                    requester="EquipmentGoal",
                    reason="Need inventory space for equipment acquisition",
                )
            )

        return sub_goals

    def _find_available_equipment_upgrades(
        self, character_state: CharacterGameState, game_data: GameData
    ) -> list[tuple[Any, str, str]]:
        """Find available equipment upgrades using real item data."""
        upgrades = []

        # Filter items to level-appropriate equipment
        level_appropriate_equipment = [
            item
            for item in game_data.items
            if (
                item.level <= self.max_item_level
                and item.type in ["weapon", "helmet", "body_armor", "leg_armor", "boots", "ring", "amulet"]
            )
        ]

        # Check each equipment slot for potential upgrades
        for slot_name, slot_attr in self.equipment_slots.items():
            if self.target_slot and slot_name != self.target_slot:
                continue

            current_item_code = getattr(character_state, slot_attr, None)
            current_item_level = 0

            # If character has equipment in this slot, look up its level from game data
            if current_item_code:
                current_item_obj = next((item for item in game_data.items if item.code == current_item_code), None)
                if current_item_obj:
                    current_item_level = current_item_obj.level

            # Find better items for this slot
            slot_items = [item for item in level_appropriate_equipment if self._item_fits_slot(item, slot_name)]

            for item in slot_items:
                if item.level > current_item_level:
                    acquisition_method = self._determine_acquisition_method(item, character_state, game_data)
                    if acquisition_method:
                        upgrades.append((item, slot_name, acquisition_method))

        return upgrades

    def _select_optimal_equipment_upgrade(
        self, character_state: CharacterGameState, game_data: GameData
    ) -> tuple[Any, str] | None:
        """Select the optimal equipment upgrade based on character needs."""
        available_upgrades = self._find_available_equipment_upgrades(character_state, game_data)

        if not available_upgrades:
            return None

        # Score upgrades by value
        scored_upgrades = []
        for upgrade_info in available_upgrades:
            item, slot, method = upgrade_info
            score = self._score_equipment_upgrade(item, slot, method, character_state)
            scored_upgrades.append((item, method, score))

        # Return highest scoring upgrade
        scored_upgrades.sort(key=lambda x: x[2], reverse=True)
        if scored_upgrades:
            return (scored_upgrades[0][0], scored_upgrades[0][1])

        return None

    def _score_equipment_upgrade(self, item: Any, slot: str, method: str, character_state: CharacterGameState) -> float:
        """Score equipment upgrade value for prioritization."""
        score = 0.0

        # Prefer higher level items (within the level 5 constraint)
        level_score = item.level / self.max_item_level
        score += level_score * 0.3

        # Prefer items for empty slots
        slot_attr = self.equipment_slots.get(slot)
        if slot_attr and not getattr(character_state, slot_attr, None):
            score += 0.4  # High bonus for filling empty slots

        # Prefer items with good acquisition methods
        method_scores = {
            "npc_purchase": 0.3,  # Most reliable
            "crafting": 0.2,  # Moderately reliable
            "monster_drop": 0.1,  # Least reliable
        }
        score += method_scores.get(method, 0.0)

        # Prefer items appropriate for character level
        level_appropriateness = max(0.0, 1.0 - abs(item.level - character_state.level) / 3.0)
        score += level_appropriateness * 0.2

        return score

    def _calculate_equipment_necessity(self, character_state: CharacterGameState, game_data: GameData) -> float:
        """Calculate how necessary equipment upgrades are for progression."""
        # High necessity for empty equipment slots
        equipment_coverage = self._calculate_equipment_coverage(character_state)
        coverage_necessity = 1.0 - equipment_coverage

        # Higher necessity if character level is high but equipment is low-level
        level_equipment_gap = self._calculate_level_equipment_gap(character_state, game_data)

        return min(1.0, coverage_necessity * 0.6 + level_equipment_gap * 0.4)

    def _calculate_equipment_feasibility(self, character_state: CharacterGameState, game_data: GameData) -> float:
        """Calculate equipment acquisition feasibility score."""
        feasibility_score = 0.0

        # Item availability (40% of feasibility)
        available_upgrades = self._find_available_equipment_upgrades(character_state, game_data)
        item_availability = min(1.0, len(available_upgrades) / 5.0)  # Normalize
        feasibility_score += item_availability * 0.4

        # Economic feasibility (30% of feasibility)
        gold_score = min(1.0, character_state.gold / 1000.0)  # Normalize to 1000 gold
        feasibility_score += gold_score * 0.3

        # Inventory space (20% of feasibility)
        inventory_score = 1.0
        if hasattr(character_state, "inventory_space_available"):
            inventory_score = min(1.0, character_state.inventory_space_available / 5.0)
        feasibility_score += inventory_score * 0.2

        # Character level appropriateness (10% of feasibility)
        level_score = min(1.0, character_state.level / 5.0)  # Normalize to level 5
        feasibility_score += level_score * 0.1

        return min(1.0, feasibility_score)

    def _calculate_equipment_coverage(self, character_state: CharacterGameState) -> float:
        """Calculate what percentage of equipment slots are filled."""
        equipped_slots = 0
        total_slots = len(self.equipment_slots)

        for slot_name, slot_attr in self.equipment_slots.items():
            if getattr(character_state, slot_attr, None):
                equipped_slots += 1

        return equipped_slots / total_slots

    def _calculate_level_appropriate_coverage(self, character_state: CharacterGameState, game_data: GameData) -> float:
        """Calculate coverage of level-appropriate equipment."""
        appropriate_slots = 0
        total_slots = len(self.equipment_slots)

        for slot_name, slot_attr in self.equipment_slots.items():
            equipped_item_code = getattr(character_state, slot_attr, None)
            if equipped_item_code:
                # Look up item in game data to check its level
                equipped_item = next((item for item in game_data.items if item.code == equipped_item_code), None)
                if equipped_item and equipped_item.level <= self.max_item_level:
                    appropriate_slots += 1

        return appropriate_slots / total_slots

    def _calculate_level_equipment_gap(self, character_state: CharacterGameState, game_data: GameData) -> float:
        """Calculate gap between character level and equipment levels."""
        equipment_levels = []

        for slot_name, slot_attr in self.equipment_slots.items():
            equipped_item_code = getattr(character_state, slot_attr, None)
            if equipped_item_code:
                # Look up item in game data to get its level
                equipped_item = next((item for item in game_data.items if item.code == equipped_item_code), None)
                if equipped_item:
                    equipment_levels.append(equipped_item.level)
                else:
                    equipment_levels.append(1)  # Assume level 1 for unknown items
            else:
                equipment_levels.append(1)  # Assume level 1 for empty slots

        if not equipment_levels:
            return 1.0  # Maximum gap if no equipment

        avg_equipment_level = sum(equipment_levels) / len(equipment_levels)
        level_gap = max(0.0, character_state.level - avg_equipment_level)

        return min(1.0, level_gap / 3.0)  # Normalize to maximum gap of 3

    def _item_fits_slot(self, item: Any, slot_name: str) -> bool:
        """Check if item fits the specified equipment slot."""
        slot_type_mapping = {
            "weapon": ["weapon"],
            "helmet": ["helmet"],
            "body_armor": ["body_armor", "chest"],
            "leg_armor": ["leg_armor", "legs"],
            "boots": ["boots"],
            "ring1": ["ring"],
            "ring2": ["ring"],
            "amulet": ["amulet"],
        }

        accepted_types = slot_type_mapping.get(slot_name, [])
        return item.type in accepted_types

    def _determine_acquisition_method(
        self, item: Any, character_state: CharacterGameState, game_data: GameData
    ) -> str | None:
        """Determine how this item can be acquired."""
        # Check if item is craftable
        if item.craft:
            return "crafting"

        # Check if NPCs sell this item (simplified)
        if self._find_npcs_selling_item(item.code, game_data):
            return "npc_purchase"

        # Check if monsters drop this item
        if self._find_monsters_dropping_item(item.code, game_data):
            return "monster_drop"

        return None

    def _find_npcs_selling_item(self, item_code: str, game_data: GameData) -> list[Any]:
        """Find NPCs that sell the specified item."""
        # Simplified implementation - would need actual NPC inventory data
        return []

    def _find_monsters_dropping_item(self, item_code: str, game_data: GameData) -> list[Any]:
        """Find monsters that drop the specified item."""
        dropping_monsters = []

        for monster in game_data.monsters:
            for drop in monster.drops:
                if isinstance(drop, dict) and drop.get("code") == item_code:
                    dropping_monsters.append((monster, drop))

        return dropping_monsters
