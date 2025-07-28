"""
API Client Module

This module provides backwards-compatible imports for the API client system.
All classes have been refactored into separate files following the one-class-per-file
convention while maintaining the same import interface.
"""

# Import all classes from their new separate files
from .token_config import TokenConfig
from .api_client_wrapper import APIClientWrapper
from .cooldown_manager import CooldownManager

# Re-export all classes for backwards compatibility
__all__ = [
    "TokenConfig",
    "APIClientWrapper", 
    "CooldownManager"
]
