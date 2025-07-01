"""Unit tests for ThrottledTransport classes."""

import unittest
from unittest.mock import Mock, patch

import httpx
from src.lib.throttled_transport import ThrottledAsyncTransport, ThrottledTransport


class TestThrottledTransport(unittest.TestCase):
    """Test cases for ThrottledTransport class."""
    
    @patch('src.lib.throttled_transport.get_global_throttle')
    def test_initialization(self, mock_get_throttle):
        """Test ThrottledTransport initialization."""
        mock_throttle = Mock()
        mock_get_throttle.return_value = mock_throttle
        
        transport = ThrottledTransport()
        
        # Should have throttle instance from global throttle
        self.assertEqual(transport.throttle, mock_throttle)
        mock_get_throttle.assert_called_once()
        
        # Should be an instance of httpx.HTTPTransport
        self.assertIsInstance(transport, httpx.HTTPTransport)
    
    @patch('src.lib.throttled_transport.get_global_throttle')
    def test_initialization_with_httpx_params(self, mock_get_throttle):
        """Test ThrottledTransport initialization with httpx parameters."""
        mock_throttle = Mock()
        mock_get_throttle.return_value = mock_throttle
        
        # Test with valid httpx parameters
        transport = ThrottledTransport(verify=False)
        
        # Should still get throttle
        self.assertEqual(transport.throttle, mock_throttle)
        mock_get_throttle.assert_called_once()
    
    @patch('src.lib.throttled_transport.get_global_throttle')
    @patch('httpx.HTTPTransport.handle_request')
    def test_handle_request_calls_throttle(self, mock_super_handle, mock_get_throttle):
        """Test that handle_request calls throttle before making request."""
        mock_throttle = Mock()
        mock_get_throttle.return_value = mock_throttle
        mock_response = Mock()
        mock_super_handle.return_value = mock_response
        
        transport = ThrottledTransport()
        mock_request = Mock()
        
        # Call handle_request
        result = transport.handle_request(mock_request)
        
        # Verify throttle acquire was called
        mock_throttle.acquire.assert_called_once()
        
        # Verify parent handle_request was called
        mock_super_handle.assert_called_once_with(mock_request)
        
        # Verify result is returned
        self.assertEqual(result, mock_response)
    
    @patch('src.lib.throttled_transport.get_global_throttle')
    def test_throttle_attribute_exists(self, mock_get_throttle):
        """Test that throttle attribute is properly set."""
        mock_throttle = Mock()
        mock_get_throttle.return_value = mock_throttle
        
        transport = ThrottledTransport()
        
        # Should have throttle attribute
        self.assertTrue(hasattr(transport, 'throttle'))
        self.assertEqual(transport.throttle, mock_throttle)
    
    def test_inheritance(self):
        """Test that ThrottledTransport properly inherits from HTTPTransport."""
        transport = ThrottledTransport()
        
        # Should be instance of both
        self.assertIsInstance(transport, ThrottledTransport)
        self.assertIsInstance(transport, httpx.HTTPTransport)
    
    def test_repr_basic(self):
        """Test basic string representation."""
        transport = ThrottledTransport()
        repr_str = repr(transport)
        
        # Should contain class name (inherited from httpx.HTTPTransport)
        self.assertIn("ThrottledTransport", repr_str)


class TestThrottledAsyncTransport(unittest.TestCase):
    """Test cases for ThrottledAsyncTransport class."""
    
    @patch('src.lib.throttled_transport.get_global_throttle')
    def test_initialization(self, mock_get_throttle):
        """Test ThrottledAsyncTransport initialization."""
        mock_throttle = Mock()
        mock_get_throttle.return_value = mock_throttle
        
        transport = ThrottledAsyncTransport()
        
        # Should have throttle instance from global throttle
        self.assertEqual(transport.throttle, mock_throttle)
        mock_get_throttle.assert_called_once()
        
        # Should be an instance of httpx.AsyncHTTPTransport
        self.assertIsInstance(transport, httpx.AsyncHTTPTransport)
    
    @patch('src.lib.throttled_transport.get_global_throttle')
    def test_initialization_with_httpx_params(self, mock_get_throttle):
        """Test ThrottledAsyncTransport initialization with httpx parameters."""
        mock_throttle = Mock()
        mock_get_throttle.return_value = mock_throttle
        
        # Test with valid httpx parameters
        transport = ThrottledAsyncTransport(verify=False)
        
        # Should still get throttle
        self.assertEqual(transport.throttle, mock_throttle)
        mock_get_throttle.assert_called_once()
    
    @patch('src.lib.throttled_transport.get_global_throttle')
    @patch('httpx.AsyncHTTPTransport.handle_async_request')
    async def test_handle_async_request_calls_throttle(self, mock_super_handle, mock_get_throttle):
        """Test that handle_async_request calls throttle before making request."""
        mock_throttle = Mock()
        mock_get_throttle.return_value = mock_throttle
        mock_response = Mock()
        
        # Make the parent handle_async_request return a coroutine
        async def mock_handle_coroutine(request):
            return mock_response
        mock_super_handle.return_value = mock_handle_coroutine(Mock())
        
        transport = ThrottledAsyncTransport()
        mock_request = Mock()
        
        # Call handle_async_request
        result = await transport.handle_async_request(mock_request)
        
        # Verify throttle acquire was called
        mock_throttle.acquire.assert_called_once()
        
        # Verify parent handle_async_request was called
        mock_super_handle.assert_called_once_with(mock_request)
        
        # Verify result is returned
        self.assertEqual(result, mock_response)
    
    @patch('src.lib.throttled_transport.get_global_throttle')
    def test_throttle_attribute_exists(self, mock_get_throttle):
        """Test that throttle attribute is properly set."""
        mock_throttle = Mock()
        mock_get_throttle.return_value = mock_throttle
        
        transport = ThrottledAsyncTransport()
        
        # Should have throttle attribute
        self.assertTrue(hasattr(transport, 'throttle'))
        self.assertEqual(transport.throttle, mock_throttle)
    
    def test_inheritance(self):
        """Test that ThrottledAsyncTransport properly inherits from AsyncHTTPTransport."""
        transport = ThrottledAsyncTransport()
        
        # Should be instance of both
        self.assertIsInstance(transport, ThrottledAsyncTransport)
        self.assertIsInstance(transport, httpx.AsyncHTTPTransport)
    
    def test_repr_basic(self):
        """Test basic string representation."""
        transport = ThrottledAsyncTransport()
        repr_str = repr(transport)
        
        # Should contain class name (inherited from httpx.AsyncHTTPTransport)
        self.assertIn("ThrottledAsyncTransport", repr_str)


if __name__ == '__main__':
    unittest.main()