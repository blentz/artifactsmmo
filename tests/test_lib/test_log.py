import asyncio
import logging
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml

import src.lib.log
from src.lib.log import (
    LogManager,
    character_logging_context,
    configure_logging,
    get_character_logger,
    get_logger,
    init_logger,
    log_action,
    log_api_call,
    log_goap_planning,
    safely_start_logger,
    stop_logger,
)


class TestLogManager:
    """Test the LogManager class."""

    def test_log_manager_init(self):
        """Test LogManager initialization."""
        manager = LogManager()
        assert manager.loggers == {}
        assert manager.queues == {}
        assert manager.listeners == {}

    def test_get_logger(self):
        """Test getting a logger instance."""
        # Ensure LOG_LEVEL is set to DEBUG for this test
        original_level = src.lib.log.LOG_LEVEL
        src.lib.log.LOG_LEVEL = logging.DEBUG

        try:
            manager = LogManager()
            logger = manager.get_logger("test_logger")

            assert logger.name == "test_logger"
            assert logger.level == logging.DEBUG
            assert "test_logger" in manager.loggers
        finally:
            src.lib.log.LOG_LEVEL = original_level

        # Getting the same logger should return the same instance
        logger2 = manager.get_logger("test_logger")
        assert logger is logger2

    def test_setup_character_logger(self):
        """Test setting up character-specific loggers."""
        # Ensure LOG_LEVEL is set to DEBUG for this test
        original_level = src.lib.log.LOG_LEVEL
        src.lib.log.LOG_LEVEL = logging.DEBUG

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                log_dir = Path(temp_dir)
                manager = LogManager()

                logger = manager.setup_character_logger("test_char", log_dir)

                assert logger.name == "character.test_char"
                assert logger.level == logging.DEBUG
                assert "character.test_char" in manager.loggers

                # Check that log file was created
                log_file = log_dir / "test_char.log"
                assert log_file.parent.exists()

                # Test logging to file
                logger.info("Test message")

                # Getting the same character logger should return the same instance
                logger2 = manager.setup_character_logger("test_char", log_dir)
                assert logger is logger2
        finally:
            src.lib.log.LOG_LEVEL = original_level


class TestConfigureLogging:
    """Test logging configuration."""

    def test_configure_logging_defaults(self):
        """Test default configuration."""
        config = configure_logging()

        assert config["version"] == 1
        assert config["level"] == "DEBUG"
        assert "console" in config["handlers"]
        assert "standard" in config["formatters"]
        assert config["root"]["level"] == "DEBUG"

    def test_configure_logging_from_file(self):
        """Test loading configuration from YAML file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            test_config = {
                "level": "INFO",
                "custom_setting": "test_value"
            }
            yaml.dump(test_config, f)
            config_path = Path(f.name)

        try:
            config = configure_logging(config_path)
            assert config["level"] == "INFO"
            assert config["custom_setting"] == "test_value"
        finally:
            config_path.unlink()

    def test_configure_logging_file_not_found(self):
        """Test handling of missing config file."""
        non_existent = Path("non_existent_config.yaml")
        config = configure_logging(non_existent)

        # Should return default config
        assert config["level"] == "DEBUG"

    def test_configure_logging_invalid_yaml(self):
        """Test handling of invalid YAML."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: [")
            config_path = Path(f.name)

        try:
            with patch('src.lib.log.logging.error') as mock_error:
                config = configure_logging(config_path)
                # Should return default config and log error
                assert config["level"] == "DEBUG"
                mock_error.assert_called_once()
        finally:
            config_path.unlink()


