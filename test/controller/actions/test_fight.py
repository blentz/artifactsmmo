"""Test FightAction"""

import unittest
from unittest.mock import Mock, MagicMock, patch

from src.controller.actions.fight import FightAction
from src.lib.action_context import ActionContext


class TestFightAction(unittest.TestCase):
    """Test cases for FightAction."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.action = FightAction()
        self.mock_client = Mock()
        
        # Create test fixtures for consistent test data
        self.test_character_name = "test_character"
        self.test_context = ActionContext()
        self.test_context.character_name = self.test_character_name
        
        # Standard test fight results
        self.win_fight_result = {'result': 'win', 'xp': 100}
        self.loss_fight_result = {'result': 'loss', 'xp': 0}
        self.victory_fight_result = {'result': 'victory', 'xp': 150}
        
        # Standard test character states
        self.healthy_character = Mock()
        self.healthy_character.hp = 80
        self.healthy_character.max_hp = 100
        
        self.damaged_character = Mock()
        self.damaged_character.hp = 20
        self.damaged_character.max_hp = 100
        
    def _create_mock_response(self, fight_result, character_state):
        """Helper to create consistent mock API responses."""
        mock_response = Mock()
        mock_data = Mock()
        
        # Set up the fight result using property mock
        type(mock_data).fight = fight_result
        type(mock_data).character = character_state
        
        mock_response.data = mock_data
        return mock_response
        
    def test_execute_successful_fight(self):
        """Test successful fight execution."""
        # Create mock response with win result
        mock_response = self._create_mock_response(
            self.win_fight_result,
            self.healthy_character
        )
        
        # Mock the API call
        with patch('src.controller.actions.fight.fight_character_api', return_value=mock_response):
            # Execute action
            result = self.action.execute(self.mock_client, self.test_context)
            
            # Verify result
            self.assertTrue(result.success)
            self.assertEqual(result.data['combat_context']['status'], 'completed')
            self.assertEqual(result.data['combat_context']['last_fight_result'], 'win')
            self.assertEqual(result.data['combat_context']['experience_gained'], 100)
            self.assertEqual(result.data['goal_progress']['steps_completed'], 1)
    
    def test_execute_failed_fight(self):
        """Test failed fight execution (lost combat)."""
        # Create mock response with loss result
        mock_response = self._create_mock_response(
            self.loss_fight_result,
            self.damaged_character
        )
        
        # Mock the API call
        with patch('src.controller.actions.fight.fight_character_api', return_value=mock_response):
            # Execute action
            result = self.action.execute(self.mock_client, self.test_context)
            
            # Verify result - fight was lost, so success should be False
            self.assertFalse(result.success)
            self.assertEqual(result.data['combat_context']['status'], 'failed')
            self.assertEqual(result.data['combat_context']['last_fight_result'], 'loss')
            self.assertEqual(result.data['goal_progress']['steps_completed'], 0)
    
    def test_execute_no_response_data(self):
        """Test execution with no response data."""
        # Mock API response with no data
        mock_response = Mock()
        mock_response.data = None
        
        # Mock the API call
        with patch('src.controller.actions.fight.fight_character_api', return_value=mock_response):
            # Execute action
            result = self.action.execute(self.mock_client, self.test_context)
            
            # Verify error result
            self.assertFalse(result.success)
            self.assertIn("no response data", result.error)
    
    def test_execute_api_exception(self):
        """Test execution with API exception."""
        # Mock the API call to raise exception
        with patch('src.controller.actions.fight.fight_character_api', side_effect=Exception("API error")):
            # Execute action
            result = self.action.execute(self.mock_client, self.test_context)
            
            # Verify error result
            self.assertFalse(result.success)
            self.assertIn("Fight execution failed", result.error)
    
    def test_analyze_fight_result_victory(self):
        """Test analyzing victory fight result."""
        # Create mock fight data with victory result
        fight_data = self._create_mock_response(
            self.victory_fight_result,
            self.healthy_character
        ).data
        
        # Analyze result
        result = self.action._analyze_fight_result(fight_data)
        
        # Verify analysis
        self.assertTrue(result['success'])
        self.assertEqual(result['result'], 'victory')
        self.assertEqual(result['xp_gained'], 150)
        self.assertEqual(result['damage_taken'], 20)  # 100 - 80 = 20
        self.assertEqual(result['character_hp'], 80)
    
    def test_analyze_fight_result_missing_data(self):
        """Test analyzing fight result with missing data."""
        # Create mock fight data with missing attributes
        fight_data = Mock()
        # getattr will return empty dict
        type(fight_data).fight = {}
        type(fight_data).character = None
        
        # Analyze result
        result = self.action._analyze_fight_result(fight_data)
        
        # Verify analysis with defaults
        self.assertFalse(result['success'])
        self.assertEqual(result['result'], 'unknown')
        self.assertEqual(result['xp_gained'], 0)
        self.assertEqual(result['damage_taken'], 0)
        self.assertEqual(result['character_hp'], 0)
    
    def test_analyze_fight_result_exception(self):
        """Test analyzing fight result with exception."""
        # Create mock fight data that causes exception
        fight_data = Mock()
        fight_data.fight = Mock(side_effect=Exception("Data error"))
        
        # Analyze result
        result = self.action._analyze_fight_result(fight_data)
        
        # Verify error handling
        self.assertFalse(result['success'])
        self.assertEqual(result['result'], 'error')
        self.assertEqual(result['xp_gained'], 0)
        self.assertEqual(result['damage_taken'], 0)
    
    def test_repr(self):
        """Test string representation."""
        expected = "FightAction()"
        self.assertEqual(repr(self.action), expected)


if __name__ == '__main__':
    unittest.main()