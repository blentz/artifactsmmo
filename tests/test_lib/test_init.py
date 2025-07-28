"""
Test module for src/lib/__init__.py

Validates that all expected exports are available and can be imported correctly.
"""

import os
import tempfile



def test_goap_imports():
    """Test that GOAP core classes can be imported from lib package."""
    from src.lib import Action_List, Planner, World

    # Verify classes are available
    assert World is not None
    assert Planner is not None
    assert Action_List is not None

    # Verify they are actually classes
    assert isinstance(World, type)
    assert isinstance(Planner, type)
    assert isinstance(Action_List, type)


def test_goap_function_imports():
    """Test that GOAP utility functions can be imported from lib package."""
    from src.lib import astar, conditions_are_met, distance_to_state, walk_path

    # Verify functions are available
    assert distance_to_state is not None
    assert conditions_are_met is not None
    assert astar is not None
    assert walk_path is not None

    # Verify they are callable
    assert callable(distance_to_state)
    assert callable(conditions_are_met)
    assert callable(astar)
    assert callable(walk_path)


def test_data_persistence_imports():
    """Test that data persistence classes can be imported from lib package."""
    from src.lib import GoapData, YamlData

    # Verify classes are available
    assert YamlData is not None
    assert GoapData is not None

    # Verify they are actually classes
    assert isinstance(YamlData, type)
    assert isinstance(GoapData, type)


def test_logging_imports():
    """Test that logging functions can be imported from lib package."""
    from src.lib import init_logger, safely_start_logger

    # Verify functions are available
    assert init_logger is not None
    assert safely_start_logger is not None

    # Verify they are callable
    assert callable(init_logger)
    assert callable(safely_start_logger)


def test_http_status_imports():
    """Test that HTTP status utilities can be imported from lib package."""
    from src.lib import ArtifactsHTTPStatus, extend_http_status

    # Verify they are available
    assert ArtifactsHTTPStatus is not None
    assert extend_http_status is not None

    # Verify types
    assert isinstance(ArtifactsHTTPStatus, dict)
    assert callable(extend_http_status)


def test_throttling_imports():
    """Test that request throttling utilities can be imported from lib package."""
    from src.lib import RequestThrottle, get_global_throttle, throttled_request

    # Verify they are available
    assert RequestThrottle is not None
    assert get_global_throttle is not None
    assert throttled_request is not None

    # Verify types
    assert isinstance(RequestThrottle, type)
    assert callable(get_global_throttle)
    assert callable(throttled_request)


def test_transport_imports():
    """Test that HTTP transport classes can be imported from lib package."""
    from src.lib import ThrottledAsyncTransport, ThrottledTransport

    # Verify classes are available
    assert ThrottledTransport is not None
    assert ThrottledAsyncTransport is not None

    # Verify they are actually classes
    assert isinstance(ThrottledTransport, type)
    assert isinstance(ThrottledAsyncTransport, type)


def test_all_exports_available():
    """Test that all items in __all__ can be imported."""
    import src.lib as lib

    # Get the __all__ list
    all_exports = getattr(lib, '__all__', [])

    # Verify __all__ is not empty
    assert len(all_exports) > 0, "__all__ should not be empty"

    # Verify each item in __all__ can be accessed
    for export_name in all_exports:
        assert hasattr(lib, export_name), f"{export_name} not found in lib module"

        # Get the actual object
        export_obj = getattr(lib, export_name)
        assert export_obj is not None, f"{export_name} is None"


def test_all_items_in_exports():
    """Test that all items in __all__ are properly exported."""
    import src.lib as lib

    # Get the __all__ list
    all_exports = getattr(lib, '__all__', [])

    # Check that each item in __all__ is actually exported
    for export_name in all_exports:
        assert hasattr(lib, export_name), f"{export_name} listed in __all__ but not exported"

        # Verify the exported item is not None
        export_obj = getattr(lib, export_name)
        assert export_obj is not None, f"{export_name} is None"


def test_goap_instantiation():
    """Test that GOAP classes can be instantiated."""
    from src.lib import Action_List, Planner, World

    # Test World instantiation
    world = World()
    assert world is not None
    assert hasattr(world, 'planners')
    assert hasattr(world, 'plans')

    # Test Action_List instantiation
    actions = Action_List()
    assert actions is not None

    # Test Planner instantiation (requires parameters)
    planner = Planner("test_state", "test_goal", "test_action")
    assert planner is not None


def test_yaml_data_instantiation():
    """Test that YamlData classes can be instantiated."""
    from src.lib import YamlData

    # Test in temporary directory to avoid creating files in project root
    with tempfile.TemporaryDirectory() as temp_dir:
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_dir)
            yaml_data = YamlData("test_data.yaml")
            assert yaml_data is not None
            assert yaml_data.filename == "test_data.yaml"
        finally:
            os.chdir(original_cwd)


def test_artifacts_http_status_content():
    """Test that ArtifactsHTTPStatus contains expected error codes."""
    from src.lib import ArtifactsHTTPStatus

    # Verify it's a dictionary
    assert isinstance(ArtifactsHTTPStatus, dict)

    # Check for some key error codes mentioned in the PRP
    expected_codes = [
        "CHARACTER_IN_COOLDOWN",
        "CHARACTER_INVENTORY_FULL",
        "CHARACTER_NOT_FOUND",
        "TOKEN_INVALID"
    ]

    for code in expected_codes:
        assert code in ArtifactsHTTPStatus, f"Expected error code {code} not found"
        assert isinstance(ArtifactsHTTPStatus[code], int), f"Error code {code} should be an integer"


def test_module_docstring():
    """Test that the module has proper documentation."""
    import src.lib as lib

    # Verify module has docstring
    assert lib.__doc__ is not None, "Module should have a docstring"
    assert len(lib.__doc__.strip()) > 0, "Module docstring should not be empty"

    # Verify docstring mentions key components
    docstring = lib.__doc__.lower()
    assert "goap" in docstring, "Docstring should mention GOAP"
    assert "yaml" in docstring, "Docstring should mention YAML"
    assert "logging" in docstring, "Docstring should mention logging"
    assert "http" in docstring, "Docstring should mention HTTP"
