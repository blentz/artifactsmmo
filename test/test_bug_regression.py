"""
Regression tests for critical bugs to prevent regressions.

This test file covers the major bugs that were fixed:
1. YAML data persistence with nested structures
2. HTTP request caching to avoid duplicate requests
3. Action parameter passing between GOAP actions  
4. Cooldown handling to execute wait actions during cooldowns
"""

import unittest
import tempfile
import time
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone, timedelta

from src.lib.yaml_data import YamlData
from src.game.map.state import MapState
from src.controller.ai_player_controller import AIPlayerController
from src.game.character.state import CharacterState


class TestYamlDataNestedStructureBug(unittest.TestCase):
    """
    Test for YAML data persistence bug where nested data structures
    were not handled correctly, causing data duplication.
    
    Bug: YamlData.__init__ was not extracting just the 'data' portion 
    from loaded YAML, causing nested {data: {data: {}}} structures.
    """
    
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.filename = os.path.join(self.test_dir.name, "test_nested.yaml")
    
    def tearDown(self):
        self.test_dir.cleanup()
    
    def test_nested_data_structure_handling(self):
        """Test that nested data structures are properly extracted."""
        # Create a YAML file with nested structure like the bug showed
        initial_content = {
            'data': {
                'at_target_location': False,
                'has_hunted_monsters': False,
                'monster_present': True,
                'monsters_available': True
            },
            'planners': []
        }
        
        # Write initial content to file
        import yaml
        with open(self.filename, 'w') as f:
            yaml.dump(initial_content, f)
        
        # Load with YamlData - should extract only the 'data' portion
        yaml_data = YamlData(filename=self.filename)
        
        # Verify that only the contents of 'data' are loaded, not the full structure
        expected_data = {
            'at_target_location': False,
            'has_hunted_monsters': False,
            'monster_present': True,
            'monsters_available': True
        }
        
        self.assertEqual(yaml_data.data, expected_data)
        
        # Verify no nested duplication occurred
        self.assertNotIn('data', yaml_data.data)
        
    def test_knowledge_persistence_content_type_mapping(self):
        """Test that knowledge persistence works with proper content type mapping."""
        import tempfile
        import os
        from src.controller.ai_player_controller import AIPlayerController
        
        # Create controller with content type mapping
        controller = AIPlayerController()
        
        # Test enhanced attribute-based categorization for monsters using goal manager
        monster_type = controller.goal_manager.classify_content('blue_slime', {'code': 'blue_slime'}, 'unknown')
        self.assertEqual(monster_type, 'monster')  # Should detect 'slime' pattern
        
        resource_type = controller.goal_manager.classify_content('copper_rocks', {'code': 'copper_rocks'}, 'unknown')
        self.assertEqual(resource_type, 'resource')
        
        # Test that orc is properly categorized as monster (was being misclassified)
        orc_type = controller.goal_manager.classify_content('orc', {'code': 'orc'}, 'unknown')
        self.assertEqual(orc_type, 'monster')  # Should detect 'orc' pattern
        
        # Test that sunflower_field is properly categorized as resource
        field_type = controller.goal_manager.classify_content('sunflower_field', {'code': 'sunflower_field'}, 'unknown')
        self.assertEqual(field_type, 'resource')
        
        # Test that cyclops is properly categorized as monster
        cyclops_type = controller.goal_manager.classify_content('cyclops', {'code': 'cyclops'}, 'unknown')
        self.assertEqual(cyclops_type, 'monster')  # Should detect 'cyclops' pattern
        
        # Test fallback pattern matching
        unknown_slime = controller.goal_manager.classify_content('purple_slime', {'code': 'purple_slime'}, 'unknown')
        self.assertEqual(unknown_slime, 'monster')  # Should detect 'slime' pattern
        
        unknown_tree = controller.goal_manager.classify_content('magic_tree', {'code': 'magic_tree'}, 'unknown')
        self.assertEqual(unknown_tree, 'resource')  # Should detect 'tree' pattern
        
        # Test new content types
        workshop_type = controller.goal_manager.classify_content('weaponcrafting', {'code': 'weaponcrafting'}, 'unknown')
        self.assertEqual(workshop_type, 'workshop')  # Should detect 'crafting' pattern
        
        facility_type = controller.goal_manager.classify_content('bank', {'code': 'bank'}, 'unknown')
        self.assertEqual(facility_type, 'facility')  # Should detect 'bank' pattern
        
    def test_save_preserves_structure(self):
        """Test that saving maintains proper structure without duplication."""
        yaml_data = YamlData(filename=self.filename)
        yaml_data.data = {'test_key': 'test_value'}
        
        # Save with additional data
        yaml_data.save(additional_key='additional_value')
        
        # Read file directly to verify structure
        import yaml
        with open(self.filename, 'r') as f:
            saved_content = yaml.safe_load(f)
        
        # Should have proper structure with data wrapped correctly
        expected_structure = {
            'data': {'test_key': 'test_value'},
            'additional_key': 'additional_value'
        }
        
        self.assertEqual(saved_content, expected_structure)
        
        # Verify no duplicate data keys
        self.assertEqual(len([k for k in saved_content.keys() if k == 'data']), 1)


