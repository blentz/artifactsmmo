"""
Gather Resource Quantity Action

This action coordinates gathering a specific quantity of a resource,
looping between gathering and checking inventory until the goal is met.
"""

from typing import Dict, Optional
from artifactsmmo_api_client.api.characters.get_character_characters_name_get import sync as get_character_api
from src.controller.actions.base import ActionBase, ActionResult
from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters


class GatherResourceQuantityAction(ActionBase):
    """
    Gather a specific quantity of a resource.
    
    This action continues gathering until the required quantity is obtained
    or a maximum number of attempts is reached.
    """
    
    # GOAP parameters
    conditions = {
        'location_context': {
            'at_resource': True
        },
        'materials': {
            'status': 'insufficient',
            'quantities_calculated': True,
            'raw_materials_needed': True
        },
        'character_status': {
            'alive': True
        }
    }
    
    reactions = {
        'materials': {
            'status': 'sufficient',
            'gathered': True
        },
        'inventory': {
            'updated': True
        }
    }
    
    weight = 2.5
    
    def __init__(self):
        """Initialize the gather resource quantity action."""
        super().__init__()
        self.max_attempts = 20  # Maximum gathering attempts
        
    def execute(self, client, context: ActionContext) -> ActionResult:
        """
        Execute resource gathering until quantity goal is met.
        
        Args:
            client: API client for gathering and inventory checks
            context: ActionContext containing gathering goal
            
        Returns:
            ActionResult with gathering progress
        """
        self._context = context
        character_name = context.get(StateParameters.CHARACTER_NAME)
        
        try:
            # Get the current gathering goal
            gathering_goal = context.get('current_gathering_goal')
            if not gathering_goal:
                return self.create_error_result("No gathering goal set")
                
            material_code = gathering_goal.get('material')
            quantity_needed = gathering_goal.get('quantity', 1)
            
            self.logger.info(f"🎯 Gathering goal: {quantity_needed} {material_code}")
            
            # Get current inventory
            current_quantity = self._get_current_quantity(client, character_name, material_code)
            self.logger.info(f"📦 Current inventory: {current_quantity} {material_code}")
            
            if current_quantity >= quantity_needed:
                self.logger.info(f"✅ Already have sufficient {material_code}")
                return self._create_success_result(material_code, quantity_needed, current_quantity)
                
            # Calculate how many more we need
            remaining_needed = quantity_needed - current_quantity
            attempts = 0
            total_gathered = 0
            
            # Import gather action
            from src.controller.action_executor import ActionExecutor
            action_executor = ActionExecutor()
            
            while remaining_needed > 0 and attempts < self.max_attempts:
                attempts += 1
                self.logger.info(f"⛏️ Gathering attempt {attempts} - need {remaining_needed} more {material_code}")
                
                # Execute single gather action using existing context
                gather_result = action_executor.execute_action(
                    action_name='gather_resources',
                    client=client,
                    context=context
                )
                
                if gather_result is None or not gather_result.success:
                    self.logger.warning(f"Gathering attempt {attempts} failed")
                    continue
                    
                # Check how many we gathered
                items_obtained = gather_result.data.get('items_obtained', [])
                gathered_this_attempt = 0
                
                for item in items_obtained:
                    if isinstance(item, dict) and item.get('code') == material_code:
                        gathered_this_attempt = item.get('quantity', 0)
                        break
                        
                total_gathered += gathered_this_attempt
                self.logger.info(f"📦 Gathered {gathered_this_attempt} {material_code} this attempt")
                
                # Update current quantity
                current_quantity = self._get_current_quantity(client, character_name, material_code)
                remaining_needed = quantity_needed - current_quantity
                
                # Handle cooldown if needed
                if gather_result.data.get('cooldown_seconds', 0) > 0:
                    self.logger.info(f"⏱️ Cooldown active, will be handled by GOAP")
                    break
                    
            # Check final result
            final_quantity = self._get_current_quantity(client, character_name, material_code)
            
            if final_quantity >= quantity_needed:
                self.logger.info(f"✅ Successfully gathered {total_gathered} {material_code} (total: {final_quantity})")
                return self._create_success_result(material_code, quantity_needed, final_quantity)
            else:
                self.logger.warning(f"⚠️ Only gathered {total_gathered} {material_code} after {attempts} attempts")
                # Still mark as success but note incomplete
                return self._create_partial_success_result(material_code, quantity_needed, final_quantity, attempts)
                
        except Exception as e:
            return self.create_error_result(f"Failed to gather resource quantity: {str(e)}")
            
    def _get_current_quantity(self, client, character_name: str, material_code: str) -> int:
        """Get current quantity of material in inventory."""
        try:
            response = get_character_api(name=character_name, client=client)
            if response and response.data:
                for item in response.data.inventory:
                    if item.code == material_code:
                        return item.quantity
            return 0
        except:
            return 0
            
    def _create_success_result(self, material_code: str, quantity_needed: int, final_quantity: int) -> ActionResult:
        """Create success result with state changes."""
        state_changes = {
            'materials': {
                'status': 'sufficient',
                'gathered': True
            },
            'inventory': {
                'updated': True
            }
        }
        
        return self.create_result_with_state_changes(
            success=True,
            state_changes=state_changes,
            message=f"Successfully gathered {material_code} to meet goal",
            material=material_code,
            quantity_needed=quantity_needed,
            final_quantity=final_quantity,
            goal_met=True
        )
        
    def _create_partial_success_result(self, material_code: str, quantity_needed: int, 
                                     final_quantity: int, attempts: int) -> ActionResult:
        """Create partial success result."""
        # Still mark materials as sufficient if we made progress
        state_changes = {
            'materials': {
                'status': 'partial',
                'gathered': True
            },
            'inventory': {
                'updated': True
            }
        }
        
        return self.create_result_with_state_changes(
            success=True,
            state_changes=state_changes,
            message=f"Partially gathered {material_code}",
            material=material_code,
            quantity_needed=quantity_needed,
            final_quantity=final_quantity,
            attempts=attempts,
            goal_met=False
        )
        
    def __repr__(self):
        return "GatherResourceQuantityAction()"