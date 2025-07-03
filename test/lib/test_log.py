"""Tests for the log module."""

import asyncio
import json
import logging
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.lib.log import JSONFormatter, init_logger, safely_start_logger, DEFAULT_LOG_LEVEL


class TestJSONFormatter(unittest.TestCase):
    """Test cases for JSONFormatter."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.formatter = JSONFormatter()
        
    def test_format_basic_log_record(self):
        """Test formatting a basic log record."""
        # Create a mock log record
        record = logging.LogRecord(
            name='test_logger',
            level=logging.INFO,
            pathname='test.py',
            lineno=42,
            msg='Test message',
            args=(),
            exc_info=None
        )
        
        # Format the record
        formatted = self.formatter.format(record)
        
        # Parse the JSON output
        log_obj = json.loads(formatted)
        
        # Verify required fields
        self.assertEqual(log_obj['level'], 'INFO')
        self.assertEqual(log_obj['logger'], 'test_logger')
        self.assertEqual(log_obj['message'], 'Test message')
        self.assertEqual(log_obj['line'], 42)
        self.assertIn('timestamp', log_obj)
        self.assertIn('module', log_obj)
        self.assertIn('function', log_obj)
        
    def test_format_with_exception(self):
        """Test formatting a log record with exception info."""
        # Create an exception
        try:
            raise ValueError("Test exception")
        except ValueError:
            import sys
            exc_info = sys.exc_info()
        
        # Create a log record with exception
        record = logging.LogRecord(
            name='test_logger',
            level=logging.ERROR,
            pathname='test.py',
            lineno=42,
            msg='Error occurred',
            args=(),
            exc_info=exc_info
        )
        
        # Format the record
        formatted = self.formatter.format(record)
        
        # Parse the JSON output
        log_obj = json.loads(formatted)
        
        # Verify exception fields
        self.assertEqual(log_obj['level'], 'ERROR')
        self.assertIn('exception', log_obj)
        self.assertIn('traceback', log_obj)
        self.assertIn('ValueError: Test exception', log_obj['exception'])
        
    def test_format_with_extra_fields(self):
        """Test formatting a log record with extra fields."""
        # Create a log record
        record = logging.LogRecord(
            name='test_logger',
            level=logging.INFO,
            pathname='test.py',
            lineno=42,
            msg='Test message',
            args=(),
            exc_info=None
        )
        
        # Add extra fields
        record.user_id = 123
        record.request_id = 'abc-123'
        record.custom_field = 'custom_value'
        
        # Format the record
        formatted = self.formatter.format(record)
        
        # Parse the JSON output
        log_obj = json.loads(formatted)
        
        # Verify extra fields are included
        self.assertEqual(log_obj['user_id'], 123)
        self.assertEqual(log_obj['request_id'], 'abc-123')
        self.assertEqual(log_obj['custom_field'], 'custom_value')
        
    def test_format_with_args(self):
        """Test formatting a log record with args."""
        # Create a log record with args
        record = logging.LogRecord(
            name='test_logger',
            level=logging.INFO,
            pathname='test.py',
            lineno=42,
            msg='User %s logged in',
            args=('alice',),
            exc_info=None
        )
        
        # Format the record
        formatted = self.formatter.format(record)
        
        # Parse the JSON output
        log_obj = json.loads(formatted)
        
        # Verify message is formatted with args
        self.assertEqual(log_obj['message'], 'User alice logged in')
        
    def test_format_ensures_ascii_false(self):
        """Test that non-ASCII characters are preserved."""
        # Create a log record with non-ASCII characters
        record = logging.LogRecord(
            name='test_logger',
            level=logging.INFO,
            pathname='test.py',
            lineno=42,
            msg='Unicode message: 你好世界',
            args=(),
            exc_info=None
        )
        
        # Format the record
        formatted = self.formatter.format(record)
        
        # Verify the unicode is preserved
        self.assertIn('你好世界', formatted)
        
        # Parse the JSON output
        log_obj = json.loads(formatted)
        self.assertEqual(log_obj['message'], 'Unicode message: 你好世界')


class TestLoggerInitialization(unittest.IsolatedAsyncioTestCase):
    """Test cases for logger initialization."""
    
    def setUp(self):
        """Set up test fixtures and save logger state."""
        # Save the original logger state
        self.root_logger = logging.getLogger()
        self.original_handlers = self.root_logger.handlers.copy()
        self.original_level = self.root_logger.level
        
    def tearDown(self):
        """Clean up test fixtures and restore logger state."""
        # Remove any handlers that were added during tests
        for handler in self.root_logger.handlers[:]:
            self.root_logger.removeHandler(handler)
        
        # Restore original handlers and level
        for handler in self.original_handlers:
            self.root_logger.addHandler(handler)
        self.root_logger.setLevel(self.original_level)
    
    @patch('src.lib.log.QueueListener')
    @patch('src.lib.log.StreamHandler')
    @patch('src.lib.log.QueueHandler')
    @patch('src.lib.log.Queue')
    async def test_init_logger(self, mock_queue_class, mock_queue_handler_class, 
                             mock_stream_handler_class, mock_listener_class):
        """Test init_logger function."""
        # Set up mocks
        mock_queue = Mock()
        mock_queue_class.return_value = mock_queue
        
        mock_queue_handler = Mock()
        mock_queue_handler_class.return_value = mock_queue_handler
        
        mock_stream_handler = Mock()
        mock_stream_handler_class.return_value = mock_stream_handler
        
        mock_listener = Mock()
        mock_listener.start = Mock()
        mock_listener.stop = Mock()
        mock_listener_class.return_value = mock_listener
        
        # Create a task that will be cancelled after a short delay
        async def run_logger():
            try:
                await init_logger()
            except asyncio.CancelledError:
                pass
                
        # Run the logger task for a short time
        logger_task = asyncio.create_task(run_logger())
        await asyncio.sleep(0.1)  # Let it run briefly
        logger_task.cancel()
        
        try:
            await logger_task
        except asyncio.CancelledError:
            pass
            
        # Verify components were created and configured
        mock_queue_class.assert_called_once()
        mock_queue_handler_class.assert_called_once_with(mock_queue)
        mock_stream_handler_class.assert_called_once()
        mock_listener_class.assert_called_once_with(mock_queue, mock_stream_handler)
        
        # Verify listener was started
        mock_listener.start.assert_called_once()
        
        # Verify stream handler was configured
        mock_stream_handler.setLevel.assert_called()
        mock_stream_handler.setFormatter.assert_called()
        
    @patch('src.lib.log.logging.getLogger')
    async def test_init_logger_uses_current_level(self, mock_get_logger):
        """Test that init_logger respects the current log level."""
        # Create a mock logger with a specific level
        mock_logger = Mock()
        mock_logger.level = logging.DEBUG
        mock_logger.addHandler = Mock()
        mock_get_logger.return_value = mock_logger
        
        # Mock other dependencies
        with patch('src.lib.log.Queue'):
            with patch('src.lib.log.StreamHandler') as mock_stream_handler_class:
                mock_stream_handler = Mock()
                mock_stream_handler_class.return_value = mock_stream_handler
                
                with patch('src.lib.log.QueueListener') as mock_listener_class:
                    mock_listener = Mock()
                    mock_listener.start = Mock()
                    mock_listener_class.return_value = mock_listener
                    
                    # Run logger briefly
                    logger_task = asyncio.create_task(init_logger())
                    await asyncio.sleep(0.01)
                    logger_task.cancel()
                    
                    try:
                        await logger_task
                    except asyncio.CancelledError:
                        pass
                        
                    # Verify DEBUG level was used
                    mock_stream_handler.setLevel.assert_called_with(logging.DEBUG)
                    
    @patch('src.lib.log.logging.getLogger')
    async def test_init_logger_uses_default_level_when_notset(self, mock_get_logger):
        """Test that init_logger uses DEFAULT_LOG_LEVEL when level is NOTSET."""
        # Create a mock logger with NOTSET level
        mock_logger = Mock()
        mock_logger.level = logging.NOTSET
        mock_logger.addHandler = Mock()
        mock_get_logger.return_value = mock_logger
        
        # Mock other dependencies
        with patch('src.lib.log.Queue'):
            with patch('src.lib.log.StreamHandler') as mock_stream_handler_class:
                mock_stream_handler = Mock()
                mock_stream_handler_class.return_value = mock_stream_handler
                
                with patch('src.lib.log.QueueListener') as mock_listener_class:
                    mock_listener = Mock()
                    mock_listener.start = Mock()
                    mock_listener_class.return_value = mock_listener
                    
                    # Run logger briefly
                    logger_task = asyncio.create_task(init_logger())
                    await asyncio.sleep(0.01)
                    logger_task.cancel()
                    
                    try:
                        await logger_task
                    except asyncio.CancelledError:
                        pass
                        
                    # Verify DEFAULT_LOG_LEVEL was used
                    mock_stream_handler.setLevel.assert_called_with(DEFAULT_LOG_LEVEL)
                    
    @patch('src.lib.log.asyncio.create_task')
    async def test_safely_start_logger(self, mock_create_task):
        """Test safely_start_logger function."""
        # Create a mock task
        mock_task = Mock()
        mock_create_task.return_value = mock_task
        
        # Call safely_start_logger
        await safely_start_logger()
        
        # Verify task was created
        mock_create_task.assert_called_once()
        
    @patch('src.lib.log.QueueListener')
    async def test_init_logger_cleanup_on_exception(self, mock_listener_class):
        """Test that listener is stopped even if an exception occurs."""
        # Create a mock listener
        mock_listener = Mock()
        mock_listener.start = Mock()
        mock_listener.stop = Mock()
        mock_listener_class.return_value = mock_listener
        
        # Mock other dependencies to raise exception during sleep
        with patch('src.lib.log.Queue'):
            with patch('src.lib.log.StreamHandler'):
                with patch('src.lib.log.asyncio.sleep', side_effect=Exception("Test error")):
                    # Run init_logger and expect exception
                    with self.assertRaises(Exception):
                        await init_logger()
                        
                    # Verify listener was still stopped
                    mock_listener.stop.assert_called_once()


if __name__ == '__main__':
    # Use asyncio test runner
    unittest.main()