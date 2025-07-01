import asyncio
import json
import logging
import traceback
from datetime import datetime
from logging import StreamHandler
from logging.handlers import QueueHandler, QueueListener
from queue import Queue

LOGGER_TASK: asyncio.Task = None

# Default log level - can be overridden by CLI
DEFAULT_LOG_LEVEL = logging.INFO


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""
    
    def format(self, record):
        log_obj = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
            log_obj["traceback"] = traceback.format_exception(*record.exc_info)
        
        # Add any extra fields
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'created', 'filename', 
                          'funcName', 'levelname', 'levelno', 'lineno', 
                          'module', 'msecs', 'message', 'pathname', 'process',
                          'processName', 'relativeCreated', 'thread', 'threadName',
                          'exc_info', 'exc_text', 'stack_info']:
                log_obj[key] = value
                
        return json.dumps(log_obj, ensure_ascii=False)

# helper coroutine to setup and manage the logger
async def init_logger():
    log = logging.getLogger()
    que = Queue()
    
    # Get the current log level that was set by CLI (if any)
    current_level = log.level
    
    # If no level was set (NOTSET), use the default
    if current_level == logging.NOTSET:
        current_level = DEFAULT_LOG_LEVEL
    
    # Create a stream handler that respects the configured log level
    stream_handler = StreamHandler()
    stream_handler.setLevel(current_level)
    
    # Set the JSON formatter on the stream handler
    json_formatter = JSONFormatter()
    stream_handler.setFormatter(json_formatter)
    
    # Add queue handler to the logger
    log.addHandler(QueueHandler(que))
    
    # Create listener with the stream handler
    listener = QueueListener(que, stream_handler)
    
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
