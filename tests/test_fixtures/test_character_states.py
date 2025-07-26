"""
Comprehensive tests for tests.fixtures.character_states module

This module validates all character state fixtures, cooldown fixtures,
JSON serialization functionality, and convenience functions to ensure
100% test coverage and correct functionality.
"""

import json

import pytest

from src.ai_player.state.game_state import CooldownInfo, GameState
from tests.fixtures.character_states import (
    CharacterStateFixtures,
    CharacterStateJSON,
    CooldownFixtures,
    get_state_transition_sequence,
    get_test_character_state,
    get_test_cooldown,
)


class TestCharacterStateFixtures:
    """Test suite for CharacterStateFixtures class"""

    def test_get_level_1_starter(self) -> None:
        """Test level 1 starter character state fixture"""
        state = CharacterStateFixtures.get_level_1_starter()

        assert isinstance(state, dict)
        assert state[GameState.CHARACTER_LEVEL] == 1
        assert state[GameState.CHARACTER_XP] == 0
        assert state[GameState.CHARACTER_GOLD] == 0
        assert state[GameState.HP_CURRENT] == 100
        assert state[GameState.HP_MAX] == 100
        assert state[GameState.CURRENT_X] == 0
        assert state[GameState.CURRENT_Y] == 0

        # Check all skills start at level 1
        assert state[GameState.MINING_LEVEL] == 1
        assert state[GameState.MINING_XP] == 0
        assert state[GameState.WOODCUTTING_LEVEL] == 1
        assert state[GameState.WOODCUTTING_XP] == 0
        assert state[GameState.FISHING_LEVEL] == 1
        assert state[GameState.FISHING_XP] == 0

        # Check no equipment
        assert state[GameState.WEAPON_EQUIPPED] is None
        assert state[GameState.TOOL_EQUIPPED] is None
        assert state[GameState.HELMET_EQUIPPED] is None

        # Check basic capabilities
        assert state[GameState.COOLDOWN_READY] is True
        assert state[GameState.CAN_FIGHT] is True
        assert state[GameState.CAN_GATHER] is True
        assert state[GameState.INVENTORY_FULL] is False

    def test_get_level_10_experienced(self) -> None:
        """Test level 10 experienced character state fixture"""
        state = CharacterStateFixtures.get_level_10_experienced()

        assert isinstance(state, dict)
        assert state[GameState.CHARACTER_LEVEL] == 10
        assert state[GameState.CHARACTER_XP] == 2500
        assert state[GameState.CHARACTER_GOLD] == 1500
        assert state[GameState.HP_CURRENT] == 120
        assert state[GameState.HP_MAX] == 120

        # Check improved skills
        assert state[GameState.MINING_LEVEL] == 8
        assert state[GameState.MINING_XP] == 1800
        assert state[GameState.WOODCUTTING_LEVEL] == 6
        assert state[GameState.WOODCUTTING_XP] == 1200

        # Check basic equipment
        assert state[GameState.WEAPON_EQUIPPED] == "iron_sword"
        assert state[GameState.TOOL_EQUIPPED] == "iron_pickaxe"
        assert state[GameState.HELMET_EQUIPPED] == "leather_helmet"

        # Check inventory state
        assert state[GameState.INVENTORY_SPACE_AVAILABLE] == 12
        assert state[GameState.INVENTORY_SPACE_USED] == 8
        assert state[GameState.INVENTORY_FULL] is False

        # Check active task
        assert state[GameState.ACTIVE_TASK] == "gather_iron_ore"
        assert state[GameState.TASK_PROGRESS] == 5

    def test_get_level_25_advanced(self) -> None:
        """Test level 25 advanced character state fixture"""
        state = CharacterStateFixtures.get_level_25_advanced()

        assert isinstance(state, dict)
        assert state[GameState.CHARACTER_LEVEL] == 25
        assert state[GameState.CHARACTER_XP] == 15000
        assert state[GameState.CHARACTER_GOLD] == 10000
        assert state[GameState.HP_CURRENT] == 180
        assert state[GameState.HP_MAX] == 200

        # Check high-level skills
        assert state[GameState.MINING_LEVEL] == 22
        assert state[GameState.MINING_XP] == 8500
        assert state[GameState.WOODCUTTING_LEVEL] == 20
        assert state[GameState.WOODCUTTING_XP] == 7800

        # Check advanced equipment
        assert state[GameState.WEAPON_EQUIPPED] == "mithril_sword"
        assert state[GameState.TOOL_EQUIPPED] == "mithril_pickaxe"
        assert state[GameState.HELMET_EQUIPPED] == "steel_helmet"
        assert state[GameState.RING1_EQUIPPED] == "copper_ring"
        assert state[GameState.RING2_EQUIPPED] == "iron_ring"
        assert state[GameState.AMULET_EQUIPPED] == "silver_amulet"

        # Check bank location
        assert state[GameState.AT_BANK_LOCATION] is True

        # Check economic states
        assert state[GameState.MARKET_ACCESS] is True
        assert state[GameState.PROFITABLE_TRADE_AVAILABLE] is True
        assert state[GameState.PORTFOLIO_VALUE] == 25000

    def test_get_emergency_low_hp(self) -> None:
        """Test emergency low HP character state fixture"""
        state = CharacterStateFixtures.get_emergency_low_hp()

        assert isinstance(state, dict)
        assert state[GameState.HP_CURRENT] == 15
        assert state[GameState.HP_MAX] == 120
        assert state[GameState.HP_LOW] is True
        assert state[GameState.HP_CRITICAL] is True
        assert state[GameState.SAFE_TO_FIGHT] is False
        assert state[GameState.IN_COMBAT] is True
        assert state[GameState.ENEMY_NEARBY] is True
        assert state[GameState.COMBAT_ADVANTAGE] is False
        assert state[GameState.CAN_FIGHT] is False
        assert state[GameState.AT_SAFE_LOCATION] is False
        assert state[GameState.PROGRESSION_BLOCKED] is True

    def test_get_inventory_full(self) -> None:
        """Test inventory full character state fixture"""
        state = CharacterStateFixtures.get_inventory_full()

        assert isinstance(state, dict)
        assert state[GameState.INVENTORY_SPACE_AVAILABLE] == 0
        assert state[GameState.INVENTORY_SPACE_USED] == 20
        assert state[GameState.INVENTORY_FULL] is True
        assert state[GameState.CAN_GATHER] is False
        assert state[GameState.HAS_REQUIRED_ITEMS] is True
        assert state[GameState.HAS_CRAFTING_MATERIALS] is True
        assert state[GameState.INVENTORY_OPTIMIZED] is False
        assert state[GameState.EFFICIENT_ACTION_AVAILABLE] is False
        assert state[GameState.PROGRESSION_BLOCKED] is True

    def test_get_character_on_cooldown(self) -> None:
        """Test character on cooldown state fixture"""
        state = CharacterStateFixtures.get_character_on_cooldown()

        assert isinstance(state, dict)
        assert state[GameState.COOLDOWN_READY] is False
        assert state[GameState.CAN_FIGHT] is False
        assert state[GameState.CAN_GATHER] is False
        assert state[GameState.CAN_CRAFT] is False
        assert state[GameState.CAN_MOVE] is False
        assert state[GameState.CAN_TRADE] is False
        assert state[GameState.CAN_USE_ITEM] is False
        assert state[GameState.EFFICIENT_ACTION_AVAILABLE] is False

    def test_get_resource_depleted_area(self) -> None:
        """Test resource depleted area character state fixture"""
        state = CharacterStateFixtures.get_resource_depleted_area()

        assert isinstance(state, dict)
        assert state[GameState.AT_RESOURCE_LOCATION] is True
        assert state[GameState.RESOURCE_AVAILABLE] is False
        assert state[GameState.RESOURCE_DEPLETED] is True
        assert state[GameState.CAN_GATHER] is False
        assert state[GameState.OPTIMAL_LOCATION] is False
        assert state[GameState.EFFICIENT_ACTION_AVAILABLE] is False
        assert state[GameState.PROGRESSION_BLOCKED] is True

    def test_get_wealthy_trader(self) -> None:
        """Test wealthy trader character state fixture"""
        state = CharacterStateFixtures.get_wealthy_trader()

        assert isinstance(state, dict)
        assert state[GameState.CHARACTER_GOLD] == 50000
        assert state[GameState.AT_GRAND_EXCHANGE] is True
        assert state[GameState.MARKET_ACCESS] is True
        assert state[GameState.PROFITABLE_TRADE_AVAILABLE] is True
        assert state[GameState.ARBITRAGE_OPPORTUNITY] is True
        assert state[GameState.PORTFOLIO_VALUE] == 100000
        assert state[GameState.ITEM_PRICE_TREND] == "bullish"
        assert state[GameState.INVENTORY_OPTIMIZED] is True
        assert state[GameState.BANK_GOLD] == 25000
        assert state[GameState.BANK_SPACE_AVAILABLE] == 50

    def test_get_max_level_endgame(self) -> None:
        """Test max level endgame character state fixture"""
        state = CharacterStateFixtures.get_max_level_endgame()

        assert isinstance(state, dict)
        assert state[GameState.CHARACTER_LEVEL] == 45
        assert state[GameState.CHARACTER_XP] == 100000
        assert state[GameState.CHARACTER_GOLD] == 100000
        assert state[GameState.HP_CURRENT] == 300
        assert state[GameState.HP_MAX] == 300

        # Check maxed skills
        assert state[GameState.MINING_LEVEL] == 45
        assert state[GameState.MINING_XP] == 50000
        assert state[GameState.WOODCUTTING_LEVEL] == 45
        assert state[GameState.WOODCUTTING_XP] == 50000
        assert state[GameState.FISHING_LEVEL] == 45
        assert state[GameState.FISHING_XP] == 50000

        # Check legendary equipment
        assert state[GameState.WEAPON_EQUIPPED] == "legendary_sword"
        assert state[GameState.TOOL_EQUIPPED] == "legendary_pickaxe"
        assert state[GameState.HELMET_EQUIPPED] == "legendary_helmet"
        assert state[GameState.RING1_EQUIPPED] == "legendary_ring"
        assert state[GameState.RING2_EQUIPPED] == "legendary_ring"
        assert state[GameState.AMULET_EQUIPPED] == "legendary_amulet"

        # Check endgame economy
        assert state[GameState.PORTFOLIO_VALUE] == 500000
        assert state[GameState.BANK_GOLD] == 200000
        assert state[GameState.BANK_SPACE_AVAILABLE] == 100

        # Check optimization states
        assert state[GameState.READY_FOR_UPGRADE] is False  # Already maxed


