"""
Test Execute Crafting Plan Action

Comprehensive tests for the ExecuteCraftingPlanAction class.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock

from src.controller.actions.execute_crafting_plan import ExecuteCraftingPlanAction
from src.controller.actions.base import ActionResult
from src.lib.action_context import ActionContext


class TestExecuteCraftingPlanAction(unittest.TestCase):
    """Test the ExecuteCraftingPlanAction class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.action = ExecuteCraftingPlanAction()
        self.client = Mock()
        self.context = ActionContext()
        self.context.character_name = "test_character"
        self.context.target_item = "iron_sword"
        
        # Mock knowledge base
        self.mock_kb = Mock()
        self.context.knowledge_base = self.mock_kb
        
    def test_init(self):
        """Test action initialization."""
        action = ExecuteCraftingPlanAction()
        self.assertIsInstance(action, ExecuteCraftingPlanAction)
        
    def test_execute_no_knowledge_base(self):
        """Test execute fails without knowledge base."""
        self.context.knowledge_base = None
        
        result = self.action.execute(self.client, self.context)
        
        self.assertFalse(result.success)
        self.assertIn("No knowledge base available", result.error)
        
    def test_execute_no_target_item(self):
        """Test execute fails without target item."""
        self.context.target_item = None
        
        with patch.object(self.action, '_determine_target_item') as mock_determine:
            mock_determine.return_value = None
            
            result = self.action.execute(self.client, self.context)
            
            self.assertFalse(result.success)
            self.assertIn("No target item specified", result.error)
    
    def test_execute_item_not_found(self):
        """Test execute fails when item data not found."""
        self.mock_kb.get_item_data.return_value = None
        
        result = self.action.execute(self.client, self.context)
        
        self.assertFalse(result.success)
        self.assertIn("Could not find item data", result.error)
    
    def test_execute_item_not_craftable(self):
        """Test execute fails when item is not craftable."""
        self.mock_kb.get_item_data.return_value = {
            'name': 'Iron Sword',
            'craft_data': {}  # Empty craft data
        }
        
        result = self.action.execute(self.client, self.context)
        
        self.assertFalse(result.success)
        self.assertIn("is not craftable", result.error)
    
    def test_execute_workshop_move_fails(self):
        """Test execute fails when can't move to workshop."""
        # Mock item data with craft info
        self.mock_kb.get_item_data.return_value = {
            'name': 'Iron Sword',
            'craft_data': {
                'skill': 'weaponsmithing',
                'items': [{'code': 'iron', 'quantity': 3}]
            }
        }
        
        # Mock workshop move failure
        with patch.object(self.action, '_ensure_at_workshop') as mock_ensure:
            mock_ensure.return_value = Mock(success=False, error='Workshop not found')
            
            result = self.action.execute(self.client, self.context)
            
            self.assertFalse(result.success)
            self.assertEqual(result.error, 'Workshop not found')
    
    def test_execute_craft_fails(self):
        """Test execute fails when crafting fails."""
        # Mock item data
        self.mock_kb.get_item_data.return_value = {
            'name': 'Iron Sword',
            'craft_data': {
                'skill': 'weaponsmithing',
                'items': [{'code': 'iron', 'quantity': 3}]
            }
        }
        
        # Mock successful workshop check
        with patch.object(self.action, '_ensure_at_workshop') as mock_ensure:
            mock_ensure.return_value = Mock(success=True)
            
            # Mock unequip materials
            with patch.object(self.action, '_unequip_required_materials') as mock_unequip:
                mock_unequip.return_value = []
                
                # Mock craft failure
                with patch('src.controller.actions.execute_crafting_plan.CraftItemAction') as mock_craft_class:
                    mock_craft_action = Mock()
                    # Mock needs to support both dict-style and ActionResult style
                    mock_craft_result = Mock(success=False, error='Not enough materials')
                    mock_craft_result.get.side_effect = lambda key, default=None: {
                        'success': False,
                        'error': 'Not enough materials'
                    }.get(key, default)
                    mock_craft_action.execute.return_value = mock_craft_result
                    mock_craft_class.return_value = mock_craft_action
                    
                    result = self.action.execute(self.client, self.context)
                    
                    self.assertFalse(result.success)
                    self.assertIn("Failed to craft", result.error)
                    self.assertIn("Not enough materials", result.error)
    
    def test_execute_success(self):
        """Test successful crafting execution."""
        # Mock item data
        self.mock_kb.get_item_data.return_value = {
            'name': 'Iron Sword',
            'craft_data': {
                'skill': 'weaponsmithing',
                'items': [{'code': 'iron', 'quantity': 3}]
            }
        }
        
        # Mock successful workshop check
        with patch.object(self.action, '_ensure_at_workshop') as mock_ensure:
            mock_ensure.return_value = Mock(success=True)
            
            # Mock unequip materials
            with patch.object(self.action, '_unequip_required_materials') as mock_unequip:
                mock_unequip.return_value = [{'item': 'iron', 'slot': 'weapon', 'success': True}]
                
                # Mock successful craft
                with patch('src.controller.actions.execute_crafting_plan.CraftItemAction') as mock_craft_class:
                    mock_craft_action = Mock()
                    mock_craft_action.execute.return_value = Mock(
                        success=True,
                        data={
                            'item_crafted': 'iron_sword',
                            'quantity': 1
                        }
                    )
                    mock_craft_class.return_value = mock_craft_action
                    
                    result = self.action.execute(self.client, self.context)
                    
                    self.assertTrue(result.success)
                    self.assertEqual(result.data['target_item'], 'iron_sword')
                    self.assertEqual(result.data['workshop_type'], 'weaponsmithing')
                    self.assertEqual(len(result.data['unequipped_items']), 1)
    
    def test_execute_with_exception(self):
        """Test execute handles exceptions."""
        # Mock knowledge base to raise exception
        self.mock_kb.get_item_data.side_effect = Exception("Test error")
        
        result = self.action.execute(self.client, self.context)
        
        self.assertFalse(result.success)
        self.assertIn("Crafting execution failed", result.error)
        self.assertIn("Test error", result.error)
    
    def test_determine_target_item_from_selected_weapon(self):
        """Test _determine_target_item gets item from selected_weapon."""
        context = {'selected_weapon': 'iron_sword', 'item_code': 'other_item'}
        
        result = self.action._determine_target_item(context)
        
        self.assertEqual(result, 'iron_sword')
    
    def test_determine_target_item_from_item_code(self):
        """Test _determine_target_item gets item from item_code."""
        context = {'item_code': 'iron_helmet', 'target_item': 'other_item'}
        
        result = self.action._determine_target_item(context)
        
        self.assertEqual(result, 'iron_helmet')
    
    def test_determine_target_item_from_target_item(self):
        """Test _determine_target_item gets item from target_item."""
        context = {'target_item': 'iron_boots'}
        
        result = self.action._determine_target_item(context)
        
        self.assertEqual(result, 'iron_boots')
    
    def test_determine_target_item_none(self):
        """Test _determine_target_item returns None when no item found."""
        context = {'other_key': 'value'}
        
        result = self.action._determine_target_item(context)
        
        self.assertIsNone(result)
    
    def test_ensure_at_workshop_already_there(self):
        """Test _ensure_at_workshop when already at correct workshop."""
        # Mock character at workshop location
        char_response = Mock()
        char_response.data = Mock()
        char_response.data.x = 10
        char_response.data.y = 20
        
        # Mock map data showing workshop
        map_response = Mock()
        map_response.data = Mock()
        map_response.data.content = Mock()
        map_response.data.content.type_ = 'workshop'
        map_response.data.content.code = 'weaponsmithing'
        
        with patch('src.controller.actions.execute_crafting_plan.get_character_api') as mock_get_char:
            mock_get_char.return_value = char_response
            
            with patch('src.controller.actions.execute_crafting_plan.get_map_api') as mock_get_map:
                mock_get_map.return_value = map_response
                
                result = self.action._ensure_at_workshop(
                    self.client, 'weaponsmithing', 'iron_sword', 'test_char', self.context
                )
                
                self.assertTrue(result.success)
                self.assertTrue(result.data['at_workshop'])
    
    def test_ensure_at_workshop_need_to_move(self):
        """Test _ensure_at_workshop when need to move to workshop."""
        # Mock character not at workshop
        char_response = Mock()
        char_response.data = Mock()
        char_response.data.x = 0
        char_response.data.y = 0
        
        # Mock map data showing no workshop
        map_response = Mock()
        map_response.data = Mock()
        map_response.data.content = None
        
        with patch('src.controller.actions.execute_crafting_plan.get_character_api') as mock_get_char:
            mock_get_char.return_value = char_response
            
            with patch('src.controller.actions.execute_crafting_plan.get_map_api') as mock_get_map:
                mock_get_map.return_value = map_response
                
                # Mock find workshop
                with patch('src.controller.actions.execute_crafting_plan.FindCorrectWorkshopAction') as mock_find_class:
                    mock_find_action = Mock()
                    mock_find_action.execute.return_value = Mock(
                        success=True,
                        data={
                            'workshop_x': 10,
                            'workshop_y': 20
                        }
                    )
                    mock_find_class.return_value = mock_find_action
                    
                    # Mock move action
                    with patch('src.controller.actions.execute_crafting_plan.MoveAction') as mock_move_class:
                        mock_move_action = Mock()
                        mock_move_action.execute.return_value = Mock(success=True)
                        mock_move_class.return_value = mock_move_action
                        
                        result = self.action._ensure_at_workshop(
                            self.client, 'weaponsmithing', 'iron_sword', 'test_char', self.context
                        )
                        
                        self.assertTrue(result.success)
                        self.assertTrue(result.data['at_workshop'])
                        self.assertTrue(result.data['moved_to_workshop'])
                        
                        # Verify the move action was called with correct context
                        mock_move_action.execute.assert_called_once()
                        move_context = mock_move_action.execute.call_args[0][1]
                        self.assertEqual(move_context.action_data['x'], 10)
                        self.assertEqual(move_context.action_data['y'], 20)
    
    def test_ensure_at_workshop_character_api_fails(self):
        """Test _ensure_at_workshop when character API fails."""
        with patch('src.controller.actions.execute_crafting_plan.get_character_api') as mock_get_char:
            mock_get_char.return_value = None
            
            result = self.action._ensure_at_workshop(
                self.client, 'weaponsmithing', 'iron_sword', 'test_char', self.context
            )
            
            self.assertFalse(result.success)
            self.assertIn("Could not get character location", result.error)
    
    def test_ensure_at_workshop_exception(self):
        """Test _ensure_at_workshop handles exceptions."""
        with patch('src.controller.actions.execute_crafting_plan.get_character_api') as mock_get_char:
            mock_get_char.side_effect = Exception("API error")
            
            result = self.action._ensure_at_workshop(
                self.client, 'weaponsmithing', 'iron_sword', 'test_char', self.context
            )
            
            self.assertFalse(result.success)
            self.assertIn("Workshop check failed", result.error)
    
    def test_unequip_required_materials_no_materials(self):
        """Test _unequip_required_materials when no materials needed."""
        craft_data = {'items': []}
        
        result = self.action._unequip_required_materials(
            self.client, 'iron_sword', craft_data, self.mock_kb, 'test_char', self.context
        )
        
        self.assertEqual(result, [])
    
    def test_unequip_required_materials_success(self):
        """Test _unequip_required_materials successfully unequips items."""
        craft_data = {
            'items': [
                {'code': 'iron', 'quantity': 3},
                {'code': 'wood', 'quantity': 1}
            ]
        }
        
        # Mock character with equipped items
        char_response = Mock()
        char_response.data = Mock()
        char_response.data.weapon_slot = 'iron'  # Iron equipped as weapon
        char_response.data.helmet_slot = ''
        char_response.data.chest_slot = 'wood'  # Wood equipped as chest
        
        with patch('src.controller.actions.execute_crafting_plan.get_character_api') as mock_get_char:
            mock_get_char.return_value = char_response
            
            # Mock dir() to return slot attributes
            with patch('src.controller.actions.execute_crafting_plan.dir') as mock_dir:
                mock_dir.return_value = ['weapon_slot', 'helmet_slot', 'chest_slot', 'other_attr']
                
                # Mock unequip action
                with patch('src.controller.actions.execute_crafting_plan.UnequipItemAction') as mock_unequip_class:
                    mock_unequip_action = Mock()
                    mock_unequip_action.execute.return_value = Mock(success=True)
                    mock_unequip_class.return_value = mock_unequip_action
                    
                    result = self.action._unequip_required_materials(
                        self.client, 'iron_sword', craft_data, self.mock_kb, 'test_char', self.context
                    )
                    
                    self.assertEqual(len(result), 2)
                    self.assertEqual(result[0]['item'], 'iron')
                    self.assertEqual(result[0]['slot'], 'weapon_slot')
                    self.assertTrue(result[0]['success'])
                    self.assertEqual(result[1]['item'], 'wood')
                    self.assertEqual(result[1]['slot'], 'chest_slot')
                    self.assertTrue(result[1]['success'])
    
    def test_unequip_required_materials_api_fails(self):
        """Test _unequip_required_materials when character API fails."""
        craft_data = {'items': [{'code': 'iron', 'quantity': 3}]}
        
        with patch('src.controller.actions.execute_crafting_plan.get_character_api') as mock_get_char:
            mock_get_char.return_value = None
            
            result = self.action._unequip_required_materials(
                self.client, 'iron_sword', craft_data, self.mock_kb, 'test_char', self.context
            )
            
            self.assertEqual(result, [])
    
    def test_unequip_required_materials_exception(self):
        """Test _unequip_required_materials handles exceptions."""
        craft_data = {'items': [{'code': 'iron', 'quantity': 3}]}
        
        with patch('src.controller.actions.execute_crafting_plan.get_character_api') as mock_get_char:
            mock_get_char.side_effect = Exception("API error")
            
            result = self.action._unequip_required_materials(
                self.client, 'iron_sword', craft_data, self.mock_kb, 'test_char', self.context
            )
            
            self.assertEqual(result, [])
    
    def test_repr(self):
        """Test string representation."""
        self.assertEqual(repr(self.action), "ExecuteCraftingPlanAction()")
    
    def test_goap_parameters(self):
        """Test GOAP parameters are properly defined."""
        self.assertIn('character_status', self.action.conditions)
        self.assertIn('craft_plan_available', self.action.conditions)
        self.assertIn('materials_sufficient', self.action.conditions)
        
        self.assertIn('has_equipment', self.action.reactions)
        self.assertIn('inventory_updated', self.action.reactions)
        self.assertIn('craft_plan_available', self.action.reactions)
        
        self.assertEqual(self.action.weight, 10)
    
    def test_ensure_at_workshop_find_workshop_fails(self):
        """Test _ensure_at_workshop when find workshop fails."""
        # Mock character not at workshop
        char_response = Mock()
        char_response.data = Mock()
        char_response.data.x = 0
        char_response.data.y = 0
        
        # Mock map data showing no workshop
        map_response = Mock()
        map_response.data = Mock()
        map_response.data.content = None
        
        with patch('src.controller.actions.execute_crafting_plan.get_character_api') as mock_get_char:
            mock_get_char.return_value = char_response
            
            with patch('src.controller.actions.execute_crafting_plan.get_map_api') as mock_get_map:
                mock_get_map.return_value = map_response
                
                # Mock find workshop failure
                with patch('src.controller.actions.execute_crafting_plan.FindCorrectWorkshopAction') as mock_find_class:
                    mock_find_action = Mock()
                    mock_find_action.execute.return_value = Mock(success=False)
                    mock_find_class.return_value = mock_find_action
                    
                    result = self.action._ensure_at_workshop(
                        self.client, 'weaponsmithing', 'iron_sword', 'test_char', self.context
                    )
                    
                    self.assertFalse(result.success)
                    self.assertIn("Could not find weaponsmithing workshop", result.error)
    
    def test_ensure_at_workshop_move_fails(self):
        """Test _ensure_at_workshop when move to workshop fails."""
        # Mock character not at workshop
        char_response = Mock()
        char_response.data = Mock()
        char_response.data.x = 0
        char_response.data.y = 0
        
        # Mock map data showing no workshop
        map_response = Mock()
        map_response.data = Mock()
        map_response.data.content = None
        
        with patch('src.controller.actions.execute_crafting_plan.get_character_api') as mock_get_char:
            mock_get_char.return_value = char_response
            
            with patch('src.controller.actions.execute_crafting_plan.get_map_api') as mock_get_map:
                mock_get_map.return_value = map_response
                
                # Mock find workshop success
                with patch('src.controller.actions.execute_crafting_plan.FindCorrectWorkshopAction') as mock_find_class:
                    mock_find_action = Mock()
                    mock_find_action.execute.return_value = Mock(
                        success=True,
                        data={
                            'workshop_x': 10,
                            'workshop_y': 20
                        }
                    )
                    mock_find_class.return_value = mock_find_action
                    
                    # Mock move failure
                    with patch('src.controller.actions.execute_crafting_plan.MoveAction') as mock_move_class:
                        mock_move_action = Mock()
                        # Mock needs to support both dict-style and ActionResult style
                        mock_move_result = Mock(success=False)
                        mock_move_result.get.return_value = False
                        mock_move_action.execute.return_value = mock_move_result
                        mock_move_class.return_value = mock_move_action
                        
                        result = self.action._ensure_at_workshop(
                            self.client, 'weaponsmithing', 'iron_sword', 'test_char', self.context
                        )
                        
                        self.assertFalse(result.success)
                        self.assertIn("Could not move to workshop", result.error)
    
    def test_unequip_required_materials_unequip_fails(self):
        """Test _unequip_required_materials when unequip fails."""
        craft_data = {
            'items': [{'code': 'iron', 'quantity': 3}]
        }
        
        # Mock character with equipped items
        char_response = Mock()
        char_response.data = Mock()
        char_response.data.weapon_slot = 'iron'
        
        with patch('src.controller.actions.execute_crafting_plan.get_character_api') as mock_get_char:
            mock_get_char.return_value = char_response
            
            # Mock dir() to return slot attributes
            with patch('src.controller.actions.execute_crafting_plan.dir') as mock_dir:
                mock_dir.return_value = ['weapon_slot']
                
                # Mock unequip action failure
                with patch('src.controller.actions.execute_crafting_plan.UnequipItemAction') as mock_unequip_class:
                    mock_unequip_action = Mock()
                    # Mock needs to support both dict-style and ActionResult style  
                    mock_unequip_result = Mock(success=False)
                    mock_unequip_result.get.side_effect = lambda key, default=None: {
                        'success': False
                    }.get(key, default)
                    mock_unequip_action.execute.return_value = mock_unequip_result
                    mock_unequip_class.return_value = mock_unequip_action
                    
                    result = self.action._unequip_required_materials(
                        self.client, 'iron_sword', craft_data, self.mock_kb, 'test_char', self.context
                    )
                    
                    self.assertEqual(len(result), 1)
                    self.assertEqual(result[0]['item'], 'iron')
                    self.assertFalse(result[0]['success'])


if __name__ == '__main__':
    unittest.main()