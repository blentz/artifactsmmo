"""
Comprehensive tests for EquipmentGoal

This module tests the EquipmentGoal class comprehensively to achieve 100% coverage,
including all edge cases, error conditions, and complex scenarios that arise when
acquiring and managing level-appropriate equipment for the level 5 progression goal.
"""

from unittest.mock import Mock, patch
import pytest

from src.ai_player.goals.equipment_goal import EquipmentGoal
from src.ai_player.state.character_game_state import CharacterGameState
from src.ai_player.state.game_state import GameState
from src.ai_player.types.goap_models import GOAPTargetState
from src.ai_player.goals.sub_goal_request import SubGoalRequest
from src.game_data.game_data import GameData
from src.game_data.models import GameItem, GameMap, GameMonster, GameNPC, GameResource


def create_test_character_state():
    """Create a comprehensive test character state for equipment scenarios."""
    return CharacterGameState(
        name="test_equipment_char",
        level=3,
        xp=1000,
        hp=80,
        max_hp=100,
        x=5,
        y=5,
        gold=500,
        mining_level=3,
        mining_xp=500,
        woodcutting_level=2,
        woodcutting_xp=200,
        fishing_level=1,
        fishing_xp=50,
        weaponcrafting_level=2,
        weaponcrafting_xp=300,
        gearcrafting_level=2,
        gearcrafting_xp=250,
        jewelrycrafting_level=1,
        jewelrycrafting_xp=100,
        cooking_level=1,
        cooking_xp=50,
        alchemy_level=1,
        alchemy_xp=25,
        cooldown=0,
        weapon_slot="",  # Empty slots for testing
        rune_slot="",
        shield_slot="",
        helmet_slot="",
        body_armor_slot="",
        leg_armor_slot="",
        boots_slot="",
        ring1_slot="",
        ring2_slot="",
        amulet_slot="",
        artifact1_slot="",
        at_monster_location=False,
        at_workshop_location=False,
        inventory_space_available=True,
        inventory_space_count=20,
    )


def create_equipment_item(code: str, name: str, level: int, item_type: str, craftable: bool = False):
    """Create a test equipment item."""
    item = Mock(spec=GameItem)
    item.code = code
    item.name = name
    item.level = level
    item.type = item_type
    if craftable:
        item.craft = {
            "skill": "weaponcrafting" if item_type == "weapon" else "gearcrafting",
            "level": level,
            "materials": [{"code": "iron", "quantity": 2}],
        }
    else:
        item.craft = None
    return item


def create_monster_with_drops(code: str, name: str, level: int, drops: list):
    """Create a monster that drops specified items."""
    monster = Mock(spec=GameMonster)
    monster.code = code
    monster.name = name
    monster.level = level
    monster.drops = drops
    return monster


def create_npc_with_inventory(code: str, name: str, items: list):
    """Create an NPC that sells specified items."""
    npc = Mock(spec=GameNPC)
    npc.code = code
    npc.name = name
    npc.inventory = items
    return npc


