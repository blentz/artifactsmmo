"""
Regression tests for refactoring issues to prevent future problems.

This test suite specifically tests the issues identified and fixed during
the modular manager architecture refactoring to ensure they don't regress.
"""

import unittest
import tempfile
import os
from unittest.mock import Mock, patch

from src.controller.ai_player_controller import AIPlayerController
from src.controller.goap_execution_manager import GOAPExecutionManager
from src.controller.action_factory import ActionFactory
from src.controller.mission_executor import MissionExecutor
from src.lib.actions_data import ActionsData
from src.lib.yaml_data import YamlData


class TestGOAPIntegrationRegression(unittest.TestCase):
    """Test GOAP integration to prevent the 'state' action regression."""
    
    def setUp(self):
        """Set up test environment."""
        self.manager = GOAPExecutionManager()
        
    def test_goap_plan_returns_valid_action_names(self):
        """
        REGRESSION TEST: Ensure GOAP plans contain valid action names, not node properties.
        
        Previously: Plans contained 'state', 'f', 'g', 'h', 'p_id' (node properties)
        Fixed: Plans now contain proper action names like 'find_monsters', 'move', 'attack'
        """
        # Complete state with all required GOAP variables
        start_state = {
            'character_alive': True, 'character_safe': True, 'can_move': True, 'can_attack': True,
            'needs_rest': False, 'is_on_cooldown': False, 'need_combat': True, 
            'monsters_available': False, 'monster_present': False, 'has_hunted_monsters': False, 
            'monster_defeated': False, 'at_target_location': False, 'at_resource_location': False, 
            'at_workshop': False, 'need_resources': False, 'has_resources': False, 
            'need_equipment': False, 'has_equipment': False, 'has_materials': False, 
            'inventory_updated': False, 'equipment_equipped': False, 'equipment_info_known': True, 
            'equipment_info_unknown': False, 'map_explored': False, 'resource_location_known': False, 
            'workshop_location_known': False, 'craft_plan_available': False, 
            'exploration_data_available': False, 'equipment_analysis_available': False, 
            'crafting_opportunities_known': False, 'character_stats_improved': False,
            'need_workshop_discovery': False, 'workshops_discovered': False,
            'need_crafting_materials': False, 'has_crafting_materials': False, 
            'materials_sufficient': False, 'recipe_known': False, 'resource_found': False,
            'has_complete_equipment_set': False, 'all_slots_equipped': False
        }
        goal_state = {'has_hunted_monsters': True, 'monster_defeated': True, 'character_safe': True}
        
        actions_data = ActionsData('data/actions.yaml')
        actions_config = actions_data.get_actions()
        
        # Create plan and verify it contains valid action names
        plan = self.manager.create_plan(start_state, goal_state, actions_config)
        
        # Should find a plan
        self.assertIsNotNone(plan, "GOAP should generate a plan for hunting scenario")
        self.assertGreater(len(plan), 0, "Plan should contain at least one action")
        
        # All plan steps should have valid action names
        valid_actions = set(actions_config.keys())
        for i, step in enumerate(plan):
            self.assertIsInstance(step, dict, f"Step {i+1} should be a dictionary")
            self.assertIn('name', step, f"Step {i+1} should have a 'name' field")
            
            action_name = step['name']
            
            # REGRESSION CHECK: Ensure action name is not a node property
            invalid_node_properties = {'state', 'f', 'g', 'h', 'p_id', 'id'}
            self.assertNotIn(action_name, invalid_node_properties, 
                           f"Step {i+1} has invalid action name '{action_name}' (node property)")
            
            # REGRESSION CHECK: Ensure action name is registered
            self.assertIn(action_name, valid_actions, 
                        f"Step {i+1} has unregistered action '{action_name}'")
    
    def test_goap_plans_handle_cooldown_state(self):
        """Test that GOAP plans properly handle cooldown states."""
        # Character on cooldown should generate wait action plan
        cooldown_state = {
            'character_alive': True, 'character_safe': True, 'can_move': True, 'can_attack': True,
            'needs_rest': False, 'is_on_cooldown': True,  # Character is on cooldown
            'need_combat': True, 'monsters_available': False, 'monster_present': False, 
            'has_hunted_monsters': False, 'monster_defeated': False, 'at_target_location': False, 
            'at_resource_location': False, 'at_workshop': False, 'need_resources': False, 
            'has_resources': False, 'need_equipment': False, 'has_equipment': False, 
            'has_materials': False, 'inventory_updated': False, 'equipment_equipped': False, 
            'equipment_info_known': True, 'equipment_info_unknown': False, 'map_explored': False, 
            'resource_location_known': False, 'workshop_location_known': False, 
            'craft_plan_available': False, 'exploration_data_available': False, 
            'equipment_analysis_available': False, 'crafting_opportunities_known': False, 
            'character_stats_improved': False, 'need_workshop_discovery': False, 
            'workshops_discovered': False, 'need_crafting_materials': False, 
            'has_crafting_materials': False, 'materials_sufficient': False, 
            'recipe_known': False, 'resource_found': False,
            'has_complete_equipment_set': False, 'all_slots_equipped': False
        }
        goal_state = {'is_on_cooldown': False}
        
        actions_data = ActionsData('data/actions.yaml')
        actions_config = actions_data.get_actions()
        
        plan = self.manager.create_plan(cooldown_state, goal_state, actions_config)
        
        # Should find a plan with wait action
        self.assertIsNotNone(plan)
        if plan:  # Plan might be None if no solution found
            self.assertTrue(any(step['name'] == 'wait' for step in plan),
                          "Cooldown scenario should include wait action")


