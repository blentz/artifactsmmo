"""Base test class for artifactsmmo tests."""

import unittest
from src.lib.httpstatus import extend_http_status


class BaseTest(unittest.TestCase):
    """Base test class that handles common setup for all tests."""
    
    @classmethod
    def setUpClass(cls):
        """Set up class-level fixtures."""
        super().setUpClass()
        # Extend HTTP status codes once for all tests
        # This is idempotent so it's safe to call multiple times
        extend_http_status()