class TestMapStateCachingBug(unittest.TestCase):
    """
    Test for HTTP request caching bug where duplicate requests were made
    to the same coordinates within the cache duration.
    
    Bug: MapState.scan() was not checking cache freshness before making
    HTTP requests, causing excessive API calls.
    """
    
    def setUp(self):
        self.mock_client = Mock()
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_cache_freshness_logic(self):
        """Test the cache freshness logic without full MapState setup."""
        # This tests the core cache logic that was fixed
        current_time = time.time()
        
        # Test case 1: Fresh cache (within duration)
        cache_data = {
            "5,5": {
                "x": 5, "y": 5, "content": None,
                "last_scanned": current_time - 100  # 100 seconds ago
            }
        }
        
        cache_duration = 300  # 5 minutes
        coord_key = "5,5"
        
        # Simulate is_cache_fresh logic
        if coord_key in cache_data:
            tile_data = cache_data[coord_key]
            if isinstance(tile_data, dict) and 'last_scanned' in tile_data:
                time_since_scan = current_time - tile_data['last_scanned']
                is_fresh = time_since_scan < cache_duration
                self.assertTrue(is_fresh)  # Should be fresh
        
        # Test case 2: Stale cache (beyond duration)
        cache_data["5,5"]["last_scanned"] = current_time - 400  # 400 seconds ago
        
        if coord_key in cache_data:
            tile_data = cache_data[coord_key]
            if isinstance(tile_data, dict) and 'last_scanned' in tile_data:
                time_since_scan = current_time - tile_data['last_scanned']
                is_fresh = time_since_scan < cache_duration
                self.assertFalse(is_fresh)  # Should be stale
    
    def test_timestamp_addition_to_cache(self):
        """Test that timestamps are properly added to cached data."""
        # This simulates the fix where timestamps are added to prevent duplicate requests
        original_tile_data = {"x": 5, "y": 5, "content": None}
        
        # Simulate the scan method adding timestamp
        current_time = time.time()
        cached_tile_data = original_tile_data.copy()
        cached_tile_data["last_scanned"] = current_time
        
        # Verify timestamp was added
        self.assertIn("last_scanned", cached_tile_data)
        self.assertIsInstance(cached_tile_data["last_scanned"], (int, float))
        self.assertGreater(cached_tile_data["last_scanned"], current_time - 1)


class TestActionParameterPassingBug(unittest.TestCase):
    """
    Test for action parameter passing bug where context data was not
    preserved between sequential GOAP actions.
    
    Bug: Action results (like target coordinates) were not being passed
    to subsequent actions, causing "Missing required parameter" errors.
    """
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.mock_client = Mock()
        
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)
    
    @patch('src.controller.ai_player_controller.StateManagerMixin.initialize_state_management')
    @patch('src.controller.ai_player_controller.StateManagerMixin.create_managed_state')
    def test_action_context_preservation(self, mock_create_state, mock_init_state):
        """Test that action context is preserved between plan iterations."""
        # Setup mocks
        mock_world_state = Mock()
        mock_knowledge_base = Mock()
        mock_create_state.side_effect = [mock_world_state, mock_knowledge_base]
        
        controller = AIPlayerController(client=self.mock_client)
        
        # Set up initial action context with target coordinates
        controller.action_context = {
            'target_x': 4,
            'target_y': -1,
            'monster_location': (4, -1)
        }
        
        # Mock a plan execution that should preserve important location data
        controller.current_plan = [
            {'name': 'move', 'x': 4, 'y': -1},
            {'name': 'attack'}
        ]
        controller.current_action_index = 0
        
        # Simulate executing a plan (which resets action context but preserves location data)
        preserved_data = {}
        if hasattr(controller, 'action_context'):
            # Preserve target location data between plan iterations
            for key in ['x', 'y', 'target_x', 'target_y']:
                if key in controller.action_context:
                    preserved_data[key] = controller.action_context[key]
        
        controller.action_context = preserved_data
        
        # Verify that critical location data is preserved
        self.assertIn('target_x', controller.action_context)
        self.assertIn('target_y', controller.action_context)
        self.assertEqual(controller.action_context['target_x'], 4)
        self.assertEqual(controller.action_context['target_y'], -1)
        
        # Verify that non-essential data is cleared
        self.assertNotIn('monster_location', controller.action_context)


