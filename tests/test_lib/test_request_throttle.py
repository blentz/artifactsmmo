import threading
import time
from collections import deque
from unittest.mock import Mock, patch

import pytest

from src.lib.request_throttle import RequestThrottle, get_global_throttle, throttled_request
import src.lib.request_throttle


class TestRequestThrottle:
    """Test the RequestThrottle class."""

    def test_request_throttle_init(self):
        """Test RequestThrottle initialization with default values."""
        throttle = RequestThrottle()

        assert throttle.max_requests == 180
        assert throttle.window_seconds == 60
        assert throttle.min_interval == 60 / 180  # 0.333...
        assert isinstance(throttle.request_times, deque)
        assert isinstance(throttle.lock, threading.Lock)
        assert throttle.last_request_time == 0

    def test_request_throttle_init_custom_values(self):
        """Test RequestThrottle initialization with custom values."""
        throttle = RequestThrottle(max_requests_per_minute=100, window_seconds=30)

        assert throttle.max_requests == 100
        assert throttle.window_seconds == 30
        assert throttle.min_interval == 30 / 100  # 0.3

    def test_cleanup_old_requests(self):
        """Test cleanup of old request timestamps."""
        throttle = RequestThrottle(max_requests_per_minute=60, window_seconds=10)
        current_time = time.time()

        # Add some old and new requests
        throttle.request_times.extend([
            current_time - 15,  # Should be removed
            current_time - 5,   # Should be kept
            current_time - 2,   # Should be kept
        ])

        throttle._cleanup_old_requests(current_time)

        assert len(throttle.request_times) == 2
        assert throttle.request_times[0] == current_time - 5
        assert throttle.request_times[1] == current_time - 2

    def test_calculate_delay_min_interval(self):
        """Test delay calculation based on minimum interval."""
        throttle = RequestThrottle(max_requests_per_minute=60, window_seconds=60)  # 1 request per second
        current_time = time.time()

        # Set last request time to 0.5 seconds ago
        throttle.last_request_time = current_time - 0.5

        delay = throttle._calculate_delay(current_time)

        # Should delay 0.5 seconds to maintain 1 second interval
        assert abs(delay - 0.5) < 0.01

    def test_calculate_delay_window_limit(self):
        """Test delay calculation when at window limit."""
        throttle = RequestThrottle(max_requests_per_minute=3, window_seconds=60)
        current_time = time.time()

        # Fill up to the limit
        throttle.request_times.extend([
            current_time - 50,  # Will expire in 10 seconds
            current_time - 30,
            current_time - 10,
        ])

        delay = throttle._calculate_delay(current_time)

        # Should delay until oldest request expires (10s) plus buffer (0.1s)
        assert abs(delay - 10.1) < 0.01

    def test_calculate_delay_no_delay_needed(self):
        """Test delay calculation when no delay is needed."""
        throttle = RequestThrottle(max_requests_per_minute=60, window_seconds=60)
        current_time = time.time()

        # Set last request time to 2 seconds ago (more than min interval)
        throttle.last_request_time = current_time - 2

        delay = throttle._calculate_delay(current_time)

        assert delay == 0

    @patch('time.sleep')
    @patch('time.time')
    def test_acquire_with_delay(self, mock_time, mock_sleep):
        """Test acquire method with required delay."""
        throttle = RequestThrottle(max_requests_per_minute=60, window_seconds=60)

        # Mock time to return consistent values
        mock_time.side_effect = [100.0, 101.0, 101.0]  # current_time calls
        throttle.last_request_time = 100.0

        throttle.acquire()

        # min_interval = 60/60 = 1.0 second
        # time_since_last = 100.0 - 100.0 = 0.0
        # delay = 1.0 - 0.0 = 1.0
        mock_sleep.assert_called_once_with(1.0)
        assert len(throttle.request_times) == 1
        assert throttle.last_request_time == 101.0

    @patch('time.sleep')
    @patch('time.time')
    def test_acquire_no_delay(self, mock_time, mock_sleep):
        """Test acquire method when no delay is needed."""
        throttle = RequestThrottle(max_requests_per_minute=60, window_seconds=60)

        mock_time.return_value = 100.0
        throttle.last_request_time = 98.0  # 2 seconds ago, more than min_interval

        throttle.acquire()

        mock_sleep.assert_not_called()
        assert len(throttle.request_times) == 1
        assert throttle.last_request_time == 100.0

    def test_get_current_rate(self):
        """Test current rate calculation."""
        throttle = RequestThrottle(max_requests_per_minute=60, window_seconds=60)
        current_time = time.time()

        # Add 30 requests in the last 60 seconds
        for i in range(30):
            throttle.request_times.append(current_time - i)

        rate = throttle.get_current_rate()

        # Should be 30 requests per minute
        assert rate == 30.0

    def test_get_stats(self):
        """Test statistics reporting."""
        throttle = RequestThrottle(max_requests_per_minute=60, window_seconds=60)
        current_time = time.time()

        # Add 20 requests in the last 60 seconds
        for i in range(20):
            throttle.request_times.append(current_time - i)

        stats = throttle.get_stats()

        assert stats['current_rate'] == 20.0
        assert stats['requests_in_window'] == 20
        assert stats['max_requests'] == 60
        assert stats['window_seconds'] == 60
        assert stats['utilization_percent'] == (20 / 60) * 100

    def test_thread_safety(self):
        """Test thread safety of the throttle."""
        throttle = RequestThrottle(max_requests_per_minute=1000, window_seconds=60)
        results = []
        errors = []

        def make_request(thread_id):
            try:
                for _ in range(10):
                    throttle.acquire()
                    results.append(thread_id)
            except Exception as e:
                errors.append(e)

        # Create and start multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=make_request, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Should have 50 total requests (5 threads * 10 requests each)
        assert len(results) == 50
        assert len(errors) == 0
        assert len(throttle.request_times) == 50


