"""
Character Game State Model

This module defines the CharacterGameState class for representing
character state using GameState enum keys with Pydantic validation.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .game_state import GameState


class CharacterGameState(BaseModel):
    """Pydantic model for character state using GameState enum keys"""
    model_config = ConfigDict(validate_assignment=True, extra='forbid')

    # Character identity
    name: str

    # Character progression
    level: int = Field(ge=1, le=45)
    xp: int = Field(ge=0)
    gold: int = Field(ge=0)
    hp: int = Field(ge=0)
    max_hp: int = Field(ge=1)

    # Position
    x: int
    y: int

    # Skills
    mining_level: int = Field(ge=1, le=45)
    mining_xp: int = Field(ge=0)
    woodcutting_level: int = Field(ge=1, le=45)
    woodcutting_xp: int = Field(ge=0)
    fishing_level: int = Field(ge=1, le=45)
    fishing_xp: int = Field(ge=0)
    weaponcrafting_level: int = Field(ge=1, le=45)
    weaponcrafting_xp: int = Field(ge=0)
    gearcrafting_level: int = Field(ge=1, le=45)
    gearcrafting_xp: int = Field(ge=0)
    jewelrycrafting_level: int = Field(ge=1, le=45)
    jewelrycrafting_xp: int = Field(ge=0)
    cooking_level: int = Field(ge=1, le=45)
    cooking_xp: int = Field(ge=0)
    alchemy_level: int = Field(ge=1, le=45)
    alchemy_xp: int = Field(ge=0)

    # Action state
    cooldown: int = Field(ge=0)
    cooldown_ready: bool = True

    # Capability states
    can_fight: bool = True
    can_gather: bool = True
    can_craft: bool = True
    can_trade: bool = True
    can_move: bool = True
    can_rest: bool = True
    can_use_item: bool = True
    can_bank: bool = True
    can_gain_xp: bool = True
    xp_source_available: bool = False

    # Derived states
    at_monster_location: bool = False
    at_resource_location: bool = False
    at_safe_location: bool = True
    safe_to_fight: bool = True
    hp_low: bool = False
    hp_critical: bool = False
    inventory_space_available: bool = True
    inventory_space_used: int = Field(ge=0, default=0)
    gained_xp: bool = False

    # Additional states required by actions
    enemy_nearby: bool = False
    resource_available: bool = False

    # Equipment slots - match API character model
    weapon_slot: str = Field(default="")
    rune_slot: str = Field(default="")
    shield_slot: str = Field(default="")
    helmet_slot: str = Field(default="")
    body_armor_slot: str = Field(default="")
    leg_armor_slot: str = Field(default="")
    boots_slot: str = Field(default="")
    ring1_slot: str = Field(default="")
    ring2_slot: str = Field(default="")
    amulet_slot: str = Field(default="")
    artifact1_slot: str = Field(default="")

    # Derived equipment states
    at_workshop_location: bool = False
    cooldown_expiration_utc: int | None = None

    def to_goap_state(self) -> dict[str, Any]:
        """Convert to GOAP state dictionary using enum values.

        Parameters:
            None (operates on self)

        Return values:
            Dictionary with string keys (GameState enum values) and state data

        This method converts the character's Pydantic model data to a GOAP-compatible
        state dictionary using GameState enum values as keys, enabling seamless
        integration with the GOAP planning library.
        """
        # Get the raw data dict from the Pydantic model
        raw_dict = self.model_dump()

        # Map the model fields to GameState enum values
        goap_dict = {}

        # Map each model field to corresponding GameState enum
        field_mapping = {
            'level': GameState.CHARACTER_LEVEL,
            'xp': GameState.CHARACTER_XP,
            'gold': GameState.CHARACTER_GOLD,
            'hp': GameState.HP_CURRENT,
            'max_hp': GameState.HP_MAX,
            'x': GameState.CURRENT_X,
            'y': GameState.CURRENT_Y,
            'mining_level': GameState.MINING_LEVEL,
            'mining_xp': GameState.MINING_XP,
            'woodcutting_level': GameState.WOODCUTTING_LEVEL,
            'woodcutting_xp': GameState.WOODCUTTING_XP,
            'fishing_level': GameState.FISHING_LEVEL,
            'fishing_xp': GameState.FISHING_XP,
            'weaponcrafting_level': GameState.WEAPONCRAFTING_LEVEL,
            'weaponcrafting_xp': GameState.WEAPONCRAFTING_XP,
            'gearcrafting_level': GameState.GEARCRAFTING_LEVEL,
            'gearcrafting_xp': GameState.GEARCRAFTING_XP,
            'jewelrycrafting_level': GameState.JEWELRYCRAFTING_LEVEL,
            'jewelrycrafting_xp': GameState.JEWELRYCRAFTING_XP,
            'cooking_level': GameState.COOKING_LEVEL,
            'cooking_xp': GameState.COOKING_XP,
            'alchemy_level': GameState.ALCHEMY_LEVEL,
            'alchemy_xp': GameState.ALCHEMY_XP,
            'cooldown_ready': GameState.COOLDOWN_READY,
            # Capability states
            'can_fight': GameState.CAN_FIGHT,
            'can_gather': GameState.CAN_GATHER,
            'can_craft': GameState.CAN_CRAFT,
            'can_trade': GameState.CAN_TRADE,
            'can_move': GameState.CAN_MOVE,
            'can_rest': GameState.CAN_REST,
            'can_use_item': GameState.CAN_USE_ITEM,
            'can_bank': GameState.CAN_BANK,
            'can_gain_xp': GameState.CAN_GAIN_XP,
            'xp_source_available': GameState.XP_SOURCE_AVAILABLE,
            # Derived states
            'at_monster_location': GameState.AT_MONSTER_LOCATION,
            'at_resource_location': GameState.AT_RESOURCE_LOCATION,
            'at_safe_location': GameState.AT_SAFE_LOCATION,
            'safe_to_fight': GameState.SAFE_TO_FIGHT,
            'hp_low': GameState.HP_LOW,
            'hp_critical': GameState.HP_CRITICAL,
            'inventory_space_available': GameState.INVENTORY_SPACE_AVAILABLE,
            'inventory_space_used': GameState.INVENTORY_SPACE_USED,
            'gained_xp': GameState.GAINED_XP,
            'enemy_nearby': GameState.ENEMY_NEARBY,
            'resource_available': GameState.RESOURCE_AVAILABLE,
        }

        # Map available fields to enum values
        for field_name, enum_key in field_mapping.items():
            if field_name in raw_dict:
                goap_dict[enum_key.value] = raw_dict[field_name]

        return goap_dict

    @classmethod
    def from_api_character(cls, character: Any, map_content=None, cooldown_manager=None) -> 'CharacterGameState':
        """Create from API character response with validated state mapping.

        Parameters:
            character: CharacterSchema object from ArtifactsMMO API response
            map_content: Optional MapContent object for location context
            cooldown_manager: Optional CooldownManager for centralized cooldown tracking

        Return values:
            CharacterGameState instance with validated data mapped to GameState enum keys

        This method creates a type-safe CharacterGameState instance from API response data,
        mapping all relevant character properties to the appropriate GameState enum keys
        while performing Pydantic validation on the data.
        """
        # Get cooldown status from cooldown manager
        if cooldown_manager:
            cooldown_ready = cooldown_manager.is_ready(character.name)
        else:
            cooldown_ready = character.cooldown == 0
        hp_low = character.hp < (character.max_hp * 0.3)
        hp_critical = character.hp < (character.max_hp * 0.1)

        # Determine location states based on map content
        at_monster_location = False
        at_resource_location = False
        at_safe_location = True
        xp_source_available = False  # XP source available at this location
        enemy_nearby = False  # Enemy at current location
        resource_available = False  # Resource at current location

        if map_content:
            if map_content.type == "monster":
                at_monster_location = True
                at_safe_location = False  # Monsters make location unsafe
                xp_source_available = True  # Monsters are XP sources
                enemy_nearby = True  # Enemy is at this location
            elif map_content.type == "resource":
                at_resource_location = True
                xp_source_available = True  # Resources are XP sources (via gathering)
                resource_available = True  # Resource is at this location
            elif map_content.type == "workshop":
                xp_source_available = True  # Workshops are XP sources (via crafting)
            # Keep at_safe_location=True for workshops, tasks_master, etc.

        return cls(
            name=character.name,
            level=character.level,
            xp=character.xp,
            gold=character.gold,
            hp=character.hp,
            max_hp=character.max_hp,
            x=character.x,
            y=character.y,
            mining_level=character.mining_level,
            mining_xp=character.mining_xp,
            woodcutting_level=character.woodcutting_level,
            woodcutting_xp=character.woodcutting_xp,
            fishing_level=character.fishing_level,
            fishing_xp=character.fishing_xp,
            weaponcrafting_level=character.weaponcrafting_level,
            weaponcrafting_xp=character.weaponcrafting_xp,
            gearcrafting_level=character.gearcrafting_level,
            gearcrafting_xp=character.gearcrafting_xp,
            jewelrycrafting_level=character.jewelrycrafting_level,
            jewelrycrafting_xp=character.jewelrycrafting_xp,
            cooking_level=character.cooking_level,
            cooking_xp=character.cooking_xp,
            alchemy_level=character.alchemy_level,
            alchemy_xp=character.alchemy_xp,
            cooldown=character.cooldown,
            cooldown_ready=cooldown_ready,
            # Set capability states based on cooldown status
            can_fight=cooldown_ready,
            can_gather=cooldown_ready,
            can_craft=cooldown_ready,
            can_trade=cooldown_ready,
            can_move=cooldown_ready,
            can_rest=cooldown_ready,
            can_use_item=cooldown_ready,
            can_bank=cooldown_ready,
            can_gain_xp=cooldown_ready,  # Can gain XP when not on cooldown
            xp_source_available=xp_source_available,
            # Set derived states based on map content and character state
            at_monster_location=at_monster_location,
            at_resource_location=at_resource_location,
            at_safe_location=at_safe_location,
            safe_to_fight=not hp_low,  # Safe to fight if HP is good
            hp_low=hp_low,
            hp_critical=hp_critical,
            inventory_space_available=True,  # Will be updated by inventory logic
            inventory_space_used=0,  # Will be updated by inventory logic
            gained_xp=False,  # Reset each state update, set by actions
            enemy_nearby=enemy_nearby,  # Set based on map content
            resource_available=resource_available,  # Set based on map content
            # Equipment slots from API character
            weapon_slot=getattr(character, 'weapon_slot', ''),
            rune_slot=getattr(character, 'rune_slot', ''),
            shield_slot=getattr(character, 'shield_slot', ''),
            helmet_slot=getattr(character, 'helmet_slot', ''),
            body_armor_slot=getattr(character, 'body_armor_slot', ''),
            leg_armor_slot=getattr(character, 'leg_armor_slot', ''),
            boots_slot=getattr(character, 'boots_slot', ''),
            ring1_slot=getattr(character, 'ring1_slot', ''),
            ring2_slot=getattr(character, 'ring2_slot', ''),
            amulet_slot=getattr(character, 'amulet_slot', ''),
            artifact1_slot=getattr(character, 'artifact1_slot', ''),
            # Derived equipment states
            at_workshop_location=bool(map_content and map_content.type == "workshop"),
            cooldown_expiration_utc=getattr(character, 'cooldown_expiration_utc', None),
        )

    def get(self, key: GameState, default=None):
        """Get value by GameState enum key for compatibility with existing code.

        Parameters:
            key: GameState enum key to look up
            default: Default value if key not found

        Return values:
            The value for the specified GameState key, or default if not found
        """
        # Create mapping from GameState enum to field names
        state_to_field = {
            GameState.CHARACTER_LEVEL: 'level',
            GameState.CHARACTER_XP: 'xp',
            GameState.CHARACTER_GOLD: 'gold',
            GameState.HP_CURRENT: 'hp',
            GameState.HP_MAX: 'max_hp',
            GameState.CURRENT_X: 'x',
            GameState.CURRENT_Y: 'y',
            GameState.MINING_LEVEL: 'mining_level',
            GameState.MINING_XP: 'mining_xp',
            GameState.WOODCUTTING_LEVEL: 'woodcutting_level',
            GameState.WOODCUTTING_XP: 'woodcutting_xp',
            GameState.FISHING_LEVEL: 'fishing_level',
            GameState.FISHING_XP: 'fishing_xp',
            GameState.WEAPONCRAFTING_LEVEL: 'weaponcrafting_level',
            GameState.WEAPONCRAFTING_XP: 'weaponcrafting_xp',
            GameState.GEARCRAFTING_LEVEL: 'gearcrafting_level',
            GameState.GEARCRAFTING_XP: 'gearcrafting_xp',
            GameState.JEWELRYCRAFTING_LEVEL: 'jewelrycrafting_level',
            GameState.JEWELRYCRAFTING_XP: 'jewelrycrafting_xp',
            GameState.COOKING_LEVEL: 'cooking_level',
            GameState.COOKING_XP: 'cooking_xp',
            GameState.ALCHEMY_LEVEL: 'alchemy_level',
            GameState.ALCHEMY_XP: 'alchemy_xp',
            GameState.COOLDOWN_READY: 'cooldown_ready',
            GameState.CAN_FIGHT: 'can_fight',
            GameState.CAN_GATHER: 'can_gather',
            GameState.CAN_CRAFT: 'can_craft',
            GameState.CAN_TRADE: 'can_trade',
            GameState.CAN_MOVE: 'can_move',
            GameState.CAN_REST: 'can_rest',
            GameState.CAN_USE_ITEM: 'can_use_item',
            GameState.CAN_BANK: 'can_bank',
            GameState.AT_MONSTER_LOCATION: 'at_monster_location',
            GameState.AT_RESOURCE_LOCATION: 'at_resource_location',
            GameState.AT_SAFE_LOCATION: 'at_safe_location',
            GameState.SAFE_TO_FIGHT: 'safe_to_fight',
            GameState.HP_LOW: 'hp_low',
            GameState.HP_CRITICAL: 'hp_critical',
            GameState.INVENTORY_SPACE_AVAILABLE: 'inventory_space_available',
            GameState.INVENTORY_SPACE_USED: 'inventory_space_used',
            GameState.GAINED_XP: 'gained_xp',
            GameState.ENEMY_NEARBY: 'enemy_nearby',
            GameState.RESOURCE_AVAILABLE: 'resource_available',
        }

        field_name = state_to_field.get(key)
        if field_name is None:
            return default

        return getattr(self, field_name, default)

    def __getitem__(self, key: GameState):
        """Allow dict-style access with GameState enum keys."""
        value = self.get(key)
        if value is None:
            raise KeyError(f"GameState key {key} not found")
        return value

    def __contains__(self, key: GameState):
        """Check if GameState key exists in this model."""
        return self.get(key) is not None

    @classmethod
    def from_goap_state(cls, goap_state: dict[str, Any]) -> 'CharacterGameState':
        """Create CharacterGameState from GOAP state dictionary.

        Parameters:
            goap_state: Dictionary with string keys (GameState enum values) and state data

        Return values:
            CharacterGameState instance with data populated from GOAP state
        """
        # Reverse mapping from GameState enum values to field names
        enum_to_field = {
            GameState.CHARACTER_LEVEL.value: 'level',
            GameState.CHARACTER_XP.value: 'xp',
            GameState.CHARACTER_GOLD.value: 'gold',
            GameState.HP_CURRENT.value: 'hp',
            GameState.HP_MAX.value: 'max_hp',
            GameState.CURRENT_X.value: 'x',
            GameState.CURRENT_Y.value: 'y',
            GameState.MINING_LEVEL.value: 'mining_level',
            GameState.MINING_XP.value: 'mining_xp',
            GameState.WOODCUTTING_LEVEL.value: 'woodcutting_level',
            GameState.WOODCUTTING_XP.value: 'woodcutting_xp',
            GameState.FISHING_LEVEL.value: 'fishing_level',
            GameState.FISHING_XP.value: 'fishing_xp',
            GameState.WEAPONCRAFTING_LEVEL.value: 'weaponcrafting_level',
            GameState.WEAPONCRAFTING_XP.value: 'weaponcrafting_xp',
            GameState.GEARCRAFTING_LEVEL.value: 'gearcrafting_level',
            GameState.GEARCRAFTING_XP.value: 'gearcrafting_xp',
            GameState.JEWELRYCRAFTING_LEVEL.value: 'jewelrycrafting_level',
            GameState.JEWELRYCRAFTING_XP.value: 'jewelrycrafting_xp',
            GameState.COOKING_LEVEL.value: 'cooking_level',
            GameState.COOKING_XP.value: 'cooking_xp',
            GameState.ALCHEMY_LEVEL.value: 'alchemy_level',
            GameState.ALCHEMY_XP.value: 'alchemy_xp',
            GameState.COOLDOWN_READY.value: 'cooldown_ready',
            GameState.CAN_FIGHT.value: 'can_fight',
            GameState.CAN_GATHER.value: 'can_gather',
            GameState.CAN_CRAFT.value: 'can_craft',
            GameState.CAN_TRADE.value: 'can_trade',
            GameState.CAN_MOVE.value: 'can_move',
            GameState.CAN_REST.value: 'can_rest',
            GameState.CAN_USE_ITEM.value: 'can_use_item',
            GameState.CAN_BANK.value: 'can_bank',
            GameState.CAN_GAIN_XP.value: 'can_gain_xp',
            GameState.XP_SOURCE_AVAILABLE.value: 'xp_source_available',
            GameState.AT_MONSTER_LOCATION.value: 'at_monster_location',
            GameState.AT_RESOURCE_LOCATION.value: 'at_resource_location',
            GameState.AT_SAFE_LOCATION.value: 'at_safe_location',
            GameState.SAFE_TO_FIGHT.value: 'safe_to_fight',
            GameState.HP_LOW.value: 'hp_low',
            GameState.HP_CRITICAL.value: 'hp_critical',
            GameState.INVENTORY_SPACE_AVAILABLE.value: 'inventory_space_available',
            GameState.INVENTORY_SPACE_USED.value: 'inventory_space_used',
            GameState.GAINED_XP.value: 'gained_xp',
            GameState.ENEMY_NEARBY.value: 'enemy_nearby',
            GameState.RESOURCE_AVAILABLE.value: 'resource_available',
        }

        # Create field data dictionary
        field_data = {}

        # Map GOAP state to model fields
        for goap_key, value in goap_state.items():
            field_name = enum_to_field.get(goap_key)
            if field_name:
                field_data[field_name] = value

        # Ensure required fields have defaults
        if 'name' not in field_data:
            field_data['name'] = 'unknown'
        if 'cooldown' not in field_data:
            field_data['cooldown'] = 0

        return cls(**field_data)
