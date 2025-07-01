"""
Regression tests for combat learning issues in ActionExecutor.

This test module prevents regression of critical bugs that were fixed:
1. HP data capture bug: Post-combat HP being used as pre-combat HP
2. Monster identification bug: Monster not identified during direct attacks
"""

import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from src.controller.action_executor import ActionExecutor


class TestActionExecutorCombatLearning(unittest.TestCase):
    """Test combat learning functionality in ActionExecutor."""
    
    def setUp(self):
        """Set up test environment with temporary files."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, 'test_config.yaml')
        
        # Create minimal config file
        with open(self.config_file, 'w') as f:
            f.write("""
action_configurations:
  test_action:
    type: "builtin"
    description: "Test action"
""")
        
        self.executor = ActionExecutor(self.config_file)
    
    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('src.controller.action_executor.ActionFactory')
    def test_hp_data_capture_regression(self, mock_factory):
        """
        Regression test for HP data capture bug.
        
        Previously, post-combat HP from response was incorrectly used as pre-combat HP,
        causing backwards HP data in knowledge.yaml.
        """
        # Setup mocks
        mock_controller = Mock()
        mock_controller.character_state = Mock()
        mock_controller.character_state.data = {'hp': 125, 'max_hp': 125}
        mock_controller.map_state = Mock()
        mock_controller.map_state.data = {
            '0,-1': {'content': {'type': 'monster', 'code': 'green_slime'}}
        }
        
        # Mock fight response with post-combat HP = 1
        mock_response = Mock()
        mock_response.data = Mock()
        mock_response.data.character = Mock()
        mock_response.data.character.hp = 1  # Post-combat HP (low)
        mock_response.data.character.x = 0
        mock_response.data.character.y = -1
        mock_response.data.character.max_hp = 125
        # Create fight mock with explicit spec that excludes 'monster' to force map fallback
        mock_response.data.fight = Mock(spec=['result', 'turns', 'xp', 'gold', 'drops', 'damage'])
        mock_response.data.fight.result = 'loss'
        # Configure Mock to return actual integers for arithmetic operations
        mock_response.data.fight.turns = 22
        mock_response.data.fight.xp = 0
        mock_response.data.fight.gold = 0
        mock_response.data.fight.drops = []
        # Ensure hasattr checks work for fight_data attributes
        mock_response.data.fight.damage = None
        
        # Mock controller learn_from_combat to capture the arguments
        captured_args = []
        def capture_learn_from_combat(*args, **kwargs):
            captured_args.extend(args)
            captured_args.append(kwargs)
        
        mock_controller.learn_from_combat = capture_learn_from_combat
        
        context = {'x': 0, 'y': -1, 'controller': mock_controller}
        
        # Execute the learning callback
        self.executor._handle_learning_callbacks('attack', mock_response, context)
        
        # Verify the HP data was captured correctly
        self.assertEqual(len(captured_args), 6)  # monster_code, result, pre_combat_hp, fight_dict, combat_context, {}
        monster_code = captured_args[0]
        result = captured_args[1] 
        pre_combat_hp = captured_args[2]
        combat_context = captured_args[4]
        
        # Critical assertions to prevent regression
        self.assertEqual(monster_code, 'green_slime', "Monster should be identified correctly")
        self.assertEqual(result, 'loss', "Combat result should be extracted correctly")
        
        # HP data regression check: pre-combat HP should be calculated, not copied from response
        self.assertGreater(pre_combat_hp, 1, 
                          "Pre-combat HP should be calculated (>1), not copied from post-combat response (1)")
        
        # Combat context should contain both pre and post combat HP
        self.assertIn('pre_combat_hp', combat_context, "Combat context should include pre-combat HP")
        self.assertIn('post_combat_hp', combat_context, "Combat context should include post-combat HP") 
        self.assertEqual(combat_context['post_combat_hp'], 1, "Post-combat HP should be 1 from response")
        
        # Damage calculation should be reasonable
        if combat_context['pre_combat_hp'] and combat_context['post_combat_hp']:
            damage = combat_context['pre_combat_hp'] - combat_context['post_combat_hp']
            self.assertGreater(damage, 0, "Damage should be positive")
            self.assertLessEqual(damage, 125, "Damage should not exceed max HP")
    
    @patch('src.controller.action_executor.ActionFactory')
    def test_monster_identification_with_action_context(self, mock_factory):
        """
        Test monster identification when action context contains target coordinates.
        
        This is the normal case when GOAP plans find_monsters→move→attack sequence.
        """
        # Setup mocks
        mock_controller = Mock()
        mock_controller.map_state = Mock()
        mock_controller.map_state.data = {
            '5,10': {'content': {'type': 'monster', 'code': 'red_slime'}}
        }
        
        mock_response = Mock()
        mock_response.data = Mock()
        mock_response.data.character = Mock()
        mock_response.data.character.hp = 50
        # Create fight mock with explicit spec that excludes 'monster' to force map fallback
        mock_response.data.fight = Mock(spec=['result', 'turns', 'xp', 'gold', 'drops', 'damage'])
        mock_response.data.fight.result = 'win'
        mock_response.data.fight.turns = 10
        mock_response.data.fight.xp = 15
        mock_response.data.fight.gold = 5
        mock_response.data.fight.drops = []
        mock_response.data.fight.damage = None
        
        captured_args = []
        mock_controller.learn_from_combat = lambda *args, **kwargs: captured_args.extend(args)
        
        # Context with target coordinates (normal case)
        context = {'x': 5, 'y': 10, 'controller': mock_controller}
        
        self.executor._handle_learning_callbacks('attack', mock_response, context)
        
        # Should identify monster from action context coordinates
        monster_code = captured_args[0]
        self.assertEqual(monster_code, 'red_slime', 
                        "Monster should be identified from action context coordinates")
    
    @patch('src.controller.action_executor.ActionFactory')
    def test_monster_identification_direct_attack_regression(self, mock_factory):
        """
        Regression test for monster identification during direct attacks.
        
        Previously, when GOAP planned direct attacks without find_monsters step,
        monster identification failed because action context lacked coordinates.
        """
        # Setup mocks
        mock_controller = Mock()
        mock_controller.character_state.data = {'x': 3, 'y': 7}
        mock_controller.map_state.data = {
            '3,7': {'content': {'type': 'monster', 'code': 'blue_slime'}}
        }
        
        mock_response = Mock()
        mock_response.data = Mock()
        mock_response.data.character = Mock()
        mock_response.data.character.hp = 75
        mock_response.data.character.x = 3
        mock_response.data.character.y = 7
        # Create fight mock with explicit spec that excludes 'monster' to force map fallback
        mock_response.data.fight = Mock(spec=['result', 'turns', 'xp', 'gold', 'drops', 'damage'])
        mock_response.data.fight.result = 'win'
        mock_response.data.fight.turns = 8
        mock_response.data.fight.xp = 12
        mock_response.data.fight.gold = 3
        mock_response.data.fight.drops = []
        mock_response.data.fight.damage = None
        
        captured_args = []
        mock_controller.learn_from_combat = lambda *args, **kwargs: captured_args.extend(args)
        
        # Context WITHOUT coordinates (direct attack case)
        context = {'char_name': 'test_char', 'controller': mock_controller}
        
        self.executor._handle_learning_callbacks('attack', mock_response, context)
        
        # Should identify monster from character position via response or character state
        monster_code = captured_args[0]
        self.assertEqual(monster_code, 'blue_slime', 
                        "Monster should be identified even in direct attacks without action context coordinates")
    
    @patch('src.controller.action_executor.ActionFactory')
    def test_monster_identification_fallback_priority(self, mock_factory):
        """Test the priority order of monster identification fallback methods."""
        mock_controller = Mock()
        mock_controller.character_state.data = {'x': 1, 'y': 1}
        mock_controller.map_state.data = {
            '0,0': {'content': {'type': 'monster', 'code': 'context_monster'}},
            '2,2': {'content': {'type': 'monster', 'code': 'response_monster'}}, 
            '1,1': {'content': {'type': 'monster', 'code': 'state_monster'}}
        }
        
        mock_response = Mock()
        mock_response.data = Mock()
        mock_response.data.character = Mock()
        mock_response.data.character.hp = 100
        mock_response.data.character.x = 2
        mock_response.data.character.y = 2
        # Create fight mock with explicit spec that excludes 'monster' to force map fallback
        mock_response.data.fight = Mock(spec=['result', 'turns', 'xp', 'gold', 'drops', 'damage'])
        mock_response.data.fight.result = 'win'
        mock_response.data.fight.turns = 5
        mock_response.data.fight.xp = 8
        mock_response.data.fight.gold = 2
        mock_response.data.fight.drops = []
        mock_response.data.fight.damage = None
        
        captured_args = []
        mock_controller.learn_from_combat = lambda *args, **kwargs: captured_args.extend(args)
        
        # Test Priority 1: Action context coordinates
        context = {'x': 0, 'y': 0, 'controller': mock_controller}
        captured_args.clear()
        self.executor._handle_learning_callbacks('attack', mock_response, context)
        self.assertEqual(captured_args[0], 'context_monster', "Should use action context coordinates (Priority 1)")
        
        # Test Priority 2: Response character position
        context = {'controller': mock_controller}  # No action coordinates
        captured_args.clear()
        self.executor._handle_learning_callbacks('attack', mock_response, context)
        self.assertEqual(captured_args[0], 'response_monster', "Should use response coordinates (Priority 2)")
        
        # Test Priority 3: Character state position  
        mock_response_no_char = Mock()
        # Create response data mock without character attribute to force character state fallback
        mock_response_no_char.data = Mock(spec=['fight'])
        # Create fight mock with explicit spec that excludes 'monster' to force map fallback
        mock_response_no_char.data.fight = Mock(spec=['result', 'turns', 'xp', 'gold', 'drops', 'damage'])
        mock_response_no_char.data.fight.result = 'win'
        mock_response_no_char.data.fight.turns = 3
        mock_response_no_char.data.fight.xp = 5
        mock_response_no_char.data.fight.gold = 1
        mock_response_no_char.data.fight.drops = []
        mock_response_no_char.data.fight.damage = None
        # No character attribute at all to force Priority 3
        
        context = {'controller': mock_controller}
        captured_args.clear()
        self.executor._handle_learning_callbacks('attack', mock_response_no_char, context)
        self.assertEqual(captured_args[0], 'state_monster', "Should use character state position (Priority 3)")
    
    @patch('src.controller.action_executor.ActionFactory')
    def test_damage_calculation_from_turns(self, mock_factory):
        """Test damage calculation when direct damage data is not available."""
        mock_controller = Mock()
        mock_controller.character_state.data = {'hp': 125, 'max_hp': 125}
        mock_controller.map_state.data = {
            '0,0': {'content': {'type': 'monster', 'code': 'test_monster'}}
        }
        
        # Response with no direct damage data, but with turns
        mock_response = Mock()
        mock_response.data = Mock()
        mock_response.data.character = Mock()
        mock_response.data.character.hp = 15  # Low HP after combat
        mock_response.data.character.max_hp = 125
        # Create fight mock with explicit spec that excludes 'monster' to force map fallback
        mock_response.data.fight = Mock(spec=['result', 'turns', 'xp', 'gold', 'drops', 'damage'])
        mock_response.data.fight.result = 'loss'
        mock_response.data.fight.turns = 20  # Many turns = high damage
        mock_response.data.fight.xp = 0
        mock_response.data.fight.gold = 0
        mock_response.data.fight.drops = []
        # No direct damage attribute
        mock_response.data.fight.damage = None
        
        captured_args = []
        def capture_combat_context(*args, **kwargs):
            captured_args.extend(args)
            captured_args.append(kwargs)
        
        mock_controller.learn_from_combat = capture_combat_context
        
        context = {'x': 0, 'y': 0, 'controller': mock_controller}
        self.executor._handle_learning_callbacks('attack', mock_response, context)
        
        # Check damage was estimated from turns
        combat_context = captured_args[4]
        pre_combat_hp = combat_context['pre_combat_hp']
        post_combat_hp = combat_context['post_combat_hp']
        
        self.assertEqual(post_combat_hp, 15, "Post-combat HP should match response")
        self.assertGreater(pre_combat_hp, post_combat_hp, "Pre-combat HP should be higher than post-combat")
        
        # Damage should be estimated as ~5 HP per turn for losses
        expected_damage = min(100, 20 * 5)  # 20 turns * 5 HP/turn = 100 HP
        estimated_damage = pre_combat_hp - post_combat_hp
        self.assertGreaterEqual(estimated_damage, 90, 
                               f"Damage estimation should be reasonable for {20} turns")


if __name__ == '__main__':
    unittest.main()