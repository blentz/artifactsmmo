"""Test to cover line 24 in game_resource.py"""

from unittest.mock import Mock
from src.game_data.game_resource import GameResource


def test_from_api_resource_covers_line_24():
    """Test GameResource.from_api_resource to cover the missing line 24"""
    # Create a mock API resource
    mock_api_resource = Mock()
    mock_api_resource.code = "iron_ore"
    mock_api_resource.name = "Iron Ore"
    mock_api_resource.skill = "mining"
    mock_api_resource.level = 1
    mock_api_resource.drops = None  # This will trigger the 'or []' part on line 29
    
    # This should exercise line 24 (the return cls() line)
    result = GameResource.from_api_resource(mock_api_resource)
    
    assert result.code == "iron_ore"
    assert result.name == "Iron Ore"
    assert result.skill == "mining"
    assert result.level == 1
    assert result.drops == []