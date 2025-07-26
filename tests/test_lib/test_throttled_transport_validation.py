"""
Validation tests for throttled transport with real API patterns.

These tests validate the transport works correctly with real-world
API client patterns from the ArtifactsMMO project.
"""

from unittest.mock import Mock, patch

import httpx
import pytest

from src.lib.throttled_transport import ThrottledAsyncTransport, ThrottledTransport


class TestThrottledTransportValidation:
    """Validation tests with real API client patterns."""

    def test_sync_transport_with_auth_header(self):
        """Test sync transport with ArtifactsMMO authentication pattern."""
        transport = ThrottledTransport()

        # Create request with ArtifactsMMO authentication pattern
        headers = {
            "Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.example_token",
            "Content-Type": "application/json"
        }
        request = httpx.Request(
            "GET",
            "https://api.artifactsmmo.com/my/characters",
            headers=headers
        )

        # Mock successful API response
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "name": "test_character",
                    "level": 1,
                    "x": 0,
                    "y": 0,
                    "cooldown": 0,
                    "hp": 100,
                    "max_hp": 100
                }
            ]
        }

        with patch.object(httpx.HTTPTransport, 'handle_request', return_value=mock_response):
            response = transport.handle_request(request)

            assert response.status_code == 200
            assert "test_character" in str(response.json())

    def test_sync_transport_with_api_error_handling(self):
        """Test sync transport handles ArtifactsMMO API errors correctly."""
        transport = ThrottledTransport()

        # Create request that might trigger API error
        request = httpx.Request(
            "POST",
            "https://api.artifactsmmo.com/action/fight",
            json={"character": "test_char"}
        )

        # Mock API error response (character on cooldown)
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 499  # Custom ArtifactsMMO cooldown error
        mock_response.json.return_value = {
            "error": {
                "code": 499,
                "message": "Character is in cooldown."
            }
        }

        with patch.object(httpx.HTTPTransport, 'handle_request', return_value=mock_response):
            response = transport.handle_request(request)

            # Transport should pass through the API error response unchanged
            assert response.status_code == 499
            assert "cooldown" in str(response.json()).lower()

    @pytest.mark.asyncio
    async def test_async_transport_with_auth_header(self):
        """Test async transport with ArtifactsMMO authentication pattern."""
        transport = ThrottledAsyncTransport()

        # Create request with ArtifactsMMO authentication pattern
        headers = {
            "Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.example_token",
            "Content-Type": "application/json"
        }
        request = httpx.Request(
            "GET",
            "https://api.artifactsmmo.com/my/characters",
            headers=headers
        )

        # Mock successful API response
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "name": "test_character",
                    "level": 1,
                    "x": 0,
                    "y": 0,
                    "cooldown": 0,
                    "hp": 100,
                    "max_hp": 100
                }
            ]
        }

        with patch.object(httpx.AsyncHTTPTransport, 'handle_async_request', return_value=mock_response):
            response = await transport.handle_async_request(request)

            assert response.status_code == 200
            assert "test_character" in str(response.json())

    @pytest.mark.asyncio
    async def test_async_transport_with_api_error_handling(self):
        """Test async transport handles ArtifactsMMO API errors correctly."""
        transport = ThrottledAsyncTransport()

        # Create request that might trigger API error
        request = httpx.Request(
            "POST",
            "https://api.artifactsmmo.com/action/fight",
            json={"character": "test_char"}
        )

        # Mock API error response (character on cooldown)
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 499  # Custom ArtifactsMMO cooldown error
        mock_response.json.return_value = {
            "error": {
                "code": 499,
                "message": "Character is in cooldown."
            }
        }

        with patch.object(httpx.AsyncHTTPTransport, 'handle_async_request', return_value=mock_response):
            response = await transport.handle_async_request(request)

            # Transport should pass through the API error response unchanged
            assert response.status_code == 499
            assert "cooldown" in str(response.json()).lower()

    @pytest.mark.asyncio
    async def test_throttling_preserves_request_order(self):
        """Test that throttling preserves request order in async context."""
        transport = ThrottledAsyncTransport()

        # Create a sequence of requests
        requests = [
            httpx.Request("GET", f"https://api.artifactsmmo.com/test/{i}")
            for i in range(3)
        ]

        # Mock responses with identifiable data
        def create_mock_response(index: int) -> Mock:
            mock_response = Mock(spec=httpx.Response)
            mock_response.status_code = 200
            mock_response.json.return_value = {"request_index": index}
            return mock_response

        mock_responses = [create_mock_response(i) for i in range(3)]

        with patch.object(httpx.AsyncHTTPTransport, 'handle_async_request', side_effect=mock_responses):
            # Process requests sequentially (not concurrently)
            responses = []
            for request in requests:
                response = await transport.handle_async_request(request)
                responses.append(response)

            # Verify responses maintain order
            for i, response in enumerate(responses):
                assert response.json()["request_index"] == i

    def test_transport_preserves_all_request_data(self):
        """Test that transport preserves all request data including headers and body."""
        transport = ThrottledTransport()

        # Create complex request with headers, body, and parameters
        headers = {
            "Authorization": "Bearer test_token",
            "Content-Type": "application/json",
            "User-Agent": "ArtifactsMMO-AI-Player/1.0"
        }
        json_data = {
            "character": "test_char",
            "action": "move",
            "x": 10,
            "y": 5
        }

        request = httpx.Request(
            "POST",
            "https://api.artifactsmmo.com/action/move",
            headers=headers,
            json=json_data
        )

        # Capture the request that gets forwarded
        captured_request = None

        def capture_request(req):
            nonlocal captured_request
            captured_request = req
            mock_response = Mock(spec=httpx.Response)
            mock_response.status_code = 200
            return mock_response

        with patch.object(httpx.HTTPTransport, 'handle_request', side_effect=capture_request):
            transport.handle_request(request)

            # Verify all request data is preserved
            assert captured_request is not None
            assert captured_request.method == "POST"
            assert str(captured_request.url) == "https://api.artifactsmmo.com/action/move"
            assert captured_request.headers["Authorization"] == "Bearer test_token"
            assert captured_request.headers["Content-Type"] == "application/json"
            assert captured_request.headers["User-Agent"] == "ArtifactsMMO-AI-Player/1.0"

    def test_sync_transport_exception_handling(self):
        """Test sync transport handles exceptions in underlying transport."""
        transport = ThrottledTransport()

        request = httpx.Request("GET", "https://api.artifactsmmo.com/test")

        # Mock the underlying transport to raise an exception
        with patch.object(httpx.HTTPTransport, 'handle_request', side_effect=httpx.RequestError("Network error")):
            with pytest.raises(httpx.RequestError):
                transport.handle_request(request)

    def test_sync_transport_close(self):
        """Test sync transport close method."""
        transport = ThrottledTransport()

        # Test normal close
        with patch.object(httpx.HTTPTransport, 'close') as mock_close:
            transport.close()
            mock_close.assert_called_once()

    def test_sync_transport_close_exception(self):
        """Test sync transport close method with exception."""
        transport = ThrottledTransport()

        # Test close with exception
        with patch.object(httpx.HTTPTransport, 'close', side_effect=Exception("Close error")):
            with pytest.raises(Exception):
                transport.close()

    @pytest.mark.asyncio
    async def test_async_transport_exception_handling(self):
        """Test async transport handles exceptions in underlying transport."""
        transport = ThrottledAsyncTransport()

        request = httpx.Request("GET", "https://api.artifactsmmo.com/test")

        # Mock the underlying transport to raise an exception
        with patch.object(httpx.AsyncHTTPTransport, 'handle_async_request', side_effect=httpx.RequestError("Network error")):
            with pytest.raises(httpx.RequestError):
                await transport.handle_async_request(request)

    @pytest.mark.asyncio
    async def test_async_transport_aclose(self):
        """Test async transport aclose method."""
        transport = ThrottledAsyncTransport()

        # Test normal aclose
        with patch.object(httpx.AsyncHTTPTransport, 'aclose') as mock_aclose:
            await transport.aclose()
            mock_aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_transport_aclose_exception(self):
        """Test async transport aclose method with exception."""
        transport = ThrottledAsyncTransport()

        # Test aclose with exception
        with patch.object(httpx.AsyncHTTPTransport, 'aclose', side_effect=Exception("Close error")):
            with pytest.raises(Exception):
                await transport.aclose()