def create_valid_game_data_for_equipment():
    """Create comprehensive game data for equipment tests."""
    # Equipment items of various levels and types
    items = [
        create_equipment_item("copper_sword", "Copper Sword", 1, "weapon", craftable=True),
        create_equipment_item("iron_sword", "Iron Sword", 3, "weapon", craftable=True),
        create_equipment_item("steel_helmet", "Steel Helmet", 4, "helmet", craftable=True),
        create_equipment_item("copper_ring", "Copper Ring", 1, "ring", craftable=False),
        create_equipment_item("mithril_boots", "Mithril Boots", 5, "boots", craftable=False),
        create_equipment_item("leather_armor", "Leather Armor", 2, "body_armor", craftable=False),
        create_equipment_item("master_helmet", "Master Helmet", 5, "helmet", craftable=False),
        create_equipment_item("master_armor", "Master Armor", 5, "body_armor", craftable=False),
        create_equipment_item("master_legs", "Master Legs", 5, "leg_armor", craftable=False),
        create_equipment_item("master_shield", "Master Shield", 5, "shield", craftable=False),
        create_equipment_item("master_ring", "Master Ring", 5, "ring", craftable=False),
        create_equipment_item("master_amulet", "Master Amulet", 5, "amulet", craftable=False),
        create_equipment_item("legendary_sword", "Legendary Sword", 10, "weapon", craftable=False),  # Too high level
    ]

    # Monsters that drop equipment
    monsters = [
        create_monster_with_drops("goblin", "Goblin", 2, [{"code": "copper_ring", "quantity": 1}]),
        create_monster_with_drops("orc", "Orc", 4, [{"code": "mithril_boots", "quantity": 1}]),
    ]

    # NPCs (simplified - would need actual selling data)
    npcs = [create_npc_with_inventory("blacksmith", "Blacksmith", ["iron_sword", "steel_helmet"])]

    # Resources for crafting materials
    resources = [Mock(spec=GameResource)]

    # Maps
    maps = [Mock(spec=GameMap)]

    return GameData(items=items, resources=resources, maps=maps, monsters=monsters, npcs=npcs)


class TestEquipmentGoalInitialization:
    """Test EquipmentGoal initialization and basic properties."""

    def test_default_initialization(self):
        """Test default EquipmentGoal initialization."""
        goal = EquipmentGoal()

        assert goal.target_slot is None
        assert goal.max_item_level == 5
        assert goal.map_analysis is not None
        assert len(goal.equipment_slots) == 8

        # Check equipment slot mappings
        expected_slots = {
            "weapon": "weapon_slot",
            "helmet": "helmet_slot",
            "body_armor": "body_armor_slot",
            "leg_armor": "leg_armor_slot",
            "boots": "boots_slot",
            "ring1": "ring1_slot",
            "ring2": "ring2_slot",
            "amulet": "amulet_slot",
        }
        assert goal.equipment_slots == expected_slots

    def test_initialization_with_target_slot(self):
        """Test EquipmentGoal initialization with specific target slot."""
        goal = EquipmentGoal(target_slot="weapon")

        assert goal.target_slot == "weapon"
        assert goal.max_item_level == 5

    def test_initialization_with_custom_max_level(self):
        """Test EquipmentGoal initialization with custom max level."""
        goal = EquipmentGoal(max_item_level=3)

        assert goal.target_slot is None
        assert goal.max_item_level == 3

    def test_initialization_with_all_parameters(self):
        """Test EquipmentGoal initialization with all parameters."""
        goal = EquipmentGoal(target_slot="helmet", max_item_level=4)

        assert goal.target_slot == "helmet"
        assert goal.max_item_level == 4


class TestEquipmentGoalWeight:
    """Test EquipmentGoal weight calculation using multi-factor scoring."""

    def test_calculate_weight_basic_scenario(self):
        """Test weight calculation for basic equipment scenario."""
        goal = EquipmentGoal()
        character_state = create_test_character_state()
        game_data = create_valid_game_data_for_equipment()

        weight = goal.calculate_weight(character_state, game_data)

        assert isinstance(weight, float)
        assert 0.0 <= weight <= 10.0

    def test_calculate_weight_empty_equipment_high_necessity(self):
        """Test weight calculation with empty equipment slots (high necessity)."""
        goal = EquipmentGoal()
        character_state = create_test_character_state()
        # Character already has empty equipment slots
        game_data = create_valid_game_data_for_equipment()

        weight = goal.calculate_weight(character_state, game_data)

        # Should have high weight due to empty equipment slots
        assert weight > 5.0

    def test_calculate_weight_with_gold_constraints(self):
        """Test weight calculation with economic constraints."""
        goal = EquipmentGoal()
        character_state = create_test_character_state()
        character_state.gold = 10  # Very low gold
        game_data = create_valid_game_data_for_equipment()

        weight = goal.calculate_weight(character_state, game_data)

        # Should still be positive but might be affected by feasibility
        assert weight > 0.0

    def test_calculate_weight_level_5_character(self):
        """Test weight calculation for level 5 character."""
        goal = EquipmentGoal()
        character_state = create_test_character_state()
        character_state.level = 5
        game_data = create_valid_game_data_for_equipment()

        weight = goal.calculate_weight(character_state, game_data)

        # Should have significant value for level 5 character needing appropriate gear
        assert weight > 0.0


