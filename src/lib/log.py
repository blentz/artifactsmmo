import asyncio
import logging
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from logging import StreamHandler
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
from pathlib import Path
from queue import Queue
from typing import Any

import yaml

# Global state for logger management
_LOGGER_TASK: asyncio.Task[None] | None = None
_LISTENER: QueueListener | None = None
_LOGGING_CONFIGURED: bool = False
_LOG_QUEUES: dict[str, Queue[Any]] = {}
_LOCK = threading.Lock()

LOG_LEVEL = logging.DEBUG


class LogManager:
    """Manages multiple loggers and provides character-specific logging contexts."""

    def __init__(self) -> None:
        self.loggers: dict[str, logging.Logger] = {}
        self.queues: dict[str, Queue[Any]] = {}
        self.listeners: dict[str, QueueListener] = {}

    def get_logger(self, name: str) -> logging.Logger:
        """Get or create a logger with the given name."""
        if name not in self.loggers:
            logger = logging.getLogger(name)
            logger.setLevel(LOG_LEVEL)
            self.loggers[name] = logger
        return self.loggers[name]

    def setup_character_logger(self, character_name: str, log_dir: Path = Path("logs")) -> logging.Logger:
        """Setup a character-specific logger with file output."""
        logger_name = f"character.{character_name}"

        if logger_name not in self.loggers:
            log_dir.mkdir(exist_ok=True)
            log_file = log_dir / f"{character_name}.log"

            logger = logging.getLogger(logger_name)
            logger.setLevel(LOG_LEVEL)

            # Create file handler with rotation
            file_handler = RotatingFileHandler(log_file, maxBytes=10 * 1024 * 1024, backupCount=5)
            file_handler.setLevel(LOG_LEVEL)

            # Create formatter for structured logging
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
            )
            file_handler.setFormatter(formatter)

            logger.addHandler(file_handler)
            self.loggers[logger_name] = logger

        return self.loggers[logger_name]


# Global log manager instance
_LOG_MANAGER = LogManager()


def configure_logging(config_path: Path | None = None) -> dict[str, Any]:
    """Configure logging from YAML file or use defaults."""
    global _LOGGING_CONFIGURED

    config = {
        "version": 1,
        "level": "DEBUG",
        "handlers": {"console": {"class": "logging.StreamHandler", "level": "INFO", "formatter": "standard"}},
        "formatters": {
            "standard": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            }
        },
        "root": {"level": "DEBUG", "handlers": ["console"]},
    }

    if config_path and config_path.exists():
        try:
            with open(config_path) as f:
                file_config = yaml.safe_load(f)
                if file_config:
                    config.update(file_config)
        except Exception as e:
            logging.error(f"Failed to load logging config from {config_path}: {e}")

    _LOGGING_CONFIGURED = True
    return config


async def init_logger(config: dict[str, Any] | None = None) -> None:
    """Initialize the async logging system with queue-based handlers."""
    global _LISTENER

    if config is None:
        config = configure_logging()

    # Setup root logger
    root_logger = logging.getLogger()

    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create queue and handlers
    que: Queue[logging.LogRecord] = Queue()
    queue_handler = QueueHandler(que)
    root_logger.addHandler(queue_handler)
    root_logger.setLevel(getattr(logging, config.get("level", "DEBUG")))

    # Create console handler for the listener
    console_handler = StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Create formatter
    formatter = logging.Formatter(
        config.get("formatters", {})
        .get("standard", {})
        .get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
        datefmt=config.get("formatters", {}).get("standard", {}).get("datefmt", "%Y-%m-%d %H:%M:%S"),
    )
    console_handler.setFormatter(formatter)

    # Setup queue listener
    _LISTENER = QueueListener(que, console_handler)
    _LISTENER.start()

    try:
        logging.info("Async logger initialized successfully")

        # Keep the logger running
        while True:
            await asyncio.sleep(60)

            # Periodic health check
            if _LISTENER and _LISTENER._thread and not _LISTENER._thread.is_alive():
                logging.error("Logger listener thread died, restarting")
                _LISTENER.stop()
                _LISTENER = QueueListener(que, console_handler)
                _LISTENER.start()

    except asyncio.CancelledError:
        logging.info("Logger shutdown requested")
        raise
    except Exception as e:
        logging.error(f"Logger error: {e}")
        raise
    finally:
        if _LISTENER:
            logging.info("Stopping logger listener")
            _LISTENER.stop()
            _LISTENER = None


async def safely_start_logger(config_path: Path | None = None) -> asyncio.Task[None]:
    """Safely start the async logger and return the task."""
    global _LOGGER_TASK

    with _LOCK:
        if _LOGGER_TASK and not _LOGGER_TASK.done():
            logging.warning("Logger already running")
            return _LOGGER_TASK

        # Configure logging if not already done
        config = None
        if not _LOGGING_CONFIGURED:
            config = configure_logging(config_path)

        # Create and start the logger task
        task = asyncio.create_task(init_logger(config))
        _LOGGER_TASK = task

        # Give the logger a moment to initialize
        await asyncio.sleep(0.1)

        return _LOGGER_TASK


async def stop_logger() -> None:
    """Stop the async logger gracefully."""
    global _LOGGER_TASK, _LISTENER

    with _LOCK:
        if _LOGGER_TASK and not _LOGGER_TASK.done():
            logging.info("Stopping async logger")
            _LOGGER_TASK.cancel()

            try:
                await _LOGGER_TASK
            except asyncio.CancelledError:
                pass

            _LOGGER_TASK = None

        if _LISTENER:
            _LISTENER.stop()
            _LISTENER = None


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the specified name."""
    return _LOG_MANAGER.get_logger(name)


def get_character_logger(character_name: str, log_dir: Path = Path("logs")) -> logging.Logger:
    """Get a character-specific logger with file output."""
    return _LOG_MANAGER.setup_character_logger(character_name, log_dir)


@asynccontextmanager
async def character_logging_context(character_name: str, log_dir: Path = Path("logs")) -> AsyncIterator[logging.Logger]:
    """Async context manager for character-specific logging."""
    logger = get_character_logger(character_name, log_dir)

    logger.info(f"Starting logging session for character: {character_name}")

    try:
        yield logger
    finally:
        logger.info(f"Ending logging session for character: {character_name}")


def log_action(
    logger: logging.Logger, action_name: str, character_name: str, details: dict[str, Any] | None = None
) -> None:
    """Log an AI player action with structured data."""
    timestamp = datetime.now().isoformat()
    log_data = {"timestamp": timestamp, "character": character_name, "action": action_name, "details": details or {}}

    logger.info(f"ACTION: {action_name} | CHARACTER: {character_name} | DATA: {log_data}")


def log_api_call(
    logger: logging.Logger, endpoint: str, method: str, status_code: int, response_time: float, character_name: str
) -> None:
    """Log API calls with performance metrics."""
    logger.info(
        f"API: {method} {endpoint} | STATUS: {status_code} | TIME: {response_time:.3f}s | CHARACTER: {character_name}"
    )


def log_goap_planning(
    logger: logging.Logger,
    character_name: str,
    current_state: dict[str, Any],
    goal_state: dict[str, Any],
    plan: list[str],
) -> None:
    """Log GOAP planning results."""
    logger.info(
        f"GOAP_PLAN | CHARACTER: {character_name} | CURRENT: {current_state} | GOAL: {goal_state} | PLAN: {plan}"
    )
