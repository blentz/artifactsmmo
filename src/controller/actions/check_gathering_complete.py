"""
Check Gathering Complete Action

This action checks if material gathering is complete and updates the material status accordingly.
"""

from src.controller.actions.base import ActionBase, ActionResult
from src.lib.action_context import ActionContext
from src.game.globals import MaterialStatus


class CheckGatheringCompleteAction(ActionBase):
    """
    Action to check if material gathering is complete.
    
    This action:
    1. Checks the gathering results from context
    2. Updates material status to trigger re-checking availability
    """
    
    # GOAP parameters
    conditions = {
        'materials': {
            'status': MaterialStatus.GATHERING,
            'gathering_initiated': True
        },
        'character_status': {
            'alive': True,
        },
    }
    
    reactions = {
        'materials': {
            'status': [MaterialStatus.SUFFICIENT, MaterialStatus.INSUFFICIENT],  # Can be either based on completion
            'availability_checked': False  # Force re-check after gathering
        }
    }
    
    weight = 1.0
    
    def __init__(self):
        """Initialize the check gathering complete action."""
        super().__init__()
        
    def execute(self, client, context: ActionContext) -> ActionResult:
        """
        Check if material gathering is complete.
        
        Args:
            client: API client for character data
            context: ActionContext containing gathering results
            
        Returns:
            Action result with completion status
        """
        self._context = context
        
        try:
            # Get gathering results from context with proper defaults
            gathering_complete = context.get('gathering_complete', False)
            materials_gathered = context.get('materials_gathered', {})
            quantity_gathered = context.get('quantity_gathered', 0) if context.get('quantity_gathered') is not None else 0
            quantity_needed = context.get('quantity_needed', 0) if context.get('quantity_needed') is not None else 0
            target_material = context.get('target_material', 'unknown') if context.get('target_material') is not None else 'unknown'
            
            self.logger.info(f"🔍 Checking gathering status: {quantity_gathered}/{quantity_needed} {target_material}")
            
            # Update state based on gathering completion
            if gathering_complete:
                state_changes = {
                    'materials': {
                        'status': MaterialStatus.SUFFICIENT,
                        'gathered': True,
                        'last_gathered': target_material,
                        'gathering_complete': True
                    }
                }
            else:
                # Reset to insufficient to trigger continued gathering
                state_changes = {
                    'materials': {
                        'status': MaterialStatus.INSUFFICIENT,
                        'gathered': False,
                        'availability_checked': False,  # Force re-check
                        'last_gathered': target_material,
                        'gathering_complete': False
                    }
                }
            
            if gathering_complete:
                message = f"Gathering complete: {quantity_gathered} {target_material} gathered"
            else:
                message = f"Gathering incomplete: {quantity_gathered}/{quantity_needed} {target_material}"
                
            return self.create_result_with_state_changes(
                success=True,
                state_changes=state_changes,
                message=message,
                gathering_complete=gathering_complete,
                materials_gathered=materials_gathered
            )
            
        except Exception as e:
            return self.create_error_result(f"Failed to check gathering status: {str(e)}")
            
    def __repr__(self):
        return "CheckGatheringCompleteAction()"