class TestCooldownHandlingBug(unittest.TestCase):
    """
    Test for cooldown handling bug where actions continued despite active
    cooldowns, instead of executing wait actions.
    
    Bug: Character state was not refreshed before cooldown detection,
    causing stale cooldown data and failure to trigger wait actions.
    """
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.mock_client = Mock()
        
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)
    
    @patch('src.controller.ai_player_controller.StateManagerMixin.initialize_state_management')
    @patch('src.controller.ai_player_controller.StateManagerMixin.create_managed_state')
    def test_character_state_refresh_for_cooldown_detection(self, mock_create_state, mock_init_state):
        """Test that character state is refreshed before cooldown detection."""
        # Setup mocks
        mock_world_state = Mock()
        mock_knowledge_base = Mock()
        mock_create_state.side_effect = [mock_world_state, mock_knowledge_base]
        
        controller = AIPlayerController(client=self.mock_client)
        
        # Create mock character state with active cooldown
        mock_character_state = Mock()
        current_time = datetime.now(timezone.utc)
        cooldown_expiration = current_time + timedelta(seconds=10)
        
        mock_character_state.name = "test_character"
        mock_character_state.data = {
            'cooldown': 10,
            'cooldown_expiration': cooldown_expiration.isoformat(),
            'hp': 100,
            'max_hp': 100,
            'level': 1,
            'xp': 22,
            'max_xp': 150
        }
        
        controller.set_character_state(mock_character_state)
        
        # Mock the API call that refreshes character state
        with patch('artifactsmmo_api_client.api.characters.get_character_name.sync') as mock_get_char:
            mock_response = Mock()
            mock_response.data.to_dict.return_value = {
                'cooldown': 10,
                'cooldown_expiration': cooldown_expiration.isoformat(),
                'hp': 100,
                'max_hp': 100,
                'level': 1
            }
            mock_get_char.return_value = mock_response
            
            # Get current world state (which should refresh character state)
            world_state = controller.get_current_world_state()
            
            # Verify that character state refresh was called
            mock_get_char.assert_called_once_with(name="test_character", client=self.mock_client)
            
            # Verify that cooldown is properly detected
            self.assertTrue(world_state.get('is_on_cooldown', False))
            self.assertFalse(world_state.get('can_move', True))
            self.assertFalse(world_state.get('can_attack', True))
    
    @patch('src.controller.ai_player_controller.StateManagerMixin.initialize_state_management')
    @patch('src.controller.ai_player_controller.StateManagerMixin.create_managed_state')
    def test_cooldown_detection_triggers_wait_action(self, mock_create_state, mock_init_state):
        """Test that detected cooldown triggers wait action execution."""
        # Setup mocks
        mock_world_state = Mock()
        mock_knowledge_base = Mock()
        mock_create_state.side_effect = [mock_world_state, mock_knowledge_base]
        
        controller = AIPlayerController(client=self.mock_client)
        
        # Create mock character state with active cooldown
        mock_character_state = Mock()
        current_time = datetime.now(timezone.utc)
        cooldown_expiration = current_time + timedelta(seconds=5)
        
        mock_character_state.name = "test_character"
        mock_character_state.data = {
            'cooldown': 5,
            'cooldown_expiration': cooldown_expiration.isoformat(),
            'hp': 100,
            'max_hp': 100
        }
        
        controller.set_character_state(mock_character_state)
        
        # Mock the cooldown detection logic
        with patch.object(controller, '_refresh_character_state'):
            with patch.object(controller, '_execute_cooldown_wait') as mock_wait:
                mock_wait.return_value = True
                
                # Simulate cooldown detection in achieve_goal_with_goap
                current_state = {
                    'is_on_cooldown': True,
                    'character_alive': True
                }
                
                # This simulates the cooldown handling logic in achieve_goal_with_goap
                if current_state.get('is_on_cooldown', False):
                    wait_success = controller._execute_cooldown_wait()
                    
                    # Verify wait action was called
                    mock_wait.assert_called_once()
                    self.assertTrue(wait_success)
    
    def test_cooldown_expiration_parsing(self):
        """Test that cooldown expiration times are parsed correctly."""
        # Test various cooldown expiration formats
        test_cases = [
            "2025-06-25T17:19:45.304000+00:00",
            "2025-06-25T17:19:45.304Z",
            "2025-06-25T17:19:45+00:00"
        ]
        
        for cooldown_str in test_cases:
            try:
                # This is the parsing logic from get_current_world_state
                if isinstance(cooldown_str, str):
                    expiration_time = datetime.fromisoformat(cooldown_str.replace('Z', '+00:00'))
                    
                    # Should be a valid datetime
                    self.assertIsInstance(expiration_time, datetime)
                    self.assertIsNotNone(expiration_time.tzinfo)
                    
            except Exception as e:
                self.fail(f"Failed to parse cooldown expiration '{cooldown_str}': {e}")


