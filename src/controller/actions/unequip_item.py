""" UnequipItemAction module """

from typing import Dict, Optional
from artifactsmmo_api_client.api.my_characters.action_unequip_item_my_name import sync as unequip_api
from artifactsmmo_api_client.models.unequip_schema import UnequipSchema
from artifactsmmo_api_client.models.item_slot import ItemSlot
from .base import ActionBase


class UnequipItemAction(ActionBase):
    """ Action to unequip an item from a specific equipment slot to inventory """

    def __init__(self, character_name: str, slot: str, quantity: int = 1):
        """
        Initialize the unequip item action.

        Args:
            character_name: Name of the character performing the action
            slot: Equipment slot to unequip from (e.g., 'weapon', 'helmet', 'body_armor')
            quantity: Quantity to unequip (applicable to utilities only, default=1)
        """
        super().__init__()
        self.character_name = character_name
        self.slot = slot
        self.quantity = quantity

    def execute(self, client, **kwargs) -> Optional[Dict]:
        """ Unequip an item from the specified equipment slot to inventory """
        if not self.validate_execution_context(client):
            return self.get_error_response("No API client provided")
            
        self.log_execution_start(
            character_name=self.character_name, 
            slot=self.slot,
            quantity=self.quantity
        )
        
        try:
            # Validate slot name and convert to ItemSlot enum
            slot_enum = self._get_item_slot_enum(self.slot)
            if not slot_enum:
                error_response = self.get_error_response(
                    f"Invalid equipment slot: {self.slot}",
                    valid_slots=list(ItemSlot)
                )
                self.log_execution_result(error_response)
                return error_response
            
            # Create the unequip schema
            unequip_request = UnequipSchema(
                slot=slot_enum,
                quantity=self.quantity
            )
            
            # Make the API call to unequip the item
            unequip_response = unequip_api(name=self.character_name, body=unequip_request, client=client)
            
            if unequip_response and unequip_response.data:
                # Extract useful information from the response
                data = unequip_response.data
                result = self.get_success_response(
                    slot=self.slot,
                    quantity=self.quantity,
                    cooldown=getattr(data.cooldown, 'total_seconds', 0) if hasattr(data, 'cooldown') else 0
                )
                
                # Add character data if available
                if hasattr(data, 'character'):
                    char_data = data.character
                    result['character_level'] = getattr(char_data, 'level', 0)
                    result['character_hp'] = getattr(char_data, 'hp', 0)
                    result['character_max_hp'] = getattr(char_data, 'max_hp', 0)
                
                # Add item data if available (the item that was unequipped)
                if hasattr(data, 'item'):
                    item_data = data.item
                    result['unequipped_item_code'] = getattr(item_data, 'code', '')
                    result['unequipped_item_name'] = getattr(item_data, 'name', '')
                    result['unequipped_item_type'] = getattr(item_data, 'type', '')
                    result['unequipped_item_level'] = getattr(item_data, 'level', 0)
                
                # Add equipment slot information
                if hasattr(data, 'slot'):
                    result['unequipped_slot'] = str(data.slot)
                
                self.log_execution_result(result)
                return result
            else:
                error_response = self.get_error_response('Unequip action failed - no response data')
                self.log_execution_result(error_response)
                return error_response
                
        except Exception as e:
            error_response = self.get_error_response(f'Unequip action failed: {str(e)}')
            self.log_execution_result(error_response)
            return error_response

    def _get_item_slot_enum(self, slot_name: str) -> Optional[ItemSlot]:
        """
        Convert a slot name string to the corresponding ItemSlot enum.
        
        Args:
            slot_name: The slot name as a string
            
        Returns:
            ItemSlot enum value or None if invalid
        """
        # Handle common slot name variations
        slot_mapping = {
            'weapon': ItemSlot.WEAPON,
            'helmet': ItemSlot.HELMET,
            'body_armor': ItemSlot.BODY_ARMOR,
            'body': ItemSlot.BODY_ARMOR,
            'chest': ItemSlot.BODY_ARMOR,
            'leg_armor': ItemSlot.LEG_ARMOR,
            'legs': ItemSlot.LEG_ARMOR,
            'boots': ItemSlot.BOOTS,
            'shoes': ItemSlot.BOOTS,
            'feet': ItemSlot.BOOTS,
            'shield': ItemSlot.SHIELD,
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
        
        # Try direct mapping first
        slot_lower = slot_name.lower()
        if slot_lower in slot_mapping:
            return slot_mapping[slot_lower]
        
        # Try to match ItemSlot enum values directly
        try:
            return ItemSlot(slot_name.lower())
        except ValueError:
            return None

    def __repr__(self):
        return f"UnequipItemAction({self.character_name}, {self.slot}, qty={self.quantity})"