class TestAsyncLogging:
    """Test async logging functionality."""

    @pytest.fixture
    def event_loop(self):
        """Create event loop for async tests."""
        loop = asyncio.new_event_loop()
        yield loop
        loop.close()

    async def test_safely_start_logger(self):
        """Test safely starting the logger."""

        # Ensure logger is not running
        if src.lib.log._LOGGER_TASK and not src.lib.log._LOGGER_TASK.done():
            await stop_logger()

        task = await safely_start_logger()

        assert task is not None
        assert not task.done()
        assert src.lib.log._LOGGER_TASK is task

        # Clean up
        await stop_logger()

    async def test_safely_start_logger_already_running(self):
        """Test starting logger when already running."""
        global _LOGGER_TASK

        # Start logger first
        task1 = await safely_start_logger()

        # Try to start again
        with patch('src.lib.log.logging.warning') as mock_warning:
            task2 = await safely_start_logger()
            assert task1 is task2
            mock_warning.assert_called_once_with("Logger already running")

        # Clean up
        await stop_logger()

    async def test_stop_logger(self):
        """Test stopping the logger."""

        # Start logger
        await safely_start_logger()
        assert src.lib.log._LOGGER_TASK is not None

        # Stop logger
        await stop_logger()
        assert src.lib.log._LOGGER_TASK is None
        assert src.lib.log._LISTENER is None

    async def test_init_logger_with_config(self):
        """Test initializing logger with custom config."""
        config = {
            "level": "INFO",
            "formatters": {
                "standard": {
                    "format": "TEST: %(message)s",
                    "datefmt": "%H:%M:%S"
                }
            }
        }

        # Mock QueueListener to avoid actual logging setup
        with patch('src.lib.log.QueueListener') as mock_listener:
            mock_listener_instance = Mock()
            mock_listener.return_value = mock_listener_instance

            # Start the init_logger task
            task = asyncio.create_task(init_logger(config))

            # Let it initialize
            await asyncio.sleep(0.1)

            # Cancel the task
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

            # Verify QueueListener was created and started
            mock_listener.assert_called_once()
            mock_listener_instance.start.assert_called_once()


class TestUtilityFunctions:
    """Test utility functions."""

    def test_get_logger(self):
        """Test get_logger function."""
        logger = get_logger("test_util")
        assert logger.name == "test_util"
        assert isinstance(logger, logging.Logger)

    def test_get_character_logger(self):
        """Test get_character_logger function."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)
            logger = get_character_logger("test_char", log_dir)

            assert logger.name == "character.test_char"
            assert isinstance(logger, logging.Logger)

    async def test_character_logging_context(self):
        """Test character logging context manager."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)

            async with character_logging_context("test_char", log_dir) as logger:
                assert logger.name == "character.test_char"
                logger.info("Test message in context")

            # Context should complete without errors

    def test_log_action(self):
        """Test action logging function."""
        logger = Mock()
        details = {"hp": 100, "location": "forest"}

        log_action(logger, "fight_monster", "test_char", details)

        logger.info.assert_called_once()
        call_args = logger.info.call_args[0][0]
        assert "ACTION: fight_monster" in call_args
        assert "CHARACTER: test_char" in call_args
        assert "DATA:" in call_args

    def test_log_api_call(self):
        """Test API call logging function."""
        logger = Mock()

        log_api_call(logger, "/character/move", "POST", 200, 0.123, "test_char")

        logger.info.assert_called_once()
        call_args = logger.info.call_args[0][0]
        assert "API: POST /character/move" in call_args
        assert "STATUS: 200" in call_args
        assert "TIME: 0.123s" in call_args
        assert "CHARACTER: test_char" in call_args

    def test_log_goap_planning(self):
        """Test GOAP planning logging function."""
        logger = Mock()
        current_state = {"hp": 100, "level": 1}
        goal_state = {"level": 2}
        plan = ["move_to_monster", "fight_monster"]

        log_goap_planning(logger, "test_char", current_state, goal_state, plan)

        logger.info.assert_called_once()
        call_args = logger.info.call_args[0][0]
        assert "GOAP_PLAN" in call_args
        assert "CHARACTER: test_char" in call_args
        assert "CURRENT:" in call_args
        assert "GOAL:" in call_args
        assert "PLAN:" in call_args


class TestThreadSafety:
    """Test thread safety of logging functions."""

    def test_lock_usage(self):
        """Test that the lock is used properly."""
        with patch('src.lib.log._LOCK') as mock_lock:
            mock_lock.__enter__ = Mock()
            mock_lock.__exit__ = Mock()

            # This should use the lock
            asyncio.run(safely_start_logger())

            # Verify lock was acquired
            mock_lock.__enter__.assert_called()