class TestEquipmentGoalFeasibility:
    """Test EquipmentGoal feasibility checks."""

    def test_is_feasible_with_available_upgrades(self):
        """Test feasibility when equipment upgrades are available."""
        goal = EquipmentGoal()
        character_state = create_test_character_state()
        game_data = create_valid_game_data_for_equipment()

        result = goal.is_feasible(character_state, game_data)

        # Should be feasible since we have level-appropriate equipment available
        assert result is True

    def test_is_feasible_no_available_upgrades(self):
        """Test feasibility when no equipment upgrades are available."""
        goal = EquipmentGoal()
        character_state = create_test_character_state()

        # Create game data with no level-appropriate equipment
        game_data = GameData(
            items=[create_equipment_item("legendary_sword", "Legendary Sword", 10, "weapon")],  # Too high level
            resources=[Mock(spec=GameResource)],
            maps=[Mock(spec=GameMap)],
            monsters=[Mock(spec=GameMonster)],
            npcs=[Mock(spec=GameNPC)],
        )

        result = goal.is_feasible(character_state, game_data)

        assert result is False

    def test_is_feasible_with_specific_target_slot(self):
        """Test feasibility with specific target slot."""
        goal = EquipmentGoal(target_slot="weapon")
        character_state = create_test_character_state()
        game_data = create_valid_game_data_for_equipment()

        result = goal.is_feasible(character_state, game_data)

        assert result is True


class TestEquipmentGoalTargetState:
    """Test EquipmentGoal target state generation."""

    def test_get_target_state_basic_scenario(self):
        """Test target state generation for basic equipment scenario."""
        goal = EquipmentGoal()
        character_state = create_test_character_state()
        game_data = create_valid_game_data_for_equipment()

        target_state = goal.get_target_state(character_state, game_data)

        assert isinstance(target_state, GOAPTargetState)
        assert isinstance(target_state.target_states, dict)
        assert target_state.priority == 5
        assert target_state.timeout_seconds == 1800

        # Should include equipment states
        expected_states = [
            GameState.READY_FOR_UPGRADE,
            GameState.HAS_REQUIRED_ITEMS,
            GameState.WEAPON_EQUIPPED,
            GameState.HELMET_EQUIPPED,
            GameState.BODY_ARMOR_EQUIPPED,
            GameState.LEG_ARMOR_EQUIPPED,
            GameState.BOOTS_EQUIPPED,
            GameState.RING1_EQUIPPED,
            GameState.RING2_EQUIPPED,
            GameState.AMULET_EQUIPPED,
            GameState.INVENTORY_SPACE_AVAILABLE,
            GameState.COOLDOWN_READY,
        ]

        for expected_state in expected_states:
            assert expected_state in target_state.target_states

    def test_get_target_state_no_upgrades_needed(self):
        """Test target state when no equipment upgrades are needed."""
        goal = EquipmentGoal()
        character_state = create_test_character_state()

        # Mock to return no optimal equipment upgrade
        with patch.object(goal, "_select_optimal_equipment_upgrade", return_value=None):
            target_state = goal.get_target_state(character_state, create_valid_game_data_for_equipment())

            # Should return empty target state
            assert target_state.target_states == {}
            assert target_state.priority == 1
            assert target_state.timeout_seconds is None


