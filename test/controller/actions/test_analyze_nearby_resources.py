"""
Comprehensive tests for AnalyzeNearbyResourcesAction.

This test suite ensures 100% coverage of the refactored action that replaced
the complex analyze_resources.py with a cleaner, more maintainable implementation.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List

from src.controller.actions.analyze_nearby_resources import AnalyzeNearbyResourcesAction
from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters


class TestAnalyzeNearbyResourcesAction(unittest.TestCase):
    """Test AnalyzeNearbyResourcesAction functionality."""
    
    def setUp(self):
        self.action = AnalyzeNearbyResourcesAction()
        self.mock_client = Mock()
        self.context = ActionContext()
        
        # Set up default context parameters
        self.context.set(StateParameters.CHARACTER_X, 0)
        self.context.set(StateParameters.CHARACTER_Y, 0)
        self.context.set(StateParameters.CHARACTER_LEVEL, 2)
        self.context.knowledge_base = Mock()
        self.context.set(StateParameters.CONFIG_DATA, Mock())
        
    def test_goap_metadata(self):
        """Test GOAP metadata is properly defined."""
        self.assertIsInstance(self.action.conditions, dict)
        self.assertIsInstance(self.action.reactions, dict)
        self.assertIsInstance(self.action.weight, (int, float))
        
        # Check specific GOAP values
        self.assertEqual(self.action.weight, 6.0)
        self.assertIn('character_status', self.action.conditions)
        self.assertTrue(self.action.conditions['character_status']['alive'])
        
        # Check reactions
        expected_reactions = [
            'resource_analysis_complete',
            'nearby_resources_known', 
            'crafting_opportunities_identified',
            'resource_locations_known'
        ]
        for reaction in expected_reactions:
            self.assertIn(reaction, self.action.reactions)
            self.assertTrue(self.action.reactions[reaction])
    
    @patch.object(AnalyzeNearbyResourcesAction, 'find_nearby_resources')
    def test_execute_no_resources_found(self, mock_find_resources):
        """Test execution when no resources are found."""
        mock_find_resources.return_value = []
        
        result = self.action.execute(self.mock_client, self.context)
        
        self.assertFalse(result.success)
        self.assertIn('No resources found', result.error)
    
    @patch.object(AnalyzeNearbyResourcesAction, 'find_nearby_resources')
    @patch.object(AnalyzeNearbyResourcesAction, '_analyze_single_resource')
    @patch.object(AnalyzeNearbyResourcesAction, '_find_equipment_opportunities')
    @patch.object(AnalyzeNearbyResourcesAction, '_prioritize_opportunities')
    @patch.object(AnalyzeNearbyResourcesAction, '_recommend_next_action')
    def test_execute_success_flow(self, mock_recommend, mock_prioritize, 
                                  mock_find_opportunities, mock_analyze_resource,
                                  mock_find_resources):
        """Test successful execution flow."""
        # Mock resource discovery
        mock_resource = {
            'resource_code': 'copper_rocks',
            'x': 1,
            'y': 1,
            'distance': 2
        }
        mock_find_resources.return_value = [mock_resource]
        
        # Mock resource analysis
        mock_analysis = {
            'resource_code': 'copper_rocks',
            'can_gather': True,
            'crafting_uses': []
        }
        mock_analyze_resource.return_value = mock_analysis
        
        # Mock equipment opportunities
        mock_opportunities = [
            {
                'item_code': 'copper_dagger',
                'feasibility_score': 0.8
            }
        ]
        mock_find_opportunities.return_value = mock_opportunities
        mock_prioritize.return_value = mock_opportunities
        
        # Mock recommendation
        mock_recommendation = {
            'action': 'gather_for_crafting',
            'priority': 'high'
        }
        mock_recommend.return_value = mock_recommendation
        
        result = self.action.execute(self.mock_client, self.context)
        
        # Verify successful execution
        self.assertTrue(result.success)
        self.assertIn('Analyzed 1 resources', result.message)
        
        # Verify state changes
        expected_state_changes = {
            'resource_analysis_complete': True,
            'nearby_resources_known': True,
            'crafting_opportunities_identified': True,
            'resource_locations_known': True
        }
        self.assertEqual(result.state_changes, expected_state_changes)
        
        # Verify result data
        self.assertEqual(result.data['nearby_resources_count'], 1)
        self.assertEqual(result.data['analyzed_resources'], ['copper_rocks'])
        self.assertEqual(result.data['equipment_opportunities'], mock_opportunities)
        self.assertEqual(result.data['recommended_action'], mock_recommendation)
    
    @patch.object(AnalyzeNearbyResourcesAction, 'find_nearby_resources')
    def test_execute_exception_handling(self, mock_find_resources):
        """Test exception handling during execution."""
        mock_find_resources.side_effect = Exception("Test error")
        
        result = self.action.execute(self.mock_client, self.context)
        
        self.assertFalse(result.success)
        self.assertIn('Resource analysis failed', result.error)
        self.assertIn('Test error', result.error)
    
    @patch.object(AnalyzeNearbyResourcesAction, 'get_resource_details')
    def test_analyze_single_resource_success(self, mock_get_details):
        """Test successful single resource analysis."""
        # Mock resource details
        mock_resource_data = Mock()
        mock_resource_data.name = 'Copper Rocks'
        mock_resource_data.skill = 'mining'
        mock_resource_data.level = 1
        
        # Mock drops
        mock_drop = Mock()
        mock_drop.code = 'copper_ore'
        mock_resource_data.drops = [mock_drop]
        
        mock_get_details.return_value = mock_resource_data
        
        # Mock find_crafting_uses_for_item
        self.action.find_crafting_uses_for_item = Mock(return_value=[
            {
                'item_code': 'copper_dagger',
                'item_name': 'Copper Dagger'
            }
        ])
        
        resource_location = {
            'resource_code': 'copper_rocks',
            'x': 1,
            'y': 1,
            'distance': 2
        }
        
        result = self.action._analyze_single_resource(
            self.mock_client, resource_location, self.context
        )
        
        # Verify analysis result
        self.assertIsNotNone(result)
        self.assertEqual(result['resource_code'], 'copper_rocks')
        self.assertEqual(result['resource_name'], 'Copper Rocks')
        self.assertEqual(result['skill_required'], 'mining')
        self.assertEqual(result['level_required'], 1)
        self.assertTrue(result['can_gather'])  # character level 2 >= required level 1
        self.assertEqual(len(result['crafting_uses']), 1)
    
    @patch.object(AnalyzeNearbyResourcesAction, 'get_resource_details')
    def test_analyze_single_resource_no_data(self, mock_get_details):
        """Test single resource analysis with no resource data."""
        mock_get_details.return_value = None
        
        resource_location = {
            'resource_code': 'unknown_resource',
            'x': 1,
            'y': 1,
            'distance': 2
        }
        
        result = self.action._analyze_single_resource(
            self.mock_client, resource_location, self.context
        )
        
        self.assertIsNone(result)
    
    def test_find_equipment_opportunities_success(self):
        """Test finding equipment opportunities from resource analysis."""
        resource_analysis = {
            'copper_rocks': {
                'can_gather': True,
                'distance': 2,
                'location': (1, 1),
                'resource_name': 'Copper Rocks',
                'crafting_uses': [
                    {
                        'item_code': 'copper_dagger',
                        'item_name': 'Copper Dagger',
                        'item_type': 'weapon',
                        'item_level': 1,
                        'all_materials_needed': [{'code': 'copper_ore', 'quantity': 2}],
                        'workshop_required': 'weaponcrafting'
                    }
                ]
            }
        }
        
        opportunities = self.action._find_equipment_opportunities(
            self.mock_client, resource_analysis, self.context
        )
        
        self.assertEqual(len(opportunities), 1)
        opp = opportunities[0]
        self.assertEqual(opp['item_code'], 'copper_dagger')
        self.assertEqual(opp['item_name'], 'Copper Dagger')
        self.assertEqual(opp['resource_code'], 'copper_rocks')
        self.assertGreater(opp['feasibility_score'], 0)
        self.assertEqual(opp['level_appropriateness'], 'good')  # level diff is 1
    
    def test_find_equipment_opportunities_cannot_gather(self):
        """Test equipment opportunities when character can't gather resource."""
        resource_analysis = {
            'iron_rocks': {
                'can_gather': False,  # Character can't gather this
                'crafting_uses': [
                    {
                        'item_code': 'iron_sword',
                        'item_name': 'Iron Sword',
                        'item_type': 'weapon',
                        'item_level': 5
                    }
                ]
            }
        }
        
        opportunities = self.action._find_equipment_opportunities(
            self.mock_client, resource_analysis, self.context
        )
        
        # Should not find opportunities if character can't gather the resource
        self.assertEqual(len(opportunities), 0)
    
    def test_prioritize_opportunities_success(self):
        """Test opportunity prioritization."""
        opportunities = [
            {
                'item_type': 'weapon',
                'level_appropriateness': 'good',
                'feasibility_score': 0.8
            },
            {
                'item_type': 'ring',
                'level_appropriateness': 'poor',
                'feasibility_score': 0.9
            },
            {
                'item_type': 'weapon',
                'level_appropriateness': 'acceptable',
                'feasibility_score': 0.7
            }
        ]
        
        # Mock config data
        mock_config = Mock()
        mock_config.data = {
            'resource_analysis_priorities': {
                'equipment_type_priorities': {
                    'weapon': 3,
                    'ring': 1
                },
                'level_appropriateness_priorities': {
                    'good': 3,
                    'acceptable': 2,
                    'poor': 1
                }
            }
        }
        
        result = self.action._prioritize_opportunities(opportunities, mock_config)
        
        # Should prioritize weapon with good level appropriateness first
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]['item_type'], 'weapon')
        self.assertEqual(result[0]['level_appropriateness'], 'good')
    
    def test_prioritize_opportunities_fallback_priorities(self):
        """Test opportunity prioritization with fallback priorities."""
        opportunities = [
            {
                'item_type': 'weapon',
                'level_appropriateness': 'good',
                'feasibility_score': 0.8
            }
        ]
        
        # No config data provided - should use fallback priorities
        result = self.action._prioritize_opportunities(opportunities, None)
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['item_type'], 'weapon')
    
    def test_get_equipment_type_priority_with_config(self):
        """Test equipment type priority with configuration."""
        mock_config = Mock()
        mock_config.data = {
            'resource_analysis_priorities': {
                'equipment_type_priorities': {
                    'weapon': 5
                }
            }
        }
        
        priority = self.action._get_equipment_type_priority('weapon', mock_config)
        self.assertEqual(priority, 5)
    
    def test_get_equipment_type_priority_fallback(self):
        """Test equipment type priority fallback."""
        priority = self.action._get_equipment_type_priority('weapon', None)
        self.assertEqual(priority, 3)  # Fallback priority for weapon
        
        priority = self.action._get_equipment_type_priority('unknown_type', None)
        self.assertEqual(priority, 0)  # Unknown types get 0 priority
    
    def test_get_level_appropriateness_priority_with_config(self):
        """Test level appropriateness priority with configuration."""
        mock_config = Mock()
        mock_config.data = {
            'resource_analysis_priorities': {
                'level_appropriateness_priorities': {
                    'good': 5
                }
            }
        }
        
        priority = self.action._get_level_appropriateness_priority('good', mock_config)
        self.assertEqual(priority, 5)
    
    def test_get_level_appropriateness_priority_fallback(self):
        """Test level appropriateness priority fallback."""
        priority = self.action._get_level_appropriateness_priority('good', None)
        self.assertEqual(priority, 3)  # Fallback priority for good
        
        priority = self.action._get_level_appropriateness_priority('unknown', None)
        self.assertEqual(priority, 0)  # Unknown appropriateness gets 0
    
    def test_recommend_next_action_no_opportunities(self):
        """Test action recommendation with no opportunities."""
        result = self.action._recommend_next_action([])
        
        self.assertEqual(result['action'], 'continue_hunting')
        self.assertEqual(result['reason'], 'No viable equipment crafting opportunities found')
        self.assertEqual(result['priority'], 'low')
    
    def test_recommend_next_action_with_opportunities(self):
        """Test action recommendation with opportunities."""
        opportunities = [
            {
                'item_code': 'copper_dagger',
                'item_name': 'Copper Dagger',
                'item_level': 1,
                'resource_code': 'copper_rocks',
                'resource_location': (1, 1),
                'materials_needed': [{'code': 'copper_ore', 'quantity': 2}],
                'workshop_skill': 'weaponcrafting'
            }
        ]
        
        result = self.action._recommend_next_action(opportunities)
        
        self.assertEqual(result['action'], 'gather_for_crafting')
        self.assertIn('Craft Copper Dagger', result['reason'])
        self.assertEqual(result['priority'], 'high')
        self.assertEqual(result['target_item'], 'copper_dagger')
        self.assertEqual(result['target_resource'], 'copper_rocks')
        self.assertEqual(result['resource_location'], (1, 1))
    
    def test_repr_method(self):
        """Test string representation of the action."""
        repr_str = repr(self.action)
        self.assertEqual(repr_str, "AnalyzeNearbyResourcesAction()")
    
    def test_context_parameters_handling(self):
        """Test handling of context parameters with defaults."""
        # Test with minimal context
        minimal_context = ActionContext()
        minimal_context.knowledge_base = Mock()
        
        # Mock the method dependencies
        self.action.find_nearby_resources = Mock(return_value=[])
        
        result = self.action.execute(self.mock_client, minimal_context)
        
        # Should handle missing parameters gracefully with defaults
        self.assertFalse(result.success)
        self.assertIn('No resources found', result.error)
        
        # Verify find_nearby_resources was called with context
        self.action.find_nearby_resources.assert_called_once_with(
            self.mock_client, minimal_context
        )


if __name__ == '__main__':
    unittest.main()