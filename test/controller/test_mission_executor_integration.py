"""
Test MissionExecutor integration with AIPlayerController.

This module tests the integration of the MissionExecutor with the AI controller,
ensuring that large monolithic methods have been successfully replaced with
goal template-driven execution.
"""

import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from src.controller.ai_player_controller import AIPlayerController
from src.controller.mission_executor import MissionExecutor

from test.fixtures import create_mock_client


class TestMissionExecutorIntegration(unittest.TestCase):
    """Test MissionExecutor integration with AIPlayerController."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create mock client
        self.mock_client = create_mock_client()
        
        # Create mock goal manager
        self.mock_goal_manager = Mock()
        self.mock_goal_manager.select_goal.return_value = ('level_up', {'description': 'Level up goal'})
        self.mock_goal_manager.generate_goal_state.return_value = {'character_level': 2}
        self.mock_goal_manager.calculate_world_state.return_value = {
            'character_level': 1,
            'character_alive': True,
            'character_safe': True
        }
        
        # Patch data directory to use temp directory
        with patch('src.game.globals.DATA_PREFIX', self.temp_dir):
            with patch('src.game.globals.CONFIG_PREFIX', self.temp_dir):
                with patch('src.controller.world.state.DATA_PREFIX', self.temp_dir):
                    with patch('src.controller.knowledge.base.DATA_PREFIX', self.temp_dir):
                        # Create required configuration files
                        self._create_test_config_files()
                        
                        # Initialize controller
                        self.controller = AIPlayerController(
                            client=self.mock_client,
                            goal_manager=self.mock_goal_manager
                        )
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _create_test_config_files(self):
        """Create minimal test configuration files."""
        # Create goal templates file
        goal_templates_content = """
goal_templates:
  level_up:
    description: "Level up goal"
    target_state:
      character_level: 2
  reach_level:
    description: "Reach specific level"
    target_state:
      character_level: "${target_level}"

thresholds:
  max_goap_iterations: 10
  max_cooldown_wait: 65
  cooldown_detection_threshold: 0.5
  min_cooldown_wait: 0.5
  character_refresh_cache_duration: 5.0
"""
        
        with open(os.path.join(self.temp_dir, 'goal_templates.yaml'), 'w') as f:
            f.write(goal_templates_content)
        
        # Create action configurations file
        action_config_content = """
action_configurations:
  move:
    type: "builtin"
    description: "Move character"
  attack:
    type: "builtin"
    description: "Attack target"

action_classes:
  move: "src.controller.actions.move.MoveAction"
  attack: "src.controller.actions.attack.AttackAction"
"""
        
        with open(os.path.join(self.temp_dir, 'action_configurations.yaml'), 'w') as f:
            f.write(action_config_content)
        
        # Create state configurations file
        state_config_content = """
state_configurations:
  world_state:
    class: "src.lib.goap_data.GOAPData"
    config:
      filename: "${data_prefix}/world.yaml"
  knowledge_base:
    class: "src.controller.knowledge.base.KnowledgeBase"
    config:
      filename: "${data_prefix}/knowledge.yaml"
"""
        
        with open(os.path.join(self.temp_dir, 'state_configurations.yaml'), 'w') as f:
            f.write(state_config_content)
        
        # Create state engine file
        state_engine_content = """
state_calculation_rules:
  character_safe:
    formula: "hp_percentage >= 30"
  character_alive:
    formula: "character_hp > 0"