class TestCooldownFixtures:
    """Test suite for CooldownFixtures class"""

    def test_get_no_cooldown(self) -> None:
        """Test no cooldown fixture"""
        cooldown = CooldownFixtures.get_no_cooldown()

        assert isinstance(cooldown, CooldownInfo)
        assert cooldown.character_name == "ready_character"
        assert cooldown.total_seconds == 0
        assert cooldown.remaining_seconds == 0
        assert cooldown.reason == "none"
        assert cooldown.is_ready is True

    def test_get_short_cooldown(self) -> None:
        """Test short cooldown fixture"""
        cooldown = CooldownFixtures.get_short_cooldown()

        assert isinstance(cooldown, CooldownInfo)
        assert cooldown.character_name == "short_cooldown_character"
        assert cooldown.total_seconds == 5
        assert cooldown.remaining_seconds == 5
        assert cooldown.reason == "move"
        # Note: is_ready might be True or False depending on timing

    def test_get_medium_cooldown(self) -> None:
        """Test medium cooldown fixture"""
        cooldown = CooldownFixtures.get_medium_cooldown()

        assert isinstance(cooldown, CooldownInfo)
        assert cooldown.character_name == "medium_cooldown_character"
        assert cooldown.total_seconds == 30
        assert cooldown.remaining_seconds == 30
        assert cooldown.reason == "fight"

    def test_get_long_cooldown(self) -> None:
        """Test long cooldown fixture"""
        cooldown = CooldownFixtures.get_long_cooldown()

        assert isinstance(cooldown, CooldownInfo)
        assert cooldown.character_name == "long_cooldown_character"
        assert cooldown.total_seconds == 300
        assert cooldown.remaining_seconds == 300
        assert cooldown.reason == "craft"

    def test_cooldown_time_properties(self) -> None:
        """Test cooldown time-related properties"""
        # Test expired cooldown
        expired_cooldown = CooldownFixtures.get_no_cooldown()
        assert expired_cooldown.time_remaining == 0.0

        # Test active cooldown
        active_cooldown = CooldownFixtures.get_short_cooldown()
        assert active_cooldown.time_remaining > 0.0