class TestActionRegistryRegression(unittest.TestCase):
    """Test action registry to prevent missing action registrations."""
    
    def test_all_goap_actions_are_registered_in_factory(self):
        """
        REGRESSION TEST: Ensure all GOAP actions have corresponding factory registrations.
        
        Previously: GOAP actions.yaml contained actions not registered in action factory
        Fixed: All GOAP actions now properly registered in action_configurations.yaml
        """
        # Load GOAP actions
        actions_data = ActionsData('data/actions.yaml')
        goap_actions = set(actions_data.get_actions().keys())
        
        # Load factory actions
        config_data = YamlData('data/action_configurations.yaml')
        factory = ActionFactory(config_data)
        factory_actions = set(factory.get_available_actions())
        
        # Composite actions don't need to be registered in factory (they're handled by ActionExecutor)
        composite_actions = {'hunt', 'gather_crafting_materials'}  # Add other composite actions here as they're created
        
        # Find actions that are in GOAP but not in factory (excluding composite actions)
        missing_from_factory = goap_actions - factory_actions - composite_actions
        
        # REGRESSION CHECK: No GOAP actions should be missing from factory
        self.assertEqual(len(missing_from_factory), 0,
                        f"GOAP actions not registered in factory: {sorted(missing_from_factory)}")
        
    def test_all_factory_actions_have_valid_classes(self):
        """Test that all registered actions have valid action classes."""
        config_data = YamlData('data/action_configurations.yaml')
        action_classes = config_data.data.get('action_classes', {})
        
        for action_name, class_path in action_classes.items():
            with self.subTest(action=action_name):
                # Try to import the class
                try:
                    module_path, class_name = class_path.rsplit('.', 1)
                    module = __import__(module_path, fromlist=[class_name])
                    action_class = getattr(module, class_name)
                    self.assertTrue(callable(action_class), 
                                  f"Action class {class_path} should be callable")
                except (ImportError, AttributeError) as e:
                    self.fail(f"Cannot import action class {class_path} for {action_name}: {e}")
    
    def test_no_orphaned_goap_actions(self):
        """Test that GOAP configuration doesn't reference non-existent actions."""
        actions_data = ActionsData('data/actions.yaml')
        goap_actions = set(actions_data.get_actions().keys())
        
        # Check that action files exist for all GOAP actions (except composite actions)
        action_files = set()
        actions_dir = 'src/controller/actions'
        for file in os.listdir(actions_dir):
            if file.endswith('.py') and file not in ['__init__.py', 'base.py']:
                action_files.add(file[:-3])  # Remove .py extension
        
        # Composite actions don't need files
        composite_actions = {'hunt', 'gather_crafting_materials'}  # Add other composite actions here
        
        missing_files = goap_actions - action_files - composite_actions
        self.assertEqual(len(missing_files), 0,
                        f"GOAP actions missing implementation files: {sorted(missing_files)}")


