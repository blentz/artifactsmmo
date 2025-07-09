"""
Test fixtures for commonly used mock objects.

This module provides reusable mock objects and helper functions to reduce
code duplication across test files.
"""

import os
import tempfile
from typing import Dict, List, Optional
from unittest.mock import Mock

# Import extend_http_status but don't call it here - tests should call it in setUpClass
from src.lib.httpstatus import extend_http_status
from src.lib.state_parameters import StateParameters


class MockAPIResponse:
    """Mock API response object that mimics the structure of real API responses."""
    
    def __init__(self, data=None, status_code=200):
        self.data = data
        self.status_code = status_code
        
    def __bool__(self):
        """Make response truthy if data exists."""
        return self.data is not None


class MockCharacterData:
    """Mock character data object."""
    
    def __init__(self, name="test_character", x=0, y=0, hp=100, max_hp=100, 
                 level=1, gold=100, inventory=None, cooldown=0, 
                 mining_level=1, woodcutting_level=1, fishing_level=1,
                 weaponcrafting_level=1, gearcrafting_level=1, 
                 jewelrycrafting_level=1, cooking_level=1, alchemy_level=1,
                 weapon="iron_sword"):
        self.name = name
        self.x = x
        self.y = y
        self.hp = hp
        self.max_hp = max_hp
        self.level = level
        self.gold = gold
        self.inventory = inventory or []
        self.cooldown = cooldown
        self.cooldown_expiration = None
        
        # Skills
        self.mining_level = mining_level
        self.woodcutting_level = woodcutting_level
        self.fishing_level = fishing_level
        self.weaponcrafting_level = weaponcrafting_level
        self.gearcrafting_level = gearcrafting_level
        self.jewelrycrafting_level = jewelrycrafting_level
        self.cooking_level = cooking_level
        self.alchemy_level = alchemy_level
        self.weapon = weapon
        
        # Create a data attribute that mirrors the structure expected by actions
        self.data = {
            'name': name,
            'x': x,
            'y': y,
            'hp': hp,
            'max_hp': max_hp,
            'level': level,
            'gold': gold,
            'cooldown': cooldown,
            'cooldown_expiration': None,
            'mining_level': mining_level,
            'woodcutting_level': woodcutting_level,
            'fishing_level': fishing_level,
            'weaponcrafting_level': weaponcrafting_level,
            'gearcrafting_level': gearcrafting_level,
            'jewelrycrafting_level': jewelrycrafting_level,
            'cooking_level': cooking_level,
            'alchemy_level': alchemy_level,
            'weapon': weapon
        }


class MockInventoryItem:
    """Mock inventory item."""
    
    def __init__(self, code="item", quantity=1):
        self.code = code
        self.quantity = quantity


class MockItemData:
    """Mock item data from API."""
    
    def __init__(self, code="item", name="Item", type="resource", level=1,
                 description="A test item", tradeable=True, craft=None, effects=None):
        self.code = code
        self.name = name
        self.type = type
        self.level = level
        self.description = description
        self.tradeable = tradeable
        self.craft = craft
        self.effects = effects or []


class MockCraftData:
    """Mock craft data for items."""
    
    def __init__(self, skill="crafting", level=1, items=None, quantity=1):
        self.skill = skill
        self.level = level
        self.items = items or []
        self.quantity = quantity


class MockCraftItem:
    """Mock craft requirement item."""
    
    def __init__(self, code="material", quantity=1):
        self.code = code
        self.quantity = quantity


class MockMapData:
    """Mock map location data."""
    
    def __init__(self, x=0, y=0, content=None):
        self.x = x
        self.y = y
        self.content = content


class MockMapContent:
    """Mock map content (monster, resource, workshop, etc.)."""
    
    def __init__(self, type_="resource", code="copper_rocks"):
        self.type_ = type_
        self.code = code


