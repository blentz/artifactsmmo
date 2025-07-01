import unittest
from unittest.mock import Mock

from src.controller.state_engine import StateCalculationEngine


class TestCombatViabilityUnified(unittest.TestCase):
    """Test unified combat viability checking with weighted calculations."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.state_engine = StateCalculationEngine()
        
        # Create mock knowledge base with combat data
        self.knowledge_base = Mock()
        self.knowledge_base.data = {
            'monsters': {
                'chicken': {
                    'level': 1,
                    'combat_results': [
                        {'result': 'win', 'timestamp': '2025-01-01T12:00:00', 'character_level': 2},
                        {'result': 'loss', 'timestamp': '2025-01-01T12:01:00', 'character_level': 2},
                        {'result': 'loss', 'timestamp': '2025-01-01T12:02:00', 'character_level': 2},
                        {'result': 'loss', 'timestamp': '2025-01-01T12:03:00', 'character_level': 2},
                        {'result': 'loss', 'timestamp': '2025-01-01T12:04:00', 'character_level': 2},
                    ]
                },
                'cow': {
                    'level': 2,
                    'combat_results': [
                        {'result': 'loss', 'timestamp': '2025-01-01T12:05:00', 'character_level': 2},
                        {'result': 'loss', 'timestamp': '2025-01-01T12:06:00', 'character_level': 2},
                        {'result': 'loss', 'timestamp': '2025-01-01T12:07:00', 'character_level': 2},
                    ]
                },
                'wolf': {
                    'level': 15,
                    'combat_results': []
                }
            }
        }
        
    def test_combat_viability_through_state_engine(self):
        """Test combat viability check through state engine."""
        # State with poor combat performance
        state = {
            'character_level': 2,
            'character_hp': 100,
            'character_max_hp': 100,
            '_knowledge_base': self.knowledge_base
        }
        
        config = {'type': 'computed', 'method': 'check_combat_viability'}
        thresholds = {
            'min_combat_win_rate': 0.2,
            'recency_decay_factor': 0.9
        }
        
        # Check combat viability - should return True (combat NOT viable)
        result = self.state_engine._check_combat_viability(config, state, thresholds)
        self.assertTrue(result, "Combat should not be viable with poor win rate")
        
    def test_combat_viability_through_state_engine_delegation(self):
        """Test combat viability check through state engine delegation."""
        # State with poor combat performance
        state = {
            'character_level': 2,
            'character_hp': 100,
            'character_max_hp': 100,
            '_knowledge_base': self.knowledge_base
        }
        
        config = {'type': 'computed', 'method': 'check_combat_viability'}
        thresholds = {
            'min_combat_win_rate': 0.2,
            'recency_decay_factor': 0.9
        }
        
        # Check through dispatch method - simulates how goal manager would call it
        result = self.state_engine._dispatch_computed_method('check_combat_viability', config, state, thresholds)
        self.assertTrue(result, "Combat should not be viable when called through dispatch")
        
    def test_combat_viability_with_good_performance(self):
        """Test combat viability with good win rate."""
        # Create knowledge base with good performance
        knowledge_base = Mock()
        knowledge_base.data = {
            'monsters': {
                'chicken': {
                    'level': 1,
                    'combat_results': [
                        {'result': 'win', 'timestamp': '2025-01-01T12:00:00', 'character_level': 2},
                        {'result': 'win', 'timestamp': '2025-01-01T12:01:00', 'character_level': 2},
                        {'result': 'win', 'timestamp': '2025-01-01T12:02:00', 'character_level': 2},
                        {'result': 'loss', 'timestamp': '2025-01-01T12:03:00', 'character_level': 2},
                        {'result': 'win', 'timestamp': '2025-01-01T12:04:00', 'character_level': 2},
                    ]
                }
            }
        }
        
        state = {
            'character_level': 2,
            'character_hp': 100,
            'character_max_hp': 100,
            '_knowledge_base': knowledge_base
        }
        
        config = {'type': 'computed', 'method': 'check_combat_viability'}
        thresholds = {
            'min_combat_win_rate': 0.2,
            'recency_decay_factor': 0.9
        }
        
        # Check combat viability - should return False (combat IS viable)
        result = self.state_engine._check_combat_viability(config, state, thresholds)
        self.assertFalse(result, "Combat should be viable with good win rate")
        
    def test_combat_viability_with_insufficient_data(self):
        """Test combat viability with insufficient combat data."""
        # Create knowledge base with minimal data
        knowledge_base = Mock()
        knowledge_base.data = {
            'monsters': {
                'chicken': {
                    'level': 1,
                    'combat_results': [
                        {'result': 'loss', 'timestamp': '2025-01-01T12:00:00', 'character_level': 2},
                        {'result': 'loss', 'timestamp': '2025-01-01T12:01:00', 'character_level': 2},
                    ]
                }
            }
        }
        
        state = {
            'character_level': 2,
            'character_hp': 100,
            'character_max_hp': 100,
            '_knowledge_base': knowledge_base
        }
        
        config = {'type': 'computed', 'method': 'check_combat_viability'}
        thresholds = {
            'min_combat_win_rate': 0.2,
            'recency_decay_factor': 0.9
        }
        
        # Check combat viability - should return False (assume viable with insufficient data)
        result = self.state_engine._check_combat_viability(config, state, thresholds)
        self.assertFalse(result, "Combat should be assumed viable with insufficient data")
        
    def test_recency_weighting(self):
        """Test that recent combats are weighted more heavily."""
        # Create knowledge base with improving performance
        knowledge_base = Mock()
        knowledge_base.data = {
            'monsters': {
                'chicken': {
                    'level': 1,
                    'combat_results': [
                        # Old losses
                        {'result': 'loss', 'timestamp': '2025-01-01T12:00:00', 'character_level': 2},
                        {'result': 'loss', 'timestamp': '2025-01-01T12:01:00', 'character_level': 2},
                        {'result': 'loss', 'timestamp': '2025-01-01T12:02:00', 'character_level': 2},
                        {'result': 'loss', 'timestamp': '2025-01-01T12:03:00', 'character_level': 2},
                        {'result': 'loss', 'timestamp': '2025-01-01T12:04:00', 'character_level': 2},
                        # Recent wins
                        {'result': 'win', 'timestamp': '2025-01-01T12:05:00', 'character_level': 2},
                        {'result': 'win', 'timestamp': '2025-01-01T12:06:00', 'character_level': 2},
                        {'result': 'win', 'timestamp': '2025-01-01T12:07:00', 'character_level': 2},
                    ]
                }
            }
        }
        
        state = {
            'character_level': 2,
            'character_hp': 100,
            'character_max_hp': 100,
            '_knowledge_base': knowledge_base
        }
        
        config = {'type': 'computed', 'method': 'check_combat_viability'}
        thresholds = {
            'min_combat_win_rate': 0.2,
            'recency_decay_factor': 0.9
        }
        
        # With recency weighting, recent wins should make combat viable
        result = self.state_engine._check_combat_viability(config, state, thresholds)
        self.assertFalse(result, "Combat should be viable due to recent wins being weighted more heavily")


if __name__ == '__main__':
    unittest.main()