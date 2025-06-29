"""Test module for AttackAction."""

import unittest
import tempfile
import os
from unittest.mock import Mock, patch
from src.controller.actions.attack import AttackAction


class TestAttackAction(unittest.TestCase):
    """Test cases for AttackAction."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_data_prefix = os.environ.get('DATA_PREFIX', '')
        os.environ['DATA_PREFIX'] = self.temp_dir
        
        self.character_name = "test_character"
        self.action = AttackAction(self.character_name)

    def tearDown(self):
        """Clean up test fixtures."""
        os.environ['DATA_PREFIX'] = self.original_data_prefix
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_attack_action_initialization(self):
        """Test AttackAction initialization."""
        self.assertEqual(self.action.char_name, "test_character")
        self.assertEqual(self.action.min_hp_threshold, 1)

    def test_attack_action_repr(self):
        """Test AttackAction string representation."""
        expected = "AttackAction(test_character)"
        self.assertEqual(repr(self.action), expected)

    def test_execute_no_client(self):
        """Test execute fails without client."""
        result = self.action.execute(None)
        self.assertFalse(result['success'])
        self.assertIn('No API client provided', result['error'])

    def test_can_safely_attack_safe_hp(self):
        """Test can_safely_attack returns True for safe HP."""
        # Test with HP above threshold
        self.assertTrue(self.action.can_safely_attack(50))
        self.assertTrue(self.action.can_safely_attack(25))
        self.assertTrue(self.action.can_safely_attack(2))

    def test_can_safely_attack_unsafe_hp(self):
        """Test can_safely_attack returns False for unsafe HP."""
        # Test with HP at or below threshold
        self.assertFalse(self.action.can_safely_attack(1))
        self.assertFalse(self.action.can_safely_attack(0))

    def test_execute_hp_too_low(self):
        """Test execute when character HP is too low."""
        client = Mock()
        
        # Mock character state with low HP
        character_state = Mock()
        character_state.data = {'hp': 1}
        
        result = self.action.execute(client, character_state=character_state)
        self.assertFalse(result['success'])
        self.assertIn('HP (1) is too low for safe combat', result['error'])
        self.assertEqual(result['character_hp'], 1)
        self.assertEqual(result['min_hp_threshold'], 1)

    @patch('src.controller.actions.attack.fight_character_api')
    def test_execute_fight_api_fails(self, mock_fight_api):
        """Test execute when fight API fails."""
        mock_fight_api.return_value = None
        client = Mock()
        
        # Mock character state with safe HP
        character_state = Mock()
        character_state.data = {'hp': 50}
        
        result = self.action.execute(client, character_state=character_state)
        self.assertFalse(result['success'])
        self.assertIn('Fight API call failed', result['error'])

    @patch('src.controller.actions.attack.fight_character_api')
    def test_execute_fight_api_no_data(self, mock_fight_api):
        """Test execute when fight API returns no data."""
        mock_response = Mock()
        mock_response.data = None
        mock_fight_api.return_value = mock_response
        client = Mock()
        
        # Mock character state with safe HP
        character_state = Mock()
        character_state.data = {'hp': 50}
        
        result = self.action.execute(client, character_state=character_state)
        self.assertFalse(result['success'])
        self.assertIn('Fight API call failed', result['error'])

    @patch('src.controller.actions.attack.fight_character_api')
    def test_execute_successful_attack(self, mock_fight_api):
        """Test successful attack execution."""
        # Mock successful fight response
        mock_fight_data = Mock()
        mock_fight_data.xp = 25
        mock_fight_data.gold = 10
        mock_fight_data.drops = []
        mock_character = Mock()
        mock_character.hp = 45
        mock_response = Mock()
        mock_response.data = Mock()
        mock_response.data.fight = mock_fight_data
        mock_response.data.character = mock_character
        mock_fight_api.return_value = mock_response
        
        client = Mock()
        
        # Mock character state with safe HP
        character_state = Mock()
        character_state.data = {'hp': 50}
        
        result = self.action.execute(client, character_state=character_state)
        self.assertTrue(result['success'])
        self.assertEqual(result['char_name'], 'test_character')
        self.assertIn('fight_data', result)
        self.assertIn('character_data', result)

    @patch('src.controller.actions.attack.fight_character_api')
    def test_execute_no_character_state(self, mock_fight_api):
        """Test execute without character state (skips HP check)."""
        # Mock successful fight response
        mock_fight_data = Mock()
        mock_fight_data.xp = 25
        mock_character = Mock()
        mock_character.hp = 45
        mock_response = Mock()
        mock_response.data = Mock()
        mock_response.data.fight = mock_fight_data
        mock_response.data.character = mock_character
        mock_fight_api.return_value = mock_response
        
        client = Mock()
        
        result = self.action.execute(client)  # No character_state
        self.assertTrue(result['success'])
        self.assertEqual(result['char_name'], 'test_character')

    @patch('src.controller.actions.attack.fight_character_api')
    def test_execute_with_different_hp_thresholds(self, mock_fight_api):
        """Test execute with different HP safety thresholds."""
        # Set different threshold
        self.action.min_hp_threshold = 10
        
        client = Mock()
        
        # Test HP above threshold (safe)
        character_state = Mock()
        character_state.data = {'hp': 15}
        
        mock_response = Mock()
        mock_response.data = Mock()
        mock_response.data.fight = Mock()
        mock_response.data.character = Mock()
        mock_fight_api.return_value = mock_response
        
        result = self.action.execute(client, character_state=character_state)
        self.assertTrue(result['success'])
        
        # Test HP at threshold (unsafe)
        character_state.data = {'hp': 10}
        result = self.action.execute(client, character_state=character_state)
        self.assertFalse(result['success'])
        self.assertIn('HP (10) is too low', result['error'])

    def test_calculate_damage_taken_helper_method(self):
        """Test _calculate_damage_taken helper method."""
        pre_hp = 100
        post_hp = 85
        
        # Test basic functionality if method exists
        if hasattr(self.action, '_calculate_damage_taken'):
            damage = self.action._calculate_damage_taken(pre_hp, post_hp)
            self.assertEqual(damage, 15)
            
            # Test no damage case
            damage = self.action._calculate_damage_taken(100, 100)
            self.assertEqual(damage, 0)

    def test_analyze_fight_result_helper_method(self):
        """Test _analyze_fight_result helper method."""
        fight_data = Mock()
        fight_data.xp = 25
        fight_data.gold = 10
        fight_data.drops = []
        
        # Test basic functionality if method exists
        if hasattr(self.action, '_analyze_fight_result'):
            analysis = self.action._analyze_fight_result(fight_data)
            self.assertIsInstance(analysis, dict)

    def test_execute_exception_handling(self):
        """Test exception handling during execution."""
        client = Mock()
        
        with patch('src.controller.actions.attack.fight_character_api', side_effect=Exception("API Error")):
            result = self.action.execute(client)
            self.assertFalse(result['success'])
            self.assertIn('Fight execution failed', result['error'])

    def test_execute_has_goap_attributes(self):
        """Test that AttackAction has expected GOAP attributes."""
        self.assertTrue(hasattr(AttackAction, 'conditions'))
        self.assertTrue(hasattr(AttackAction, 'reactions'))
        self.assertTrue(hasattr(AttackAction, 'weights'))
        self.assertTrue(hasattr(AttackAction, 'g'))

    def test_goap_conditions(self):
        """Test GOAP conditions are properly defined."""
        expected_conditions = {
            'monster_present': True,
            'can_attack': True,
            'character_safe': True,
            'character_alive': True
        }
        self.assertEqual(AttackAction.conditions, expected_conditions)

    def test_goap_reactions(self):
        """Test GOAP reactions are properly defined."""
        expected_reactions = {
            'monster_present': False,
            'has_hunted_monsters': True
        }
        self.assertEqual(AttackAction.reactions, expected_reactions)

    def test_goap_weights(self):
        """Test GOAP weights are properly defined."""
        expected_weights = {'attack': 3.0}
        self.assertEqual(AttackAction.weights, expected_weights)

    def test_different_character_names(self):
        """Test action works with different character names."""
        character_names = ['player1', 'test_char', 'ai_player', 'special-character']
        
        for name in character_names:
            action = AttackAction(name)
            self.assertEqual(action.char_name, name)
            
            # Test representation includes character name
            self.assertIn(name, repr(action))

    def test_hp_threshold_customization(self):
        """Test customizing HP safety threshold."""
        # Test default threshold
        action1 = AttackAction("player")
        self.assertEqual(action1.min_hp_threshold, 1)
        
        # Test custom threshold
        action2 = AttackAction("player")
        action2.min_hp_threshold = 20
        self.assertEqual(action2.min_hp_threshold, 20)
        
        # Test threshold behavior
        self.assertFalse(action2.can_safely_attack(20))
        self.assertFalse(action2.can_safely_attack(15))
        self.assertTrue(action2.can_safely_attack(25))

    @patch('src.controller.actions.attack.fight_character_api')
    def test_execute_fight_data_extraction(self, mock_fight_api):
        """Test proper extraction of fight data from API response."""
        # Mock complex fight response
        mock_drops = [
            Mock(code='feather', quantity=2),
            Mock(code='raw_chicken', quantity=1)
        ]
        mock_fight_data = Mock()
        mock_fight_data.xp = 15
        mock_fight_data.gold = 5
        mock_fight_data.drops = mock_drops
        mock_fight_data.result = 'win'
        mock_fight_data.turns = 3
        
        mock_character = Mock()
        mock_character.hp = 80
        mock_character.xp = 250
        
        mock_response = Mock()
        mock_response.data = Mock()
        mock_response.data.fight = mock_fight_data
        mock_response.data.character = mock_character
        mock_fight_api.return_value = mock_response
        
        client = Mock()
        character_state = Mock()
        character_state.data = {'hp': 90}
        
        result = self.action.execute(client, character_state=character_state)
        self.assertTrue(result['success'])
        
        # Verify fight data extraction
        fight_data = result['fight_data']
        self.assertEqual(fight_data.xp, 15)
        self.assertEqual(fight_data.gold, 5)
        self.assertEqual(len(fight_data.drops), 2)
        
        # Verify character data extraction
        character_data = result['character_data']
        self.assertEqual(character_data.hp, 80)
        self.assertEqual(character_data.xp, 250)

    def test_character_state_data_formats(self):
        """Test handling different character state data formats."""
        client = Mock()
        
        # Test with standard data format
        character_state1 = Mock()
        character_state1.data = {'hp': 50, 'max_hp': 100}
        
        # Test with missing max_hp
        character_state2 = Mock()
        character_state2.data = {'hp': 50}
        
        # Test with zero HP
        character_state3 = Mock()
        character_state3.data = {'hp': 0}
        
        test_cases = [
            (character_state1, True),   # Safe HP
            (character_state2, True),   # Safe HP, missing max_hp
            (character_state3, False),  # Unsafe HP
        ]
        
        for char_state, should_be_safe in test_cases:
            hp = char_state.data.get('hp', 0)
            result_safe = self.action.can_safely_attack(hp)
            self.assertEqual(result_safe, should_be_safe, 
                           f"HP {hp} safety check failed: expected {should_be_safe}, got {result_safe}")

    @patch('src.controller.actions.attack.fight_character_api')
    def test_execute_api_response_edge_cases(self, mock_fight_api):
        """Test handling of edge cases in API responses."""
        client = Mock()
        character_state = Mock()
        character_state.data = {'hp': 50}
        
        # Test response with missing fight data
        mock_response1 = Mock()
        mock_response1.data = Mock()
        mock_response1.data.fight = None
        mock_response1.data.character = Mock()
        mock_fight_api.return_value = mock_response1
        
        result = self.action.execute(client, character_state=character_state)
        # Should handle gracefully
        self.assertIn('success', result)
        
        # Test response with missing character data
        mock_response2 = Mock()
        mock_response2.data = Mock()
        mock_response2.data.fight = Mock()
        mock_response2.data.character = None
        mock_fight_api.return_value = mock_response2
        
        result = self.action.execute(client, character_state=character_state)
        # Should handle gracefully
        self.assertIn('success', result)


if __name__ == '__main__':
    unittest.main()