class TestGlobalThrottle:
    """Test global throttle functionality."""

    def setup_method(self):
        """Reset global throttle before each test."""
        src.lib.request_throttle._global_throttle = None

    def test_get_global_throttle_creates_instance(self):
        """Test that get_global_throttle creates an instance."""
        throttle = get_global_throttle()

        assert isinstance(throttle, RequestThrottle)
        assert throttle.max_requests == 180  # Default value

    def test_get_global_throttle_returns_same_instance(self):
        """Test that get_global_throttle returns the same instance."""
        throttle1 = get_global_throttle()
        throttle2 = get_global_throttle()

        assert throttle1 is throttle2


class TestThrottledRequestDecorator:
    """Test the throttled_request decorator."""

    def setup_method(self):
        """Reset global throttle before each test."""
        src.lib.request_throttle._global_throttle = None

    @patch('src.lib.request_throttle.get_global_throttle')
    def test_throttled_request_decorator(self, mock_get_throttle):
        """Test that the decorator calls throttle.acquire()."""
        mock_throttle = Mock()
        mock_get_throttle.return_value = mock_throttle

        @throttled_request
        def test_function(x, y):
            return x + y

        result = test_function(1, 2)

        assert result == 3
        mock_throttle.acquire.assert_called_once()

    @patch('src.lib.request_throttle.get_global_throttle')
    def test_throttled_request_decorator_with_exception(self, mock_get_throttle):
        """Test that the decorator still calls throttle.acquire() even if function raises exception."""
        mock_throttle = Mock()
        mock_get_throttle.return_value = mock_throttle

        @throttled_request
        def test_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            test_function()

        mock_throttle.acquire.assert_called_once()

    def test_throttled_request_decorator_integration(self):
        """Test decorator with real throttle instance."""
        call_times = []

        @throttled_request
        def test_function():
            call_times.append(time.time())
            return "success"

        # Make multiple calls
        results = []
        for _ in range(3):
            results.append(test_function())

        # All calls should succeed
        assert all(result == "success" for result in results)
        assert len(call_times) == 3

        # Calls should be spaced by at least the minimum interval
        # (with some tolerance for timing variations)
        for i in range(1, len(call_times)):
            time_diff = call_times[i] - call_times[i-1]
            assert time_diff >= 0.33 - 0.05  # min_interval with tolerance


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_zero_max_requests(self):
        """Test behavior with zero max requests."""
        with pytest.raises(ZeroDivisionError):
            RequestThrottle(max_requests_per_minute=0, window_seconds=60)

    def test_negative_max_requests(self):
        """Test behavior with negative max requests."""
        # The implementation doesn't validate negative values, it just calculates min_interval
        throttle = RequestThrottle(max_requests_per_minute=-1, window_seconds=60)
        assert throttle.max_requests == -1
        assert throttle.min_interval == -60  # 60 / -1

    def test_zero_window_seconds(self):
        """Test behavior with zero window seconds."""
        throttle = RequestThrottle(max_requests_per_minute=60, window_seconds=0)

        # Should handle zero window gracefully
        assert throttle.window_seconds == 0
        assert throttle.min_interval == 0

    def test_very_high_rate_limit(self):
        """Test behavior with very high rate limits."""
        throttle = RequestThrottle(max_requests_per_minute=10000, window_seconds=1)

        # Should handle high rates without issues
        for _ in range(10):
            throttle.acquire()

        assert len(throttle.request_times) == 10

    @patch('time.time')
    def test_time_goes_backwards(self, mock_time):
        """Test behavior when system time goes backwards."""
        throttle = RequestThrottle(max_requests_per_minute=60, window_seconds=60)

        # Simulate time going backwards
        mock_time.side_effect = [100.0, 99.0, 98.0]

        # Should handle gracefully without crashing
        throttle.acquire()
        throttle.acquire()

        assert len(throttle.request_times) == 2