class TestMissionExecutorDelegationRegression(unittest.TestCase):
    """Test mission executor delegation to prevent method call errors."""
    
    def test_mission_executor_uses_goap_execution_manager(self):
        """
        REGRESSION TEST: Ensure MissionExecutor delegates to GOAPExecutionManager.
        
        Previously: Called controller.achieve_goal_with_goap() (removed method)
        Fixed: Now calls controller.goap_execution_manager.achieve_goal_with_goap()
        """
        mock_controller = Mock()
        mock_goal_manager = Mock()
        
        # Set up the controller's goap_execution_manager
        mock_goap_manager = Mock()
        mock_controller.goap_execution_manager = mock_goap_manager
        mock_controller.client = Mock()  # Required for mission execution
        mock_controller.character_state = Mock()
        mock_controller.character_state.data = {'level': 1}
        
        mission_executor = MissionExecutor(mock_goal_manager, mock_controller)
        
        # Mock goal manager methods
        mock_goal_manager.generate_goal_state.return_value = {'test_goal': True}
        
        # Test goal template execution
        goal_config = {'test': 'config'}
        mission_params = {'target_level': 2}
        
        # This should NOT raise AttributeError for achieve_goal_with_goap
        try:
            mission_executor._execute_goal_template('test_goal', goal_config, mission_params)
        except AttributeError as e:
            if "achieve_goal_with_goap" in str(e):
                self.fail("MissionExecutor still trying to call removed achieve_goal_with_goap method")
        except:
            pass  # Other exceptions are fine for this test
        
        # Verify the correct method was called
        mock_goap_manager.achieve_goal_with_goap.assert_called_once()


