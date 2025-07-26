"""
Tests for throttled HTTP transport functionality.

Comprehensive test suite covering throttling behavior, error handling,
and integration with httpx transport layer.
"""

import asyncio
import logging
import time
from unittest.mock import Mock, patch

import httpx
import pytest

from src.lib.request_throttle import RequestThrottle
from src.lib.throttled_transport import ThrottledAsyncTransport, ThrottledTransport


class TestThrottledTransport:
    """Test the synchronous throttled transport."""

    def test_init(self):
        """Test transport initialization."""
        transport = ThrottledTransport()

        assert transport.throttle is not None
        assert hasattr(transport, 'logger')
        assert isinstance(transport.logger, logging.Logger)

    def test_init_with_args(self):
        """Test transport initialization with httpx arguments."""
        # Test with various httpx.HTTPTransport arguments
        transport = ThrottledTransport(
            verify=False,
            trust_env=False,
            http2=True
        )

        assert transport.throttle is not None
        assert hasattr(transport, 'logger')

    @patch('src.lib.throttled_transport.get_global_throttle')
    def test_handle_request_basic(self, mock_get_throttle):
        """Test basic request handling with throttling."""
        # Setup
        mock_throttle = Mock()
        mock_get_throttle.return_value = mock_throttle

        transport = ThrottledTransport()

        # Create a mock request
        request = httpx.Request("GET", "https://api.example.com/test")

        # Mock the parent class method
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200

        with patch.object(httpx.HTTPTransport, 'handle_request', return_value=mock_response):
            response = transport.handle_request(request)

        # Verify throttling was applied
        mock_throttle.acquire.assert_called_once()

        # Verify response is returned
        assert response == mock_response

    @patch('src.lib.throttled_transport.get_global_throttle')
    def test_handle_request_throttling_sequence(self, mock_get_throttle):
        """Test that multiple requests properly use throttling."""
        # Setup
        mock_throttle = Mock()
        mock_get_throttle.return_value = mock_throttle

        transport = ThrottledTransport()

        # Create multiple requests
        requests = [
            httpx.Request("GET", "https://api.example.com/test1"),
            httpx.Request("POST", "https://api.example.com/test2"),
            httpx.Request("PUT", "https://api.example.com/test3"),
        ]

        # Mock responses
        mock_responses = [Mock(spec=httpx.Response) for _ in requests]
        for i, mock_response in enumerate(mock_responses):
            mock_response.status_code = 200 + i

        with patch.object(httpx.HTTPTransport, 'handle_request', side_effect=mock_responses):
            for i, request in enumerate(requests):
                response = transport.handle_request(request)
                assert response == mock_responses[i]

        # Verify throttling was called for each request
        assert mock_throttle.acquire.call_count == 3

    @patch('src.lib.throttled_transport.get_global_throttle')
    def test_handle_request_error_handling(self, mock_get_throttle):
        """Test error handling in request processing."""
        # Setup
        mock_throttle = Mock()
        mock_get_throttle.return_value = mock_throttle

        transport = ThrottledTransport()
        request = httpx.Request("GET", "https://api.example.com/test")

        # Test throttling error
        mock_throttle.acquire.side_effect = RuntimeError("Throttle error")

        with pytest.raises(RuntimeError, match="Throttle error"):
            transport.handle_request(request)

        # Reset and test transport error
        mock_throttle.acquire.side_effect = None

        with patch.object(httpx.HTTPTransport, 'handle_request', side_effect=httpx.RequestError("Transport error")):
            with pytest.raises(httpx.RequestError, match="Transport error"):
                transport.handle_request(request)

    @patch('src.lib.throttled_transport.get_global_throttle')
    def test_handle_request_logging(self, mock_get_throttle, caplog):
        """Test that requests are properly logged."""
        # Setup
        mock_throttle = Mock()
        mock_get_throttle.return_value = mock_throttle

        transport = ThrottledTransport()
        request = httpx.Request("GET", "https://api.example.com/test")

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200

        with caplog.at_level(logging.DEBUG):
            with patch.object(httpx.HTTPTransport, 'handle_request', return_value=mock_response):
                transport.handle_request(request)

        # Check debug logs were created
        log_messages = [record.message for record in caplog.records]
        assert any("Throttled request: GET" in msg for msg in log_messages)
        assert any("Response received: 200" in msg for msg in log_messages)

    def test_close_method(self):
        """Test transport close method."""
        transport = ThrottledTransport()

        with patch.object(httpx.HTTPTransport, 'close') as mock_close:
            transport.close()
            mock_close.assert_called_once()

    def test_close_method_error_handling(self):
        """Test error handling in close method."""
        transport = ThrottledTransport()

        with patch.object(httpx.HTTPTransport, 'close', side_effect=RuntimeError("Close error")):
            with pytest.raises(RuntimeError, match="Close error"):
                transport.close()