class TestCharacterStateJSON:
    """Test suite for CharacterStateJSON class"""

    def test_save_state_to_json(self) -> None:
        """Test saving character state to JSON format"""
        state = CharacterStateFixtures.get_level_10_experienced()
        json_str = CharacterStateJSON.save_state_to_json(state, "test.json")

        assert isinstance(json_str, str)

        # Parse and validate JSON structure
        json_data = json.loads(json_str)
        assert "character_state" in json_data
        assert "timestamp" in json_data
        assert "version" in json_data
        assert json_data["version"] == "1.0"

        # Verify character state data
        character_state = json_data["character_state"]
        assert character_state["character_level"] == 10
        assert character_state["character_xp"] == 2500
        assert character_state["character_gold"] == 1500

    def test_load_state_from_json(self) -> None:
        """Test loading character state from JSON string"""
        original_state = CharacterStateFixtures.get_level_10_experienced()
        json_str = CharacterStateJSON.save_state_to_json(original_state, "test.json")
        loaded_state = CharacterStateJSON.load_state_from_json(json_str)

        assert isinstance(loaded_state, dict)

        # Verify key types are GameState enums
        for key in loaded_state.keys():
            assert isinstance(key, GameState)

        # Verify data integrity
        assert loaded_state[GameState.CHARACTER_LEVEL] == 10
        assert loaded_state[GameState.CHARACTER_XP] == 2500
        assert loaded_state[GameState.CHARACTER_GOLD] == 1500

    def test_json_roundtrip(self) -> None:
        """Test JSON save/load roundtrip integrity"""
        original_state = CharacterStateFixtures.get_level_25_advanced()
        json_str = CharacterStateJSON.save_state_to_json(original_state, "test.json")
        loaded_state = CharacterStateJSON.load_state_from_json(json_str)

        # Compare all common keys
        for key, value in original_state.items():
            if key in loaded_state:
                assert (
                    loaded_state[key] == value
                ), f"Mismatch for {key}: {loaded_state[key]} != {value}"

    def test_load_state_invalid_keys(self) -> None:
        """Test loading state with invalid keys"""
        invalid_json = """
        {
            "character_state": {
                "character_level": 10,
                "invalid_key": "should_be_ignored"
            },
            "timestamp": "2024-01-01T00:00:00",
            "version": "1.0"
        }
        """

        loaded_state = CharacterStateJSON.load_state_from_json(invalid_json)

        # Should only contain valid keys
        assert GameState.CHARACTER_LEVEL in loaded_state
        assert loaded_state[GameState.CHARACTER_LEVEL] == 10

        # Invalid key should be ignored
        invalid_keys = [key for key in loaded_state.keys() if key.value == "invalid_key"]
        assert len(invalid_keys) == 0

    def test_get_all_test_states(self) -> None:
        """Test getting all test states as JSON strings"""
        all_states = CharacterStateJSON.get_all_test_states()

        assert isinstance(all_states, dict)
        expected_states = [
            "level_1_starter",
            "level_10_experienced",
            "level_25_advanced",
            "emergency_low_hp",
            "inventory_full",
            "character_on_cooldown",
            "resource_depleted",
            "wealthy_trader",
            "max_level_endgame",
        ]

        for state_name in expected_states:
            assert state_name in all_states
            assert isinstance(all_states[state_name], str)

            # Verify each JSON string is valid
            json_data = json.loads(all_states[state_name])
            assert "character_state" in json_data
            assert "timestamp" in json_data
            assert "version" in json_data