class MockMonsterData:
    """Mock monster data."""
    
    def __init__(self, code="chicken", name="Chicken", level=1, hp=10,
                 attack_fire=0, attack_earth=0, attack_water=0, attack_air=0,
                 res_fire=0, res_earth=0, res_water=0, res_air=0):
        self.code = code
        self.name = name
        self.level = level
        self.hp = hp
        self.attack_fire = attack_fire
        self.attack_earth = attack_earth
        self.attack_water = attack_water
        self.attack_air = attack_air
        self.res_fire = res_fire
        self.res_earth = res_earth
        self.res_water = res_water
        self.res_air = res_air


class MockResourceData:
    """Mock resource data."""
    
    def __init__(self, code="copper_rocks", name="Copper Rocks", skill="mining", level=1, drops=None):
        self.code = code
        self.name = name
        self.skill = skill
        self.level = level
        self.drops = drops or []


class MockResourceDrop:
    """Mock resource drop."""
    
    def __init__(self, code="copper_ore", quantity=1, rate=1.0):
        self.code = code
        self.quantity = quantity
        self.rate = rate


class MockKnowledgeBase:
    """Mock knowledge base for testing."""
    
    def __init__(self):
        self.data = {
            'monsters': {},
            'resources': {},
            'items': {},
            'workshops': {}
        }
        # Add mock methods that tests expect
        self.find_monsters_in_map = Mock(return_value=[])
        
    def get_monster_win_rate(self, monster_code: str) -> Optional[float]:
        """Get win rate for a monster."""
        monster_data = self.data['monsters'].get(monster_code, {})
        return monster_data.get('win_rate')
        
    def get_all_known_monster_codes(self) -> List[str]:
        """Get all known monster codes."""
        return list(self.data['monsters'].keys())
        
    def get_all_known_resource_codes(self) -> List[str]:
        """Get all known resource codes."""
        return list(self.data['resources'].keys())
    
    def get_monster_data(self, monster_code: str, client=None) -> Optional[Dict]:
        """Get monster data with optional API fallback."""
        return self.data['monsters'].get(monster_code)


class MockMapState:
    """Mock map state for testing."""
    
    def __init__(self):
        self.data = {}
        self._learning_callback = None
        
    def set_learning_callback(self, callback):
        """Set learning callback."""
        self._learning_callback = callback
        
    def scan(self, x: int, y: int, cache=True, save_immediately=True) -> Optional[Dict]:
        """Mock map scan."""
        key = f"{x},{y}"
        return self.data.get(key)