"""
        
        with open(os.path.join(self.temp_dir, 'state_engine.yaml'), 'w') as f:
            f.write(state_engine_content)
        
        # Create empty world and knowledge files
        with open(os.path.join(self.temp_dir, 'world.yaml'), 'w') as f:
            f.write("{}\n")
        
        with open(os.path.join(self.temp_dir, 'knowledge.yaml'), 'w') as f:
            f.write("{}\n")
    
    def test_mission_executor_initialization(self):
        """Test that MissionExecutor is properly initialized in controller."""
        self.assertIsInstance(self.controller.mission_executor, MissionExecutor)
        self.assertEqual(self.controller.mission_executor.controller, self.controller)
        self.assertEqual(self.controller.mission_executor.goal_manager, self.mock_goal_manager)
    
    def test_execute_autonomous_mission_delegation(self):
        """Test that execute_autonomous_mission delegates to MissionExecutor."""
        # Mock character state
        mock_character_state = Mock()
        mock_character_state.data = {'level': 1, 'hp': 100}
        self.controller.character_state = mock_character_state
        
        # Mock mission executor
        with patch.object(self.controller.mission_executor, 'execute_progression_mission') as mock_execute:
            mock_execute.return_value = True
            
            # Test mission execution
            mission_params = {'target_level': 2}
            result = self.controller.execute_autonomous_mission(mission_params)
            
            # Verify delegation
            self.assertTrue(result)
            mock_execute.assert_called_once_with(mission_params)
    
    def test_level_up_goal_delegation(self):
        """Test that level_up_goal delegates to MissionExecutor."""
        # Mock character state
        mock_character_state = Mock()
        mock_character_state.data = {'level': 1, 'hp': 100}
        self.controller.character_state = mock_character_state
        
        # Mock mission executor
        with patch.object(self.controller.mission_executor, 'execute_level_progression') as mock_execute:
            mock_execute.return_value = True
            
            # Test level progression
            result = self.controller.level_up_goal(target_level=3)
            
            # Verify delegation
            self.assertTrue(result)
            mock_execute.assert_called_once_with(3)
    
    def test_level_up_goal_default_target(self):
        """Test that level_up_goal works with default target level."""
        # Mock character state
        mock_character_state = Mock()
        mock_character_state.data = {'level': 1, 'hp': 100}
        self.controller.character_state = mock_character_state
        
        # Mock mission executor
        with patch.object(self.controller.mission_executor, 'execute_level_progression') as mock_execute:
            mock_execute.return_value = True
            
            # Test level progression with default target
            result = self.controller.level_up_goal()
            
            # Verify delegation with None (default)
            self.assertTrue(result)
            mock_execute.assert_called_once_with(None)
    
    def test_configuration_reload_includes_mission_executor(self):
        """Test that configuration reload includes MissionExecutor."""
        # Mock the mission executor's _load_configuration method
        with patch.object(self.controller.mission_executor, '_load_configuration') as mock_load:
            with patch.object(self.controller.action_executor, 'reload_configuration'):
                with patch.object(self.controller, 'reload_state_configurations'):
                    
                    # Reload configurations
                    self.controller.reload_action_configurations()
                    
                    # Verify mission executor configuration was reloaded
                    mock_load.assert_called_once()
    
    def test_mission_executor_configuration_access(self):
        """Test that MissionExecutor can access its configuration."""
        # Verify that the mission executor has loaded its configuration
        self.assertIsNotNone(self.controller.mission_executor.goal_templates)
        self.assertIsNotNone(self.controller.mission_executor.thresholds)
        self.assertIn('level_up', self.controller.mission_executor.goal_templates)
        self.assertIn('reach_level', self.controller.mission_executor.goal_templates)
    
    def test_large_method_replacement_reduction(self):
        """Test that large monolithic methods have been replaced with delegation."""
        # Get the source code of the methods to check their size
        import inspect
        
        # Test execute_autonomous_mission method size
        execute_method_source = inspect.getsource(self.controller.execute_autonomous_mission)
        # Should be much smaller now (just delegation)
        execute_lines = len(execute_method_source.strip().split('\n'))
        self.assertLess(execute_lines, 20, "execute_autonomous_mission should be much smaller after refactoring")
        
        # Test level_up_goal method size
        level_up_method_source = inspect.getsource(self.controller.level_up_goal)
        # Should be small (just delegation)
        level_up_lines = len(level_up_method_source.strip().split('\n'))
        self.assertLess(level_up_lines, 20, "level_up_goal should be small after refactoring")
    
    def test_backward_compatibility_maintained(self):
        """Test that existing method signatures are maintained for backward compatibility."""
        # Test that the methods exist and have the expected signatures
        self.assertTrue(hasattr(self.controller, 'execute_autonomous_mission'))
        self.assertTrue(hasattr(self.controller, 'level_up_goal'))
        self.assertTrue(hasattr(self.controller, 'find_and_move_to_level_appropriate_monster'))
        
        # Test that methods can still be called (even if they delegate)
        self.assertTrue(callable(self.controller.execute_autonomous_mission))
        self.assertTrue(callable(self.controller.level_up_goal))
        self.assertTrue(callable(self.controller.find_and_move_to_level_appropriate_monster))


if __name__ == '__main__':
    unittest.main()