class TestConvenienceFunctions:
    """Test suite for convenience functions"""

    def test_get_test_character_state_default(self) -> None:
        """Test get_test_character_state with default scenario"""
        state = get_test_character_state()

        assert isinstance(state, dict)
        assert state[GameState.CHARACTER_LEVEL] == 10  # Default is level_10_experienced

    def test_get_test_character_state_specific_scenarios(self) -> None:
        """Test get_test_character_state with specific scenarios"""
        scenarios = [
            "level_1_starter",
            "level_10_experienced",
            "level_25_advanced",
            "emergency_low_hp",
            "inventory_full",
            "character_on_cooldown",
            "resource_depleted",
            "wealthy_trader",
            "max_level_endgame",
        ]

        for scenario in scenarios:
            state = get_test_character_state(scenario)
            assert isinstance(state, dict)
            assert len(state) > 0

    def test_get_test_character_state_invalid_scenario(self) -> None:
        """Test get_test_character_state with invalid scenario"""
        with pytest.raises(ValueError, match="Unknown scenario"):
            get_test_character_state("invalid_scenario")

    def test_get_test_cooldown_default(self) -> None:
        """Test get_test_cooldown with default scenario"""
        cooldown = get_test_cooldown()

        assert isinstance(cooldown, CooldownInfo)
        assert cooldown.character_name == "ready_character"  # Default is no_cooldown

    def test_get_test_cooldown_specific_scenarios(self) -> None:
        """Test get_test_cooldown with specific scenarios"""
        scenarios = ["no_cooldown", "short_cooldown", "medium_cooldown", "long_cooldown"]

        for scenario in scenarios:
            cooldown = get_test_cooldown(scenario)
            assert isinstance(cooldown, CooldownInfo)
            assert hasattr(cooldown, "character_name")

    def test_get_test_cooldown_invalid_scenario(self) -> None:
        """Test get_test_cooldown with invalid scenario"""
        with pytest.raises(ValueError, match="Unknown cooldown scenario"):
            get_test_cooldown("invalid_cooldown")

    def test_get_state_transition_sequence(self) -> None:
        """Test get_state_transition_sequence function"""
        sequence = get_state_transition_sequence()

        assert isinstance(sequence, list)
        assert len(sequence) == 4

        # Verify progression levels
        levels = [state[GameState.CHARACTER_LEVEL] for state in sequence]
        expected_levels = [1, 10, 25, 45]
        assert levels == expected_levels

        # Verify each state is a valid dict
        for state in sequence:
            assert isinstance(state, dict)
            assert GameState.CHARACTER_LEVEL in state
            assert GameState.CHARACTER_XP in state