class TestErrorHandling:
    """Test error handling in logging functions."""

    async def test_init_logger_exception_handling(self):
        """Test exception handling in init_logger."""
        # Mock QueueListener to raise an exception
        with patch('src.lib.log.QueueListener') as mock_listener:
            mock_listener.side_effect = Exception("Test exception")

            with pytest.raises(Exception, match="Test exception"):
                await init_logger()

    async def test_init_logger_non_cancelled_exception(self):
        """Test non-CancelledError exception handling in init_logger."""
        config = {"level": "DEBUG"}

        # Mock QueueListener to work initially but then have thread die
        with patch('src.lib.log.QueueListener') as mock_listener_class:
            mock_listener = Mock()
            mock_thread = Mock()
            mock_thread.is_alive.return_value = False  # Thread is dead
            mock_listener._thread = mock_thread
            mock_listener_class.return_value = mock_listener

            # Mock asyncio.sleep to raise a non-CancelledError exception after first call
            sleep_call_count = 0
            async def mock_sleep(duration):
                nonlocal sleep_call_count
                sleep_call_count += 1
                if sleep_call_count == 1:
                    return  # First call succeeds
                else:
                    raise RuntimeError("Test runtime error")  # Second call fails

            with patch('asyncio.sleep', side_effect=mock_sleep):
                with pytest.raises(RuntimeError, match="Test runtime error"):
                    await init_logger(config)

    async def test_init_logger_listener_thread_restart(self):
        """Test listener thread restart when it dies."""
        config = {"level": "DEBUG"}

        # Mock QueueListener
        with patch('src.lib.log.QueueListener') as mock_listener_class:
            mock_listener = Mock()
            mock_thread = Mock()

            # First check: thread is dead, second check: thread is alive
            mock_thread.is_alive.side_effect = [False, True]
            mock_listener._thread = mock_thread
            mock_listener_class.return_value = mock_listener

            # Mock asyncio.sleep to only allow two iterations
            sleep_call_count = 0
            async def mock_sleep(duration):
                nonlocal sleep_call_count
                sleep_call_count += 1
                if sleep_call_count >= 3:  # Stop after health check
                    raise asyncio.CancelledError("Test cancelled")

            with patch('asyncio.sleep', side_effect=mock_sleep):
                with pytest.raises(asyncio.CancelledError):
                    await init_logger(config)

            # Verify listener was restarted
            assert mock_listener.stop.call_count >= 1
            assert mock_listener_class.call_count >= 2  # Original + restart

    def test_log_manager_setup_character_logger_exception(self):
        """Test exception handling in character logger setup."""
        manager = LogManager()

        # Test with invalid log directory
        with patch('pathlib.Path.mkdir', side_effect=PermissionError("Permission denied")):
            with pytest.raises(PermissionError):
                manager.setup_character_logger("test_char", Path("/invalid/path"))

    async def test_stop_logger_with_listener(self):
        """Test stopping logger when listener exists."""

        # Set up a mock listener
        mock_listener = Mock()
        original_listener = src.lib.log._LISTENER
        src.lib.log._LISTENER = mock_listener

        # Create a proper asyncio task that can be cancelled
        async def dummy_coro():
            while True:
                await asyncio.sleep(1)

        task = asyncio.create_task(dummy_coro())
        original_task = src.lib.log._LOGGER_TASK
        src.lib.log._LOGGER_TASK = task

        try:
            await stop_logger()

            # Verify listener was stopped
            mock_listener.stop.assert_called_once()
            assert src.lib.log._LISTENER is None
            assert src.lib.log._LOGGER_TASK is None
        finally:
            # Clean up
            src.lib.log._LISTENER = original_listener
            src.lib.log._LOGGER_TASK = original_task
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass


class TestIntegration:
    """Integration tests for the logging system."""

    async def test_full_logging_lifecycle(self):
        """Test complete logging lifecycle."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)

            # Start logger
            task = await safely_start_logger()
            assert task is not None

            # Create character logger
            char_logger = get_character_logger("integration_test", log_dir)

            # Log some actions
            log_action(char_logger, "test_action", "integration_test", {"test": "data"})
            log_api_call(char_logger, "/test", "GET", 200, 0.1, "integration_test")

            # Use context manager
            async with character_logging_context("integration_test", log_dir) as context_logger:
                context_logger.info("Context test message")

            # Stop logger
            await stop_logger()

            # Verify log file exists and has content
            log_file = log_dir / "integration_test.log"
            assert log_file.exists()


# Test fixtures and helpers
@pytest.fixture
def clean_logging_state():
    """Clean up logging state before and after tests."""

    # Clean up before test
    if src.lib.log._LOGGER_TASK and not src.lib.log._LOGGER_TASK.done():
        asyncio.run(stop_logger())

    original_configured = src.lib.log._LOGGING_CONFIGURED

    yield

    # Clean up after test
    if src.lib.log._LOGGER_TASK and not src.lib.log._LOGGER_TASK.done():
        asyncio.run(stop_logger())

    # Reset configuration state
    src.lib.log._LOGGING_CONFIGURED = original_configured


# Apply the fixture to all async test classes
pytestmark = pytest.mark.usefixtures("clean_logging_state")
