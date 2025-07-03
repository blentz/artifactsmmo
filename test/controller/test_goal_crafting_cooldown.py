"""
Test that crafting goals are not selected during cooldown.

This test validates the fix for the bug where equipment upgrade goals were being
selected while the character was on cooldown, causing planning failures.
"""

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from src.controller.goal_manager import GOAPGoalManager


class TestGoalCraftingCooldown(unittest.TestCase):
    """Test goal manager crafting goal selection during cooldown."""
    
    def setUp(self):
        """Set up test environment with mocked configuration."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create a mock configuration file to avoid loading from disk
        with patch('src.lib.yaml_data.YamlData') as mock_yaml_data:
            mock_yaml_data.return_value.data = {
                'goal_templates': {
                    'upgrade_weapon': {
                        'description': 'Craft and equip a better weapon',
                        'target_state': {
                            'equipment_status': {
                                'upgrade_status': 'completed'
                            }
                        }
                    },
                    'upgrade_armor': {
                        'description': 'Craft and equip better armor',
                        'target_state': {
                            'equipment_status': {
                                'upgrade_status': 'completed'
                            }
                        }
                    },
                    'wait_for_cooldown': {
                        'description': 'Wait for cooldown to expire',
                        'target_state': {
                            'character_status': {
                                'cooldown_active': False
                            }
                        }
                    }
                },
                'goal_selection_rules': {
                    'maintenance': [
                        {
                            'condition': {
                                'character_status': {
                                    'cooldown_active': True
                                }
                            },
                            'goal': 'wait_for_cooldown',
                            'priority': 80
                        }
                    ]
                },
                'state_calculation_rules': {},
                'state_mappings': {},
                'thresholds': {},
                'state_defaults': {
                    'character_status': {},
                    'equipment_status': {},
                    'combat_context': {},
                    'skills': {}
                }
            }
            self.goal_manager = GOAPGoalManager()
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_crafting_goal_not_viable_during_cooldown(self):
        """Test that crafting goals are not viable when character is on cooldown."""
        # Create state with active cooldown
        current_state = {
            'character_status': {
                'level': 3,
                'cooldown_active': True,
                'safe': True,
                'alive': True
            },
            'equipment_status': {
                'upgrade_status': 'needs_analysis'
            }
        }
        
        # Test that crafting goals are not viable
        self.assertFalse(
            self.goal_manager._is_crafting_goal_viable('upgrade_weapon', current_state),
            "upgrade_weapon should not be viable during cooldown"
        )
        self.assertFalse(
            self.goal_manager._is_crafting_goal_viable('upgrade_armor', current_state),
            "upgrade_armor should not be viable during cooldown"
        )
    
    def test_crafting_goal_viable_without_cooldown(self):
        """Test that crafting goals are viable when character is not on cooldown."""
        # Create state without cooldown
        current_state = {
            'character_status': {
                'level': 3,
                'cooldown_active': False,
                'safe': True,
                'alive': True
            },
            'equipment_status': {
                'upgrade_status': 'needs_analysis'
            }
        }
        
        # Test that crafting goals are viable
        self.assertTrue(
            self.goal_manager._is_crafting_goal_viable('upgrade_weapon', current_state),
            "upgrade_weapon should be viable without cooldown"
        )
        self.assertTrue(
            self.goal_manager._is_crafting_goal_viable('upgrade_armor', current_state),
            "upgrade_armor should be viable without cooldown"
        )
    
    def test_goal_selection_during_cooldown(self):
        """Test that wait_for_cooldown is selected over crafting goals during cooldown."""
        # Create state with active cooldown
        future_time = datetime.now(timezone.utc) + timedelta(seconds=10)
        char_data = {
            'cooldown': 10,
            'cooldown_expiration': future_time.isoformat(),
            'hp': 100,
            'max_hp': 100,
            'level': 3,
            'xp': 88,
            'max_xp': 350,
            'x': 0,
            'y': 0,
            'weapon_slot': 'wooden_stick'
        }
        
        # Create mock character state
        mock_character_state = Mock()
        mock_character_state.data = char_data
        
        # Calculate world state
        world_state = self.goal_manager.calculate_world_state(mock_character_state)
        
        # Verify cooldown is active
        self.assertTrue(world_state['character_status']['cooldown_active'])
        
        # Select goal - should get wait_for_cooldown, not upgrade_weapon
        available_goals = ['upgrade_weapon', 'upgrade_armor', 'wait_for_cooldown']
        selected_goal = self.goal_manager.select_goal(world_state, available_goals)
        
        # Should select wait_for_cooldown
        self.assertIsNotNone(selected_goal)
        goal_name, goal_config = selected_goal
        self.assertEqual(goal_name, 'wait_for_cooldown',
                        f"Should select wait_for_cooldown during cooldown, not {goal_name}")
    
    def test_crafting_goal_selected_after_cooldown(self):
        """Test that crafting goals can be selected after cooldown expires."""
        # Create state without cooldown
        char_data = {
            'cooldown': 0,
            'cooldown_expiration': None,
            'hp': 100,
            'max_hp': 100,
            'level': 3,
            'xp': 88,
            'max_xp': 350,
            'x': 0,
            'y': 0,
            'weapon_slot': 'wooden_stick'
        }
        
        # Create mock character state
        mock_character_state = Mock()
        mock_character_state.data = char_data
        
        # Calculate world state
        world_state = self.goal_manager.calculate_world_state(mock_character_state)
        
        # Verify cooldown is not active
        self.assertFalse(world_state['character_status']['cooldown_active'])
        
        # Manually set equipment status to trigger crafting goals
        world_state['equipment_status']['upgrade_status'] = 'needs_analysis'
        
        # Select goal - crafting goals should now be available
        available_goals = ['upgrade_weapon', 'upgrade_armor']
        
        # Check that crafting goals are viable
        self.assertTrue(
            self.goal_manager._is_crafting_goal_viable('upgrade_weapon', world_state),
            "upgrade_weapon should be viable after cooldown"
        )


if __name__ == '__main__':
    unittest.main()