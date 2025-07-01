"""
Throttled HTTP Transport for httpx

Implements request throttling at the transport layer to ensure API rate limit compliance.
"""


import httpx

from .request_throttle import get_global_throttle


class ThrottledTransport(httpx.HTTPTransport):
    """
    HTTP transport that applies throttling to all requests.
    
    This transport wraps the default httpx transport and applies request throttling
    before forwarding requests to ensure API rate limit compliance.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.throttle = get_global_throttle()
    
    def handle_request(self, request: httpx.Request) -> httpx.Response:
        """Handle a request with throttling applied."""
        # Apply throttling before making the request
        self.throttle.acquire()
        
        # Forward the request to the underlying transport
        return super().handle_request(request)


class ThrottledAsyncTransport(httpx.AsyncHTTPTransport):
    """
    Async HTTP transport that applies throttling to all requests.
    
    This transport wraps the default httpx async transport and applies request throttling
    before forwarding requests to ensure API rate limit compliance.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.throttle = get_global_throttle()
    
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Handle an async request with throttling applied."""
        # Apply throttling before making the request
        self.throttle.acquire()
        
        # Forward the request to the underlying transport
        return await super().handle_async_request(request)