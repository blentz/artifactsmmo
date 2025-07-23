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
    
    def __init__(self, map_state=None):
        self.data = {
            'monsters': {},
            'resources': {},
            'items': {},
            'workshops': {}
        }
        # Add mock methods that tests expect
        self.find_monsters_in_map = Mock(return_value=[])
        self.find_resources_in_map = Mock(return_value=[])
        self.map_state = map_state
        
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
    
    def get_item_data(self, item_code: str, client=None) -> Optional[Dict]:
        """Get item data with optional API fallback."""
        return self.data['items'].get(item_code)
    
    def refresh_character_data(self, client, character_name: str) -> bool:
        """Mock refresh character data from API."""
        return True
    
    def get_material_requirements(self, recipe_or_item: str) -> Dict[str, int]:
        """Get material requirements for a recipe/item."""
        item_data = self.data['items'].get(recipe_or_item, {})
        craft_data = item_data.get('craft_data', {})
        items = craft_data.get('items', [])
        # Convert from list format to dict format
        return {item['code']: item['quantity'] for item in items}
    
    def has_target_item(self, context, client=None) -> bool:
        """
        Check if character has the target item in inventory or equipped.
        Uses knowledge_base + action_context heuristic instead of state parameter.
        
        Args:
            context: ActionContext containing TARGET_ITEM and character info
            client: API client for real-time character data (optional)
            
        Returns:
            True if character has the target item, False otherwise
        """
        from src.lib.state_parameters import StateParameters
        
        target_item = context.get(StateParameters.TARGET_ITEM)
        if not target_item:
            return False
            
        # Check character inventory through API or context
        character_name = context.get(StateParameters.CHARACTER_NAME)
        if client and character_name:
            # Use real API data if available
            try:
                from artifactsmmo_api_client.api.characters.get_character_characters_name_get import sync as get_character_api
                char_response = get_character_api(name=character_name, client=client)
                if char_response and char_response.data:
                    # Check inventory
                    inventory = char_response.data.inventory or []
                    for item in inventory:
                        if getattr(item, 'code', None) == target_item:
                            return True
                    
                    # Check equipped items
                    equipment_slots = ['weapon_slot', 'helmet_slot', 'body_armor_slot', 
                                     'leg_armor_slot', 'boots_slot', 'ring1_slot', 'ring2_slot',
                                     'amulet_slot', 'artifact1_slot', 'artifact2_slot', 'artifact3_slot']
                    for slot in equipment_slots:
                        equipped_item = getattr(char_response.data, slot, None)
                        if equipped_item == target_item:
                            return True
            except Exception:
                # Fall back to context data if API fails
                pass
        
        # Fallback: check context/mock data
        if hasattr(context, 'character_state') and context.character_state:
            # Check mock inventory if available
            inventory = getattr(context.character_state, 'inventory', [])
            for item in inventory:
                if getattr(item, 'code', item.get('code') if isinstance(item, dict) else None) == target_item:
                    return True
        
        return False
    
    def is_at_workshop(self, context, client=None) -> bool:
        """
        Check if character is at the correct workshop location.
        Uses knowledge_base + action_context heuristic instead of state parameter.
        
        Args:
            context: ActionContext containing character position and workshop requirements
            client: API client for real-time character data (optional)
            
        Returns:
            True if character is at correct workshop, False otherwise
        """
        from src.lib.state_parameters import StateParameters
        
        # Get character position
        char_x = context.get(StateParameters.CHARACTER_X, 0)
        char_y = context.get(StateParameters.CHARACTER_Y, 0)
        
        # Get required workshop type from context or target recipe
        workshop_type = context.get(StateParameters.WORKSHOP_TYPE)
        if not workshop_type:
            target_recipe = context.get(StateParameters.TARGET_RECIPE)
            if target_recipe and isinstance(target_recipe, dict):
                craft_data = target_recipe.get('craft', {})
                workshop_type = craft_data.get('skill', 'weaponcrafting')  # Default to weaponcrafting
        
        if not workshop_type:
            return False
            
        # Check workshop locations from knowledge base
        workshops = self.data.get('workshops', {})
        for workshop_code, workshop_data in workshops.items():
            if workshop_data.get('type') == workshop_type:
                workshop_x = workshop_data.get('x', -1)
                workshop_y = workshop_data.get('y', -1)
                if char_x == workshop_x and char_y == workshop_y:
                    return True
        
        return False
    
    def is_at_resource_location(self, context, client=None) -> bool:
        """
        Check if character is at a resource location for the target material.
        Uses knowledge_base + action_context heuristic instead of state parameter.
        
        Args:
            context: ActionContext containing character position and target material
            client: API client for real-time character data (optional)
            
        Returns:
            True if character is at resource location, False otherwise
        """
        from src.lib.state_parameters import StateParameters
        
        # Get character position
        char_x = context.get(StateParameters.CHARACTER_X, 0)
        char_y = context.get(StateParameters.CHARACTER_Y, 0)
        
        # Get target material from context
        target_material = context.get(StateParameters.TARGET_MATERIAL)
        if not target_material:
            return False
            
        # Check resource locations from knowledge base
        resources = self.data.get('resources', {})
        for resource_code, resource_data in resources.items():
            # Check if this resource provides the target material
            drops = resource_data.get('drops', [])
            for drop in drops:
                if drop.get('code') == target_material:
                    resource_x = resource_data.get('x', -1)
                    resource_y = resource_data.get('y', -1)
                    if char_x == resource_x and char_y == resource_y:
                        return True
        
        return False
    
    def get_character_data(self, character_name: str = None, client=None) -> Dict:
        """Get character data for testing."""
        return {
            'cooldown': 3,
            'hp': 100,
            'max_hp': 100,
            'level': 1
        }
    
    def get_location_info(self, x: int, y: int) -> Optional[Dict]:
        """
        Get stored information about a specific location.
        
        Args:
            x: X coordinate
            y: Y coordinate
            
        Returns:
            Location data dictionary or None if location not found
        """
        if not hasattr(self, 'map_state') or not self.map_state:
            return None
            
        location_key = f"{x},{y}"
        return getattr(self.map_state, 'data', {}).get(location_key)
    
    def get_combat_location(self, context, client=None) -> Optional[str]:
        """
        Get the current combat location identifier.
        Uses knowledge_base + action_context heuristic instead of state parameter.
        
        Args:
            context: ActionContext containing character position and combat target
            client: API client for real-time character data (optional)
            
        Returns:
            Combat location identifier or None
        """
        from src.lib.state_parameters import StateParameters
        
        # Get character position
        char_x = context.get(StateParameters.CHARACTER_X, 0)
        char_y = context.get(StateParameters.CHARACTER_Y, 0)
        
        # Return location identifier for combat tracking
        return f"combat_{char_x}_{char_y}"


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
        self.map_state = MockMapState() if map_state == "default" else map_state
        self.knowledge_base = MockKnowledgeBase(self.map_state) if knowledge_base == "default" else knowledge_base
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
            StateParameters.TARGET_ITEM: 'target_item',
            StateParameters.TARGET_ITEM: 'selected_item',
            StateParameters.TARGET_SLOT: 'target_slot',
            StateParameters.TARGET_X: 'target_x',
            StateParameters.TARGET_Y: 'target_y',
            StateParameters.ITEM_CODE: 'item_code',
            StateParameters.TARGET_ITEM: 'selected_item',
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
            StateParameters.TARGET_ITEM: 'target_item',
            StateParameters.TARGET_ITEM: 'selected_item',
            StateParameters.TARGET_SLOT: 'target_slot',
            StateParameters.TARGET_X: 'target_x',
            StateParameters.TARGET_Y: 'target_y',
            StateParameters.ITEM_CODE: 'item_code',
            StateParameters.TARGET_ITEM: 'selected_item',
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