class TestThrottledAsyncTransport:
    """Test the asynchronous throttled transport."""

    def test_init(self):
        """Test async transport initialization."""
        transport = ThrottledAsyncTransport()

        assert transport.throttle is not None
        assert hasattr(transport, 'logger')
        assert isinstance(transport.logger, logging.Logger)

    def test_init_with_args(self):
        """Test async transport initialization with httpx arguments."""
        transport = ThrottledAsyncTransport(
            verify=False,
            trust_env=False,
            http2=True
        )

        assert transport.throttle is not None
        assert hasattr(transport, 'logger')

    @pytest.mark.asyncio
    @patch('src.lib.throttled_transport.get_global_throttle')
    async def test_handle_async_request_basic(self, mock_get_throttle):
        """Test basic async request handling with throttling."""
        # Setup
        mock_throttle = Mock()
        mock_get_throttle.return_value = mock_throttle

        transport = ThrottledAsyncTransport()
        request = httpx.Request("GET", "https://api.example.com/test")

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200

        with patch.object(httpx.AsyncHTTPTransport, 'handle_async_request', return_value=mock_response):
            response = await transport.handle_async_request(request)

        # Verify throttling was applied (via executor)
        mock_throttle.acquire.assert_called_once()

        # Verify response is returned
        assert response == mock_response

    @pytest.mark.asyncio
    @patch('src.lib.throttled_transport.get_global_throttle')
    async def test_handle_async_request_throttling_sequence(self, mock_get_throttle):
        """Test that multiple async requests properly use throttling."""
        # Setup
        mock_throttle = Mock()
        mock_get_throttle.return_value = mock_throttle

        transport = ThrottledAsyncTransport()

        # Create multiple requests
        requests = [
            httpx.Request("GET", "https://api.example.com/test1"),
            httpx.Request("POST", "https://api.example.com/test2"),
            httpx.Request("PUT", "https://api.example.com/test3"),
        ]

        # Mock responses
        mock_responses = [Mock(spec=httpx.Response) for _ in requests]
        for i, mock_response in enumerate(mock_responses):
            mock_response.status_code = 200 + i

        with patch.object(httpx.AsyncHTTPTransport, 'handle_async_request', side_effect=mock_responses):
            for i, request in enumerate(requests):
                response = await transport.handle_async_request(request)
                assert response == mock_responses[i]

        # Verify throttling was called for each request
        assert mock_throttle.acquire.call_count == 3

    @pytest.mark.asyncio
    @patch('src.lib.throttled_transport.get_global_throttle')
    async def test_handle_async_request_error_handling(self, mock_get_throttle):
        """Test error handling in async request processing."""
        # Setup
        mock_throttle = Mock()
        mock_get_throttle.return_value = mock_throttle

        transport = ThrottledAsyncTransport()
        request = httpx.Request("GET", "https://api.example.com/test")

        # Test throttling error
        mock_throttle.acquire.side_effect = RuntimeError("Throttle error")

        with pytest.raises(RuntimeError, match="Throttle error"):
            await transport.handle_async_request(request)

        # Reset and test transport error
        mock_throttle.acquire.side_effect = None

        with patch.object(httpx.AsyncHTTPTransport, 'handle_async_request', side_effect=httpx.RequestError("Transport error")):
            with pytest.raises(httpx.RequestError, match="Transport error"):
                await transport.handle_async_request(request)

    @pytest.mark.asyncio
    @patch('src.lib.throttled_transport.get_global_throttle')
    async def test_handle_async_request_logging(self, mock_get_throttle, caplog):
        """Test that async requests are properly logged."""
        # Setup
        mock_throttle = Mock()
        mock_get_throttle.return_value = mock_throttle

        transport = ThrottledAsyncTransport()
        request = httpx.Request("GET", "https://api.example.com/test")

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200

        with caplog.at_level(logging.DEBUG):
            with patch.object(httpx.AsyncHTTPTransport, 'handle_async_request', return_value=mock_response):
                await transport.handle_async_request(request)

        # Check debug logs were created
        log_messages = [record.message for record in caplog.records]
        assert any("Async throttled request: GET" in msg for msg in log_messages)
        assert any("Async response received: 200" in msg for msg in log_messages)

    @pytest.mark.asyncio
    async def test_aclose_method(self):
        """Test async transport close method."""
        transport = ThrottledAsyncTransport()

        with patch.object(httpx.AsyncHTTPTransport, 'aclose') as mock_aclose:
            await transport.aclose()
            mock_aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_aclose_method_error_handling(self):
        """Test error handling in async close method."""
        transport = ThrottledAsyncTransport()

        with patch.object(httpx.AsyncHTTPTransport, 'aclose', side_effect=RuntimeError("Close error")):
            with pytest.raises(RuntimeError, match="Close error"):
                await transport.aclose()