class TestFixtureDataIntegrity:
    """Test suite for data integrity across fixtures"""

    def test_all_fixtures_have_required_fields(self) -> None:
        """Test that all fixtures have required GameState fields"""
        required_fields = [
            GameState.CHARACTER_LEVEL,
            GameState.CHARACTER_XP,
            GameState.CHARACTER_GOLD,
            GameState.HP_CURRENT,
            GameState.HP_MAX,
            GameState.CURRENT_X,
            GameState.CURRENT_Y,
        ]

        fixture_methods = [
            CharacterStateFixtures.get_level_1_starter,
            CharacterStateFixtures.get_level_10_experienced,
            CharacterStateFixtures.get_level_25_advanced,
            CharacterStateFixtures.get_emergency_low_hp,
            CharacterStateFixtures.get_inventory_full,
            CharacterStateFixtures.get_character_on_cooldown,
            CharacterStateFixtures.get_resource_depleted_area,
            CharacterStateFixtures.get_wealthy_trader,
            CharacterStateFixtures.get_max_level_endgame,
        ]

        for fixture_method in fixture_methods:
            state = fixture_method()
            for field in required_fields:
                assert field in state, f"Missing {field} in {fixture_method.__name__}"

    def test_hp_constraints(self) -> None:
        """Test HP constraints across all fixtures"""
        fixture_methods = [
            CharacterStateFixtures.get_level_1_starter,
            CharacterStateFixtures.get_level_10_experienced,
            CharacterStateFixtures.get_level_25_advanced,
            CharacterStateFixtures.get_emergency_low_hp,
            CharacterStateFixtures.get_inventory_full,
            CharacterStateFixtures.get_character_on_cooldown,
            CharacterStateFixtures.get_resource_depleted_area,
            CharacterStateFixtures.get_wealthy_trader,
            CharacterStateFixtures.get_max_level_endgame,
        ]

        for fixture_method in fixture_methods:
            state = fixture_method()
            hp_current = state[GameState.HP_CURRENT]
            hp_max = state[GameState.HP_MAX]

            assert (
                hp_current >= 0
            ), f"HP current cannot be negative in {fixture_method.__name__}"
            assert hp_max > 0, f"HP max must be positive in {fixture_method.__name__}"
            assert (
                hp_current <= hp_max
            ), f"HP current cannot exceed max in {fixture_method.__name__}"

    def test_level_constraints(self) -> None:
        """Test level constraints across all fixtures"""
        fixture_methods = [
            CharacterStateFixtures.get_level_1_starter,
            CharacterStateFixtures.get_level_10_experienced,
            CharacterStateFixtures.get_level_25_advanced,
            CharacterStateFixtures.get_emergency_low_hp,
            CharacterStateFixtures.get_inventory_full,
            CharacterStateFixtures.get_character_on_cooldown,
            CharacterStateFixtures.get_resource_depleted_area,
            CharacterStateFixtures.get_wealthy_trader,
            CharacterStateFixtures.get_max_level_endgame,
        ]

        for fixture_method in fixture_methods:
            state = fixture_method()
            char_level = state[GameState.CHARACTER_LEVEL]

            assert (
                1 <= char_level <= 45
            ), f"Character level out of range in {fixture_method.__name__}"

            # Check skill levels
            skill_states = [
                GameState.MINING_LEVEL,
                GameState.WOODCUTTING_LEVEL,
                GameState.FISHING_LEVEL,
                GameState.WEAPONCRAFTING_LEVEL,
                GameState.GEARCRAFTING_LEVEL,
                GameState.JEWELRYCRAFTING_LEVEL,
                GameState.COOKING_LEVEL,
                GameState.ALCHEMY_LEVEL,
            ]

            for skill_state in skill_states:
                if skill_state in state:
                    skill_level = state[skill_state]
                    assert (
                        1 <= skill_level <= 45
                    ), f"Skill level out of range in {fixture_method.__name__}"

    def test_inventory_constraints(self) -> None:
        """Test inventory constraints across all fixtures"""
        fixture_methods = [
            CharacterStateFixtures.get_level_1_starter,
            CharacterStateFixtures.get_level_10_experienced,
            CharacterStateFixtures.get_level_25_advanced,
            CharacterStateFixtures.get_emergency_low_hp,
            CharacterStateFixtures.get_inventory_full,
            CharacterStateFixtures.get_character_on_cooldown,
            CharacterStateFixtures.get_resource_depleted_area,
            CharacterStateFixtures.get_wealthy_trader,
            CharacterStateFixtures.get_max_level_endgame,
        ]

        for fixture_method in fixture_methods:
            state = fixture_method()

            if (
                GameState.INVENTORY_SPACE_AVAILABLE in state
                and GameState.INVENTORY_SPACE_USED in state
            ):
                available = state[GameState.INVENTORY_SPACE_AVAILABLE]
                used = state[GameState.INVENTORY_SPACE_USED]

                assert (
                    available >= 0
                ), f"Inventory available cannot be negative in {fixture_method.__name__}"
                assert (
                    used >= 0
                ), f"Inventory used cannot be negative in {fixture_method.__name__}"

                # Check inventory full consistency
                if GameState.INVENTORY_FULL in state:
                    inventory_full = state[GameState.INVENTORY_FULL]
                    if inventory_full:
                        assert (
                            available == 0
                        ), f"Inventory marked full but has space in {fixture_method.__name__}"