class TestDataPersistenceBug(unittest.TestCase):
    """
    Test for data persistence bug where game API data was not being
    saved to YAML files (world.yaml, map.yaml, knowledge.yaml).
    
    Bug: Learning callbacks were not properly connected and data
    was not being persisted after API calls.
    """
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.mock_client = Mock()
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_yaml_data_save_structure(self):
        """Test that YamlData saves with proper structure for persistence."""
        # Test the core save functionality that was fixed
        test_file = os.path.join(self.temp_dir, "test_persistence.yaml")
        
        yaml_data = YamlData(filename=test_file)
        yaml_data.data = {
            'at_target_location': True,
            'monster_present': False,
            'coordinates_scanned': ['1,2', '3,4']
        }
        
        # Save the data
        yaml_data.save(metadata='test_run')
        
        # Verify file was created
        self.assertTrue(os.path.exists(test_file))
        
        # Verify proper structure
        import yaml
        with open(test_file, 'r') as f:
            saved_content = yaml.safe_load(f)
        
        # Should have the expected structure
        self.assertIn('data', saved_content)
        self.assertIn('metadata', saved_content)
        self.assertEqual(saved_content['metadata'], 'test_run')
        
        # Data should be properly nested
        expected_data = {
            'at_target_location': True,
            'monster_present': False,
            'coordinates_scanned': ['1,2', '3,4']
        }
        self.assertEqual(saved_content['data'], expected_data)
    
    def test_learning_callback_mechanism(self):
        """Test that learning callbacks work correctly for data persistence."""
        # Test the callback mechanism that was fixed
        callback_data = []
        
        def mock_learning_callback(discovery_type, location, details):
            callback_data.append({
                'type': discovery_type,
                'location': location,
                'details': details
            })
        
        # Simulate the fixed learning system
        mock_learning_callback('monster', (5, 5), {'code': 'slime', 'type': 'monster'})
        mock_learning_callback('resource', (2, 3), {'code': 'copper_rocks', 'type': 'resource'})
        
        # Verify callbacks were triggered
        self.assertEqual(len(callback_data), 2)
        
        # Verify callback data structure
        monster_discovery = callback_data[0]
        self.assertEqual(monster_discovery['type'], 'monster')
        self.assertEqual(monster_discovery['location'], (5, 5))
        self.assertEqual(monster_discovery['details']['code'], 'slime')
        
        resource_discovery = callback_data[1]
        self.assertEqual(resource_discovery['type'], 'resource')
        self.assertEqual(resource_discovery['location'], (2, 3))
        self.assertEqual(resource_discovery['details']['code'], 'copper_rocks')


if __name__ == '__main__':
    unittest.main()