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

    def test_combat_loss_simple_behavior(self):
        """Test that combat loss has simple boolean behavior."""
        # Arrange
        attack_action = AttackAction()
        
        # Assert - simple boolean reactions as per architecture
        # The action should have simple, declarative conditions/reactions
        self.assertIsInstance(attack_action.conditions, dict)
        self.assertIsInstance(attack_action.reactions, dict)

    def test_initiate_equipment_analysis_requires_needs_analysis(self):
        """Test that initiate_equipment_analysis requires needs_analysis status."""
        # Arrange
        action = InitiateEquipmentAnalysisAction()
        
        # Assert
        self.assertEqual(action.conditions['equipment_status']['upgrade_status'], 'needs_analysis')
        self.assertEqual(action.reactions['equipment_status']['upgrade_status'], 'analyzing')

    def test_analyze_equipment_gaps_simple_conditions(self):
        """Test that analyze_equipment_gaps has simple boolean conditions."""
        # Arrange
        action = AnalyzeEquipmentGapsAction()
        
        # Assert - simple boolean conditions as per architecture
        self.assertEqual(action.conditions['character_status']['alive'], True)

    def test_analyze_equipment_gaps_simple_reactions(self):
        """Test that analyze_equipment_gaps has simple boolean reactions."""
        # Arrange
        action = AnalyzeEquipmentGapsAction()
        
        # Assert - simple boolean reactions as per architecture
        self.assertEqual(action.reactions['equipment_status']['gaps_analyzed'], True)

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