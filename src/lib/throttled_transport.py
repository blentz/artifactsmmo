"""
Throttled HTTP Transport for httpx

Implements request throttling at the transport layer to ensure API rate limit compliance.
"""

import asyncio
import logging
from typing import Any

import httpx

from .request_throttle import get_global_throttle


class ThrottledTransport(httpx.HTTPTransport):
    """
    HTTP transport that applies throttling to all requests.

    This transport wraps the default httpx transport and applies request throttling
    before forwarding requests to ensure API rate limit compliance.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.throttle = get_global_throttle()
        self.logger = logging.getLogger(__name__)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        """Handle a request with throttling applied."""
        try:
            # Apply throttling before making the request
            self.throttle.acquire()

            # Log the throttled request
            self.logger.debug(f"🚀 Throttled request: {request.method} {request.url}")

            # Forward the request to the underlying transport
            response = super().handle_request(request)

            # Log the response
            self.logger.debug(f"✅ Response received: {response.status_code} for {request.method} {request.url}")

            return response

        except httpx.RequestError as e:
            self.logger.error(f"❌ Error in throttled request {request.method} {request.url}: {e}")
            raise

    def close(self) -> None:
        """Close the transport and clean up resources."""
        try:
            self.logger.debug("🔒 Closing ThrottledTransport")
            super().close()
        except OSError as e:
            self.logger.error(f"❌ Error closing ThrottledTransport: {e}")
            raise


class ThrottledAsyncTransport(httpx.AsyncHTTPTransport):
    """
    Async HTTP transport that applies throttling to all requests.

    This transport wraps the default httpx async transport and applies request throttling
    before forwarding requests to ensure API rate limit compliance.

    Note: The throttle.acquire() method is synchronous and will block the thread,
    but this is acceptable for rate limiting as it ensures proper sequencing.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.throttle = get_global_throttle()
        self.logger = logging.getLogger(__name__)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Handle an async request with throttling applied."""
        try:
            # Apply throttling before making the request
            # Note: throttle.acquire() is synchronous and will block the thread
            # This is intentional for rate limiting to ensure proper request sequencing
            await asyncio.get_running_loop().run_in_executor(None, self.throttle.acquire)

            # Log the throttled request
            self.logger.debug(f"🚀 Async throttled request: {request.method} {request.url}")

            # Forward the request to the underlying transport
            response = await super().handle_async_request(request)

            # Log the response
            self.logger.debug(f"✅ Async response received: {response.status_code} for {request.method} {request.url}")

            return response

        except (httpx.RequestError, asyncio.CancelledError) as e:
            self.logger.error(f"❌ Error in async throttled request {request.method} {request.url}: {e}")
            raise

    async def aclose(self) -> None:
        """Close the async transport and clean up resources."""
        try:
            self.logger.debug("🔒 Closing ThrottledAsyncTransport")
            await super().aclose()
        except (OSError, asyncio.CancelledError) as e:
            self.logger.error(f"❌ Error closing ThrottledAsyncTransport: {e}")
            raise
