"""
Test suite for the ArtifactsMMO AI Player Library

This test package provides comprehensive testing for all lib components:
- GOAP (Goal-Oriented Action Planning) implementation
- YAML data persistence and configuration management  
- Async logging infrastructure
- HTTP transport with throttling and rate limiting
- Custom HTTP status codes for ArtifactsMMO API

Test Modules:
- test_goap: Tests for GOAP planning algorithms and data structures
- test_goap_data: Tests for GOAP data persistence layer
- test_yaml_data: Tests for YAML configuration and data management
- test_log: Tests for async logging infrastructure
- test_httpstatus: Tests for custom HTTP status code extensions
- test_request_throttle: Tests for request rate limiting and throttling
- test_throttled_transport: Tests for HTTP transport with throttling
- test_throttled_transport_validation: Additional validation tests for throttled transport
- test_init: Tests for lib package initialization and exports

Usage:
    Import this module to access test utilities and run the complete test suite.
    Individual test modules can be run independently or as part of the full suite.

Example:
    # Run all lib tests
    pytest tests/test_lib/

    # Run specific test module  
    pytest tests/test_lib/test_goap.py

    # Import test utilities
    # These utilities are defined in this module
"""

import importlib
import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pytest


def get_test_modules() -> list[str]:
    """
    Get list of all test modules in this package.
    
    Returns:
        List[str]: Names of all test modules (without .py extension)
    """
    test_dir = Path(__file__).parent
    test_files = list(test_dir.glob("test_*.py"))
    return [f.stem for f in test_files]


def run_all_tests(verbose: bool = True, coverage: bool = True) -> int:
    """
    Run all tests in the test_lib package.
    
    Args:
        verbose: Whether to run tests in verbose mode
        coverage: Whether to include coverage reporting
        
    Returns:
        int: Exit code (0 for success, non-zero for failure)
    """
    test_dir = Path(__file__).parent

    args = [str(test_dir)]

    if verbose:
        args.append("-v")

    if coverage:
        args.extend(["--cov=src.lib", "--cov-report=term-missing"])

    return pytest.main(args)


def validate_imports() -> tuple[bool, list[str]]:
    """
    Validate that all test modules can be imported successfully.
    
    Returns:
        Tuple[bool, List[str]]: (success, list of errors)
    """
    errors = []
    test_modules = get_test_modules()

    for module_name in test_modules:
        importlib.import_module(f"tests.test_lib.{module_name}")

    return len(errors) == 0, errors


def check_lib_coverage() -> dict[str, bool]:
    """
    Check if all lib modules have corresponding test modules.
    
    Returns:
        Dict[str, bool]: Mapping of lib module names to whether they have tests
    """
    lib_dir = Path(__file__).parent.parent.parent / "src" / "lib"
    lib_modules = [f.stem for f in lib_dir.glob("*.py") if f.stem != "__init__"]

    test_modules = get_test_modules()
    test_targets = [m.replace("test_", "") for m in test_modules]

    coverage = {}
    for module in lib_modules:
        coverage[module] = module in test_targets

    return coverage


# Test utilities and fixtures that can be shared across test modules
class TestFixtures:
    """Common test fixtures and utilities for lib tests."""

    @staticmethod
    def get_temp_yaml_path() -> str:
        """Get a temporary path for YAML test files."""
        return tempfile.mktemp(suffix=".yaml")

    @staticmethod
    def cleanup_temp_files(*paths: str) -> None:
        """Clean up temporary test files."""
        for path in paths:
            try:
                if os.path.exists(path):
                    os.unlink(path)
            except OSError:
                pass


# Re-export commonly used test utilities
__all__ = [
    "get_test_modules",
    "run_all_tests",
    "validate_imports",
    "check_lib_coverage",
    "TestFixtures",
]
