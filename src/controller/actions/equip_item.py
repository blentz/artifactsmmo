""" EquipItemAction module """

from typing import Dict, Optional
from artifactsmmo_api_client.api.my_characters.action_equip_item_my_name import sync as equip_api
from artifactsmmo_api_client.models.equip_schema import EquipSchema
from artifactsmmo_api_client.models.item_slot import ItemSlot
from .base import ActionBase


class EquipItemAction(ActionBase):
    """ Action to equip items from inventory to equipment slots """

    def __init__(self, character_name: str, item_code: str, slot: str, quantity: int = 1):
        """
        Initialize the equip item action.

        Args:
            character_name: Name of the character performing the action
            item_code: Code of the item to equip
            slot: Equipment slot to equip to (weapon, shield, helmet, etc.)
            quantity: Quantity to equip (default 1)
        """
        super().__init__()
        self.character_name = character_name
        self.item_code = item_code
        self.slot = slot
        self.quantity = quantity

    def execute(self, client, **kwargs) -> Optional[Dict]:
        """ Equip the specified item """
        if not self.validate_execution_context(client):
            return self.get_error_response("No API client provided")
            
        self.log_execution_start(
            character_name=self.character_name,
            item_code=self.item_code,
            slot=self.slot
        )
        
        try:
            # Convert slot name to ItemSlot enum
            item_slot = self._get_item_slot_enum(self.slot)
            if item_slot is None:
                error_response = self.get_error_response(f'Invalid equipment slot: {self.slot}')
                self.log_execution_result(error_response)
                return error_response
            
            # Prepare equip schema
            equip_schema = EquipSchema(
                code=self.item_code,
                slot=item_slot
            )
            
            # Perform the equip action
            equip_response = equip_api(
                name=self.character_name,
                client=client,
                body=equip_schema
            )
            
            if equip_response and equip_response.data:
                # Extract useful information from the response
                character_data = equip_response.data
                result = {
                    'success': True,
                    'item_code': self.item_code,
                    'slot': self.slot,
                    'character_name': self.character_name,
                    'equipped': True
                }
                
                # Add character data if available
                if hasattr(character_data, 'character'):
                    char_data = character_data.character
                    result['character_level'] = getattr(char_data, 'level', 0)
                    result['character_hp'] = getattr(char_data, 'hp', 0)
                    result['character_max_hp'] = getattr(char_data, 'max_hp', 0)
                    
                    # Add equipment status
                    result['weapon_slot'] = getattr(char_data, 'weapon_slot', '')
                    result['shield_slot'] = getattr(char_data, 'shield_slot', '')
                    result['helmet_slot'] = getattr(char_data, 'helmet_slot', '')
                    result['body_armor_slot'] = getattr(char_data, 'body_armor_slot', '')
                    result['leg_armor_slot'] = getattr(char_data, 'leg_armor_slot', '')
                    result['boots_slot'] = getattr(char_data, 'boots_slot', '')
                
                # Add cooldown information
                if hasattr(character_data, 'cooldown') and character_data.cooldown:
                    result['cooldown'] = getattr(character_data.cooldown, 'total_seconds', 0)
                else:
                    result['cooldown'] = 0
                
                self.log_execution_result(result)
                return result
            else:
                error_response = self.get_error_response('Equip action failed - no response data')
                self.log_execution_result(error_response)
                return error_response
                
        except Exception as e:
            error_response = self.get_error_response(f'Equip action failed: {str(e)}')
            self.log_execution_result(error_response)
            return error_response

    def _get_item_slot_enum(self, slot_name: str) -> Optional[ItemSlot]:
        """
        Convert a slot name string to ItemSlot enum.
        
        Args:
            slot_name: String name of the slot
            
        Returns:
            ItemSlot enum value or None if invalid
        """
        if not slot_name:
            return None
            
        # Normalize slot name to lowercase for comparison
        slot_lower = slot_name.lower()
        
        # Map common slot names to ItemSlot enum values
        slot_mapping = {
            'weapon': ItemSlot.WEAPON,
            'shield': ItemSlot.SHIELD,
            'helmet': ItemSlot.HELMET,
            'body_armor': ItemSlot.BODY_ARMOR,
            'body': ItemSlot.BODY_ARMOR,
            'chest': ItemSlot.BODY_ARMOR,
            'leg_armor': ItemSlot.LEG_ARMOR,
            'legs': ItemSlot.LEG_ARMOR,
            'boots': ItemSlot.BOOTS,
            'shoes': ItemSlot.BOOTS,
            'feet': ItemSlot.BOOTS,
            'ring1': ItemSlot.RING1,
            'ring2': ItemSlot.RING2,
            'amulet': ItemSlot.AMULET,
            'necklace': ItemSlot.AMULET,
            'artifact1': ItemSlot.ARTIFACT1,
            'artifact2': ItemSlot.ARTIFACT2,
            'artifact3': ItemSlot.ARTIFACT3,
            'utility1': ItemSlot.UTILITY1,
            'utility2': ItemSlot.UTILITY2,
            'bag': ItemSlot.BAG,
            'rune': ItemSlot.RUNE
        }
        
        return slot_mapping.get(slot_lower)

    def __repr__(self):
        return f"EquipItemAction({self.character_name}, {self.item_code}, {self.slot}, qty={self.quantity})"