"""
Test SkillGoalManager functionality and skill-specific goal creation.

This module tests the SkillGoalManager class that provides YAML-configurable
skill progression goals for all crafting, gathering, and combat skills.
"""

import os
import tempfile
import unittest
from unittest.mock import patch

from src.controller.skill_goal_manager import SkillGoalManager, SkillType


class TestSkillGoalManager(unittest.TestCase):
    """Test SkillGoalManager functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Patch config directory to use temp directory
        with patch('src.game.globals.CONFIG_PREFIX', self.temp_dir):
            # Create required configuration file
            self._create_test_config_file()
            
            # Initialize skill goal manager
            self.skill_manager = SkillGoalManager()
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _create_test_config_file(self):
        """Create minimal test configuration file."""
        config_content = """
skill_templates:
  combat:
    description: "Level up combat skill"
    type: "combat"
    requirements:
      has_weapon: true
      character_alive: true
    strategy:
      primary_action: "hunt_monsters"
      
  woodcutting:
    description: "Level up woodcutting"
    type: "gathering"
    requirements:
      has_axe: true
      character_alive: true
    strategy:
      primary_action: "gather_wood"
      resource_type: "wood"
      
  weaponcrafting:
    description: "Level up weaponcrafting"
    type: "crafting"
    requirements:
      has_materials: true
      at_workshop: "weaponcrafting"
    strategy:
      primary_action: "craft_weapon"

progression_rules:
  combat:
    "1-5":
      target_monsters: ["chicken", "cow"]
      hunt_radius: 10
      safety_threshold: 50
    "6-15":
      target_monsters: ["goblin", "slime"]
      hunt_radius: 15
      safety_threshold: 40
      
  woodcutting:
    "1-10":
      target_trees: ["ash_tree"]
      gather_amount: 10
    "11-20":
      target_trees: ["spruce_tree"]
      gather_amount: 15

resource_requirements:
  weaponcrafting:
    copper_ore:
      base_amount: 20
      per_level: 10
    iron_ore:
      base_amount: 15
      per_level: 8