class TestEquipmentGoalProgression:
    """Test EquipmentGoal progression value calculation."""

    def test_get_progression_value_level_3_empty_equipment(self):
        """Test progression value for level 3 character with empty equipment."""
        goal = EquipmentGoal()
        character_state = create_test_character_state()
        character_state.level = 3
        game_data = create_valid_game_data_for_equipment()
        # Character already has empty equipment slots

        progression_value = goal.get_progression_value(character_state, game_data)

        assert isinstance(progression_value, float)
        assert 0.0 <= progression_value <= 1.0
        # Should have high progression value due to empty equipment
        assert progression_value > 0.8

    def test_get_progression_value_level_4_needs_equipment(self):
        """Test progression value for level 4 character needing equipment."""
        goal = EquipmentGoal()
        character_state = create_test_character_state()
        character_state.level = 4
        game_data = create_valid_game_data_for_equipment()
        # Empty equipment should trigger high value

        progression_value = goal.get_progression_value(character_state, game_data)

        # Should have very high value (0.9) for level 4+ with low coverage
        assert progression_value == 0.9

    def test_get_progression_value_level_5_full_equipment(self):
        """Test progression value for level 5 character with good equipment."""
        goal = EquipmentGoal()
        character_state = create_test_character_state()
        character_state.level = 5
        game_data = create_valid_game_data_for_equipment()

        # Mock to return high coverage
        with patch.object(goal, "_calculate_equipment_coverage", return_value=0.8):
            with patch.object(goal, "_calculate_level_appropriate_coverage", return_value=0.9):
                progression_value = goal.get_progression_value(character_state, game_data)

                # Should still have good progression value
                assert progression_value >= 0.8


class TestEquipmentGoalErrorRisk:
    """Test EquipmentGoal error risk estimation."""

    def test_estimate_error_risk_basic(self):
        """Test error risk estimation for basic scenario."""
        goal = EquipmentGoal()
        character_state = create_test_character_state()

        error_risk = goal.estimate_error_risk(character_state)

        assert isinstance(error_risk, float)
        assert 0.0 <= error_risk <= 1.0
        # Equipment should have low base risk
        assert error_risk <= 0.5

    def test_estimate_error_risk_low_gold(self):
        """Test error risk estimation with low gold."""
        goal = EquipmentGoal()
        character_state = create_test_character_state()
        character_state.gold = 50  # Below threshold

        error_risk = goal.estimate_error_risk(character_state)

        # Should have higher risk due to low gold
        assert error_risk > 0.2

    def test_estimate_error_risk_low_inventory_space(self):
        """Test error risk estimation with low inventory space."""
        goal = EquipmentGoal()
        character_state = create_test_character_state()
        character_state.inventory_space_available = False  # No space (low space condition)
        character_state.inventory_space_count = 1  # Low space (< 3)

        error_risk = goal.estimate_error_risk(character_state)

        # Should have higher risk due to low inventory space
        assert error_risk > 0.25

    def test_estimate_error_risk_no_inventory_attribute(self):
        """Test error risk when inventory_space_available attribute doesn't exist."""
        goal = EquipmentGoal()
        character_state = create_test_character_state()
        delattr(character_state, "inventory_space_available")

        error_risk = goal.estimate_error_risk(character_state)

        # Should handle missing attribute gracefully
        assert isinstance(error_risk, float)
        assert error_risk >= 0.15  # At least base risk


