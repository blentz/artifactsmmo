"""Basic unit tests for LearningManager class."""

import unittest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from src.controller.learning_manager import LearningManager


class TestLearningManagerBasic(unittest.TestCase):
    """Basic test cases for LearningManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_config_prefix = os.environ.get('CONFIG_PREFIX', '')
        os.environ['CONFIG_PREFIX'] = self.temp_dir
        
        # Create mock dependencies
        self.mock_knowledge_base = Mock()
        self.mock_map_state = Mock()
        self.mock_client = Mock()
        
        # Create minimal config file
        self.config_file = os.path.join(self.temp_dir, 'goal_templates.yaml')
        with open(self.config_file, 'w') as f:
            f.write("""
thresholds:
  min_monsters_for_recommendations: 5
  min_locations_for_exploration: 25
  good_success_rate_threshold: 0.8
""")

    def tearDown(self):
        """Clean up test fixtures."""
        os.environ['CONFIG_PREFIX'] = self.original_config_prefix
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch('src.controller.learning_manager.CapabilityAnalyzer')
    def test_initialization_with_client(self, mock_capability_analyzer):
        """Test LearningManager initialization with client."""
        manager = LearningManager(
            self.mock_knowledge_base,
            self.mock_map_state,
            client=self.mock_client,
            config_file=self.config_file
        )
        
        self.assertEqual(manager.knowledge_base, self.mock_knowledge_base)
        self.assertEqual(manager.map_state, self.mock_map_state)
        self.assertIsNotNone(manager.capability_analyzer)
        mock_capability_analyzer.assert_called_once_with(self.mock_client)
        
        # Check configuration was loaded
        self.assertEqual(manager.min_monsters_for_recommendations, 5)
        self.assertEqual(manager.min_locations_for_exploration, 25)
        self.assertEqual(manager.good_success_rate_threshold, 0.8)

    def test_initialization_without_client(self):
        """Test LearningManager initialization without client."""
        manager = LearningManager(
            self.mock_knowledge_base,
            self.mock_map_state,
            config_file=self.config_file
        )
        
        self.assertEqual(manager.knowledge_base, self.mock_knowledge_base)
        self.assertEqual(manager.map_state, self.mock_map_state)
        self.assertIsNone(manager.capability_analyzer)

    def test_initialization_with_default_config(self):
        """Test LearningManager initialization with default config file."""
        # Create default config file location
        default_config = f"{self.temp_dir}/goal_templates.yaml"
        
        manager = LearningManager(
            self.mock_knowledge_base,
            self.mock_map_state
        )
        
        # Should have loaded defaults even if file doesn't exist
        self.assertIsInstance(manager.min_monsters_for_recommendations, int)
        self.assertIsInstance(manager.min_locations_for_exploration, int)
        self.assertIsInstance(manager.good_success_rate_threshold, float)

    def test_load_configuration_defaults(self):
        """Test loading configuration with defaults when thresholds missing."""
        # Create config without thresholds
        config_file = os.path.join(self.temp_dir, 'minimal.yaml')
        with open(config_file, 'w') as f:
            f.write("# Minimal config\n")
        
        manager = LearningManager(
            self.mock_knowledge_base,
            self.mock_map_state,
            config_file=config_file
        )
        
        # Should use defaults
        self.assertEqual(manager.min_monsters_for_recommendations, 3)
        self.assertEqual(manager.min_locations_for_exploration, 20)
        self.assertEqual(manager.good_success_rate_threshold, 0.7)

    def test_load_configuration_partial(self):
        """Test loading configuration with only some thresholds defined."""
        # Create config with partial thresholds
        config_file = os.path.join(self.temp_dir, 'partial.yaml')
        with open(config_file, 'w') as f:
            f.write("""
thresholds:
  min_monsters_for_recommendations: 10
""")
        
        manager = LearningManager(
            self.mock_knowledge_base,
            self.mock_map_state,
            config_file=config_file
        )
        
        # Should use custom value for defined threshold, defaults for others
        self.assertEqual(manager.min_monsters_for_recommendations, 10)
        self.assertEqual(manager.min_locations_for_exploration, 20)  # default
        self.assertEqual(manager.good_success_rate_threshold, 0.7)  # default

    def test_has_required_attributes(self):
        """Test that LearningManager has expected attributes."""
        manager = LearningManager(
            self.mock_knowledge_base,
            self.mock_map_state,
            config_file=self.config_file
        )
        
        # Check for expected attributes
        self.assertTrue(hasattr(manager, 'logger'))
        self.assertTrue(hasattr(manager, 'knowledge_base'))
        self.assertTrue(hasattr(manager, 'map_state'))
        self.assertTrue(hasattr(manager, 'config_data'))
        self.assertTrue(hasattr(manager, 'min_monsters_for_recommendations'))
        self.assertTrue(hasattr(manager, 'min_locations_for_exploration'))
        self.assertTrue(hasattr(manager, 'good_success_rate_threshold'))

    def test_logger_initialization(self):
        """Test that logger is properly initialized."""
        manager = LearningManager(
            self.mock_knowledge_base,
            self.mock_map_state,
            config_file=self.config_file
        )
        
        self.assertIsNotNone(manager.logger)
        self.assertEqual(manager.logger.name, 'src.controller.learning_manager')

    @patch('src.controller.learning_manager.YamlData')
    def test_config_file_loading(self, mock_yaml_data):
        """Test that config file is loaded correctly."""
        mock_yaml_instance = Mock()
        mock_yaml_data.return_value = mock_yaml_instance
        mock_yaml_instance.data = {
            'thresholds': {
                'min_monsters_for_recommendations': 7,
                'min_locations_for_exploration': 30,
                'good_success_rate_threshold': 0.9
            }
        }
        
        manager = LearningManager(
            self.mock_knowledge_base,
            self.mock_map_state,
            config_file='custom_config.yaml'
        )
        
        # Verify YamlData was called with correct file
        mock_yaml_data.assert_called_once_with('custom_config.yaml')
        
        # Verify configuration was loaded
        self.assertEqual(manager.min_monsters_for_recommendations, 7)
        self.assertEqual(manager.min_locations_for_exploration, 30)
        self.assertEqual(manager.good_success_rate_threshold, 0.9)

    def test_threshold_values_are_reasonable(self):
        """Test that loaded threshold values are reasonable."""
        manager = LearningManager(
            self.mock_knowledge_base,
            self.mock_map_state,
            config_file=self.config_file
        )
        
        # Check that thresholds are positive and reasonable
        self.assertGreater(manager.min_monsters_for_recommendations, 0)
        self.assertGreater(manager.min_locations_for_exploration, 0)
        self.assertGreater(manager.good_success_rate_threshold, 0.0)
        self.assertLessEqual(manager.good_success_rate_threshold, 1.0)


if __name__ == '__main__':
    unittest.main()