class TestPlanExecutionRegression(unittest.TestCase):
    """Test plan execution to prevent action execution failures."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.mock_client = Mock()
        
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_action_factory_loads_all_configurations(self):
        """Test that ActionFactory properly loads all action configurations."""
        config_data = YamlData('data/action_configurations.yaml')
        factory = ActionFactory(config_data)
        
        # Check that YAML-defined actions are loaded
        yaml_action_classes = config_data.data.get('action_classes', {})
        
        for action_name in yaml_action_classes:
            with self.subTest(action=action_name):
                self.assertTrue(factory.is_action_registered(action_name),
                              f"Action {action_name} should be registered in factory")
    
    @patch('src.controller.ai_player_controller.StateManagerMixin.initialize_state_management')
    @patch('src.controller.ai_player_controller.StateManagerMixin.create_managed_state')
    def test_controller_has_required_managers(self, mock_create_state, mock_init_state):
        """Test that controller has all required manager instances."""
        # Mock state creation
        mock_create_state.side_effect = [Mock(), Mock()]  # world_state, knowledge_base
        
        controller = AIPlayerController(self.mock_client)
        
        # REGRESSION CHECK: Ensure all managers exist
        required_managers = [
            'goap_execution_manager', 'skill_goal_manager', 'mission_executor',
            'cooldown_manager', 'learning_manager', 'goal_manager'
        ]
        
        for manager_name in required_managers:
            with self.subTest(manager=manager_name):
                self.assertTrue(hasattr(controller, manager_name),
                              f"Controller missing {manager_name}")
                self.assertIsNotNone(getattr(controller, manager_name),
                                   f"Controller {manager_name} is None")
    
    def test_goap_world_state_completeness(self):
        """Test that world state includes all variables needed by GOAP actions."""
        actions_data = ActionsData('data/actions.yaml')
        actions_config = actions_data.get_actions()
        
        # Collect all state variables used in GOAP actions
        all_conditions = set()
        all_reactions = set()
        
        for action_name, action_config in actions_config.items():
            conditions = action_config.get('conditions', {})
            reactions = action_config.get('reactions', {})
            
            all_conditions.update(conditions.keys())
            all_reactions.update(reactions.keys())
        
        all_state_variables = all_conditions | all_reactions
        
        # Test with a mock controller that has proper state calculation
        with patch('src.controller.ai_player_controller.StateManagerMixin.initialize_state_management'):
            with patch('src.controller.ai_player_controller.StateManagerMixin.create_managed_state') as mock_create_state:
                mock_world_state = Mock()
                mock_knowledge_base = Mock()
                mock_create_state.side_effect = [mock_world_state, mock_knowledge_base]
                
                controller = AIPlayerController(self.mock_client)
                
                # Mock character state
                mock_character = Mock()
                mock_character.data = {
                    'hp': 100, 'max_hp': 120, 'level': 1, 'x': 0, 'y': 0,
                    'cooldown_expiration': None
                }
                controller.character_state = mock_character
                
                # Mock goal manager to return complete state
                controller.goal_manager.calculate_world_state = Mock(return_value={
                    var: False for var in all_state_variables  # Default all to False
                })
                
                # Get world state
                world_state = controller.get_current_world_state()
                
                # REGRESSION CHECK: All GOAP variables should be present
                missing_variables = all_state_variables - set(world_state.keys())
                self.assertEqual(len(missing_variables), 0,
                               f"World state missing GOAP variables: {sorted(missing_variables)}")


class TestManagerIntegrationRegression(unittest.TestCase):
    """Test manager integration to prevent delegation failures."""
    
    def test_removed_methods_are_actually_removed(self):
        """Test that removed redundant methods are actually gone."""
        with patch('src.controller.ai_player_controller.StateManagerMixin.initialize_state_management'):
            with patch('src.controller.ai_player_controller.StateManagerMixin.create_managed_state') as mock_create_state:
                mock_create_state.side_effect = [Mock(), Mock()]
                controller = AIPlayerController(Mock())
                
                # REGRESSION CHECK: These methods should be removed
                removed_methods = [
                    'create_planner', 'plan_goal', 'create_world_with_planner',
                    'calculate_best_plan', '_get_action_class_defaults'
                ]
                
                for method_name in removed_methods:
                    with self.subTest(method=method_name):
                        self.assertFalse(hasattr(controller, method_name),
                                       f"Method {method_name} should be removed but still exists")
    
    def test_delegation_methods_exist(self):
        """Test that delegation methods exist and work."""
        with patch('src.controller.ai_player_controller.StateManagerMixin.initialize_state_management'):
            with patch('src.controller.ai_player_controller.StateManagerMixin.create_managed_state') as mock_create_state:
                mock_create_state.side_effect = [Mock(), Mock()]
                controller = AIPlayerController(Mock())
                
                # REGRESSION CHECK: These delegation methods should exist
                delegation_methods = [
                    'level_up_goal', 'get_available_actions', 'reload_action_configurations'
                ]
                
                for method_name in delegation_methods:
                    with self.subTest(method=method_name):
                        self.assertTrue(hasattr(controller, method_name),
                                      f"Delegation method {method_name} is missing")
                        self.assertTrue(callable(getattr(controller, method_name)),
                                      f"Delegation method {method_name} is not callable")


if __name__ == '__main__':
    unittest.main()