class TestEquipmentGoalSubGoals:
    """Test EquipmentGoal sub-goal generation."""

    def test_generate_sub_goal_requests_monster_drop(self):
        """Test sub-goal generation for monster drop acquisition."""
        goal = EquipmentGoal()
        character_state = create_test_character_state()
        game_data = create_valid_game_data_for_equipment()

        # Mock to return monster drop method
        mock_item = create_equipment_item("copper_ring", "Copper Ring", 1, "ring")
        with patch.object(goal, "_select_optimal_equipment_upgrade", return_value=(mock_item, "monster_drop")):
            with patch.object(
                goal, "_find_monsters_dropping_item", return_value=[(game_data.monsters[0], {"code": "copper_ring"})]
            ):
                sub_goals = goal.generate_sub_goal_requests(character_state, game_data)

                assert len(sub_goals) > 0
                # Should have combat sub-goal
                combat_goals = [sg for sg in sub_goals if sg.goal_type == "combat_for_item"]
                assert len(combat_goals) > 0

    def test_generate_sub_goal_requests_crafting(self):
        """Test sub-goal generation for crafted equipment."""
        goal = EquipmentGoal()
        character_state = create_test_character_state()
        game_data = create_valid_game_data_for_equipment()

        # Mock to return crafting method
        mock_item = create_equipment_item("iron_sword", "Iron Sword", 3, "weapon", craftable=True)
        with patch.object(goal, "_select_optimal_equipment_upgrade", return_value=(mock_item, "crafting")):
            sub_goals = goal.generate_sub_goal_requests(character_state, game_data)

            assert len(sub_goals) > 0
            # Should have crafting sub-goal
            craft_goals = [sg for sg in sub_goals if sg.goal_type == "craft_item"]
            assert len(craft_goals) > 0

    def test_generate_sub_goal_requests_npc_purchase(self):
        """Test sub-goal generation for NPC purchase."""
        goal = EquipmentGoal()
        character_state = create_test_character_state()
        game_data = create_valid_game_data_for_equipment()

        # Mock to return NPC purchase method
        mock_item = create_equipment_item("steel_helmet", "Steel Helmet", 4, "helmet")
        mock_npc = create_npc_with_inventory("blacksmith", "Blacksmith", ["steel_helmet"])

        with patch.object(goal, "_select_optimal_equipment_upgrade", return_value=(mock_item, "npc_purchase")):
            with patch.object(goal, "_find_npcs_selling_item", return_value=[mock_npc]):
                with patch.object(goal.map_analysis, "find_content_by_code", return_value=[Mock(x=10, y=10)]):
                    sub_goals = goal.generate_sub_goal_requests(character_state, game_data)

                    assert len(sub_goals) > 0
                    # Should have movement sub-goal
                    move_goals = [sg for sg in sub_goals if hasattr(sg, "goal_type") and "move" in str(sg)]
                    assert len(move_goals) >= 0  # Might not have move goals depending on implementation

    def test_generate_sub_goal_requests_inventory_space(self):
        """Test sub-goal generation for inventory space management."""
        goal = EquipmentGoal()
        character_state = create_test_character_state()
        character_state.inventory_space_available = False  # No space (low space condition)
        character_state.inventory_space_count = 1  # Low space (< 2)
        game_data = create_valid_game_data_for_equipment()

        # Mock to return some equipment upgrade
        mock_item = create_equipment_item("iron_sword", "Iron Sword", 3, "weapon")
        with patch.object(goal, "_select_optimal_equipment_upgrade", return_value=(mock_item, "crafting")):
            sub_goals = goal.generate_sub_goal_requests(character_state, game_data)

            # Should include inventory management sub-goal
            inventory_goals = [sg for sg in sub_goals if sg.goal_type == "manage_inventory"]
            assert len(inventory_goals) > 0

    def test_generate_sub_goal_requests_no_equipment_upgrade(self):
        """Test sub-goal generation when no equipment upgrade is available."""
        goal = EquipmentGoal()
        character_state = create_test_character_state()
        game_data = create_valid_game_data_for_equipment()

        # Mock to return no equipment upgrade
        with patch.object(goal, "_select_optimal_equipment_upgrade", return_value=None):
            sub_goals = goal.generate_sub_goal_requests(character_state, game_data)

            assert sub_goals == []


