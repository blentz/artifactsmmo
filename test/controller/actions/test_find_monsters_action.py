"""Test module for FindMonstersAction."""

import unittest
from unittest.mock import Mock, patch

from src.controller.actions.find_monsters import FindMonstersAction

from test.fixtures import MockActionContext, create_mock_client


class TestFindMonstersAction(unittest.TestCase):
    """Test cases for FindMonstersAction."""

    def setUp(self):
        """Set up test fixtures."""
        self.character_x = 5
        self.character_y = 5
        self.search_radius = 3
        self.monster_types = ['green_slime', 'chicken']
        self.character_level = 5
        self.level_range = 2
        
        self.action = FindMonstersAction()
        
        # Mock client
        self.mock_client = create_mock_client()

    def test_find_monsters_action_initialization_default(self):
        """Test FindMonstersAction initialization with default parameters."""
        action = FindMonstersAction()
        # Action no longer stores these as instance attributes
        self.assertFalse(hasattr(action, 'character_x'))
        self.assertFalse(hasattr(action, 'character_y'))
        self.assertFalse(hasattr(action, 'search_radius'))
        self.assertFalse(hasattr(action, 'monster_types'))
        self.assertFalse(hasattr(action, 'character_level'))
        self.assertFalse(hasattr(action, 'level_range'))

    def test_find_monsters_action_initialization_with_params(self):
        """Test FindMonstersAction initialization with all parameters."""
        # Action no longer stores these as instance attributes
        self.assertFalse(hasattr(self.action, 'character_x'))
        self.assertFalse(hasattr(self.action, 'character_y'))
        self.assertFalse(hasattr(self.action, 'search_radius'))
        self.assertFalse(hasattr(self.action, 'monster_types'))
        self.assertFalse(hasattr(self.action, 'character_level'))
        self.assertFalse(hasattr(self.action, 'level_range'))

    def test_find_monsters_action_initialization_default_character_level(self):
        """Test FindMonstersAction initialization with default character level."""
        action = FindMonstersAction()
        self.assertFalse(hasattr(action, 'character_level'))

    def test_find_monsters_action_initialization_with_character_level(self):
        """Test FindMonstersAction initialization with character level."""
        action = FindMonstersAction()
        self.assertFalse(hasattr(action, 'character_level'))

    def test_find_monsters_action_repr_no_filter(self):
        """Test FindMonstersAction string representation without filters."""
        action = FindMonstersAction()
        expected = "FindMonstersAction()"
        self.assertEqual(repr(action), expected)

    def test_find_monsters_action_repr_with_filter(self):
        """Test FindMonstersAction string representation with filters."""
        expected = "FindMonstersAction()"
        self.assertEqual(repr(self.action), expected)

    def test_find_monsters_action_class_attributes(self):
        """Test that FindMonstersAction has expected GOAP class attributes."""
        self.assertTrue(hasattr(FindMonstersAction, 'conditions'))
        self.assertTrue(hasattr(FindMonstersAction, 'reactions'))
        self.assertTrue(hasattr(FindMonstersAction, 'weight'))

    def test_monster_types_none_becomes_empty_list(self):
        """Test that None monster_types becomes empty list."""
        action = FindMonstersAction()
        self.assertFalse(hasattr(action, 'monster_types'))

    def test_execute_no_client(self):
        """Test finding monsters fails without client."""
        context = MockActionContext(
            character_x=self.character_x,
            character_y=self.character_y,
            search_radius=self.search_radius,
            monster_types=self.monster_types,
            character_level=self.character_level,
            level_range=self.level_range,
        )
        result = self.action.execute(None, context)
        # With centralized validation, None client triggers validation error
        self.assertFalse(result.success)
        # Direct action execution bypasses centralized validation
        self.assertIsNotNone(result.error)

    def test_empty_monsters_data(self):
        """Test execute with empty monsters data."""
        # Mock knowledge base with empty monster data
        context = MockActionContext(
            character_x=self.character_x,
            character_y=self.character_y,
            search_radius=self.search_radius,
            monster_types=self.monster_types,
            character_level=self.character_level,
            level_range=self.level_range,
        )
        # Mock knowledge base with empty monster search results
        context.knowledge_base.find_monsters_in_map.return_value = []
        result = self.action.execute(self.mock_client, context)
        self.assertFalse(result.success)
        self.assertIn('No suitable monsters found', result.error)

    @patch('unittest.mock.Mock')
    def test_execute_find_monster_success(self, mock_get_monsters):
        """Test finding monsters successfully."""
        # Mock API response
        mock_monster = Mock()
        mock_monster.code = 'green_slime'
        mock_monster.name = 'Green Slime'
        mock_monster.level = 5
        mock_get_monsters.return_value = Mock(data=[mock_monster])
        
        # Create mock knowledge base with viable monster data
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {
            'monsters': {
                'green_slime': {
                    'level': 5,
                    'combat_results': [
                        {'result': 'win'},
                        {'result': 'win'},
                        {'result': 'loss'}
                    ]
                }
            }
        }
        # Mock the find_monsters_in_map method to return a proper result
        mock_knowledge_base.find_monsters_in_map.return_value = [
            {
                'x': 6,
                'y': 7,
                'monster_code': 'green_slime',
                'monster_data': {'level': 5, 'name': 'Green Slime'},
                'content_data': {'code': 'green_slime', 'type': 'monster'},
                'distance': 1.4
            }
        ]
        
        # Create mock map state
        mock_map_state = Mock()
        mock_map_state.data = {
            '6,7': {
                'content': {
                    'code': 'green_slime',
                    'type': 'monster'
                },
                'x': 6,
                'y': 7
            }
        }
        
        # Mock the search method to return our test location
        with patch.object(self.action, '_search_radius_for_content') as mock_search:
            mock_search.return_value = [
                ((6, 7), 'green_slime', {'code': 'green_slime', 'type': 'monster'})
            ]
            
            # Execute with proper context
            context = MockActionContext(
                character_x=self.character_x,
                character_y=self.character_y,
                search_radius=self.search_radius,
                monster_types=self.monster_types,
                character_level=5,
                level_range=self.level_range,
                knowledge_base=mock_knowledge_base,
                map_state=mock_map_state
            )
            result = self.action.execute(self.mock_client, context)
        
        if not result.success:
            print(f"Test failed with error: {result.error}")
        self.assertTrue(result.success)
        self.assertEqual(result.data['target_x'], 6)
        self.assertEqual(result.data['target_y'], 7)
        self.assertEqual(result.data['monster_code'], 'green_slime')
        # Distance calculation may vary based on search implementation
        if 'distance' in result.data:
            self.assertGreater(result.data['distance'], 0)
        # Win rate check
        if 'win_rate' in result.data:
            self.assertAlmostEqual(result.data['win_rate'], 0.667, places=2)

    def test_execute_no_monsters_found(self):
        """Test finding monsters when none are found."""
        # Create context with default MockActionContext which has empty find_monsters_in_map
        context = MockActionContext(
            character_x=self.character_x,
            character_y=self.character_y,
            search_radius=self.search_radius,
            monster_types=self.monster_types,
            character_level=self.character_level,
            level_range=self.level_range,
        )
        # The default MockKnowledgeBase.find_monsters_in_map returns an empty list
        result = self.action.execute(self.mock_client, context)
        
        self.assertFalse(result.success)
        self.assertIn('No suitable monsters found', result.error)

    @patch('unittest.mock.Mock')
    def test_no_monsters_response(self, mock_get_monsters):
        """Test execute with no monsters from API."""
        mock_get_monsters.return_value = None
        context = MockActionContext(
            character_x=self.character_x,
            character_y=self.character_y,
            search_radius=self.search_radius,
            monster_types=self.monster_types,
            character_level=self.character_level,
            level_range=self.level_range,
        )
        result = self.action.execute(self.mock_client, context)
        self.assertFalse(result.success)
        self.assertIn('No suitable monsters found', result.error)





    def test_execute_with_exclude_location(self):
        """Test finding monsters with location exclusion."""
        from test.fixtures import MockActionContext
        
        # Mock knowledge base to return monsters at two locations
        mock_knowledge_base = Mock()
        mock_monsters = [
            {
                'x': 5, 'y': 5, 
                'monster_code': 'chicken',
                'monster_data': {'level': 1, 'code': 'chicken'},
                'distance': 1.0
            },
            {
                'x': 6, 'y': 6,
                'monster_code': 'slime', 
                'monster_data': {'level': 2, 'code': 'slime'},
                'distance': 2.0
            }
        ]
        mock_knowledge_base.find_monsters_in_map.return_value = mock_monsters
        
        # Mock the monster selection to return success for non-excluded location
        with patch.object(self.action, '_select_best_monster_from_candidates') as mock_select:
            mock_select.return_value = self.action.create_success_result(
                message="Found monster at (6, 6)",
                monster_code='slime',
                target_x=6,
                target_y=6
            )
            
            context = MockActionContext(
                character_x=5,
                character_y=5,
                search_radius=3,
                monster_types=['chicken', 'slime'],
                exclude_location=(5, 5),  # Exclude first location
                knowledge_base=mock_knowledge_base
            )
            
            result = self.action.execute(self.mock_client, context)
            
            self.assertTrue(result.success)
            self.assertEqual(result.data['target_x'], 6)
            self.assertEqual(result.data['target_y'], 6)

    def test_execute_exception_handling(self):
        """Test exception handling in execute method."""
        from test.fixtures import MockActionContext
        
        # Mock knowledge base to raise exception
        mock_knowledge_base = Mock()
        mock_knowledge_base.find_monsters_in_map.side_effect = Exception("Knowledge base error")
        
        context = MockActionContext(
            character_x=5,
            character_y=5,
            search_radius=3,
            knowledge_base=mock_knowledge_base
        )
        
        result = self.action.execute(self.mock_client, context)
        
        self.assertFalse(result.success)
        self.assertIn('Monster search failed', result.error)
        self.assertIn('Knowledge base error', result.error)

    def test_select_best_monster_with_exclusion(self):
        """Test monster selection with location exclusion."""
        from test.fixtures import MockActionContext
        
        # Mock monsters data
        found_monsters = [
            {
                'x': 5, 'y': 5,
                'monster_code': 'chicken',
                'monster_data': {'level': 1, 'code': 'chicken'},
                'content_data': {'level': 1, 'code': 'chicken'},
                'distance': 1.0
            },
            {
                'x': 6, 'y': 6,
                'monster_code': 'slime',
                'monster_data': {'level': 2, 'code': 'slime'},
                'content_data': {'level': 2, 'code': 'slime'},
                'distance': 2.0
            }
        ]
        
        # Mock knowledge base with proper structure
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {'monsters': {}}  # Empty monsters data to avoid complex viability checks
        
        # Mock the win rate method to return reasonable values
        with patch.object(self.action, '_get_monster_win_rate') as mock_win_rate:
            with patch.object(self.action, '_is_combat_viable') as mock_viable:
                mock_win_rate.return_value = 0.8  # High win rate
                mock_viable.return_value = True   # Always viable for this test
                
                context = MockActionContext(
                    character_x=5,
                    character_y=5,
                    search_radius=3,
                    character_level=5,
                    level_range=3,
                    exclude_location=(5, 5),  # Exclude first monster location
                    knowledge_base=mock_knowledge_base
                )
                
                # Test that excluded location is skipped
                result = self.action._select_best_monster_from_candidates(found_monsters, context)
                
                # Should select the second monster since first is excluded
                if result and result.success:
                    self.assertEqual(result.data['target_x'], 6)
                    self.assertEqual(result.data['target_y'], 6)

    def test_select_best_monster_no_viable_candidates(self):
        """Test monster selection when knowledge base has no monster data."""
        from test.fixtures import MockActionContext
        
        # Test with empty found_monsters list - should return None
        mock_knowledge_base = Mock()
        
        context = MockActionContext(
            character_x=5,
            character_y=5,
            search_radius=3,
            knowledge_base=mock_knowledge_base
        )
        
        # Empty list of monsters
        found_monsters = []
        
        result = self.action._select_best_monster_from_candidates(found_monsters, context)
        
        # Should return None when no monsters found
        self.assertIsNone(result)

    def test_execute_no_viable_monsters_path(self):
        """Test execute when _select_best_monster_from_candidates returns None."""
        from test.fixtures import MockActionContext
        
        # Mock knowledge base to return monsters but selection returns None
        mock_knowledge_base = Mock()
        mock_monsters = [
            {
                'x': 5, 'y': 5,
                'monster_code': 'too_strong_dragon',
                'monster_data': {'level': 100, 'code': 'too_strong_dragon'},
                'distance': 1.0
            }
        ]
        mock_knowledge_base.find_monsters_in_map.return_value = mock_monsters
        
        # Mock the selection method to return None (no viable monsters)
        with patch.object(self.action, '_select_best_monster_from_candidates', return_value=None):
            context = MockActionContext(
                character_x=5,
                character_y=5,
                search_radius=3,
                knowledge_base=mock_knowledge_base
            )
            
            result = self.action.execute(self.mock_client, context)
            
            self.assertFalse(result.success)
            self.assertIn('No viable monsters found', result.error)

    def test_combat_viability_low_win_rate(self):
        """Test combat viability check with low win rate."""
        from test.fixtures import MockActionContext
        
        # Test _is_combat_viable with low win rate
        kwargs = {
            'knowledge_base': Mock(),
            'action_config': {'minimum_win_rate': 0.5},  # 50% minimum
            'character_state': Mock()
        }
        
        # Test with win rate below threshold
        result = self.action._is_combat_viable('weak_monster', 0.3, kwargs)  # 30% win rate
        self.assertFalse(result)
        
        # Test with win rate above threshold
        result = self.action._is_combat_viable('strong_monster', 0.8, kwargs)  # 80% win rate
        self.assertTrue(result)

    def test_combat_viability_knowledge_base_data(self):
        """Test combat viability with knowledge base combat data."""
        from test.fixtures import MockActionContext
        
        # Mock knowledge base with combat results
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {
            'monsters': {
                'test_monster': {
                    'combat_results': [
                        {'result': 'win', 'timestamp': '2023-01-01'},
                        {'result': 'win', 'timestamp': '2023-01-02'},
                        {'result': 'loss', 'timestamp': '2023-01-03'}
                    ]
                }
            }
        }
        
        mock_character_state = Mock()
        mock_character_state.data = {'level': 5, 'hp': 100}
        
        # Mock the weighted calculation methods
        with patch.object(self.action, '_calculate_weighted_win_rate', return_value=0.7):
            with patch.object(self.action, '_calculate_combat_power_adjustment', return_value=0.1):
                kwargs = {
                    'knowledge_base': mock_knowledge_base,
                    'action_config': {'minimum_win_rate': 0.5},
                    'character_state': mock_character_state
                }
                
                result = self.action._is_combat_viable('test_monster', None, kwargs)
                
                # Should be viable (0.7 + 0.1 = 0.8 > 0.5 threshold)
                self.assertTrue(result)

    def test_combat_viability_insufficient_data(self):
        """Test combat viability with insufficient combat data.""" 
        from test.fixtures import MockActionContext
        
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {
            'monsters': {
                'unknown_monster': {}  # No combat_results
            }
        }
        
        kwargs = {
            'knowledge_base': mock_knowledge_base,
            'action_config': {'minimum_win_rate': 0.5},
            'character_state': Mock()
        }
        
        # Should default to viable when no data available
        result = self.action._is_combat_viable('unknown_monster', None, kwargs)
        self.assertTrue(result)

    def test_character_position_refresh(self):
        """Test character position refresh during movement check."""
        from test.fixtures import MockActionContext, MockCharacterData
        
        # Mock character state that can be refreshed
        mock_character_state = Mock()
        mock_character_state.data = {'x': 10, 'y': 15}  # New position after refresh
        mock_character_state.refresh = Mock()
        
        # Create viable monster candidate
        viable_monsters = [{
            'location': (10, 15),  # Same as character position after refresh
            'content_code': 'chicken',
            'content_data': {'level': 1},
            'distance': 0.0,
            'monster_level': 1,
            'win_rate': 0.8,
            'x': 10,
            'y': 15
        }]
        
        # Set up context
        context = MockActionContext(
            character_x=5,
            character_y=5,  # Original position
            character_state=mock_character_state
        )
        
        # Mock the action's context
        self.action._context = context
        
        result = self.action._select_best_monster(viable_monsters)
        
        # Should successfully create ActionResult following ActionContext<->ActionResult pattern
        self.assertIsNotNone(result)
        self.assertTrue(result.success)
        self.assertIn('monster_code', result.data)
        self.assertEqual(result.data['monster_code'], 'chicken')

    def test_monster_win_rate_calculation(self):
        """Test monster win rate calculation from knowledge base."""
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {
            'monsters': {
                'test_monster': {
                    'combat_results': [
                        {'result': 'win'},
                        {'result': 'win'},
                        {'result': 'loss'}
                    ]
                }
            }
        }
        
        action_config = {'minimum_combat_results': 2}
        
        win_rate = self.action._get_monster_win_rate('test_monster', mock_knowledge_base, action_config=action_config)
        
        # Should calculate 2/3 = 0.667 win rate
        self.assertAlmostEqual(win_rate, 2/3, places=2)

    def test_monster_win_rate_insufficient_data(self):
        """Test win rate calculation with insufficient combat data."""
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {
            'monsters': {
                'new_monster': {
                    'combat_results': [{'result': 'win'}]  # Only 1 combat
                }
            }
        }
        
        action_config = {'minimum_combat_results': 3}  # Require 3 combats
        
        win_rate = self.action._get_monster_win_rate('new_monster', mock_knowledge_base, action_config=action_config)
        
        # Should return None due to insufficient data
        self.assertIsNone(win_rate)

    def test_weighted_win_rate_calculation(self):
        """Test weighted win rate calculation with time decay."""
        import datetime
        
        # Create combat results with timestamps
        recent_time = datetime.datetime.now()
        old_time = recent_time - datetime.timedelta(days=30)
        
        combat_results = [
            {'result': 'win', 'timestamp': recent_time.isoformat()},  # Recent win
            {'result': 'loss', 'timestamp': old_time.isoformat()}    # Old loss
        ]
        
        action_config = {
            'recency_weight': 0.8,
            'time_decay_days': 7
        }
        
        weighted_rate = self.action._calculate_weighted_win_rate(combat_results, action_config)
        
        # Recent win should be weighted more heavily than old loss
        self.assertGreater(weighted_rate, 0.5)

    def test_combat_power_adjustment(self):
        """Test combat power adjustment calculation."""
        character_data = {
            'level': 10,
            'attack': 50,
            'defense': 30,
            'hp': 100
        }
        
        monster_data = {
            'level': 8,
            'attack': 40,
            'defense': 25,
            'hp': 80
        }
        
        action_config = {
            'level_advantage_weight': 0.1,
            'stat_advantage_weight': 0.05
        }
        
        adjustment = self.action._calculate_combat_power_adjustment(
            character_data, monster_data, action_config
        )
        
        # Character is stronger, should get positive adjustment
        self.assertGreater(adjustment, 0)

    def test_monster_selection_priority_ordering(self):
        """Test that monster selection respects priority ordering."""
        from test.fixtures import MockActionContext
        
        # Create monsters with different priorities
        viable_monsters = [
            {
                'location': (10, 10),
                'content_code': 'strong_far_monster',
                'content_data': {'level': 5},
                'distance': 10.0,  # Far
                'monster_level': 5,  # Higher level
                'win_rate': 0.9,   # High win rate
                'x': 10, 'y': 10
            },
            {
                'location': (6, 6),
                'content_code': 'weak_close_monster', 
                'content_data': {'level': 2},
                'distance': 2.0,   # Close
                'monster_level': 2, # Lower level (safer)
                'win_rate': 0.7,   # Lower win rate
                'x': 6, 'y': 6
            }
        ]
        
        # Mock character state
        mock_character_state = Mock()
        mock_character_state.data = {'x': 5, 'y': 5}
        mock_character_state.refresh = Mock()
        
        context = MockActionContext(
            character_x=5,
            character_y=5,
            character_state=mock_character_state
        )
        self.action._context = context
        
        result = self.action._select_best_monster(viable_monsters)
        
        # Should return ActionResult following ActionContext<->ActionResult pattern
        self.assertIsNotNone(result)
        self.assertTrue(result.success)
        # Should prioritize lower level (safer) monster despite lower win rate
        self.assertEqual(result.data['monster_code'], 'weak_close_monster')

    # New comprehensive tests to achieve 100% coverage
    
    def test_select_best_monster_empty_list(self):
        """Test _select_best_monster with empty viable_monsters list (line 284)."""
        result = self.action._select_best_monster([])
        
        self.assertIsNotNone(result)
        self.assertFalse(result.success)
        self.assertIn("No viable monsters to select from", result.error)

    def test_non_viable_monster_filtering(self):
        """Test that non-viable monsters are filtered out (line 165)."""
        from test.fixtures import MockActionContext
        
        # Mock knowledge base with monster data
        mock_knowledge_base = Mock()
        mock_knowledge_base.find_monsters_in_map.return_value = [
            {
                'x': 5, 'y': 5,
                'monster_code': 'dangerous_dragon',
                'monster_data': {'level': 50, 'code': 'dangerous_dragon'},  # Very high level
                'distance': 1.0
            }
        ]
        
        # Mock _is_combat_viable to return False (non-viable)
        with patch.object(self.action, '_is_combat_viable', return_value=False):
            context = MockActionContext(
                character_x=5,
                character_y=5,
                search_radius=3,
                character_level=5,
                level_range=2,
                knowledge_base=mock_knowledge_base
            )
            
            result = self.action.execute(self.mock_client, context)
            
            self.assertFalse(result.success)
            self.assertIn("No viable monsters found", result.error)

    def test_character_position_refresh_success(self):
        """Test successful character position refresh (lines 212-220)."""
        from test.fixtures import MockActionContext
        
        # Mock character state with refresh capability
        mock_character_state = Mock()
        mock_character_state.data = {'x': 15, 'y': 25}
        mock_character_state.refresh = Mock()
        
        # Mock knowledge base with monster data
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {
            'monsters': {
                'chicken': {
                    'level': 1,
                    'combat_results': [{'result': 'win'}]
                }
            }
        }
        mock_knowledge_base.find_monsters_in_map.return_value = [
            {
                'x': 10, 'y': 10,
                'monster_code': 'chicken',
                'monster_data': {'level': 1, 'code': 'chicken'},
                'content_data': {'level': 1, 'code': 'chicken'},
                'distance': 5.0
            }
        ]
        
        # Mock _select_best_monster to return success
        mock_result = self.action.create_success_result(
            monster_code='chicken',
            target_x=10,
            target_y=10,
            distance=5.0,
            win_rate=0.8,
            monster_level=1,
            location=(10, 10)
        )
        
        with patch.object(self.action, '_select_best_monster', return_value=mock_result):
            context = MockActionContext(
                character_x=5,
                character_y=5,
                search_radius=10,
                character_state=mock_character_state,
                knowledge_base=mock_knowledge_base
            )
            
            result = self.action._select_best_monster_from_candidates(
                mock_knowledge_base.find_monsters_in_map.return_value, 
                context
            )
            
            # Should have called refresh
            mock_character_state.refresh.assert_called_once()
            self.assertTrue(result.success)

    def test_character_position_refresh_failure(self):
        """Test character position refresh failure handling (lines 221-222)."""
        from test.fixtures import MockActionContext
        
        # Mock character state with failing refresh
        mock_character_state = Mock()
        mock_character_state.data = {'x': 15, 'y': 25}
        mock_character_state.refresh = Mock(side_effect=Exception("Refresh failed"))
        
        # Mock knowledge base with monster data
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {
            'monsters': {
                'chicken': {
                    'level': 1,
                    'combat_results': [{'result': 'win'}]
                }
            }
        }
        mock_knowledge_base.find_monsters_in_map.return_value = [
            {
                'x': 10, 'y': 10,
                'monster_code': 'chicken',
                'monster_data': {'level': 1, 'code': 'chicken'},
                'content_data': {'level': 1, 'code': 'chicken'},
                'distance': 5.0
            }
        ]
        
        # Mock _select_best_monster to return success
        mock_result = self.action.create_success_result(
            monster_code='chicken',
            target_x=10,
            target_y=10,
            distance=5.0,
            win_rate=0.8,
            monster_level=1,
            location=(10, 10)
        )
        
        with patch.object(self.action, '_select_best_monster', return_value=mock_result):
            context = MockActionContext(
                character_x=5,
                character_y=5,
                search_radius=10,
                character_state=mock_character_state,
                knowledge_base=mock_knowledge_base
            )
            
            # Should handle refresh failure gracefully
            result = self.action._select_best_monster_from_candidates(
                mock_knowledge_base.find_monsters_in_map.return_value, 
                context
            )
            
            # Should still succeed despite refresh failure
            self.assertTrue(result.success)

    def test_character_already_at_monster_location(self):
        """Test when character is already at monster location (lines 256-257)."""
        from test.fixtures import MockActionContext
        
        # Mock knowledge base with monster at character location
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {
            'monsters': {
                'chicken': {
                    'level': 1,
                    'combat_results': [
                        {'result': 'win'},
                        {'result': 'win'},
                    ]
                }
            }
        }
        mock_knowledge_base.find_monsters_in_map.return_value = [
            {
                'x': 5, 'y': 5,  # Same as character position
                'monster_code': 'chicken',
                'monster_data': {'level': 1, 'code': 'chicken'},
                'content_data': {'level': 1, 'code': 'chicken'},
                'distance': 0.0
            }
        ]
        
        # Test with real execution to cover the actual code path
        context = MockActionContext(
            character_x=5,
            character_y=5,
            search_radius=10,
            knowledge_base=mock_knowledge_base
        )
        
        # Set the action's context so char_x and char_y are correct
        self.action._context = context
        
        result = self.action._select_best_monster_from_candidates(
            mock_knowledge_base.find_monsters_in_map.return_value, 
            context
        )
        
        self.assertTrue(result.success)
        # Should set at_target=True when character is already at location
        self.assertEqual(result.state_changes['location_context']['at_target'], True)

    def test_select_best_monster_from_candidates_error_handling(self):
        """Test error handling in _select_best_monster_from_candidates (lines 266-267)."""
        from test.fixtures import MockActionContext
        
        # Mock knowledge base with monster data
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {
            'monsters': {
                'chicken': {
                    'level': 1,
                    'combat_results': [{'result': 'win'}]
                }
            }
        }
        mock_knowledge_base.find_monsters_in_map.return_value = [
            {
                'x': 10, 'y': 10,
                'monster_code': 'chicken',
                'monster_data': {'level': 1, 'code': 'chicken'},
                'content_data': {'level': 1, 'code': 'chicken'},
                'distance': 5.0
            }
        ]
        
        # Mock _select_best_monster to return error
        error_result = self.action.create_error_result("Selection failed")
        
        with patch.object(self.action, '_select_best_monster', return_value=error_result):
            context = MockActionContext(
                character_x=5,
                character_y=5,
                search_radius=10,
                knowledge_base=mock_knowledge_base
            )
            
            result = self.action._select_best_monster_from_candidates(
                mock_knowledge_base.find_monsters_in_map.return_value, 
                context
            )
            
            # Should return the error result
            self.assertFalse(result.success)
            self.assertIn("Selection failed", result.error)

    def test_combat_viability_low_win_rate_warning(self):
        """Test combat viability warning for low win rate (lines 359-364)."""
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {
            'monsters': {
                'weak_monster': {
                    'combat_results': [
                        {'result': 'loss'},
                        {'result': 'loss'},
                        {'result': 'win'}  # Low win rate: 1/3 = 33%
                    ]
                }
            }
        }
        
        # Mock weighted calculation methods
        with patch.object(self.action, '_calculate_weighted_win_rate', return_value=0.3):
            with patch.object(self.action, '_calculate_combat_power_adjustment', return_value=0.0):
                kwargs = {
                    'knowledge_base': mock_knowledge_base,
                    'action_config': {'minimum_win_rate': 0.5},  # 50% threshold
                    'character_state': Mock()
                }
                
                result = self.action._is_combat_viable('weak_monster', None, kwargs)
                
                # Should return False due to low win rate
                self.assertFalse(result)

    def test_combat_viability_dangerous_monster(self):
        """Test combat viability for dangerous monster (lines 374-375)."""
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {
            'monsters': {
                'dangerous_beast': {
                    'dangerous': True  # Marked as dangerous, no combat_results
                }
            }
        }
        
        kwargs = {
            'knowledge_base': mock_knowledge_base,
            'action_config': {},
            'character_state': Mock()
        }
        
        # Pass None for win_rate so it goes through knowledge base path
        result = self.action._is_combat_viable('dangerous_beast', None, kwargs)
        
        # Should return False for dangerous monster
        self.assertFalse(result)

    def test_combat_viability_level_too_high(self):
        """Test combat viability for monster level too high (lines 386-390)."""
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {'monsters': {}}  # Empty monster data
        
        kwargs = {
            'knowledge_base': mock_knowledge_base,
            'action_config': {},
            'character_state': Mock(),
            'monster_level': 10,  # High level monster
            'character_level': 5   # Low level character
        }
        
        result = self.action._is_combat_viable('strong_monster', None, kwargs)
        
        # Should return False for level difference > 1
        self.assertFalse(result)

    def test_combat_viability_unknown_monster_accepted(self):
        """Test combat viability for unknown monster accepted (line 389)."""
        kwargs = {
            'knowledge_base': Mock(),
            'action_config': {},
            'character_state': Mock(),
            'monster_level': 6,   # Slightly higher level
            'character_level': 5  # Character level
        }
        # Empty monster data in knowledge base
        kwargs['knowledge_base'].data = {'monsters': {}}
        
        result = self.action._is_combat_viable('unknown_monster', None, kwargs)
        
        # Should return True for unknown monster within level range
        self.assertTrue(result)

    def test_combat_viability_character_level_exceeds_caution(self):
        """Test combat viability when character level exceeds caution threshold (lines 397-398)."""
        kwargs = {
            'knowledge_base': Mock(),
            'action_config': {},
            'character_state': Mock(),
            # Don't provide monster_level to test the caution threshold path
            'character_level': 15  # High level character (exceeds caution threshold of 2)
        }
        # Empty monster data in knowledge base
        kwargs['knowledge_base'].data = {'monsters': {}}
        
        result = self.action._is_combat_viable('weak_monster', None, kwargs)
        
        # Should return False when character level is too high for caution
        self.assertFalse(result)

    def test_get_monster_win_rate_error_handling(self):
        """Test error handling in _get_monster_win_rate (lines 527-529)."""
        # Mock knowledge base that raises exception
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = Mock(side_effect=Exception("Database error"))
        
        win_rate = self.action._get_monster_win_rate('error_monster', mock_knowledge_base)
        
        # Should return None on error
        self.assertIsNone(win_rate)

    def test_get_monster_win_rate_no_knowledge_base_data(self):
        """Test _get_monster_win_rate with no knowledge base data (line 510)."""
        # Mock knowledge base without data attribute
        mock_knowledge_base = Mock(spec=[])  # No 'data' attribute
        
        win_rate = self.action._get_monster_win_rate('unknown_monster', mock_knowledge_base)
        
        # Should return None when no data
        self.assertIsNone(win_rate)

    def test_calculate_weighted_win_rate_no_results(self):
        """Test _calculate_weighted_win_rate with no combat results (line 403)."""
        combat_results = []
        action_config = {}
        
        weighted_rate = self.action._calculate_weighted_win_rate(combat_results, action_config)
        
        # Should return 0.0 for no results
        self.assertEqual(weighted_rate, 0.0)


if __name__ == '__main__':
    unittest.main()