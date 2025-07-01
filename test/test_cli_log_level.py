"""Test CLI log level functionality"""

import logging
import os
import sys
import unittest

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.cli import parse_args, setup_logging


class TestCLILogLevel(unittest.TestCase):
    """Test CLI log level setting functionality"""
    
    def setUp(self):
        """Reset logging before each test"""
        # Remove all handlers from root logger
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        # Reset to default level
        root_logger.setLevel(logging.WARNING)
    
    def test_setup_logging_debug(self):
        """Test setting DEBUG log level"""
        setup_logging('DEBUG')
        root_logger = logging.getLogger()
        self.assertEqual(root_logger.level, logging.DEBUG)
    
    def test_setup_logging_info(self):
        """Test setting INFO log level"""
        setup_logging('INFO')
        root_logger = logging.getLogger()
        self.assertEqual(root_logger.level, logging.INFO)
    
    def test_setup_logging_warning(self):
        """Test setting WARNING log level"""
        setup_logging('WARNING')
        root_logger = logging.getLogger()
        self.assertEqual(root_logger.level, logging.WARNING)
    
    def test_setup_logging_error(self):
        """Test setting ERROR log level"""
        setup_logging('ERROR')
        root_logger = logging.getLogger()
        self.assertEqual(root_logger.level, logging.ERROR)
    
    def test_setup_logging_critical(self):
        """Test setting CRITICAL log level"""
        setup_logging('CRITICAL')
        root_logger = logging.getLogger()
        self.assertEqual(root_logger.level, logging.CRITICAL)
    
    def test_setup_logging_case_insensitive(self):
        """Test that log level is case insensitive"""
        setup_logging('debug')
        root_logger = logging.getLogger()
        self.assertEqual(root_logger.level, logging.DEBUG)
        
        setup_logging('InFo')
        root_logger = logging.getLogger()
        self.assertEqual(root_logger.level, logging.INFO)
    
    def test_setup_logging_invalid_level(self):
        """Test that invalid log level raises ValueError"""
        with self.assertRaises(ValueError):
            setup_logging('INVALID')
    
    def test_parse_args_default_log_level(self):
        """Test that default log level is INFO"""
        args = parse_args([])
        self.assertEqual(args.log_level, 'INFO')
    
    def test_parse_args_custom_log_level(self):
        """Test parsing custom log level"""
        args = parse_args(['-l', 'DEBUG'])
        self.assertEqual(args.log_level, 'DEBUG')
        
        args = parse_args(['--log-level', 'ERROR'])
        self.assertEqual(args.log_level, 'ERROR')
    
    def test_module_loggers_inherit_root_level(self):
        """Test that module loggers inherit root logger level"""
        setup_logging('ERROR')
        
        # Create a module logger
        module_logger = logging.getLogger('test.module')
        
        # Module logger should inherit root logger's level
        # (effective level is ERROR even if module logger's level is NOTSET)
        self.assertEqual(module_logger.getEffectiveLevel(), logging.ERROR)


if __name__ == '__main__':
    unittest.main()