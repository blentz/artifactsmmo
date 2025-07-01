"""Simple unit tests for main.py focusing on core functionality"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

# Ensure src is in the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.main import (
    DATA_DIR,
    MAX_THREADS,
    RAISE_ON_UNEXPECTED_STATUS,
    clean_data_files,
    create_character,
    delete_character,
    handle_shutdown,
)


class TestMainConstants(unittest.TestCase):
    """Test main constants and simple functions."""
    
    def test_constants(self):
        """Test that main constants are properly defined."""
        self.assertEqual(MAX_THREADS, 1)
        self.assertTrue(RAISE_ON_UNEXPECTED_STATUS)
        self.assertIsInstance(DATA_DIR, Path)


class TestDataFileOperations(unittest.TestCase):
    """Test cases for data file operations."""
    
    def setUp(self):
        """Create temporary directory for testing."""
        self.temp_dir = tempfile.mkdtemp()
        self.data_dir_patcher = patch('src.main.DATA_DIR', Path(self.temp_dir))
        self.data_dir_patcher.start()
        
    def tearDown(self):
        """Clean up temporary directory."""
        self.data_dir_patcher.stop()
        import shutil
        shutil.rmtree(self.temp_dir)
    
    @patch('src.main.logging')
    def test_clean_data_files_existing(self, mock_logging):
        """Test cleaning existing data files."""
        # Create test files
        test_files = ["world.yaml", "map.yaml", "knowledge.yaml"]
        for filename in test_files:
            file_path = Path(self.temp_dir) / filename
            file_path.write_text("test data")
        
        # Run clean
        clean_data_files()
        
        # Verify files are deleted
        for filename in test_files:
            file_path = Path(self.temp_dir) / filename
            self.assertFalse(file_path.exists())
        
        # Verify logging
        self.assertTrue(mock_logging.info.called)
    
    def test_clean_data_files_missing(self):
        """Test cleaning when files don't exist."""
        # Run clean (no files exist)
        clean_data_files()  # Should not raise any errors


class TestCharacterManagement(unittest.TestCase):
    """Test cases for character management functions."""
    
    @patch('src.main.logging')
    def test_create_character(self, mock_logging):
        """Test character creation (currently not implemented)."""
        create_character('NewChar', Mock())
        
        # Verify logging of not implemented
        log_calls = [str(call) for call in mock_logging.info.call_args_list]
        self.assertTrue(any('not yet implemented' in call for call in log_calls))
    
    @patch('src.main.logging')
    def test_delete_character(self, mock_logging):
        """Test character deletion (currently not implemented)."""
        delete_character('OldChar', Mock())
        
        # Verify logging of not implemented
        log_calls = [str(call) for call in mock_logging.info.call_args_list]
        self.assertTrue(any('not yet implemented' in call for call in log_calls))


class TestSignalHandling(unittest.TestCase):
    """Test cases for signal handling."""
    
    @patch('sys.exit')
    @patch('src.main.logging')
    def test_handle_shutdown(self, mock_logging, mock_exit):
        """Test shutdown signal handling."""
        handle_shutdown(None, None)
        
        # Verify logging
        mock_logging.info.assert_called_with("Shutdown signal received, cleaning up...")
        
        # Verify exit
        mock_exit.assert_called_once_with(0)


class TestGoalPlanning(unittest.TestCase):
    """Test cases for basic goal planning functionality."""
    
    @patch('src.main.logging')
    @patch('src.main.GOAPGoalManager')
    @patch('src.main.GOAPExecutionManager')
    @patch('src.main.ActionsData')
    @patch('src.main.GoapData')
    def test_show_goal_plan_basic(self, mock_goap_data, mock_actions_data,
                                 mock_executor, mock_goal_manager, mock_logging):
        """Test basic goal plan functionality."""
        from src.main import show_goal_plan
        
        # Set up mocks
        mock_goal_manager.return_value = Mock(goal_templates={})
        mock_actions_data.return_value = Mock(get_actions=Mock(return_value={}))
        mock_goap_data.return_value = Mock(data={})
        mock_executor.return_value = Mock(create_plan=Mock(return_value=None))
        
        # Run function
        show_goal_plan('test_goal', Mock())
        
        # Verify basic execution
        mock_goal_manager.assert_called_once()
        mock_executor.assert_called_once()
    
    @patch('src.main.logging')
    @patch('src.main.ActionsData')  
    @patch('src.main.GoapData')
    def test_evaluate_user_plan_basic(self, mock_goap_data, mock_actions_data, mock_logging):
        """Test basic plan evaluation functionality."""
        from src.main import evaluate_user_plan
        
        # Set up mocks
        mock_actions_data.return_value = Mock(get_actions=Mock(return_value={}))
        mock_goap_data.return_value = Mock(data={})
        
        # Run function
        evaluate_user_plan('test_plan', Mock())
        
        # Verify basic execution
        mock_actions_data.assert_called_once()
        mock_goap_data.assert_called_once()


if __name__ == '__main__':
    unittest.main()