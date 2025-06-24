import unittest
import asyncio
from unittest.mock import patch, MagicMock

from src.lib.log import init_logger, safely_start_logger, LOGGER_TASK

class TestLoggerModule(unittest.TestCase):

    @patch('logging.getLogger')
    @patch('queue.Queue')
    @patch('logging.handlers.QueueHandler')
    @patch('logging.StreamHandler')
    @patch('logging.handlers.QueueListener')
    async def async_test_init_logger(self, MockQueueListener, MockStreamHandler,
                                     MockQueueHandler, MockQueue, MockGetLogger):
        # Setup mocks
        log_mock = MagicMock()
        MockGetLogger.return_value = log_mock

        listener_mock = MagicMock()
        MockQueueListener.return_value = listener_mock

        # Run the function
        await init_logger()

        # Check that logging was set up correctly
        MockGetLogger.assert_called_once()
        MockQueue.assert_called_once()
        MockQueueHandler.assert_called_once_with(MockQueue())
        log_mock.setLevel.assert_called_once_with(logging.DEBUG)
        MockQueueListener.assert_called_once_with(MockQueue(), MockStreamHandler())

        # Check that listener was started
        listener_mock.start.assert_called_once()

    @patch('asyncio.create_task')
    async def async_test_safely_start_logger(self, mock_create_task):
        await safely_start_logger()
        mock_create_task.assert_called_once_with(init_logger)

if __name__ == '__main__':
    unittest.main()