class MockActionContext:
    """Mock ActionContext for testing without excessive setup."""
    
    def __init__(self, character_name="test_character", character_x=0, character_y=0,
                 character_level=1, character_hp=100, character_max_hp=100,
                 knowledge_base="default", map_state="default", world_state=None,
                 character_state=None, client=None, controller=None,
                 equipment=None, **kwargs):
        # Core attributes
        self.character_name = character_name
        self.character_x = character_x
        self.character_y = character_y
        self.character_level = character_level
        self.character_hp = character_hp
        self.character_max_hp = character_max_hp
        
        # Dependencies
        self.knowledge_base = MockKnowledgeBase() if knowledge_base == "default" else knowledge_base
        self.map_state = MockMapState() if map_state == "default" else map_state
        self.world_state = world_state or {}
        if character_state == "no_state":
            self.character_state = None
        elif character_state is None:
            self.character_state = MockCharacterData(
                name=character_name, x=character_x, y=character_y,
                level=character_level, hp=character_hp, max_hp=character_max_hp
            )
        else:
            self.character_state = character_state
        self.client = client
        self.controller = controller
        self.equipment = equipment or {}
        
        # Store any additional attributes
        self.action_data = kwargs.copy()
        self.action_results = {}
        
        # Add any extra kwargs as attributes
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def _get_state_parameter(self, param: str, default=None):
        """Map StateParameters to MockActionContext attributes."""
        # Map StateParameters to legacy attributes
        mapping = {
            StateParameters.CHARACTER_NAME: 'character_name',
            StateParameters.CHARACTER_LEVEL: 'character_level', 
            StateParameters.CHARACTER_HP: 'character_hp',
            StateParameters.CHARACTER_MAX_HP: 'character_max_hp',
            StateParameters.CHARACTER_X: 'character_x',
            StateParameters.CHARACTER_Y: 'character_y',
            StateParameters.MATERIALS_TARGET_ITEM: 'target_item',
            StateParameters.EQUIPMENT_SELECTED_ITEM: 'selected_item',
            StateParameters.EQUIPMENT_TARGET_SLOT: 'target_slot',
            StateParameters.TARGET_X: 'target_x',
            StateParameters.TARGET_Y: 'target_y',
            StateParameters.ITEM_CODE: 'item_code',
            StateParameters.SELECTED_ITEM: 'selected_item',
            StateParameters.SEARCH_RADIUS: 'search_radius',
        }
        
        if param in mapping:
            attr_name = mapping[param]
            if hasattr(self, attr_name):
                return getattr(self, attr_name)
        
        # Check action_data for the parameter
        if param in self.action_data:
            return self.action_data[param]
            
        return default
    
    def get(self, key, default=None):
        """Dictionary-like get method with StateParameters support."""
        # Handle StateParameters by mapping to attributes
        if key in StateParameters.get_all_parameters():
            return self._get_state_parameter(key, default)
        
        # Legacy support for direct attribute access
        if hasattr(self, key):
            return getattr(self, key)
        if key in self.action_data:
            return self.action_data[key]
        return default
    
    def __getitem__(self, key):
        """Dictionary-like access."""
        return self.get(key)
    
    def __setitem__(self, key, value):
        """Dictionary-like setting."""
        self.action_data[key] = value
    
    def set(self, param: str, value):
        """Set parameter using StateParameters pattern."""
        # Map StateParameters to legacy attributes
        mapping = {
            StateParameters.CHARACTER_NAME: 'character_name',
            StateParameters.CHARACTER_LEVEL: 'character_level', 
            StateParameters.CHARACTER_HP: 'character_hp',
            StateParameters.CHARACTER_MAX_HP: 'character_max_hp',
            StateParameters.CHARACTER_X: 'character_x',
            StateParameters.CHARACTER_Y: 'character_y',
            StateParameters.MATERIALS_TARGET_ITEM: 'target_item',
            StateParameters.EQUIPMENT_SELECTED_ITEM: 'selected_item',
            StateParameters.EQUIPMENT_TARGET_SLOT: 'target_slot',
            StateParameters.TARGET_X: 'target_x',
            StateParameters.TARGET_Y: 'target_y',
            StateParameters.ITEM_CODE: 'item_code',
            StateParameters.SELECTED_ITEM: 'selected_item',
            StateParameters.SEARCH_RADIUS: 'search_radius',
        }
        
        if param in mapping:
            attr_name = mapping[param]
            setattr(self, attr_name, value)
        else:
            # Store in action_data for other parameters
            self.action_data[param] = value
    
    def __contains__(self, key):
        """Dictionary-like contains check."""
        return hasattr(self, key) or key in self.action_data
    
    def update(self, other):
        """Update from dictionary."""
        if isinstance(other, dict):
            self.action_data.update(other)
        
    def get_parameter(self, key, default=None):
        """Get parameter compatible with ActionContext interface."""
        return self.get(key, default)
    
    def set_parameter(self, key, value):
        """Set parameter compatible with ActionContext interface."""
        self[key] = value
    
    def set_result(self, key, value):
        """Set result data."""
        self.action_results[key] = value
    
    def keys(self):
        """Dictionary-like keys method."""
        # Include standard attributes
        standard_attrs = ['character_name', 'character_x', 'character_y', 
                         'character_level', 'character_hp', 'character_max_hp',
                         'x', 'y', 'target_x', 'target_y', 'use_target_coordinates']
        keys = []
        for attr in standard_attrs:
            if hasattr(self, attr) and getattr(self, attr) is not None:
                keys.append(attr)
        # Include action_data keys
        keys.extend(self.action_data.keys())
        return keys
    
    def __iter__(self):
        """Make MockActionContext iterable like a dict."""
        return iter(self.keys())
    
    def items(self):
        """Dictionary-like items method."""
        for key in self.keys():
            yield key, self.get(key)


