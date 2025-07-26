"""
Tests for game_data module __init__.py

Tests module imports, exports, and interface to ensure proper functionality
and 100% code coverage for the game_data module initialization.
"""

from src.game_data import (
    APIClientWrapper,
    CacheManager,
    CacheMetadata,
    CooldownManager,
    TokenConfig,
    __all__,
    __version__,
)


class TestGameDataModule:
    """Test game_data module interface and exports"""

    def test_module_version_exists(self) -> None:
        """Test that module has version string"""
        assert isinstance(__version__, str)
        assert len(__version__) > 0
        assert "." in __version__

    def test_module_version_format(self) -> None:
        """Test that version follows semantic versioning format"""
        version_parts = __version__.split(".")
        assert len(version_parts) >= 2
        for part in version_parts[:2]:
            assert part.isdigit()

    def test_all_list_exists(self) -> None:
        """Test that __all__ list is defined"""
        assert isinstance(__all__, list)
        assert len(__all__) > 0

    def test_all_list_contents(self) -> None:
        """Test that __all__ contains expected exports"""
        expected_exports = [
            "TokenConfig",
            "APIClientWrapper",
            "CooldownManager",
            "CacheMetadata",
            "CacheManager",
        ]

        for export in expected_exports:
            assert export in __all__

    def test_all_list_no_duplicates(self) -> None:
        """Test that __all__ has no duplicate entries"""
        assert len(__all__) == len(set(__all__))

    def test_token_config_importable(self) -> None:
        """Test TokenConfig class can be imported"""
        assert TokenConfig is not None
        assert hasattr(TokenConfig, "__name__")
        assert TokenConfig.__name__ == "TokenConfig"

    def test_api_client_wrapper_importable(self) -> None:
        """Test APIClientWrapper class can be imported"""
        assert APIClientWrapper is not None
        assert hasattr(APIClientWrapper, "__name__")
        assert APIClientWrapper.__name__ == "APIClientWrapper"

    def test_cooldown_manager_importable(self) -> None:
        """Test CooldownManager class can be imported"""
        assert CooldownManager is not None
        assert hasattr(CooldownManager, "__name__")
        assert CooldownManager.__name__ == "CooldownManager"

    def test_cache_metadata_importable(self) -> None:
        """Test CacheMetadata class can be imported"""
        assert CacheMetadata is not None
        assert hasattr(CacheMetadata, "__name__")
        assert CacheMetadata.__name__ == "CacheMetadata"

    def test_cache_manager_importable(self) -> None:
        """Test CacheManager class can be imported"""
        assert CacheManager is not None
        assert hasattr(CacheManager, "__name__")
        assert CacheManager.__name__ == "CacheManager"

    def test_imports_are_classes(self) -> None:
        """Test that all imports are actually classes"""
        imports_to_test = [
            TokenConfig,
            APIClientWrapper,
            CooldownManager,
            CacheMetadata,
            CacheManager,
        ]

        for imported_class in imports_to_test:
            assert hasattr(imported_class, "__bases__")

    def test_module_docstring_exists(self) -> None:
        """Test that module has proper documentation"""
        import src.game_data
        assert src.game_data.__doc__ is not None
        assert len(src.game_data.__doc__.strip()) > 0
        assert "Game Data Module" in src.game_data.__doc__

    def test_star_import_works(self) -> None:
        """Test that 'from game_data import *' only imports __all__ items"""
        import importlib
        module = importlib.import_module("src.game_data")

        # Get all public attributes from module
        public_attrs = [name for name in dir(module) if not name.startswith("_")]

        # Filter to only those that should be exported
        expected_in_all = []
        for attr_name in public_attrs:
            attr = getattr(module, attr_name)
            # Only classes should be in __all__
            if hasattr(attr, "__bases__"):
                expected_in_all.append(attr_name)

        # All classes should be in __all__
        for attr_name in expected_in_all:
            assert attr_name in __all__

    def test_import_statement_completeness(self) -> None:
        """Test that all __all__ items can actually be imported"""
        import src.game_data as game_data_module

        for item_name in __all__:
            assert hasattr(game_data_module, item_name)
            item = getattr(game_data_module, item_name)
            assert item is not None