class TestThrottledTransportIntegration:
    """Integration tests with real throttling behavior."""

    def test_real_throttling_sync(self):
        """Test real throttling behavior with timing."""
        # Create a throttle with very low rate for testing
        test_throttle = RequestThrottle(max_requests_per_minute=60, window_seconds=60)  # 1 per second

        with patch('src.lib.throttled_transport.get_global_throttle', return_value=test_throttle):
            transport = ThrottledTransport()

            # Create test requests
            requests = [
                httpx.Request("GET", "https://api.example.com/test1"),
                httpx.Request("GET", "https://api.example.com/test2"),
            ]

            mock_response = Mock(spec=httpx.Response)
            mock_response.status_code = 200

            start_time = time.time()

            with patch.object(httpx.HTTPTransport, 'handle_request', return_value=mock_response):
                for request in requests:
                    transport.handle_request(request)

            elapsed_time = time.time() - start_time

            # Should take at least 1 second due to throttling (allowing some tolerance for test timing)
            assert elapsed_time >= 0.9, f"Expected at least 0.9s delay, got {elapsed_time}s"

    @pytest.mark.asyncio
    async def test_real_throttling_async(self):
        """Test real throttling behavior with timing in async context."""
        # Create a throttle with very low rate for testing
        test_throttle = RequestThrottle(max_requests_per_minute=60, window_seconds=60)  # 1 per second

        with patch('src.lib.throttled_transport.get_global_throttle', return_value=test_throttle):
            transport = ThrottledAsyncTransport()

            # Create test requests
            requests = [
                httpx.Request("GET", "https://api.example.com/test1"),
                httpx.Request("GET", "https://api.example.com/test2"),
            ]

            mock_response = Mock(spec=httpx.Response)
            mock_response.status_code = 200

            start_time = time.time()

            with patch.object(httpx.AsyncHTTPTransport, 'handle_async_request', return_value=mock_response):
                for request in requests:
                    await transport.handle_async_request(request)

            elapsed_time = time.time() - start_time

            # Should take at least 1 second due to throttling (allowing some tolerance for test timing)
            assert elapsed_time >= 0.9, f"Expected at least 0.9s delay, got {elapsed_time}s"

    def test_transport_method_call_verification_sync(self):
        """Test that transport methods are called correctly in httpx client context."""
        # This test validates the transport methods are called without full httpx integration
        transport = ThrottledTransport()

        # Create a test request
        request = httpx.Request("GET", "https://api.example.com/test")

        # Mock the parent method to avoid network calls
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200

        with patch.object(httpx.HTTPTransport, 'handle_request', return_value=mock_response) as mock_parent:
            response = transport.handle_request(request)

            # Verify parent transport was called
            mock_parent.assert_called_once_with(request)
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_transport_method_call_verification_async(self):
        """Test that async transport methods are called correctly in httpx client context."""
        # This test validates the async transport methods are called without full httpx integration
        transport = ThrottledAsyncTransport()

        # Create a test request
        request = httpx.Request("GET", "https://api.example.com/test")

        # Mock the parent method to avoid network calls
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200

        with patch.object(httpx.AsyncHTTPTransport, 'handle_async_request', return_value=mock_response) as mock_parent:
            response = await transport.handle_async_request(request)

            # Verify parent transport was called
            mock_parent.assert_called_once_with(request)
            assert response.status_code == 200


class TestThrottledTransportThreadSafety:
    """Test thread safety of throttled transport."""

    @pytest.mark.asyncio
    async def test_concurrent_async_requests(self):
        """Test that concurrent async requests are properly throttled."""
        # Create throttle with higher rate for testing
        test_throttle = RequestThrottle(max_requests_per_minute=120, window_seconds=60)

        with patch('src.lib.throttled_transport.get_global_throttle', return_value=test_throttle):
            transport = ThrottledAsyncTransport()

            mock_response = Mock(spec=httpx.Response)
            mock_response.status_code = 200

            # Patch the parent class method to avoid actual network calls
            with patch.object(httpx.AsyncHTTPTransport, 'handle_async_request', return_value=mock_response):
                # Create multiple concurrent requests
                async def make_request(url: str) -> httpx.Response:
                    request = httpx.Request("GET", url)
                    return await transport.handle_async_request(request)

                # Launch multiple concurrent requests
                urls = [f"https://api.example.com/test{i}" for i in range(5)]
                tasks = [make_request(url) for url in urls]

                start_time = time.time()
                responses = await asyncio.gather(*tasks)
                elapsed_time = time.time() - start_time

                # All requests should complete
                assert len(responses) == 5
                assert all(r.status_code == 200 for r in responses)

                # Should take some time due to throttling
                assert elapsed_time > 0.1  # At least some delay expected
