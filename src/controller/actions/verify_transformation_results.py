"""
Verify Transformation Results Action

This bridge action verifies that material transformations
were successful by checking inventory.
"""

from typing import Dict, Any, List

from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters
from .base import ActionBase, ActionResult
from .check_inventory import CheckInventoryAction


class VerifyTransformationResultsAction(ActionBase):
    """
    Bridge action to verify transformation results in inventory.
    
    This action checks that the expected refined materials are now
    present in the character's inventory after transformation.
    """
    
    def __init__(self):
        """Initialize verify transformation results action."""
        super().__init__()
        
    def execute(self, client, context: ActionContext) -> ActionResult:
        """
        Verify transformation results.
        
        Args:
            client: API client
            context: Action context containing:
                - character_name: Name of character
                - transformations_completed: List of completed transformations
                - knowledge_base: Knowledge base instance
                
        Returns:
            Dict with verification results
        """
        self._context = context
        
        try:
            transformations = context.get(StateParameters.TRANSFORMATIONS_COMPLETED, [])
            
            if not transformations:
                return self.create_success_result(
                    "No transformations to verify",
                    verified=True
                )
            
            self.logger.debug(f"🔍 Verifying {len(transformations)} transformation results")
            
            # Get list of refined materials to check
            materials_to_verify = []
            for transformation in transformations:
                refined_material = transformation.get('refined_material')
                if refined_material and refined_material not in materials_to_verify:
                    materials_to_verify.append(refined_material)
            
            # Use CheckInventoryAction to verify
            check_action = CheckInventoryAction()
            # Use existing context and set required_items
            context.set(StateParameters.REQUIRED_ITEMS, materials_to_verify)
            
            inventory_result = check_action.execute(client, context)
            
            if not inventory_result or not inventory_result.get('success'):
                return self.create_error_result("Could not verify inventory")
            
            # Analyze results
            inventory_status = inventory_result.get('inventory_status', {})
            verification_results = []
            all_verified = True
            
            for transformation in transformations:
                refined_material = transformation.get('refined_material')
                expected_quantity = transformation.get('quantity', 0)
                
                if refined_material in inventory_status:
                    available = inventory_status[refined_material].get('available', 0)
                    verified = available >= expected_quantity
                    
                    verification_results.append({
                        'material': refined_material,
                        'expected': expected_quantity,
                        'available': available,
                        'verified': verified
                    })
                    
                    if not verified:
                        all_verified = False
                        self.logger.warning(
                            f"⚠️ {refined_material}: expected {expected_quantity}, found {available}"
                        )
                    else:
                        self.logger.info(f"✅ Verified {available}x {refined_material} in inventory")
                else:
                    all_verified = False
                    verification_results.append({
                        'material': refined_material,
                        'expected': expected_quantity,
                        'available': 0,
                        'verified': False
                    })
                    self.logger.warning(f"❌ {refined_material} not found in inventory")
            
            return self.create_success_result(
                f"Transformation verification {'successful' if all_verified else 'partially successful'}",
                all_verified=all_verified,
                verification_results=verification_results,
                inventory_status=inventory_status
            )
            
        except Exception as e:
            return self.create_error_result(f"Failed to verify transformation results: {e}")
    
    def __repr__(self):
        return "VerifyTransformationResultsAction()"