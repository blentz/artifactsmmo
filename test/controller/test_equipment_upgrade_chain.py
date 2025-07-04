"""Test equipment upgrade chain triggered by combat loss."""

import unittest
from unittest.mock import MagicMock, patch

from src.controller.actions.attack import AttackAction
from src.controller.actions.analyze_equipment_gaps import AnalyzeEquipmentGapsAction
from src.controller.actions.initiate_equipment_analysis import InitiateEquipmentAnalysisAction
from src.controller.ai_player_controller import AIPlayerController
from src.lib.action_context import ActionContext


class TestEquipmentUpgradeChain(unittest.TestCase):
    """Test the equipment upgrade chain triggered by combat loss."""

    def setUp(self):
        """Set up test fixtures."""
        self.controller = AIPlayerController()
        self.mock_client = MagicMock()
        self.controller.set_client(self.mock_client)

    def test_combat_loss_triggers_equipment_analysis(self):
        """Test that combat loss sets upgrade_status to needs_analysis."""
        # Arrange
        attack_action = AttackAction()
        context = ActionContext()
        context.character_name = "test_char"
        
        # Mock a combat loss response
        mock_response = MagicMock()
        mock_response.data.fight.to_dict.return_value = {
            'result': 'loss',
            'xp': 0,
            'gold': 0,
            'drops': []
        }
        
        # Act
        with patch('src.controller.actions.attack.fight_character_api', return_value=mock_response):
            result = attack_action.execute(self.mock_client, context)
        
        # Assert
        self.assertTrue(result.success)
        # Check that reactions were updated for combat loss
        self.assertEqual(attack_action.reactions['equipment_status']['upgrade_status'], 'needs_analysis')
        self.assertEqual(attack_action.reactions['combat_context']['status'], 'completed')

    def test_initiate_equipment_analysis_requires_needs_analysis(self):
        """Test that initiate_equipment_analysis requires needs_analysis status."""
        # Arrange
        action = InitiateEquipmentAnalysisAction()
        
        # Assert
        self.assertEqual(action.conditions['equipment_status']['upgrade_status'], 'needs_analysis')
        self.assertEqual(action.reactions['equipment_status']['upgrade_status'], 'analyzing')

    def test_analyze_equipment_gaps_requires_analyzing(self):
        """Test that analyze_equipment_gaps requires analyzing status."""
        # Arrange
        action = AnalyzeEquipmentGapsAction()
        
        # Assert
        self.assertEqual(action.conditions['equipment_status']['upgrade_status'], 'analyzing')

    def test_analyze_equipment_gaps_sets_combat_ready(self):
        """Test that analyze_equipment_gaps can set combat_ready status."""
        # Arrange
        action = AnalyzeEquipmentGapsAction()
        context = ActionContext()
        
        # Mock character state with good equipment
        context.character_state = MagicMock()
        context.character_state.data = {
            'level': 1,
            'weapon_slot': 'wooden_stick'  # Character data has equipment slots
        }
        
        # Set equipment status in world state
        context.set_result('equipment_status', {
            'weapon': 'wooden_stick'
        })
        
        # Act
        result = action.execute(self.mock_client, context)
        
        # Assert
        self.assertTrue(result.success)
        self.assertTrue(result.data.get('is_combat_ready', False))
        # Check that reactions were updated for combat ready
        self.assertEqual(action.reactions['equipment_status']['upgrade_status'], 'combat_ready')

    def test_goap_chain_from_needs_analysis_to_combat_ready(self):
        """Test the complete GOAP chain from needs_analysis to combat_ready."""
        # This tests that GOAP can find a valid plan
        start_state = {
            'equipment_status': {
                'upgrade_status': 'needs_analysis',
                'gaps_analyzed': False
            },
            'character_status': {
                'alive': True
            }
        }
        
        goal_state = {
            'equipment_status': {
                'upgrade_status': 'combat_ready'
            }
        }
        
        actions_config = {
            'initiate_equipment_analysis': {
                'conditions': {
                    'equipment_status': {'upgrade_status': 'needs_analysis'},
                    'character_status': {'alive': True}
                },
                'reactions': {
                    'equipment_status': {'upgrade_status': 'analyzing'}
                },
                'weight': 1.5
            },
            'analyze_equipment_gaps': {
                'conditions': {
                    'equipment_status': {'upgrade_status': 'analyzing'},
                    'character_status': {'alive': True}
                },
                'reactions': {
                    'equipment_status': {
                        'upgrade_status': 'combat_ready',  # Assuming equipment is good
                        'gaps_analyzed': True
                    }
                },
                'weight': 1.0
            }
        }
        
        # Create world with planner
        world = self.controller.goap_execution_manager.create_world_with_planner(
            start_state, goal_state, actions_config
        )
        
        # Verify world was created
        self.assertIsNotNone(world)
        
        # Try to create a plan using the execution manager
        plan = self.controller.goap_execution_manager.create_plan(
            start_state, goal_state, actions_config
        )
        
        # Verify plan was found
        self.assertIsNotNone(plan, "GOAP should find a plan from needs_analysis to combat_ready")
        self.assertGreaterEqual(len(plan), 2, "Plan should have at least 2 steps")
        
        # Extract action names from plan
        action_names = [action['name'] for action in plan]
        self.assertIn('initiate_equipment_analysis', action_names)
        self.assertIn('analyze_equipment_gaps', action_names)


if __name__ == '__main__':
    unittest.main()