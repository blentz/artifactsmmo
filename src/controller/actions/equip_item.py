""" EquipItemAction module """

from typing import Dict, Optional

from artifactsmmo_api_client.api.my_characters.action_equip_item_my_name_action_equip_post import sync as equip_api
from artifactsmmo_api_client.models.equip_schema import EquipSchema
from artifactsmmo_api_client.models.item_slot import ItemSlot

from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters

from .base import ActionBase, ActionResult


class EquipItemAction(ActionBase):
    """ Action to equip items from inventory to equipment slots """

    # GOAP parameters
    conditions = {
        'equipment_status': {
            'item_crafted': True,
            'equipped': False
        },
        'character_status': {
            'alive': True,
            'cooldown_active': False
        }
    }
    reactions = {
        'equipment_status': {
            'equipped': True,
            'upgrade_status': 'completed'
        }
    }
    weight = 2

    def __init__(self):
        """
        Initialize the equip item action.
        """
        super().__init__()

    def execute(self, client, context: ActionContext) -> ActionResult:
        """ Equip the specified item """
        # Get parameters from context
        character_name = context.get(StateParameters.CHARACTER_NAME)
        item_code = context.get('item_code')
        slot = context.get('slot')
        quantity = context.get('quantity', 1)
        
        if not item_code:
            return self.create_error_result("No item code provided")
        if not slot:
            return self.create_error_result("No slot provided")
            
        self._context = context
        
        try:
            # Convert slot name to ItemSlot enum
            item_slot = self._get_item_slot_enum(slot)
            if item_slot is None:
                return self.create_error_result(f'Invalid equipment slot: {slot}')
            
            # Prepare equip schema
            equip_schema = EquipSchema(
                code=item_code,
                slot=item_slot
            )
            
            # Perform the equip action
            equip_response = equip_api(
                name=character_name,
                client=client,
                body=equip_schema
            )
            
            if equip_response and equip_response.data:
                # Extract useful information from the response
                character_data = equip_response.data
                # Extract useful information from the response
                result_data = {
                    'item_code': item_code,
                    'slot': slot,
                    'character_name': character_name,
                    'equipped': True
                }
                
                # Add character data if available
                if hasattr(character_data, 'character'):
                    char_data = character_data.character
                    result_data['character_level'] = getattr(char_data, 'level', 0)
                    result_data['character_hp'] = getattr(char_data, 'hp', 0)
                    result_data['character_max_hp'] = getattr(char_data, 'max_hp', 0)
                    
                    # Add equipment status
                    result_data['weapon_slot'] = getattr(char_data, 'weapon_slot', '')
                    result_data['shield_slot'] = getattr(char_data, 'shield_slot', '')
                    result_data['helmet_slot'] = getattr(char_data, 'helmet_slot', '')
                    result_data['body_armor_slot'] = getattr(char_data, 'body_armor_slot', '')
                    result_data['leg_armor_slot'] = getattr(char_data, 'leg_armor_slot', '')
                    result_data['boots_slot'] = getattr(char_data, 'boots_slot', '')
                
                # Add cooldown information
                if hasattr(character_data, 'cooldown') and character_data.cooldown:
                    result_data['cooldown'] = getattr(character_data.cooldown, 'total_seconds', 0)
                else:
                    result_data['cooldown'] = 0
                
                return self.create_success_result(**result_data)
            else:
                return self.create_error_result('Equip action failed - no response data')
                
        except Exception as e:
            return self.create_error_result(f'Equip action failed: {str(e)}')

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
        return "EquipItemAction()"