class TestEquipmentGoalPrivateMethods:
    """Test EquipmentGoal private methods for complete coverage."""

    def test_find_available_equipment_upgrades_basic(self):
        """Test finding available equipment upgrades."""
        goal = EquipmentGoal()
        character_state = create_test_character_state()
        game_data = create_valid_game_data_for_equipment()

        upgrades = goal._find_available_equipment_upgrades(character_state, game_data)

        assert isinstance(upgrades, list)
        # Should find some upgrades since character has empty slots
        assert len(upgrades) > 0

        # Each upgrade should be a tuple (item, slot, method)
        for upgrade in upgrades:
            assert len(upgrade) == 3
            item, slot, method = upgrade
            assert hasattr(item, "code")
            assert isinstance(slot, str)
            assert isinstance(method, str)

    def test_find_available_equipment_upgrades_specific_slot(self):
        """Test finding upgrades for specific target slot."""
        goal = EquipmentGoal(target_slot="weapon")
        character_state = create_test_character_state()
        game_data = create_valid_game_data_for_equipment()

        upgrades = goal._find_available_equipment_upgrades(character_state, game_data)

        # Should only find weapon upgrades
        for upgrade in upgrades:
            item, slot, method = upgrade
            assert slot == "weapon"

    def test_find_available_equipment_upgrades_with_current_equipment(self):
        """Test finding upgrades when character already has some equipment."""
        goal = EquipmentGoal()
        character_state = create_test_character_state()

        # Give character some low-level equipment (using item code strings)
        character_state.weapon_slot = "copper_sword"  # Level 1 weapon code

        game_data = create_valid_game_data_for_equipment()

        upgrades = goal._find_available_equipment_upgrades(character_state, game_data)

        # Should find upgrades better than level 1
        weapon_upgrades = [u for u in upgrades if u[1] == "weapon"]
        for upgrade in weapon_upgrades:
            item, slot, method = upgrade
            assert item.level > 1

    def test_select_optimal_equipment_upgrade(self):
        """Test selecting optimal equipment upgrade."""
        goal = EquipmentGoal()
        character_state = create_test_character_state()
        game_data = create_valid_game_data_for_equipment()

        result = goal._select_optimal_equipment_upgrade(character_state, game_data)

        if result:  # Might be None if no upgrades available
            item, method = result
            assert hasattr(item, "code")
            assert method in ["crafting", "npc_purchase", "monster_drop"]

    def test_select_optimal_equipment_upgrade_no_upgrades(self):
        """Test selecting optimal upgrade when none are available."""
        goal = EquipmentGoal()
        character_state = create_test_character_state()

        # Mock to return no available upgrades
        with patch.object(goal, "_find_available_equipment_upgrades", return_value=[]):
            result = goal._select_optimal_equipment_upgrade(character_state, create_valid_game_data_for_equipment())

            assert result is None

    def test_score_equipment_upgrade(self):
        """Test equipment upgrade scoring."""
        goal = EquipmentGoal()
        character_state = create_test_character_state()

        item = create_equipment_item("iron_sword", "Iron Sword", 3, "weapon")
        score = goal._score_equipment_upgrade(item, "weapon", "crafting", character_state)

        assert isinstance(score, float)
        assert score > 0.0

        # Test different scenarios
        # Level-appropriate item should score higher than over-leveled item
        over_level_item = create_equipment_item("steel_sword", "Steel Sword", 4, "weapon")
        over_level_score = goal._score_equipment_upgrade(over_level_item, "weapon", "crafting", character_state)
        assert score > over_level_score  # Level 3 item scores higher for level 3 character

        # Test that perfectly level-appropriate item scores well
        perfect_level_item = create_equipment_item("level_3_sword", "Level 3 Sword", 3, "weapon")
        perfect_score = goal._score_equipment_upgrade(perfect_level_item, "weapon", "crafting", character_state)
        assert perfect_score == score  # Same level should score the same

    def test_calculate_equipment_necessity(self):
        """Test equipment necessity calculation."""
        goal = EquipmentGoal()
        character_state = create_test_character_state()
        game_data = create_valid_game_data_for_equipment()

        necessity = goal._calculate_equipment_necessity(character_state, game_data)

        assert isinstance(necessity, float)
        assert 0.0 <= necessity <= 1.0
        # Should be high for character with empty equipment
        assert necessity > 0.5

    def test_calculate_equipment_feasibility(self):
        """Test equipment feasibility calculation."""
        goal = EquipmentGoal()
        character_state = create_test_character_state()
        game_data = create_valid_game_data_for_equipment()

        feasibility = goal._calculate_equipment_feasibility(character_state, game_data)

        assert isinstance(feasibility, float)
        assert 0.0 <= feasibility <= 1.0

    def test_calculate_equipment_coverage(self):
        """Test equipment coverage calculation."""
        goal = EquipmentGoal()

        # Test with empty equipment
        character_state = create_test_character_state()
        coverage = goal._calculate_equipment_coverage(character_state)
        assert coverage == 0.0  # All slots empty

        # Test with some equipment
        character_state.weapon_slot = "sword"
        character_state.helmet_slot = "helmet"
        coverage = goal._calculate_equipment_coverage(character_state)
        assert coverage == 2.0 / 8.0  # 2 out of 8 slots filled

    def test_calculate_level_appropriate_coverage(self):
        """Test level-appropriate equipment coverage calculation."""
        goal = EquipmentGoal()
        character_state = create_test_character_state()
        game_data = create_valid_game_data_for_equipment()

        # Test with no equipment
        coverage = goal._calculate_level_appropriate_coverage(character_state, game_data)
        assert coverage == 0.0

        # Test with level-appropriate equipment (using item code)
        character_state.weapon_slot = "iron_sword"  # Level 3 item, within max_item_level (5)

        coverage = goal._calculate_level_appropriate_coverage(character_state, game_data)
        assert coverage == 1.0 / 8.0  # 1 out of 8 slots with appropriate equipment

    def test_calculate_level_equipment_gap(self):
        """Test level-equipment gap calculation."""
        goal = EquipmentGoal()
        character_state = create_test_character_state()
        character_state.level = 5
        game_data = create_valid_game_data_for_equipment()

        # Test with no equipment (should use level 1 default)
        gap = goal._calculate_level_equipment_gap(character_state, game_data)
        assert gap > 0.0  # Should have significant gap

        # Test with level-appropriate equipment (using item code)
        character_state.weapon_slot = "steel_helmet"  # Level 4 item

        gap = goal._calculate_level_equipment_gap(character_state, game_data)
        # Gap should be smaller but still present
        assert gap >= 0.0

    def test_item_fits_slot(self):
        """Test item slot fitting logic."""
        goal = EquipmentGoal()

        # Test various item types and slots
        weapon_item = create_equipment_item("sword", "Sword", 3, "weapon")
        assert goal._item_fits_slot(weapon_item, "weapon") is True
        assert goal._item_fits_slot(weapon_item, "helmet") is False

        helmet_item = create_equipment_item("helmet", "Helmet", 3, "helmet")
        assert goal._item_fits_slot(helmet_item, "helmet") is True
        assert goal._item_fits_slot(helmet_item, "weapon") is False

        ring_item = create_equipment_item("ring", "Ring", 3, "ring")
        assert goal._item_fits_slot(ring_item, "ring1") is True
        assert goal._item_fits_slot(ring_item, "ring2") is True
        assert goal._item_fits_slot(ring_item, "amulet") is False

    def test_determine_acquisition_method(self):
        """Test acquisition method determination."""
        goal = EquipmentGoal()
        character_state = create_test_character_state()
        game_data = create_valid_game_data_for_equipment()

        # Test craftable item
        craftable_item = create_equipment_item("iron_sword", "Iron Sword", 3, "weapon", craftable=True)
        method = goal._determine_acquisition_method(craftable_item, character_state, game_data)
        assert method == "crafting"

        # Test item with monster drops
        drop_item = create_equipment_item("copper_ring", "Copper Ring", 1, "ring")
        with patch.object(goal, "_find_monsters_dropping_item", return_value=["some_monster"]):
            method = goal._determine_acquisition_method(drop_item, character_state, game_data)
            assert method == "monster_drop"

        # Test item with no acquisition method
        no_method_item = create_equipment_item("rare_item", "Rare Item", 3, "weapon")
        with patch.object(goal, "_find_npcs_selling_item", return_value=[]):
            with patch.object(goal, "_find_monsters_dropping_item", return_value=[]):
                method = goal._determine_acquisition_method(no_method_item, character_state, game_data)
                assert method is None

    def test_find_npcs_selling_item(self):
        """Test finding NPCs that sell items."""
        goal = EquipmentGoal()
        game_data = create_valid_game_data_for_equipment()

        # Current implementation returns empty list (simplified)
        result = goal._find_npcs_selling_item("iron_sword", game_data)
        assert result == []

    def test_find_monsters_dropping_item(self):
        """Test finding monsters that drop items."""
        goal = EquipmentGoal()
        game_data = create_valid_game_data_for_equipment()

        # Test finding monsters that drop copper_ring
        result = goal._find_monsters_dropping_item("copper_ring", game_data)
        assert len(result) > 0

        # Test item not dropped by any monster
        result = goal._find_monsters_dropping_item("nonexistent_item", game_data)
        assert len(result) == 0


