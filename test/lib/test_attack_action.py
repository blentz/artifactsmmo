import unittest
from unittest.mock import Mock, patch

from artifactsmmo_api_client.client import AuthenticatedClient
from src.controller.actions.attack import AttackAction

# Mock CharacterState for testing
class CharacterState:
    def __init__(self, data=None):
        self.data = data or {}

class TestAttackAction(unittest.TestCase):
    def setUp(self):
        self.client = AuthenticatedClient(base_url="https://api.artifactsmmo.com", token="test_token")
        self.char_name = "test_character"

    def test_attack_action_initialization(self):
        action = AttackAction(char_name=self.char_name)
        self.assertEqual(action.char_name, self.char_name)

    @patch('src.controller.actions.attack.fight_character_api')
    def test_attack_action_execute(self, mock_fight_api):
        # Mock the API response to avoid making actual API calls
        mock_response = Mock()
        mock_fight_api.return_value = mock_response
        
        action = AttackAction(char_name=self.char_name)
        response = action.execute(client=self.client)
        
        # Verify the API was called with correct parameters
        mock_fight_api.assert_called_once_with(
            name=self.char_name,
            client=self.client
        )
        
        # Verify response is returned
        self.assertIsNotNone(response)
        self.assertEqual(response, mock_response)

    @patch('src.controller.actions.attack.fight_character_api')
    def test_attack_action_execute_with_safe_hp(self, mock_fight_api):
        # Test attack execution with safe HP
        mock_response = Mock()
        mock_fight_api.return_value = mock_response
        
        # Create character state with safe HP
        mock_character_state = Mock(spec=CharacterState)
        mock_character_state.data = {'hp': 10}
        
        action = AttackAction(char_name=self.char_name)
        response = action.execute(client=self.client, character_state=mock_character_state)
        
        # Verify the API was called (HP is safe)
        mock_fight_api.assert_called_once_with(
            name=self.char_name,
            client=self.client
        )
        self.assertEqual(response, mock_response)

    @patch('src.controller.actions.attack.fight_character_api')
    def test_attack_action_execute_with_unsafe_hp(self, mock_fight_api):
        # Test attack prevention with unsafe HP
        # Create character state with unsafe HP
        mock_character_state = Mock(spec=CharacterState)
        mock_character_state.data = {'hp': 1}
        
        action = AttackAction(char_name=self.char_name)
        response = action.execute(client=self.client, character_state=mock_character_state)
        
        # Verify the API was NOT called (HP is unsafe)
        mock_fight_api.assert_not_called()
        self.assertIsNotNone(response)
        self.assertFalse(response['success'])
        self.assertIn('Attack cancelled', response['error'])
        self.assertEqual(response['character_hp'], 1)

    def test_can_safely_attack_with_sufficient_hp(self):
        # Test HP safety check with sufficient HP
        action = AttackAction(char_name=self.char_name)
        self.assertTrue(action.can_safely_attack(character_hp=10))
        self.assertTrue(action.can_safely_attack(character_hp=2))

    def test_can_safely_attack_with_insufficient_hp(self):
        # Test HP safety check with insufficient HP
        action = AttackAction(char_name=self.char_name)
        self.assertFalse(action.can_safely_attack(character_hp=1))
        self.assertFalse(action.can_safely_attack(character_hp=0))

    def test_can_safely_attack_with_enemy_damage(self):
        # Test HP safety check with enemy damage estimation
        action = AttackAction(char_name=self.char_name)
        
        # Safe case: 10 HP - 5 damage = 5 HP (safe)
        self.assertTrue(action.can_safely_attack(character_hp=10, estimated_enemy_damage=5))
        
        # Unsafe case: 3 HP - 3 damage = 0 HP (unsafe)
        self.assertFalse(action.can_safely_attack(character_hp=3, estimated_enemy_damage=3))
        
        # Critical case: 2 HP - 2 damage = 0 HP (unsafe, would reduce HP below 1)
        self.assertFalse(action.can_safely_attack(character_hp=2, estimated_enemy_damage=2))
        
        # Borderline case: 2 HP - 1 damage = 1 HP (safe, exactly at threshold)
        self.assertTrue(action.can_safely_attack(character_hp=2, estimated_enemy_damage=1))
        
        # Opponent lethal attack case: 5 HP - 6 damage would be negative (unsafe)
        self.assertFalse(action.can_safely_attack(character_hp=5, estimated_enemy_damage=6))

    def test_is_safe_to_continue(self):
        # Test the is_safe_to_continue method
        action = AttackAction(char_name=self.char_name)
        
        # Safe levels
        self.assertTrue(action.is_safe_to_continue(10))
        self.assertTrue(action.is_safe_to_continue(2))
        
        # Unsafe levels
        self.assertFalse(action.is_safe_to_continue(1))
        self.assertFalse(action.is_safe_to_continue(0))

    def test_min_hp_threshold_customization(self):
        # Test that the min HP threshold can be customized
        action = AttackAction(char_name=self.char_name)
        action.min_hp_threshold = 5
        
        # Test with HP above custom threshold
        self.assertTrue(action.can_safely_attack(character_hp=10))
        self.assertTrue(action.can_safely_attack(character_hp=6))
        
        # Test with HP at or below custom threshold
        self.assertFalse(action.can_safely_attack(character_hp=5))
        self.assertFalse(action.can_safely_attack(character_hp=1))

    def test_avoid_attack_when_opponent_could_kill(self):
        # Test that player avoids attacking when opponent's attack could reduce HP below 1
        action = AttackAction(char_name=self.char_name)
        
        # Scenario: Player has 5 HP, opponent deals 5 damage -> would result in 0 HP (unsafe)
        self.assertFalse(action.can_safely_attack(character_hp=5, estimated_enemy_damage=5))
        
        # Scenario: Player has 3 HP, opponent deals 4 damage -> would result in -1 HP (unsafe)  
        self.assertFalse(action.can_safely_attack(character_hp=3, estimated_enemy_damage=4))
        
        # Scenario: Player has 10 HP, opponent deals 15 damage -> would result in -5 HP (unsafe)
        self.assertFalse(action.can_safely_attack(character_hp=10, estimated_enemy_damage=15))

    def test_allow_attack_when_hp_remains_above_threshold(self):
        # Test that player can attack when HP would remain above the safety threshold
        action = AttackAction(char_name=self.char_name)
        
        # Scenario: Player has 10 HP, opponent deals 8 damage -> would result in 2 HP (safe)
        self.assertTrue(action.can_safely_attack(character_hp=10, estimated_enemy_damage=8))
        
        # Scenario: Player has 5 HP, opponent deals 3 damage -> would result in 2 HP (safe)
        self.assertTrue(action.can_safely_attack(character_hp=5, estimated_enemy_damage=3))
        
        # Scenario: Player has 100 HP, opponent deals 50 damage -> would result in 50 HP (safe)
        self.assertTrue(action.can_safely_attack(character_hp=100, estimated_enemy_damage=50))

    def test_hp_safety_with_different_thresholds(self):
        # Test HP safety with different minimum HP thresholds
        action = AttackAction(char_name=self.char_name)
        
        # Test with default threshold (1)
        self.assertTrue(action.can_safely_attack(character_hp=5, estimated_enemy_damage=3))  # 5-3=2 >= 1 (safe)
        self.assertTrue(action.can_safely_attack(character_hp=5, estimated_enemy_damage=4))  # 5-4=1 >= 1 (safe, at threshold)
        self.assertFalse(action.can_safely_attack(character_hp=5, estimated_enemy_damage=5))  # 5-5=0 < 1 (unsafe)
        
        # Test with custom threshold (3)
        action.min_hp_threshold = 3
        self.assertTrue(action.can_safely_attack(character_hp=10, estimated_enemy_damage=6))  # 10-6=4 >= 3 (safe)
        self.assertTrue(action.can_safely_attack(character_hp=10, estimated_enemy_damage=7))  # 10-7=3 >= 3 (safe, at threshold)
        self.assertFalse(action.can_safely_attack(character_hp=10, estimated_enemy_damage=8))  # 10-8=2 < 3 (unsafe)

    def test_attack_action_repr(self):
        action = AttackAction(char_name=self.char_name)
        expected_repr = f"AttackAction({self.char_name})"
        self.assertEqual(repr(action), expected_repr)

if __name__ == '__main__':
    unittest.main()