class TestFixtureConsistency:
    """Test suite for consistency between related fixtures"""

    def test_emergency_state_derived_from_experienced(self) -> None:
        """Test that emergency state is properly derived from experienced state"""
        base_state = CharacterStateFixtures.get_level_10_experienced()
        emergency_state = CharacterStateFixtures.get_emergency_low_hp()

        # Should preserve base character stats
        assert emergency_state[GameState.CHARACTER_LEVEL] == base_state[GameState.CHARACTER_LEVEL]
        assert emergency_state[GameState.CHARACTER_XP] == base_state[GameState.CHARACTER_XP]
        assert emergency_state[GameState.CHARACTER_GOLD] == base_state[GameState.CHARACTER_GOLD]

        # But modify emergency-specific states
        assert emergency_state[GameState.HP_CURRENT] == 15
        assert emergency_state[GameState.HP_LOW] is True
        assert emergency_state[GameState.HP_CRITICAL] is True

    def test_inventory_full_derived_from_experienced(self) -> None:
        """Test that inventory full state is properly derived from experienced state"""
        base_state = CharacterStateFixtures.get_level_10_experienced()
        inventory_full_state = CharacterStateFixtures.get_inventory_full()

        # Should preserve base character stats
        assert (
            inventory_full_state[GameState.CHARACTER_LEVEL]
            == base_state[GameState.CHARACTER_LEVEL]
        )
        assert (
            inventory_full_state[GameState.CHARACTER_XP] == base_state[GameState.CHARACTER_XP]
        )
        assert (
            inventory_full_state[GameState.CHARACTER_GOLD]
            == base_state[GameState.CHARACTER_GOLD]
        )

        # But modify inventory-specific states
        assert inventory_full_state[GameState.INVENTORY_SPACE_AVAILABLE] == 0
        assert inventory_full_state[GameState.INVENTORY_FULL] is True

    def test_wealthy_trader_derived_from_advanced(self) -> None:
        """Test that wealthy trader state is properly derived from advanced state"""
        base_state = CharacterStateFixtures.get_level_25_advanced()
        wealthy_state = CharacterStateFixtures.get_wealthy_trader()

        # Should preserve base character level
        assert wealthy_state[GameState.CHARACTER_LEVEL] == base_state[GameState.CHARACTER_LEVEL]

        # But modify wealth-specific states
        assert wealthy_state[GameState.CHARACTER_GOLD] == 50000
        assert wealthy_state[GameState.AT_GRAND_EXCHANGE] is True
        assert wealthy_state[GameState.ARBITRAGE_OPPORTUNITY] is True
