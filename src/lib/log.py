import logging
from logging.handlers import QueueHandler
from logging.handlers import QueueListener
from logging import StreamHandler
from queue import Queue
import asyncio

LOGGER_TASK: asyncio.Task = None


# helper coroutine to setup and manage the logger
async def init_logger():
    log: Logger = logging.getLogger()
    que: Queue = Queue()
    log.addHandler(QueueHandler(que))
    log.setLevel(logging.DEBUG)
    listener: QueueListener = QueueListener(que, StreamHandler())
    try:
        listener.start()
        logging.debug("Logger started")
        while True:
            await asyncio.sleep(60)
    finally:
        logging.debug("Logger stopped")
        listener.stop()


async def safely_start_logger():
    LOGGER_TASK = asyncio.create_task(init_logger())
    await asyncio.sleep(0)