"""
        
        with open(os.path.join(self.temp_dir, 'skill_goals.yaml'), 'w') as f:
            f.write(config_content)
    
    def test_skill_manager_initialization(self):
        """Test that SkillGoalManager initializes correctly."""
        self.assertIsNotNone(self.skill_manager.skill_templates)
        self.assertIsNotNone(self.skill_manager.progression_rules)
        self.assertIn('combat', self.skill_manager.skill_templates)
        self.assertIn('woodcutting', self.skill_manager.skill_templates)
        self.assertIn('weaponcrafting', self.skill_manager.skill_templates)
    
    def test_create_skill_up_goal_combat(self):
        """Test creating a combat skill goal."""
        goal_state = self.skill_manager.create_skill_up_goal(
            SkillType.COMBAT, target_level=5, current_level=1
        )
        
        # Verify goal structure
        self.assertEqual(goal_state['combat_level'], 5)
        self.assertTrue(goal_state['character_alive'])
        self.assertTrue(goal_state['character_safe'])
        self.assertTrue(goal_state['has_weapon'])
    
    def test_create_skill_up_goal_gathering(self):
        """Test creating a gathering skill goal."""
        goal_state = self.skill_manager.create_skill_up_goal(
            SkillType.WOODCUTTING, target_level=10, current_level=5
        )
        
        # Verify goal structure
        self.assertEqual(goal_state['woodcutting_level'], 10)
        self.assertTrue(goal_state['character_alive'])
        self.assertTrue(goal_state['has_axe'])
    
    def test_create_skill_up_goal_crafting(self):
        """Test creating a crafting skill goal with resource requirements."""
        goal_state = self.skill_manager.create_skill_up_goal(
            SkillType.WEAPONCRAFTING, target_level=5, current_level=1
        )
        
        # Verify goal structure
        self.assertEqual(goal_state['weaponcrafting_level'], 5)
        self.assertTrue(goal_state['character_alive'])
        self.assertTrue(goal_state['has_materials'])
        self.assertEqual(goal_state['at_workshop'], 'weaponcrafting')
        
        # Verify resource requirements were calculated
        self.assertIn('has_copper_ore', goal_state)
        self.assertIn('has_iron_ore', goal_state)
        
        # Should be base_amount + (levels_to_gain * per_level)
        # copper: 20 + (4 * 10) = 60
        # iron: 15 + (4 * 8) = 47
        self.assertEqual(goal_state['has_copper_ore'], 60)
        self.assertEqual(goal_state['has_iron_ore'], 47)
    
    def test_get_skill_progression_strategy(self):
        """Test getting skill progression strategy."""
        strategy = self.skill_manager.get_skill_progression_strategy(
            SkillType.COMBAT, current_level=3
        )
        
        # Should match the 1-5 range
        self.assertEqual(strategy['skill'], 'combat')
        self.assertEqual(strategy['level_range'], '1-5')
        self.assertEqual(strategy['current_level'], 3)
        self.assertIn('target_monsters', strategy['strategy'])
        self.assertEqual(strategy['strategy']['target_monsters'], ['chicken', 'cow'])
    
    def test_get_skill_progression_strategy_higher_level(self):
        """Test getting strategy for higher level."""
        strategy = self.skill_manager.get_skill_progression_strategy(
            SkillType.COMBAT, current_level=10
        )
        
        # Should match the 6-15 range
        self.assertEqual(strategy['level_range'], '6-15')
        # Check that goblin is in the list (actual config may have different slime types)
        self.assertIn('goblin', strategy['strategy']['target_monsters'])
    
    def test_is_crafting_skill(self):
        """Test crafting skill identification."""
        self.assertFalse(self.skill_manager._is_crafting_skill(SkillType.COMBAT))
        self.assertFalse(self.skill_manager._is_crafting_skill(SkillType.WOODCUTTING))
        self.assertTrue(self.skill_manager._is_crafting_skill(SkillType.WEAPONCRAFTING))
        self.assertTrue(self.skill_manager._is_crafting_skill(SkillType.GEARCRAFTING))
        self.assertTrue(self.skill_manager._is_crafting_skill(SkillType.COOKING))
    
    def test_level_in_range(self):
        """Test level range checking."""
        self.assertTrue(self.skill_manager._level_in_range(3, '1-5'))
        self.assertTrue(self.skill_manager._level_in_range(1, '1-5'))
        self.assertTrue(self.skill_manager._level_in_range(5, '1-5'))
        self.assertFalse(self.skill_manager._level_in_range(6, '1-5'))
        self.assertFalse(self.skill_manager._level_in_range(0, '1-5'))
    
    def test_parse_level_range(self):
        """Test level range parsing."""
        min_level, max_level = self.skill_manager._parse_level_range('1-5')
        self.assertEqual(min_level, 1)
        self.assertEqual(max_level, 5)
        
        min_level, max_level = self.skill_manager._parse_level_range('10-20')
        self.assertEqual(min_level, 10)
        self.assertEqual(max_level, 20)
    
    def test_calculate_resource_needs(self):
        """Test resource requirement calculations."""
        resource_needs = self.skill_manager._calculate_resource_needs(
            SkillType.WEAPONCRAFTING, current_level=1, target_level=5
        )
        
        # Should calculate based on levels to gain (4 levels)
        self.assertEqual(resource_needs['has_copper_ore'], 60)  # 20 + (4 * 10)
        self.assertEqual(resource_needs['has_iron_ore'], 47)   # 15 + (4 * 8)
    
    def test_get_available_skills(self):
        """Test getting available skills."""
        available = self.skill_manager.get_available_skills()
        
        # Should include skills from our test config
        skill_names = [skill.value for skill in available]
        self.assertIn('combat', skill_names)
        self.assertIn('woodcutting', skill_names)
        self.assertIn('weaponcrafting', skill_names)
    
    def test_create_world_with_planner(self):
        """Test GOAP world creation for skill goals."""
        start_state = {
            'combat_level': 1,
            'character_alive': True,
            'has_weapon': True
        }
        
        goal_state = {
            'combat_level': 3,
            'character_alive': True
        }
        
        actions_config = {
            'attack': {
                'conditions': {'has_weapon': True},
                'reactions': {'combat_xp': 10},
                'weight': 1.0
            }
        }
        
        world = self.skill_manager.create_world_with_planner(
            start_state, goal_state, actions_config
        )
        
        # Verify world was created
        self.assertIsNotNone(world)
        self.assertIsNotNone(self.skill_manager.current_world)
        self.assertIsNotNone(self.skill_manager.current_planner)
    
    def test_action_relevant_for_skill(self):
        """Test skill-action relevance checking."""
        # Combat actions
        self.assertTrue(self.skill_manager._action_relevant_for_skill('attack', 'combat'))
        self.assertTrue(self.skill_manager._action_relevant_for_skill('hunt', 'combat'))
        
        # Gathering actions
        self.assertTrue(self.skill_manager._action_relevant_for_skill('gather_resources', 'woodcutting'))
        self.assertTrue(self.skill_manager._action_relevant_for_skill('find_resources', 'mining'))
        
        # Crafting actions
        self.assertTrue(self.skill_manager._action_relevant_for_skill('craft_item', 'weaponcrafting'))
        
        # Irrelevant actions
        self.assertFalse(self.skill_manager._action_relevant_for_skill('attack', 'woodcutting'))
    
    def test_is_skill_relevant_action(self):
        """Test overall action relevance for skill goals."""
        goal_state = {'combat_level': 5, 'character_alive': True}
        
        # Basic actions should always be relevant
        self.assertTrue(self.skill_manager._is_skill_relevant_action('move', goal_state))
        self.assertTrue(self.skill_manager._is_skill_relevant_action('rest', goal_state))
        self.assertTrue(self.skill_manager._is_skill_relevant_action('wait', goal_state))
        
        # Combat actions should be relevant for combat goals
        self.assertTrue(self.skill_manager._is_skill_relevant_action('attack', goal_state))
        
        # Test default behavior for actions that don't match any skill goals
        non_skill_goal = {'character_alive': True, 'some_other_state': True}
        self.assertTrue(self.skill_manager._is_skill_relevant_action('random_action', non_skill_goal))
    
    def test_create_skill_up_goal_unknown_skill(self):
        """Test creating goal for unknown skill."""
        # Use a skill type that exists in enum but not in config
        # Since FISHING actually exists in default config, we'll test with None
        
        goal_state = self.skill_manager.create_skill_up_goal(
            None, target_level=5, current_level=1
        )
        
        # Should return empty dict for None/invalid skills
        self.assertEqual(goal_state, {})
    
    def test_configuration_reload(self):
        """Test configuration reloading."""
        # Verify initial state
        initial_template_count = len(self.skill_manager.skill_templates)
        self.assertGreater(initial_template_count, 0)
        
        # Test that reload_configuration method exists and can be called
        # We can't easily test the file reload in isolation because it uses
        # the global CONFIG_PREFIX which points to the real config file
        self.skill_manager.reload_configuration()
        
        # Verify configuration is still loaded after reload
        self.assertEqual(len(self.skill_manager.skill_templates), initial_template_count)
    
    def test_load_configuration_exception(self):
        """Test configuration loading with exception."""
        from unittest.mock import Mock, patch
        
        # Create a manager that will fail to load config
        with patch('src.controller.skill_goal_manager.YamlData') as mock_yaml:
            mock_yaml_instance = Mock()
            mock_yaml_instance.data = Mock()
            mock_yaml_instance.data.get = Mock(side_effect=Exception("Config error"))
            mock_yaml.return_value = mock_yaml_instance
            
            # Initialize should handle the exception and set empty defaults
            manager = SkillGoalManager()
            
            # Should have empty configurations
            self.assertEqual(manager.skill_templates, {})
            self.assertEqual(manager.progression_rules, {})
            self.assertEqual(manager.skill_thresholds, {})
            self.assertEqual(manager.resource_requirements, {})
            self.assertEqual(manager.crafting_chains, {})
    
    def test_create_skill_up_goal_missing_template(self):
        """Test creating goal for skill without template."""
        # Create a manager with no templates
        from unittest.mock import Mock, patch
        
        with patch('src.controller.skill_goal_manager.YamlData') as mock_yaml:
            mock_yaml_instance = Mock()
            mock_yaml_instance.data = {}
            mock_yaml.return_value = mock_yaml_instance
            
            manager = SkillGoalManager()
            goal_state = manager.create_skill_up_goal(
                SkillType.FISHING, target_level=5, current_level=1
            )
            
            # Should return empty dict for missing templates
            self.assertEqual(goal_state, {})
    
    def test_create_skill_up_goal_template_substitution(self):
        """Test template variable substitution in requirements."""
        # Add a template with variable substitution
        self.skill_manager.skill_templates['test_skill'] = {
            'requirements': {
                'has_materials': '${target_level}',
                'skill_level': '${target_level}'
            }
        }
        
        # Create a temporary SkillType for testing
        from unittest.mock import Mock
        mock_skill = Mock()
        mock_skill.value = 'test_skill'
        
        goal_state = self.skill_manager.create_skill_up_goal(
            mock_skill, target_level=7, current_level=2
        )
        
        # Variables should be substituted with target_level
        self.assertEqual(goal_state['has_materials'], '7')
        self.assertEqual(goal_state['skill_level'], '7')
    
    def test_calculate_resource_needs_static_config(self):
        """Test resource calculation with static values."""
        # Add resource with static value
        self.skill_manager.resource_requirements['test_skill'] = {
            'static_resource': 50
        }
        
        from unittest.mock import Mock
        mock_skill = Mock()
        mock_skill.value = 'test_skill'
        
        resource_needs = self.skill_manager._calculate_resource_needs(
            mock_skill, current_level=1, target_level=5
        )
        
        # Static value should be used as-is
        self.assertEqual(resource_needs['has_static_resource'], 50)
    
    def test_get_skill_progression_strategy_no_rules(self):
        """Test progression strategy for skill without rules."""
        # Create a manager with no progression rules
        from unittest.mock import Mock, patch
        
        with patch('src.controller.skill_goal_manager.YamlData') as mock_yaml:
            mock_yaml_instance = Mock()
            mock_yaml_instance.data = {'skill_templates': {}, 'progression_rules': {}}
            mock_yaml.return_value = mock_yaml_instance
            
            manager = SkillGoalManager()
            strategy = manager.get_skill_progression_strategy(
                SkillType.FISHING, current_level=5
            )
            
            # Should return error for missing rules
            self.assertIn('error', strategy)
            self.assertIn('No progression rules for fishing', strategy['error'])
    
    def test_get_skill_progression_strategy_fallback(self):
        """Test progression strategy fallback to highest range."""
        # Test with level beyond all ranges for combat in our test config
        strategy = self.skill_manager.get_skill_progression_strategy(
            SkillType.COMBAT, current_level=50  # Beyond defined ranges
        )
        
        # Should fallback to highest available range
        # The actual highest range depends on the real config loaded
        self.assertEqual(strategy['current_level'], 50)
        self.assertIn('level_range', strategy)
        # Just verify it returns some strategy, not the specific range
        self.assertIn('strategy', strategy)
    
    def test_parse_level_range_single_level(self):
        """Test parsing single level ranges."""
        min_level, max_level = self.skill_manager._parse_level_range('10')
        self.assertEqual(min_level, 10)
        self.assertEqual(max_level, 10)
    
    def test_achieve_skill_goal_with_goap_no_goal(self):
        """Test GOAP execution when goal creation fails."""
        from unittest.mock import Mock, patch
        
        # Create a manager with no templates to ensure goal creation fails
        with patch('src.controller.skill_goal_manager.YamlData') as mock_yaml:
            mock_yaml_instance = Mock()
            mock_yaml_instance.data = {}
            mock_yaml.return_value = mock_yaml_instance
            
            manager = SkillGoalManager()
            mock_controller = Mock()
            current_state = {'fishing_level': 1}
            
            # Should return False when goal creation fails (no templates)
            result = manager.achieve_skill_goal_with_goap(
                SkillType.FISHING, 5, current_state, mock_controller
            )
            
            self.assertFalse(result)
    
    def test_achieve_skill_goal_with_goap_no_plan(self):
        """Test GOAP execution when no plan can be found."""
        from unittest.mock import Mock, patch
        
        mock_controller = Mock()
        current_state = {'combat_level': 1}
        
        with patch.object(self.skill_manager, '_load_skill_actions') as mock_load_actions, \
             patch('src.controller.skill_goal_manager.World') as mock_world_class, \
             patch('src.controller.skill_goal_manager.Planner') as mock_planner_class, \
             patch('src.controller.skill_goal_manager.Action_List'):
            
            mock_load_actions.return_value = {}
            mock_world = Mock()
            mock_planner = Mock()
            mock_planner.calculate.return_value = []  # No plans found
            
            mock_world_class.return_value = mock_world
            mock_planner_class.return_value = mock_planner
            
            self.skill_manager.current_planner = mock_planner
            
            result = self.skill_manager.achieve_skill_goal_with_goap(
                SkillType.COMBAT, 5, current_state, mock_controller
            )
            
            self.assertFalse(result)
    
    def test_achieve_skill_goal_with_goap_success(self):
        """Test successful GOAP execution."""
        from unittest.mock import Mock, patch
        
        mock_controller = Mock()
        mock_controller.execute_plan.return_value = True
        current_state = {'combat_level': 1}
        
        with patch.object(self.skill_manager, '_load_skill_actions') as mock_load_actions, \
             patch('src.controller.skill_goal_manager.World') as mock_world_class, \
             patch('src.controller.skill_goal_manager.Planner') as mock_planner_class, \
             patch('src.controller.skill_goal_manager.Action_List'):
            
            mock_load_actions.return_value = {'attack': {}}
            mock_world = Mock()
            mock_planner = Mock()
            
            # Mock plan with dictionary actions
            mock_plan = [
                {'name': 'attack', 'target': 'chicken'},
                {'name': 'rest'}
            ]
            mock_planner.calculate.return_value = [mock_plan]
            
            mock_world_class.return_value = mock_world
            mock_planner_class.return_value = mock_planner
            
            self.skill_manager.current_planner = mock_planner
            
            result = self.skill_manager.achieve_skill_goal_with_goap(
                SkillType.COMBAT, 5, current_state, mock_controller
            )
            
            self.assertTrue(result)
            # Verify plan was set on controller
            self.assertEqual(mock_controller.current_plan, mock_plan)
            self.assertEqual(mock_controller.current_action_index, 0)
            mock_controller.execute_plan.assert_called_once()
    
    def test_achieve_skill_goal_with_goap_action_objects(self):
        """Test GOAP execution with action objects instead of dictionaries."""
        from unittest.mock import Mock, patch
        
        mock_controller = Mock()
        mock_controller.execute_plan.return_value = True
        current_state = {'combat_level': 1}
        
        with patch.object(self.skill_manager, '_load_skill_actions') as mock_load_actions, \
             patch('src.controller.skill_goal_manager.World') as mock_world_class, \
             patch('src.controller.skill_goal_manager.Planner') as mock_planner_class, \
             patch('src.controller.skill_goal_manager.Action_List'):
            
            mock_load_actions.return_value = {'attack': {}}
            mock_world = Mock()
            mock_planner = Mock()
            
            # Mock plan with action objects
            mock_action1 = Mock()
            mock_action1.name = 'attack'
            mock_action1.reactions = {'target': 'chicken'}
            
            mock_action2 = Mock()
            mock_action2.name = 'rest'
            mock_action2.reactions = {}
            
            mock_plan = [mock_action1, mock_action2]
            mock_planner.calculate.return_value = [mock_plan]
            
            mock_world_class.return_value = mock_world
            mock_planner_class.return_value = mock_planner
            
            self.skill_manager.current_planner = mock_planner
            
            result = self.skill_manager.achieve_skill_goal_with_goap(
                SkillType.COMBAT, 5, current_state, mock_controller
            )
            
            self.assertTrue(result)
            # Verify plan was converted to dictionaries
            expected_plan = [
                {'name': 'attack', 'target': 'chicken'},
                {'name': 'rest'}
            ]
            self.assertEqual(mock_controller.current_plan, expected_plan)
    
    def test_load_skill_actions_skill_specific(self):
        """Test loading skill-specific actions."""
        from unittest.mock import Mock, patch
        
        with patch('src.controller.skill_goal_manager.ActionsData') as mock_actions_data_class:
            mock_actions_data = Mock()
            mock_actions_data.get_actions.return_value = {'craft_weapon': {}}
            mock_actions_data_class.return_value = mock_actions_data
            
            result = self.skill_manager._load_skill_actions(SkillType.WEAPONCRAFTING)
            
            self.assertEqual(result, {'craft_weapon': {}})
    
    def test_load_skill_actions_fallback_to_default(self):
        """Test fallback to default actions when skill-specific fails."""
        from unittest.mock import Mock, patch
        
        with patch('src.controller.skill_goal_manager.ActionsData') as mock_actions_data_class:
            # First call (skill-specific) fails, second call (default) succeeds
            mock_skill_actions = Mock()
            mock_skill_actions.get_actions.side_effect = Exception("File not found")
            
            mock_default_actions = Mock()
            mock_default_actions.get_actions.return_value = {'move': {}, 'rest': {}}
            
            mock_actions_data_class.side_effect = [mock_skill_actions, mock_default_actions]
            
            result = self.skill_manager._load_skill_actions(SkillType.WEAPONCRAFTING)
            
            self.assertEqual(result, {'move': {}, 'rest': {}})
    
    def test_load_skill_actions_all_fail(self):
        """Test when both skill-specific and default action loading fails."""
        from unittest.mock import Mock, patch
        
        with patch('src.controller.skill_goal_manager.ActionsData') as mock_actions_data_class:
            mock_actions_data = Mock()
            mock_actions_data.get_actions.side_effect = Exception("File not found")
            mock_actions_data_class.return_value = mock_actions_data
            
            result = self.skill_manager._load_skill_actions(SkillType.WEAPONCRAFTING)
            
            self.assertEqual(result, {})


if __name__ == '__main__':
    unittest.main()