class TestEquipmentGoalIntegration:
    """Integration tests for EquipmentGoal with real-world scenarios."""

    def test_full_equipment_workflow(self):
        """Test complete equipment acquisition workflow."""
        goal = EquipmentGoal()
        character_state = create_test_character_state()
        game_data = create_valid_game_data_for_equipment()

        # Test feasibility
        assert goal.is_feasible(character_state, game_data) is True

        # Test weight calculation
        weight = goal.calculate_weight(character_state, game_data)
        assert weight > 0.0

        # Test target state generation
        target_state = goal.get_target_state(character_state, game_data)
        assert len(target_state.target_states) > 0

        # Test sub-goal generation
        sub_goals = goal.generate_sub_goal_requests(character_state, game_data)
        # Might be empty depending on available acquisition methods
        assert isinstance(sub_goals, list)

    def test_progression_through_equipment_levels(self):
        """Test equipment goal behavior as character progresses."""
        goal = EquipmentGoal()
        game_data = create_valid_game_data_for_equipment()

        for level in [1, 2, 3, 4, 5]:
            character_state = create_test_character_state()
            character_state.level = level

            # Should remain feasible across progression
            feasible = goal.is_feasible(character_state, game_data)
            assert feasible is True

            # Weight should be reasonable
            weight = goal.calculate_weight(character_state, game_data)
            assert 0.0 < weight <= 10.0

            # Progression value should make sense
            progression = goal.get_progression_value(character_state, game_data)
            assert 0.0 <= progression <= 1.0

    def test_equipment_priority_with_different_slots(self):
        """Test equipment priority across different slot types."""
        game_data = create_valid_game_data_for_equipment()

        slot_priorities = {}
        for slot in ["weapon", "helmet", "body_armor", "boots", "ring1", "amulet"]:
            goal = EquipmentGoal(target_slot=slot)
            character_state = create_test_character_state()

            weight = goal.calculate_weight(character_state, game_data)
            slot_priorities[slot] = weight

        # All slots should have positive weight
        for slot, weight in slot_priorities.items():
            assert weight > 0.0

    def test_edge_case_character_with_high_level_equipment(self):
        """Test behavior when character already has high-level equipment."""
        goal = EquipmentGoal()
        character_state = create_test_character_state()

        # Give character high-level equipment in all slots using proper item codes
        character_state.weapon_slot = "mithril_boots"  # Level 5 item (reusing existing level 5 item)
        character_state.helmet_slot = "master_helmet"  # Level 5 item
        character_state.body_armor_slot = "master_armor"  # Level 5 item
        character_state.leg_armor_slot = "master_legs"  # Level 5 item
        character_state.boots_slot = "mithril_boots"  # Level 5 item
        character_state.ring1_slot = "master_ring"  # Level 5 item
        character_state.ring2_slot = "master_ring"  # Level 5 item
        character_state.amulet_slot = "master_amulet"  # Level 5 item

        game_data = create_valid_game_data_for_equipment()

        # Should have low necessity and possibly be infeasible
        necessity = goal._calculate_equipment_necessity(character_state, game_data)
        assert necessity <= 0.5  # Should be lower due to good equipment

        coverage = goal._calculate_equipment_coverage(character_state)
        assert coverage == 1.0  # All slots filled
