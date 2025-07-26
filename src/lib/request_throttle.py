"""
API Request Throttling Utility

Implements rate limiting to stay below the ArtifactsMMO API limit of 200 requests per minute.
Uses a sliding window approach with proper delays to ensure compliance.
"""

import logging
import threading
import time
from collections import deque
from collections.abc import Callable
from functools import wraps
from typing import Any


class RequestThrottle:
    """
    Request throttling utility to prevent API rate limit violations.

    Implements a sliding window rate limiter with automatic delays.
    """

    def __init__(self, max_requests_per_minute: int = 180, window_seconds: int = 60):
        """
        Initialize the request throttle.

        Args:
            max_requests_per_minute: Maximum requests allowed per minute (default 180 for safety)
            window_seconds: Time window in seconds (default 60)
        """
        self.max_requests = max_requests_per_minute
        self.window_seconds = window_seconds
        self.min_interval = window_seconds / max_requests_per_minute  # Minimum time between requests

        # Thread-safe request tracking
        self.request_times: deque[float] = deque()
        self.lock = threading.Lock()
        self.last_request_time: float = 0.0

        self.logger = logging.getLogger(__name__)

        # Log throttling configuration
        self.logger.info(f"🚦 Request throttling initialized: {max_requests_per_minute} requests/minute "
                        f"(min interval: {self.min_interval:.3f}s)")

    def acquire(self) -> None:
        """
        Acquire permission to make a request, blocking if necessary to respect rate limits.

        This method will automatically delay if needed to maintain the rate limit.
        """
        with self.lock:
            current_time = time.time()

            # Remove old requests outside the window
            self._cleanup_old_requests(current_time)

            # Calculate required delay
            delay_needed = self._calculate_delay(current_time)

            if delay_needed > 0:
                self.logger.debug(f"⏱️  Throttling: delaying {delay_needed:.3f}s to respect rate limit")
                time.sleep(delay_needed)
                current_time = time.time()

            # Record this request
            self.request_times.append(current_time)
            self.last_request_time = current_time

            # Log current rate
            requests_in_window = len(self.request_times)
            current_rate = (requests_in_window / self.window_seconds) * 60

            if requests_in_window % 10 == 0:  # Log every 10th request to avoid spam
                self.logger.debug(f"📊 Current rate: {current_rate:.1f} requests/minute "
                                f"({requests_in_window}/{self.max_requests} in window)")

    def _cleanup_old_requests(self, current_time: float) -> None:
        """Remove request timestamps outside the current window."""
        cutoff_time = current_time - self.window_seconds
        while self.request_times and self.request_times[0] < cutoff_time:
            self.request_times.popleft()

    def _calculate_delay(self, current_time: float) -> float:
        """
        Calculate the delay needed to respect rate limits.

        Returns:
            Delay in seconds (0 if no delay needed)
        """
        # Check minimum interval since last request
        time_since_last = current_time - self.last_request_time
        min_interval_delay = max(0, self.min_interval - time_since_last)

        # Check if we're at the request limit for the window
        if len(self.request_times) >= self.max_requests:
            # Calculate when the oldest request will expire
            oldest_request = self.request_times[0]
            window_delay = max(0.0, oldest_request + self.window_seconds - current_time + 0.1)  # +0.1s buffer
            return max(min_interval_delay, window_delay)

        return min_interval_delay

    def get_current_rate(self) -> float:
        """
        Get the current request rate in requests per minute.

        Returns:
            Current rate in requests/minute
        """
        with self.lock:
            current_time = time.time()
            self._cleanup_old_requests(current_time)
            requests_in_window = len(self.request_times)
            return (requests_in_window / self.window_seconds) * 60

    def get_stats(self) -> dict[str, Any]:
        """
        Get throttling statistics.

        Returns:
            Dictionary with current stats
        """
        with self.lock:
            current_time = time.time()
            self._cleanup_old_requests(current_time)
            requests_in_window = len(self.request_times)
            current_rate = (requests_in_window / self.window_seconds) * 60

            return {
                'current_rate': current_rate,
                'requests_in_window': requests_in_window,
                'max_requests': self.max_requests,
                'window_seconds': self.window_seconds,
                'utilization_percent': (requests_in_window / self.max_requests) * 100
            }


# Global throttle instance
_global_throttle: RequestThrottle | None = None


def get_global_throttle() -> RequestThrottle:
    """Get or create the global request throttle instance."""
    global _global_throttle
    if _global_throttle is None:
        _global_throttle = RequestThrottle()
    return _global_throttle


def throttled_request[F: Callable[..., Any]](func: F) -> F:
    """
    Decorator to automatically throttle function calls that make API requests.

    Usage:
        @throttled_request
        def my_api_call():
            return requests.get(url)
    """
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        throttle = get_global_throttle()
        throttle.acquire()
        return func(*args, **kwargs)
    return wrapper  # type: ignore
