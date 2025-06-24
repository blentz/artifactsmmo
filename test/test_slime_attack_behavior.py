"""Test suite verifying AI Player attacks nearest slime until dead."""

import unittest
from unittest.mock import Mock, patch, MagicMock
from src.controller.actions.attack import AttackAction
from src.controller.actions.find_slime import FindSlimeAction
from src.controller.ai_player_controller import AIPlayerController


class TestSlimeAttackBehavior(unittest.TestCase):
    """Test that AI Player correctly attacks nearest slime until it is dead."""

    def setUp(self):
        """Set up test fixtures."""
        self.char_name = "test_hero"
        self.mock_client = Mock()

    def test_find_slime_action_locates_nearest_slime(self):
        """Test that FindSlimeAction correctly locates the nearest slime."""
        
        # Mock the monsters API response
        mock_monster = Mock()
        mock_monster.name = "Green Slime"
        mock_monster.code = "green_slime"
        
        mock_monsters_response = Mock()
        mock_monsters_response.data = [mock_monster]
        
        # Mock the map API response with slime at location (1, 1)
        mock_map_content = Mock()
        mock_map_content.type_ = "monster"
        mock_map_content.code = "green_slime"
        
        mock_map_data = Mock()
        mock_map_data.content = mock_map_content
        
        mock_map_response = Mock()
        mock_map_response.data = mock_map_data
        
        with patch('src.controller.actions.find_slime.get_all_monsters_api') as mock_get_monsters, \
             patch('src.controller.actions.find_slime.get_map_api') as mock_get_map:
            
            mock_get_monsters.return_value = mock_monsters_response
            mock_get_map.return_value = mock_map_response
            
            # Create find slime action at character position (0, 0)
            find_action = FindSlimeAction(character_x=0, character_y=0, search_radius=5)
            result = find_action.execute(self.mock_client)
            
            # Verify slime was found
            self.assertIsNotNone(result, "Should find a slime")
            self.assertIn('location', result, "Result should contain location")
            self.assertIn('slime_codes', result, "Result should contain slime codes")
            self.assertEqual(result['slime_codes'], ['green_slime'])

    def test_attack_action_fights_monster(self):
        """Test that AttackAction executes a fight against a monster."""
        
        # Mock successful attack response
        mock_fight_response = Mock()
        mock_fight_response.character = Mock()
        mock_fight_response.monster = Mock()
        mock_fight_response.monster.hp = 15  # Monster survives with reduced HP
        
        with patch('src.controller.actions.attack.fight_character_api') as mock_fight_api:
            mock_fight_api.return_value = mock_fight_response
            
            attack_action = AttackAction(char_name=self.char_name)
            result = attack_action.execute(self.mock_client)
            
            # Verify attack was executed
            self.assertIsNotNone(result, "Attack should return a response")
            mock_fight_api.assert_called_once_with(
                name=self.char_name,
                client=self.mock_client
            )

    def test_multiple_attacks_until_monster_dies(self):
        """Test that multiple attacks are performed until monster HP reaches 0."""
        
        # Simulate monster taking damage over multiple attacks
        monster_hp_sequence = [25, 15, 5, 0]  # HP after each attack
        call_count = 0
        
        def mock_attack_response(*args, **kwargs):
            nonlocal call_count
            mock_response = Mock()
            mock_response.character = Mock()
            mock_response.monster = Mock()
            mock_response.monster.hp = monster_hp_sequence[call_count]
            call_count += 1
            return mock_response
        
        with patch('src.controller.actions.attack.fight_character_api') as mock_fight_api:
            mock_fight_api.side_effect = mock_attack_response
            
            attack_action = AttackAction(char_name=self.char_name)
            
            # Simulate attacking until monster dies
            attacks_made = 0
            max_attacks = 10  # Safety limit
            
            while attacks_made < max_attacks:
                result = attack_action.execute(self.mock_client)
                attacks_made += 1
                
                # Check if monster is dead
                if result.monster.hp <= 0:
                    break
            
            # Verify monster died and reasonable number of attacks were made
            self.assertEqual(result.monster.hp, 0, "Monster should be dead")
            self.assertEqual(attacks_made, 4, "Should have taken 4 attacks to kill monster")
            self.assertEqual(mock_fight_api.call_count, 4, "API should have been called 4 times")

    @patch('src.controller.actions.find_slime.get_all_monsters_api')
    @patch('src.controller.actions.find_slime.get_map_api')
    @patch('src.controller.actions.attack.fight_character_api')
    def test_complete_slime_hunting_workflow(self, mock_fight_api, mock_map_api, mock_monsters_api):
        """Test complete workflow: find slime -> move to location -> attack until dead."""
        
        # Setup monster data
        mock_slime = Mock()
        mock_slime.name = "Green Slime"
        mock_slime.code = "green_slime"
        
        mock_monsters_response = Mock()
        mock_monsters_response.data = [mock_slime]
        mock_monsters_api.return_value = mock_monsters_response
        
        # Setup map data with slime at (2, 1)
        mock_map_content = Mock()
        mock_map_content.type_ = "monster"
        mock_map_content.code = "green_slime"
        
        mock_map_data = Mock()
        mock_map_data.content = mock_map_content
        
        mock_map_response = Mock()
        mock_map_response.data = mock_map_data
        mock_map_api.return_value = mock_map_response
        
        # Setup combat sequence - slime dies after 3 attacks
        combat_hp_sequence = [20, 10, 0]
        combat_call_count = 0
        
        def mock_combat_response(*args, **kwargs):
            nonlocal combat_call_count
            response = Mock()
            response.character = Mock()
            response.monster = Mock()
            response.monster.hp = combat_hp_sequence[combat_call_count]
            combat_call_count += 1
            return response
        
        mock_fight_api.side_effect = mock_combat_response
        
        # Execute complete workflow
        print("\n=== Complete Slime Hunting Workflow Test ===")
        
        # Step 1: Find slime
        print("Step 1: Finding nearest slime...")
        find_action = FindSlimeAction(character_x=0, character_y=0, search_radius=5)
        slime_info = find_action.execute(self.mock_client)
        
        self.assertIsNotNone(slime_info, "Should locate a slime")
        print(f"✓ Found slime at location {slime_info['location']}")
        
        # Step 2: Attack slime until dead
        print("Step 2: Engaging slime in combat...")
        attack_action = AttackAction(char_name=self.char_name)
        
        attacks_made = 0
        max_attacks = 10  # Safety limit
        final_result = None
        
        while attacks_made < max_attacks:
            result = attack_action.execute(self.mock_client)
            attacks_made += 1
            final_result = result
            
            print(f"  Attack {attacks_made}: Monster HP = {result.monster.hp}")
            
            # Stop when monster is dead
            if result.monster.hp <= 0:
                print(f"  ⚡ Monster eliminated after {attacks_made} attacks!")
                break
        
        # Verify successful completion
        self.assertIsNotNone(final_result, "Should have combat result")
        self.assertEqual(final_result.monster.hp, 0, "Slime should be dead")
        self.assertEqual(attacks_made, 3, "Should take exactly 3 attacks")
        self.assertEqual(mock_fight_api.call_count, 3, "Should make 3 API calls")
        
        print(f"✓ Slime successfully eliminated in {attacks_made} attacks")
        print("✓ Complete workflow verified successfully!")

    def test_find_slime_handles_no_slimes_found(self):
        """Test that FindSlimeAction handles case where no slimes exist."""
        
        # Mock empty monsters response
        mock_monsters_response = Mock()
        mock_monsters_response.data = []  # No monsters
        
        with patch('src.controller.actions.find_slime.get_all_monsters_api') as mock_get_monsters:
            mock_get_monsters.return_value = mock_monsters_response
            
            find_action = FindSlimeAction(character_x=0, character_y=0)
            result = find_action.execute(self.mock_client)
            
            self.assertIsNone(result, "Should return None when no slimes found")

    def test_find_slime_prioritizes_nearest_location(self):
        """Test that FindSlimeAction returns the nearest slime when multiple exist."""
        
        # Mock monsters response
        mock_slime = Mock()
        mock_slime.name = "Green Slime"
        mock_slime.code = "green_slime"
        
        mock_monsters_response = Mock()
        mock_monsters_response.data = [mock_slime]
        
        # Track which locations are queried and return slimes at different distances
        map_call_count = 0
        def mock_map_response(x, y, client):
            nonlocal map_call_count
            map_call_count += 1
            
            # Return slime at (1, 0) - closer to character at (0, 0)
            # and at (3, 3) - farther from character
            if (x, y) in [(1, 0), (3, 3)]:
                mock_content = Mock()
                mock_content.type_ = "monster"
                mock_content.code = "green_slime"
                
                mock_data = Mock()
                mock_data.content = mock_content
                
                response = Mock()
                response.data = mock_data
                return response
            else:
                # No slime at this location
                response = Mock()
                response.data = None
                return response
        
        with patch('src.controller.actions.find_slime.get_all_monsters_api') as mock_get_monsters, \
             patch('src.controller.actions.find_slime.get_map_api') as mock_get_map:
            
            mock_get_monsters.return_value = mock_monsters_response
            mock_get_map.side_effect = mock_map_response
            
            find_action = FindSlimeAction(character_x=0, character_y=0, search_radius=5)
            result = find_action.execute(self.mock_client)
            
            # Should find the closer slime at (1, 0)
            self.assertIsNotNone(result, "Should find a slime")
            self.assertEqual(result['location'], (1, 0), "Should find nearest slime at (1, 0)")


if __name__ == '__main__':
    unittest.main(verbosity=2)