def create_mock_client():
    """Create a properly configured mock API client."""
    client = Mock()
    
    # Mock the httpx client
    mock_httpx_client = Mock()
    mock_request = Mock()
    mock_request.status_code = 200
    mock_httpx_client.request.return_value = mock_request
    
    # Set up get_httpx_client to return our mock
    client.get_httpx_client.return_value = mock_httpx_client
    
    return client


class ActionTestCase:
    """Mixin class to ensure proper ActionContext singleton isolation in tests."""
    
    def setUp(self):
        """Reset singleton state for proper test isolation."""
        # Import here to avoid circular imports
        from src.lib.action_context import ActionContext
        context = ActionContext()
        context._state.reset()
        super().setUp() if hasattr(super(), 'setUp') else None
    
    def tearDown(self):
        """Clean up singleton state after test.""" 
        # Import here to avoid circular imports
        from src.lib.action_context import ActionContext
        context = ActionContext()
        context._state.reset()
        super().tearDown() if hasattr(super(), 'tearDown') else None


def create_mock_action_config():
    """Create a mock action configuration dictionary."""
    return {
        'minimum_win_rate': 0.2,
        'unknown_monster_max_level': 2,
        'minimum_combat_results': 2,
        'cooldown_buffer_seconds': 1,
        'default_transform_quantity': 1,
        'raw_material_patterns': ['_ore', '_wood'],
        'equipment_level_range': 2,
        'max_resource_search_radius': 8,
        'resource_search_radius_expansion': 3,
        'min_resource_knowledge_threshold': 20
    }


def create_test_environment():
    """Create a test environment with temporary directories."""
    temp_dir = tempfile.mkdtemp()
    original_data_prefix = os.environ.get('DATA_PREFIX', '')
    os.environ['DATA_PREFIX'] = temp_dir
    return temp_dir, original_data_prefix


def cleanup_test_environment(temp_dir, original_data_prefix):
    """Clean up test environment."""
    os.environ['DATA_PREFIX'] = original_data_prefix
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)


# Helper functions for creating mock API responses

def mock_character_response(character_data=None):
    """Create a mock character API response."""
    if character_data is None:
        character_data = MockCharacterData()
    return MockAPIResponse(data=character_data)


def mock_item_response(item_data=None):
    """Create a mock item API response."""
    if item_data is None:
        item_data = MockItemData()
    return MockAPIResponse(data=item_data)


def mock_map_response(map_data=None):
    """Create a mock map API response."""
    if map_data is None:
        map_data = MockMapData()
    return MockAPIResponse(data=map_data)


def mock_monster_response(monster_data=None):
    """Create a mock monster API response."""
    if monster_data is None:
        monster_data = MockMonsterData()
    return MockAPIResponse(data=monster_data)


def mock_resource_response(resource_data=None):
    """Create a mock resource API response."""
    if resource_data is None:
        resource_data = MockResourceData()
    return MockAPIResponse(data=resource_data)


def mock_attack_response(success=True, fight_data=None):
    """Create a mock attack API response."""
    data = Mock()
    data.success = success
    data.fight = fight_data or {}
    return MockAPIResponse(data=data)


def mock_craft_response(success=True, xp=10, items=None):
    """Create a mock craft API response."""
    data = Mock()
    data.success = success
    data.xp = xp
    data.items = items or []
    return MockAPIResponse(data=data)


def mock_move_response(success=True, x=0, y=0):
    """Create a mock move API response."""
    data = Mock()
    data.success = success
    data.destination = Mock(x=x, y=y)
    return MockAPIResponse(data=data)