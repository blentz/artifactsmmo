"""Unit tests for RequestThrottle class."""

import unittest
import time
from unittest.mock import Mock, patch
from src.lib.request_throttle import RequestThrottle, get_global_throttle, throttled_request


class TestRequestThrottle(unittest.TestCase):
    """Test cases for RequestThrottle class."""
    
    def test_initialization_default(self):
        """Test RequestThrottle initialization with default values."""
        throttle = RequestThrottle()
        
        self.assertEqual(throttle.max_requests, 180)
        self.assertEqual(throttle.window_seconds, 60)
        self.assertAlmostEqual(throttle.min_interval, 60/180, places=3)
        self.assertEqual(throttle.last_request_time, 0)
        self.assertIsNotNone(throttle.logger)
        self.assertEqual(len(throttle.request_times), 0)
    
    def test_initialization_custom(self):
        """Test RequestThrottle initialization with custom values."""
        throttle = RequestThrottle(max_requests_per_minute=120, window_seconds=30)
        
        self.assertEqual(throttle.max_requests, 120)
        self.assertEqual(throttle.window_seconds, 30)
        self.assertEqual(throttle.min_interval, 30/120)  # 0.25
        self.assertEqual(throttle.last_request_time, 0)
    
    @patch('time.time')
    @patch('time.sleep')
    def test_acquire_first_request(self, mock_sleep, mock_time):
        """Test acquire on first request."""
        mock_time.return_value = 100.0
        
        throttle = RequestThrottle(max_requests_per_minute=60, window_seconds=60)
        throttle.acquire()
        
        # First request should not sleep
        mock_sleep.assert_not_called()
        self.assertEqual(len(throttle.request_times), 1)
        self.assertEqual(throttle.last_request_time, 100.0)
    
    @patch('time.time')
    @patch('time.sleep')
    def test_acquire_needs_min_interval_delay(self, mock_sleep, mock_time):
        """Test acquire when minimum interval delay is needed."""
        throttle = RequestThrottle(max_requests_per_minute=60, window_seconds=60)  # 1 second interval
        
        # First request
        mock_time.return_value = 100.0
        throttle.acquire()
        
        # Second request too soon (0.5 seconds later)
        mock_time.return_value = 100.5
        throttle.acquire()
        
        # Should sleep to reach minimum interval
        mock_sleep.assert_called_with(0.5)  # 1.0 - 0.5 = 0.5
    
    @patch('time.time')
    @patch('time.sleep')
    def test_acquire_no_delay_needed(self, mock_sleep, mock_time):
        """Test acquire when no delay is needed."""
        throttle = RequestThrottle(max_requests_per_minute=60, window_seconds=60)  # 1 second interval
        
        # First request
        mock_time.return_value = 100.0
        throttle.acquire()
        
        # Second request after sufficient time (1.5 seconds later)
        mock_time.return_value = 101.5
        throttle.acquire()
        
        # Should not sleep since enough time has passed
        self.assertEqual(mock_sleep.call_count, 0)
    
    def test_cleanup_old_requests(self):
        """Test cleanup of old request timestamps."""
        throttle = RequestThrottle(max_requests_per_minute=60, window_seconds=10)
        
        # Manually add some old requests
        throttle.request_times.extend([100.0, 105.0, 110.0, 115.0])
        
        # Cleanup with current time 115 (window goes back to 105)
        throttle._cleanup_old_requests(115.0)
        
        # Should remove requests older than 105
        self.assertEqual(len(throttle.request_times), 3)  # 105, 110, 115
        self.assertEqual(throttle.request_times[0], 105.0)
    
    def test_calculate_delay_min_interval(self):
        """Test delay calculation for minimum interval."""
        throttle = RequestThrottle(max_requests_per_minute=60, window_seconds=60)  # 1 second interval
        throttle.last_request_time = 100.0
        
        # Test when 0.5 seconds have passed (need 0.5 more)
        delay = throttle._calculate_delay(100.5)
        self.assertAlmostEqual(delay, 0.5, places=2)
        
        # Test when 1.5 seconds have passed (no delay needed)
        delay = throttle._calculate_delay(101.5)
        self.assertEqual(delay, 0.0)
    
    def test_calculate_delay_window_limit(self):
        """Test delay calculation when window limit is reached."""
        throttle = RequestThrottle(max_requests_per_minute=3, window_seconds=60)
        
        # Fill up the request window
        throttle.request_times.extend([100.0, 120.0, 140.0])  # 3 requests
        throttle.last_request_time = 140.0
        
        # Try to make request at 150 (should wait for first request to expire)
        delay = throttle._calculate_delay(150.0)
        
        # Should wait until 100 + 60 + 0.1 = 160.1
        expected_delay = 160.1 - 150.0
        self.assertAlmostEqual(delay, expected_delay, places=1)
    
    @patch('time.time')
    def test_get_current_rate(self, mock_time):
        """Test current rate calculation."""
        mock_time.return_value = 100.0
        
        throttle = RequestThrottle(max_requests_per_minute=60, window_seconds=60)
        
        # Add some requests in the last 60 seconds
        throttle.request_times.extend([50.0, 60.0, 70.0, 80.0, 90.0])  # 5 requests
        
        rate = throttle.get_current_rate()
        
        # Should be 5 requests in 60 seconds = 5 requests/minute
        self.assertEqual(rate, 5.0)
    
    @patch('time.time')
    def test_get_stats(self, mock_time):
        """Test statistics gathering."""
        mock_time.return_value = 100.0
        
        throttle = RequestThrottle(max_requests_per_minute=60, window_seconds=60)
        
        # Add some requests
        throttle.request_times.extend([50.0, 60.0, 70.0])  # 3 requests
        
        stats = throttle.get_stats()
        
        self.assertEqual(stats['requests_in_window'], 3)
        self.assertEqual(stats['max_requests'], 60)
        self.assertEqual(stats['window_seconds'], 60)
        self.assertEqual(stats['current_rate'], 3.0)
        self.assertEqual(stats['utilization_percent'], 5.0)  # 3/60 * 100
    
    def test_get_global_throttle(self):
        """Test global throttle singleton."""
        # Reset global throttle
        import src.lib.request_throttle
        src.lib.request_throttle._global_throttle = None
        
        # Get global throttle twice
        throttle1 = get_global_throttle()
        throttle2 = get_global_throttle()
        
        # Should be the same instance
        self.assertIs(throttle1, throttle2)
        self.assertIsInstance(throttle1, RequestThrottle)
    
    @patch('src.lib.request_throttle.get_global_throttle')
    def test_throttled_request_decorator(self, mock_get_throttle):
        """Test the throttled_request decorator."""
        mock_throttle = Mock()
        mock_get_throttle.return_value = mock_throttle
        
        @throttled_request
        def test_function():
            return "result"
        
        result = test_function()
        
        # Should have called acquire and returned the function result
        mock_throttle.acquire.assert_called_once()
        self.assertEqual(result, "result")
    
    def test_thread_safety_lock(self):
        """Test that throttle has thread safety mechanisms."""
        throttle = RequestThrottle()
        
        # Should have a lock for thread safety
        self.assertIsNotNone(throttle.lock)
        
        # Request times should be a deque for efficient operations
        from collections import deque
        self.assertIsInstance(throttle.request_times, deque)


if __name__ == '__main__':
    unittest.main()