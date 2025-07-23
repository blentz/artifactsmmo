"""
State Computation Manager

Specialized manager for computing derived values from available context data.
Follows architecture principle: specialized managers handle specific concerns.
Does not store calculable values - computes them on-demand from source data.
"""

import logging
from typing import Any, Dict, Optional

from src.lib.character_utils import (
    calculate_hp_percentage, 
    is_character_safe, 
    is_hp_critically_low, 
    is_hp_sufficient_for_combat
)


class StateComputationManager:
    """
    Specialized manager for computing derived state values on-demand.
    
    Handles all business logic for computing derived values from source data
    without storing calculable values in state.
    
    Single Responsibility: On-demand state computation only.
    """
    
    def __init__(self):
        """Initialize the state computation manager."""
        self.logger = logging.getLogger(__name__)
    
    def compute_character_flags(self, character_state) -> Dict[str, Any]:
        """
        Compute character-related derived flags from character data.
        
        Args:
            character_state: Character state with source data
            
        Returns:
            Dictionary of computed character flags
        """
        try:
            if not character_state or not hasattr(character_state, 'data'):
                return {}
            
            char_data = character_state.data
            level = char_data.get('level', 1)
            current_hp = char_data.get('hp', 100)
            max_hp = char_data.get('max_hp', 100)
            
            # Compute derived boolean flags using character utilities
            return {
                'hp_critically_low': is_hp_critically_low(current_hp, max_hp, 30.0),
                'hp_sufficient_for_combat': is_hp_sufficient_for_combat(current_hp, max_hp, 80.0),
                'is_low_level': level <= 5,
                'safe': is_character_safe(current_hp, max_hp, 30.0),
                'alive': current_hp > 0,
                'cooldown_active': self._is_cooldown_active(char_data),
                'hp_percentage': calculate_hp_percentage(current_hp, max_hp),
            }
            
        except Exception as e:
            self.logger.error(f"Failed to compute character flags: {e}")
            return {}
    
    def _is_cooldown_active(self, char_data: Dict[str, Any]) -> bool:
        """
        Determine if character is currently on cooldown.
        
        Args:
            char_data: Character data dictionary
            
        Returns:
            True if character is on cooldown, False otherwise
        """
        from datetime import datetime, timezone
        
        cooldown_expiration = char_data.get('cooldown_expiration')
        if cooldown_expiration is None:
            return False
            
        # Parse the datetime string and compare with current time
        expiry_time = datetime.fromisoformat(cooldown_expiration.replace('Z', '+00:00'))
        current_time = datetime.now(timezone.utc)
        return expiry_time > current_time
    
    def compute_equipment_flags(self, character_state) -> Dict[str, Any]:
        """
        Compute equipment-related derived flags from character data.
        
        Args:
            character_state: Character state with equipment data
            
        Returns:
            Dictionary of computed equipment flags
        """
        try:
            if not character_state or not hasattr(character_state, 'data'):
                return {}
                
            char_data = character_state.data
            weapon = char_data.get('weapon_slot', char_data.get('weapon', ''))
            
            # Count equipped armor pieces
            armor_slots = ['helmet_slot', 'body_armor_slot', 'leg_armor_slot', 'boots_slot']
            equipped_armor = sum(1 for slot in armor_slots if char_data.get(slot, ''))
            
            return {
                'has_weapon': weapon and weapon != 'wooden_stick',
                'weapon_equipped': bool(weapon),
                'armor_count': equipped_armor,
                'has_armor': equipped_armor > 0,
                'has_complete_armor': equipped_armor >= 4,
            }
            
        except Exception as e:
            self.logger.error(f"Failed to compute equipment flags: {e}")
            return {}
    
    def compute_combat_flags(self, knowledge_base, character_state) -> Dict[str, Any]:
        """
        Compute combat-related derived flags from knowledge base data.
        
        Args:
            knowledge_base: Knowledge base with combat history
            character_state: Character state for context
            
        Returns:
            Dictionary of computed combat flags
        """
        try:
            if not knowledge_base or not hasattr(knowledge_base, 'data'):
                return {'has_recent_combat': False, 'is_combat_viable': True}
            
            # Analyze recent combat data from knowledge base
            monsters_data = knowledge_base.data.get('monsters', {})
            total_combats = 0
            total_wins = 0
            
            for monster_data in monsters_data.values():
                combat_results = monster_data.get('combat_results', [])
                for result in combat_results[-10:]:  # Recent 10 combats
                    if result.get('result') in ['win', 'loss']:
                        total_combats += 1
                        if result.get('result') == 'win':
                            total_wins += 1
            
            win_rate = total_wins / total_combats if total_combats > 0 else 1.0
            
            return {
                'has_recent_combat': total_combats > 0,
                'recent_win_rate': win_rate,
                'is_combat_viable': win_rate >= 0.3,  # 30% minimum viable win rate
                'total_recent_combats': total_combats,
            }
            
        except Exception as e:
            self.logger.error(f"Failed to compute combat flags: {e}")
            return {'has_recent_combat': False, 'is_combat_viable': True}
    
    def compute_resource_flags(self, map_state) -> Dict[str, Any]:
        """
        Compute resource availability flags from map data.
        
        Args:
            map_state: Map state with resource/monster locations
            
        Returns:
            Dictionary of computed resource flags
        """
        try:
            if not map_state or not hasattr(map_state, 'data'):
                return {'monsters_available': False, 'resources_available': False}
            
            map_data = map_state.data
            
            return {
                'monsters_available': len(map_data.get('monsters', [])) > 0,
                'resources_available': len(map_data.get('resources', [])) > 0,
                'workshops_discovered': len(map_data.get('workshops', {})) > 0,
            }
            
        except Exception as e:
            self.logger.error(f"Failed to compute resource flags: {e}")
            return {'monsters_available': False, 'resources_available': False}