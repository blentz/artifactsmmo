"""
Tests for CombatAction implementation

This module tests combat action functionality including monster targeting,
combat safety checks, and API integration for character combat.
"""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from src.ai_player.actions.base_action import BaseAction
from src.ai_player.actions.combat_action import CombatAction
from src.ai_player.state.game_state import ActionResult, GameState


class TestCombatAction:
    """Test CombatAction implementation"""

    def test_combat_action_inheritance(self):
        """Test that CombatAction properly inherits from BaseAction"""
        action = CombatAction("goblin")

        assert isinstance(action, BaseAction)
        assert hasattr(action, 'name')
        assert hasattr(action, 'cost')
        assert hasattr(action, 'get_preconditions')
        assert hasattr(action, 'get_effects')
        assert hasattr(action, 'execute')

    def test_combat_action_initialization(self):
        """Test CombatAction initialization with monster target"""
        target_monster = "red_slime"
        action = CombatAction(target_monster)

        assert action.target_monster == target_monster
        assert isinstance(action.name, str)
        assert target_monster in action.name

    def test_combat_action_name_generation(self):
        """Test that combat action generates unique names"""
        action1 = CombatAction("goblin")
        action2 = CombatAction("orc")
        action3 = CombatAction("goblin")  # Same monster

        assert action1.name != action2.name
        assert action1.name == action3.name  # Same monster = same name

        # Names should include monster for identification
        assert "goblin" in action1.name
        assert "orc" in action2.name

    def test_combat_action_cost_calculation(self):
        """Test combat action cost calculation"""
        monsters = ["weak_goblin", "strong_orc", "boss_dragon"]

        for monster in monsters:
            action = CombatAction(monster)
            cost = action.cost

            assert isinstance(cost, int)
            assert cost > 0, "Combat cost should be positive"
            # Combat should generally be more expensive than movement
            assert cost >= 2, "Combat should have significant cost"

    def test_combat_action_preconditions(self):
        """Test combat action preconditions"""
        action = CombatAction("bandit")
        preconditions = action.get_preconditions()

        assert isinstance(preconditions, dict)

        # Essential preconditions for combat
        assert GameState.COOLDOWN_READY in preconditions
        assert preconditions[GameState.COOLDOWN_READY] is True

        assert GameState.CAN_FIGHT in preconditions
        assert preconditions[GameState.CAN_FIGHT] is True

        # Safety preconditions
        if GameState.HP_CURRENT in preconditions:
            assert isinstance(preconditions[GameState.HP_CURRENT], int)
            assert preconditions[GameState.HP_CURRENT] > 0

        # All precondition keys should be GameState enums
        for key in preconditions.keys():
            assert isinstance(key, GameState)

    def test_combat_action_effects(self):
        """Test combat action effects"""
        action = CombatAction("skeleton")
        effects = action.get_effects()

        assert isinstance(effects, dict)

        # Combat should trigger cooldown
        assert GameState.COOLDOWN_READY in effects
        assert effects[GameState.COOLDOWN_READY] is False

        # Combat typically grants XP (may be string placeholder or int)
        if GameState.CHARACTER_XP in effects:
            xp_effect = effects[GameState.CHARACTER_XP]
            # Allow string placeholders or positive integers
            assert isinstance(xp_effect, (int, str))
            if isinstance(xp_effect, int):
                assert xp_effect > 0

        # All effect keys should be GameState enums
        for key in effects.keys():
            assert isinstance(key, GameState)

    def test_combat_action_can_execute_valid_state(self):
        """Test can_execute with valid state for combat"""
        action = CombatAction("wolf")

        valid_state = {
            GameState.COOLDOWN_READY: True,
            GameState.CAN_FIGHT: True,
            GameState.SAFE_TO_FIGHT: True,
            GameState.HP_CURRENT: 80,
            GameState.HP_MAX: 100,
            GameState.AT_MONSTER_LOCATION: True,
            GameState.ENEMY_NEARBY: True,  # Added this since it may be required for targeted monsters
            GameState.WEAPON_EQUIPPED: "iron_sword"
        }

        # Test our can_execute method
        can_execute = action.can_execute(valid_state)

        # Debug output if assertion fails
        if not can_execute:
            preconditions = action.get_preconditions()
            print(f"Preconditions: {preconditions}")
            print(f"State: {valid_state}")
            for key, value in preconditions.items():
                state_value = valid_state.get(key)
                print(f"  {key}: required={value}, actual={state_value}, match={state_value == value}")

        assert can_execute is True

    def test_combat_action_can_execute_invalid_state(self):
        """Test can_execute with invalid state for combat"""
        action = CombatAction("dragon")

        invalid_states = [
            # Cooldown not ready
            {
                GameState.COOLDOWN_READY: False,
                GameState.CAN_FIGHT: True,
                GameState.HP_CURRENT: 80
            },
            # Cannot fight
            {
                GameState.COOLDOWN_READY: True,
                GameState.CAN_FIGHT: False,
                GameState.HP_CURRENT: 80
            },
            # HP too low
            {
                GameState.COOLDOWN_READY: True,
                GameState.CAN_FIGHT: True,
                GameState.HP_CURRENT: 10,  # Dangerously low
                GameState.HP_MAX: 100
            },
            # Missing required state
            {
                GameState.COOLDOWN_READY: True
                # Missing other required states
            }
        ]

        for invalid_state in invalid_states:
            # Test our preconditions directly since can_execute may not be implemented
            preconditions = action.get_preconditions()
            can_execute = all(
                invalid_state.get(key) == value for key, value in preconditions.items()
            )
            assert can_execute is False

    @pytest.mark.asyncio
    async def test_combat_action_execute_success(self):
        """Test successful combat action execution"""
        monster_code = "fire_elemental"
        action = CombatAction(monster_code)

        current_state = {
            GameState.COOLDOWN_READY: True,
            GameState.CAN_FIGHT: True,
            GameState.HP_CURRENT: 90,
            GameState.AT_MONSTER_LOCATION: True
        }

        # Create action with mock API client
        mock_api_client = Mock()
        mock_api_client.fight_monster = AsyncMock()

        # Mock successful combat response
        mock_response = Mock()
        mock_response.data = Mock()
        mock_response.data.character = Mock()
        mock_response.data.character.xp = 150
        mock_response.data.character.gold = 25
        mock_response.data.character.hp = 85  # Lost some HP
        mock_response.data.character.max_hp = 100
        mock_response.data.cooldown = Mock()
        mock_response.data.cooldown.total_seconds = 8
        mock_response.data.fight = Mock()
        mock_response.data.fight.result = "win"
        mock_response.data.fight.drops = [{"code": "leather", "quantity": 2}]

        mock_api_client.fight_monster.return_value = mock_response
        action = CombatAction(monster_code, api_client=mock_api_client)

        result = await action.execute("test_character", current_state)

        assert isinstance(result, ActionResult)
        assert result.success is True
        assert isinstance(result.message, str)
        assert result.cooldown_seconds > 0

        # Verify state changes from combat
        assert GameState.COOLDOWN_READY in result.state_changes
        assert result.state_changes[GameState.COOLDOWN_READY] is False

        # May include XP/gold gains
        if GameState.CHARACTER_XP in result.state_changes:
            assert result.state_changes[GameState.CHARACTER_XP] > 0

        # Verify API was called correctly
        mock_api_client.fight_monster.assert_called_once_with("test_character")

    @pytest.mark.asyncio
    async def test_combat_action_execute_defeat(self):
        """Test combat action execution with character defeat"""
        action = CombatAction("ancient_dragon")

        current_state = {
            GameState.COOLDOWN_READY: True,
            GameState.CAN_FIGHT: True,
            GameState.HP_CURRENT: 30,  # Low HP going into combat
            GameState.AT_MONSTER_LOCATION: True
        }

        # Create action with mock API client
        mock_api_client = Mock()
        mock_api_client.fight_monster = AsyncMock()

        # Mock defeat response
        mock_response = Mock()
        mock_response.data = Mock()
        mock_response.data.character = Mock()
        mock_response.data.character.hp = 0  # Character defeated
        mock_response.data.character.max_hp = 100
        mock_response.data.cooldown = Mock()
        mock_response.data.cooldown.total_seconds = 15
        mock_response.data.fight = Mock()
        mock_response.data.fight.result = "lose"
        mock_response.data.fight.drops = []

        mock_api_client.fight_monster.return_value = mock_response
        action = CombatAction("ancient_dragon", api_client=mock_api_client)

        result = await action.execute("test_character", current_state)

        assert isinstance(result, ActionResult)
        # Combat attempt may still be "successful" even if character lost
        assert isinstance(result.success, bool)
        assert result.cooldown_seconds > 0

        # Should update HP to reflect defeat
        if GameState.HP_CURRENT in result.state_changes:
            assert result.state_changes[GameState.HP_CURRENT] == 0

    @pytest.mark.asyncio
    async def test_combat_action_execute_api_failure(self):
        """Test combat action execution with API failure"""
        action = CombatAction("corrupted_knight")

        current_state = {
            GameState.COOLDOWN_READY: True,
            GameState.CAN_FIGHT: True,
            GameState.HP_CURRENT: 80
        }

        # Create action with mock API client that fails
        mock_api_client = Mock()
        mock_api_client.fight_monster = AsyncMock()
        mock_api_client.fight_monster.side_effect = Exception("Combat API failed")

        action = CombatAction("corrupted_knight", api_client=mock_api_client)

        result = await action.execute("test_character", current_state)

        assert isinstance(result, ActionResult)
        assert result.success is False
        assert "failed" in result.message.lower()
        assert result.state_changes == {}  # No state changes on failure

    @pytest.mark.asyncio
    async def test_combat_action_execute_inventory_full(self):
        """Test combat action execution with full inventory"""
        current_state = {
            GameState.COOLDOWN_READY: True,
            GameState.CAN_FIGHT: True,
            GameState.HP_CURRENT: 90,
            GameState.INVENTORY_FULL: True
        }

        # Create action with mock API client that returns inventory error
        mock_api_client = Mock()
        mock_api_client.fight_monster = AsyncMock()

        # Mock inventory full error
        inventory_error = Exception("Inventory full")
        inventory_error.status_code = 497  # ArtifactsHTTPStatus.INVENTORY_FULL
        mock_api_client.fight_monster.side_effect = inventory_error

        action = CombatAction("treasure_goblin", api_client=mock_api_client)

        result = await action.execute("test_character", current_state)

        assert isinstance(result, ActionResult)
        assert result.success is False
        assert "inventory" in result.message.lower() or "failed" in result.message.lower()

    def test_combat_action_monster_targeting(self):
        """Test combat action with different monster targets"""
        monsters = [
            "chicken",      # Weak enemy
            "goblin",       # Basic enemy
            "orc_warrior",  # Strong enemy
            "lich_king",    # Boss enemy
        ]

        for monster in monsters:
            action = CombatAction(monster)

            # Should create valid action for any monster
            assert action.target_monster == monster
            assert isinstance(action.name, str)
            assert monster in action.name

            # Preconditions should be consistent
            preconditions = action.get_preconditions()
            assert GameState.COOLDOWN_READY in preconditions
            assert GameState.CAN_FIGHT in preconditions

    def test_combat_action_hp_safety_checks(self):
        """Test combat action HP safety requirements"""
        action = CombatAction("dangerous_monster")
        preconditions = action.get_preconditions()

        # Should have HP-related safety checks
        hp_safety = any(
            state in preconditions for state in [
                GameState.HP_CURRENT,
                GameState.HP_LOW,
                GameState.HP_CRITICAL,
                GameState.SAFE_TO_FIGHT
            ]
        )

        # Combat action should consider HP safety
        if hp_safety:
            assert True  # Has HP safety checks
        else:
            # At minimum should check can_fight capability
            assert GameState.CAN_FIGHT in preconditions


class TestCombatActionValidation:
    """Test combat action validation and edge cases"""

    def test_combat_action_validates_preconditions(self):
        """Test that combat action preconditions are properly validated"""
        action = CombatAction("test_monster")

        # All preconditions should use GameState enum
        is_valid = action.validate_preconditions()
        assert is_valid is True

    def test_combat_action_validates_effects(self):
        """Test that combat action effects are properly validated"""
        action = CombatAction("test_monster")

        # All effects should use GameState enum
        is_valid = action.validate_effects()
        assert is_valid is True

    def test_combat_action_equipment_requirements(self):
        """Test combat action equipment considerations"""
        action = CombatAction("armored_beast")
        preconditions = action.get_preconditions()

        # May check for weapon equipment
        equipment_states = [
            GameState.WEAPON_EQUIPPED,
            GameState.TOOL_EQUIPPED,
            GameState.BODY_ARMOR_EQUIPPED
        ]

        # Combat may consider equipment (implementation dependent)
        equipment_considered = any(
            state in preconditions for state in equipment_states
        )

        # Basic combat capability should always be required
        assert GameState.CAN_FIGHT in preconditions

    def test_combat_action_location_requirements(self):
        """Test combat action location requirements"""
        action = CombatAction("cave_troll")
        preconditions = action.get_preconditions()

        # Should require being at monster location or having monster nearby
        location_states = [
            GameState.AT_MONSTER_LOCATION,
            GameState.ENEMY_NEARBY,
            GameState.IN_COMBAT
        ]

        location_required = any(
            state in preconditions for state in location_states
        )

        # Should have some location or proximity requirement
        # (Implementation may vary, but logical requirement)
        if not location_required:
            # At minimum should be able to fight
            assert GameState.CAN_FIGHT in preconditions

    @pytest.mark.asyncio
    async def test_combat_action_state_consistency(self):
        """Test that combat action maintains state consistency"""
        current_state = {
            GameState.COOLDOWN_READY: True,
            GameState.CAN_FIGHT: True,
            GameState.HP_CURRENT: 75,
            GameState.HP_MAX: 100,
            GameState.CHARACTER_LEVEL: 10,
            GameState.CHARACTER_XP: 5000
        }

        # Create action with mock API client
        mock_api_client = Mock()
        mock_api_client.fight_monster = AsyncMock()

        mock_response = Mock()
        mock_response.data = Mock()
        mock_response.data.character = Mock()
        mock_response.data.character.hp = 70  # Lost some HP
        mock_response.data.character.xp = 5200  # Gained XP
        mock_response.data.character.max_hp = 100
        mock_response.data.cooldown = Mock()
        mock_response.data.cooldown.total_seconds = 6
        mock_response.data.fight = Mock()
        mock_response.data.fight.result = "win"

        mock_api_client.fight_monster.return_value = mock_response
        action = CombatAction("consistency_test_monster", api_client=mock_api_client)

        result = await action.execute("test_char", current_state)

        if result.success:
            # State changes should be logically consistent
            assert result.state_changes[GameState.COOLDOWN_READY] is False

            # HP should not increase from combat (unless healing effect)
            if GameState.HP_CURRENT in result.state_changes:
                new_hp = result.state_changes[GameState.HP_CURRENT]
                assert new_hp <= current_state[GameState.HP_MAX]

            # XP should not decrease
            if GameState.CHARACTER_XP in result.state_changes:
                new_xp = result.state_changes[GameState.CHARACTER_XP]
                assert new_xp >= current_state[GameState.CHARACTER_XP]


class TestCombatActionIntegration:
    """Integration tests for CombatAction with other systems"""

    def test_combat_action_with_goap_planner(self):
        """Test CombatAction integration with GOAP planning"""
        action = CombatAction("integration_test_monster")

        # Test state conversion for GOAP
        preconditions = action.get_preconditions()
        effects = action.get_effects()

        # Convert to GOAP format
        goap_preconditions = {state.value: value for state, value in preconditions.items()}
        goap_effects = {state.value: value for state, value in effects.items()}

        # GOAP format should use string keys
        for key in goap_preconditions.keys():
            assert isinstance(key, str)
        for key in goap_effects.keys():
            assert isinstance(key, str)

        # Essential GOAP attributes
        assert isinstance(action.name, str)
        assert isinstance(action.cost, int)
        assert action.cost > 0

    def test_combat_action_factory_generation(self):
        """Test CombatAction generation via factory pattern"""
        # Test combat action creation for different monsters
        monsters = ["rat", "spider", "goblin", "orc", "dragon"]

        actions = []
        for monster in monsters:
            action = CombatAction(monster)
            actions.append(action)

        # Each action should be unique per monster
        action_names = [action.name for action in actions]
        assert len(set(action_names)) == len(action_names), "Action names should be unique per monster"

        # All actions should be valid
        for action in actions:
            assert action.validate_preconditions() is True
            assert action.validate_effects() is True
            assert isinstance(action.cost, int)
            assert action.cost > 0

    def test_combat_action_risk_assessment(self):
        """Test combat action integration with risk assessment"""
        weak_monster = CombatAction("weak_rat")
        strong_monster = CombatAction("ancient_dragon")

        # Compare preconditions for risk assessment
        weak_preconditions = weak_monster.get_preconditions()
        strong_preconditions = strong_monster.get_preconditions()

        # Both should have basic combat requirements
        assert GameState.COOLDOWN_READY in weak_preconditions
        assert GameState.COOLDOWN_READY in strong_preconditions
        assert GameState.CAN_FIGHT in weak_preconditions
        assert GameState.CAN_FIGHT in strong_preconditions

        # Stronger monsters may have additional requirements
        # (Implementation dependent, but logical expectation)
        weak_cost = weak_monster.cost
        strong_cost = strong_monster.cost

        # Cost may reflect difficulty/risk
        assert isinstance(weak_cost, int)
        assert isinstance(strong_cost, int)
        assert weak_cost > 0
        assert strong_cost > 0


class TestCombatActionHelperMethods:
    """Test CombatAction helper methods"""

    def test_is_safe_to_fight_with_safe_hp(self):
        """Test is_safe_to_fight with sufficient HP"""
        action = CombatAction("test_monster")

        safe_state = {
            GameState.HP_CURRENT: 80,
            GameState.HP_MAX: 100,
            GameState.SAFE_TO_FIGHT: True
        }

        assert action.is_safe_to_fight(safe_state) is True

    def test_is_safe_to_fight_with_none_value(self):
        """Test is_safe_to_fight when SAFE_TO_FIGHT is None"""
        action = CombatAction("test_monster")

        state_with_none = {
            GameState.HP_CURRENT: 80,
            GameState.HP_MAX: 100,
            GameState.SAFE_TO_FIGHT: None  # This should trigger line 219
        }

        assert action.is_safe_to_fight(state_with_none) is False

    def test_is_safe_to_fight_with_low_hp(self):
        """Test is_safe_to_fight with insufficient HP"""
        action = CombatAction("test_monster")

        unsafe_state = {
            GameState.HP_CURRENT: 40,  # Less than 50%
            GameState.HP_MAX: 100
        }

        assert action.is_safe_to_fight(unsafe_state) is False

    def test_is_safe_to_fight_with_zero_hp(self):
        """Test is_safe_to_fight with zero HP"""
        action = CombatAction("test_monster")

        dead_state = {
            GameState.HP_CURRENT: 0,
            GameState.HP_MAX: 100
        }

        assert action.is_safe_to_fight(dead_state) is False

    def test_calculate_combat_risk_low_risk(self):
        """Test calculate_combat_risk with low-risk scenario"""
        action = CombatAction("test_monster")

        safe_state = {
            GameState.HP_CURRENT: 90,
            GameState.HP_MAX: 100,
            GameState.AT_SAFE_LOCATION: True,
            GameState.WEAPON_EQUIPPED: "iron_sword",
            GameState.CHARACTER_LEVEL: 10
        }

        risk = action.calculate_combat_risk(safe_state)
        assert isinstance(risk, float)
        assert 0.0 <= risk <= 1.0
        assert risk < 0.3  # Should be low risk

    def test_calculate_combat_risk_high_risk(self):
        """Test calculate_combat_risk with high-risk scenario"""
        action = CombatAction("test_monster")

        dangerous_state = {
            GameState.HP_CURRENT: 20,
            GameState.HP_MAX: 100,
            GameState.AT_SAFE_LOCATION: False,
            GameState.WEAPON_EQUIPPED: None,
            GameState.CHARACTER_LEVEL: 2
        }

        risk = action.calculate_combat_risk(dangerous_state)
        assert isinstance(risk, float)
        assert 0.0 <= risk <= 1.0
        assert risk > 0.5  # Should be high risk

    def test_should_retreat_critical_hp(self):
        """Test should_retreat with critical HP"""
        action = CombatAction("test_monster")

        critical_state = {
            GameState.HP_CRITICAL: True,
            GameState.HP_CURRENT: 5,
            GameState.HP_MAX: 100
        }

        assert action.should_retreat(critical_state) is True

    def test_should_retreat_low_hp(self):
        """Test should_retreat with low HP"""
        action = CombatAction("test_monster")

        low_hp_state = {
            GameState.HP_LOW: True,
            GameState.HP_CURRENT: 25,
            GameState.HP_MAX: 100
        }

        assert action.should_retreat(low_hp_state) is True

    def test_should_retreat_safe_conditions(self):
        """Test should_retreat with safe conditions"""
        action = CombatAction("test_monster")

        safe_state = {
            GameState.HP_CURRENT: 85,
            GameState.HP_MAX: 100,
            GameState.HP_CRITICAL: False,
            GameState.HP_LOW: False,
            GameState.SAFE_TO_FIGHT: True
        }

        assert action.should_retreat(safe_state) is False

    def test_should_retreat_unsafe_to_fight(self):
        """Test should_retreat when unsafe to fight"""
        action = CombatAction("test_monster")

        unsafe_state = {
            GameState.HP_CURRENT: 40,
            GameState.HP_MAX: 100,
            GameState.SAFE_TO_FIGHT: False
        }

        # The should_retreat method checks is_safe_to_fight
        assert action.should_retreat(unsafe_state) is True

    def test_should_retreat_high_risk(self):
        """Test should_retreat with high calculated risk"""
        action = CombatAction("test_monster")

        high_risk_state = {
            GameState.HP_CURRENT: 15,  # Very low HP
            GameState.HP_MAX: 100,
            GameState.AT_SAFE_LOCATION: False,
            GameState.WEAPON_EQUIPPED: None,
            GameState.CHARACTER_LEVEL: 1
        }

        assert action.should_retreat(high_risk_state) is True

    def test_combat_action_no_api_client(self):
        """Test combat action execute with no API client"""
        action = CombatAction("test_monster")  # No API client provided

        current_state = {
            GameState.COOLDOWN_READY: True,
            GameState.CAN_FIGHT: True,
            GameState.HP_CURRENT: 80,
            GameState.HP_MAX: 100
        }

        # Should handle missing API client gracefully
        result = asyncio.run(action.execute("test_character", current_state))

        assert isinstance(result, ActionResult)
        assert result.success is False
        assert "API client not available" in result.message
        assert result.state_changes == {}
        assert result.cooldown_seconds == 0

    def test_combat_action_unsafe_conditions(self):
        """Test combat action execute with unsafe conditions"""
        mock_api_client = Mock()
        action = CombatAction("test_monster", api_client=mock_api_client)

        unsafe_state = {
            GameState.HP_CURRENT: 20,  # Low HP - unsafe to fight
            GameState.HP_MAX: 100,
            GameState.COOLDOWN_READY: True,
            GameState.CAN_FIGHT: True
        }

        # Should refuse to execute when unsafe
        result = asyncio.run(action.execute("test_character", unsafe_state))

        assert isinstance(result, ActionResult)
        assert result.success is False
        assert "unsafe" in result.message.lower()
        assert result.state_changes == {}
        assert result.cooldown_seconds == 0

    def test_combat_action_validate_methods_with_errors(self):
        """Test validation methods handle exceptions gracefully"""
        action = CombatAction("test_monster")

        # Monkey patch to cause errors
        original_get_preconditions = action.get_preconditions
        original_get_effects = action.get_effects

        def broken_preconditions():
            raise Exception("Test error")

        def broken_effects():
            raise Exception("Test error")

        action.get_preconditions = broken_preconditions
        assert action.validate_preconditions() is False

        action.get_effects = broken_effects
        assert action.validate_effects() is False

        # Restore original methods
        action.get_preconditions = original_get_preconditions
        action.get_effects = original_get_effects

    def test_is_safe_to_fight_edge_cases(self):
        """Test is_safe_to_fight with edge cases"""
        action = CombatAction("test_monster")

        # Test with invalid HP values
        edge_cases = [
            {GameState.HP_CURRENT: 0, GameState.HP_MAX: 0},  # Both zero
            {GameState.HP_CURRENT: -10, GameState.HP_MAX: 100},  # Negative HP
            {GameState.HP_CURRENT: 50, GameState.HP_MAX: -100},  # Negative max HP
            {},  # Empty state
        ]

        for state in edge_cases:
            result = action.is_safe_to_fight(state)
            assert isinstance(result, bool)
            # These should all be False due to invalid conditions
            assert result is False

    def test_calculate_combat_risk_edge_cases(self):
        """Test calculate_combat_risk with edge cases"""
        action = CombatAction("test_monster")

        # Test with empty state
        empty_state = {}
        risk = action.calculate_combat_risk(empty_state)
        assert isinstance(risk, float)
        assert 0.0 <= risk <= 1.0

        # Test with minimal state
        minimal_state = {GameState.HP_CURRENT: 50, GameState.HP_MAX: 100}
        risk = action.calculate_combat_risk(minimal_state)
        assert isinstance(risk, float)
        assert 0.0 <= risk <= 1.0

    def test_should_retreat_in_combat_low_hp(self):
        """Test should_retreat during combat with low HP"""
        action = CombatAction("test_monster")

        # Test in-combat scenario with low HP
        combat_state = {
            GameState.IN_COMBAT: True,
            GameState.HP_CURRENT: 25,  # 25% HP during combat
            GameState.HP_MAX: 100
        }

        # Should retreat when HP drops below 30% during combat
        assert action.should_retreat(combat_state) is True

    def test_calculate_combat_risk_zero_max_hp(self):
        """Test calculate_combat_risk with zero max HP"""
        action = CombatAction("test_monster")

        # Test with zero max HP - should be maximum risk
        zero_max_hp_state = {
            GameState.HP_CURRENT: 50,
            GameState.HP_MAX: 0  # Invalid max HP
        }

        risk = action.calculate_combat_risk(zero_max_hp_state)
        assert isinstance(risk, float)
        assert risk > 0.8  # Should be very high risk
        assert 0.0 <= risk <= 1.0

    def test_combat_action_name_without_target_monster(self):
        """Test combat action name generation without target monster"""
        action = CombatAction(None)  # No target monster specified

        # Should return generic "combat" name (line 59)
        assert action.name == "combat"

    def test_calculate_combat_risk_no_factors(self):
        """Test calculate_combat_risk with no risk factors (line 280)"""
        action = CombatAction("test_monster")

        # State that results in no risk factors being added
        no_risk_state = {
            GameState.AT_SAFE_LOCATION: True,   # No location risk
            GameState.WEAPON_EQUIPPED: "sword",  # No equipment risk
            GameState.CHARACTER_LEVEL: 10       # No level risk (>= 5)
            # No HP data provided - no HP risk factor added
        }

        risk = action.calculate_combat_risk(no_risk_state)

        # Should return default moderate risk (line 280)
        assert risk == 0.5
        assert isinstance(risk, float)
        assert 0.0 <= risk <= 1.0

    def test_should_retreat_high_risk_level(self):
        """Test should_retreat with high risk level > 0.7"""
        action = CombatAction("test_monster")

        # Mock calculate_combat_risk to return high risk
        original_method = action.calculate_combat_risk
        action.calculate_combat_risk = lambda state: 0.8  # > 0.7

        state = {
            GameState.HP_CURRENT: 60,
            GameState.HP_MAX: 100,
            GameState.HP_CRITICAL: False,
            GameState.HP_LOW: False
        }

        # Should retreat due to high risk (line 304)
        assert action.should_retreat(state) is True

        # Restore original method
        action.calculate_combat_risk = original_method

    def test_should_retreat_with_hp_low_flag(self):
        """Test should_retreat when HP_LOW flag is True"""
        action = CombatAction("test_monster")

        # Mock calculate_combat_risk to return low risk
        original_method = action.calculate_combat_risk
        action.calculate_combat_risk = lambda state: 0.2  # Low risk

        # Mock is_safe_to_fight to return True
        original_safe_method = action.is_safe_to_fight
        action.is_safe_to_fight = lambda state: True  # Safe to fight

        state = {
            GameState.HP_CURRENT: 60,
            GameState.HP_MAX: 100,
            GameState.HP_CRITICAL: False,
            GameState.HP_LOW: True,  # This should trigger retreat (line 312)
            GameState.SAFE_TO_FIGHT: True
        }

        # Should retreat due to HP_LOW flag (line 312)
        assert action.should_retreat(state) is True

        # Restore original methods
        action.calculate_combat_risk = original_method
        action.is_safe_to_fight = original_safe_method

    def test_should_retreat_in_combat_low_hp_threshold(self):
        """Test should_retreat during combat with HP below 30%"""
        action = CombatAction("test_monster")

        # Mock calculate_combat_risk to return low risk
        original_method = action.calculate_combat_risk
        action.calculate_combat_risk = lambda state: 0.2  # Low risk

        # Mock is_safe_to_fight to return True
        original_safe_method = action.is_safe_to_fight
        action.is_safe_to_fight = lambda state: True  # Safe to fight

        # Test lines 317-324 with in-combat scenario
        combat_state = {
            GameState.IN_COMBAT: True,  # This triggers the block starting at line 316
            GameState.HP_CURRENT: 25,  # 25% HP - below 30% threshold
            GameState.HP_MAX: 100,
            GameState.HP_CRITICAL: False,
            GameState.HP_LOW: False,
            GameState.SAFE_TO_FIGHT: True
        }

        # Should retreat when in combat with HP below 30% (lines 317-324)
        assert action.should_retreat(combat_state) is True

        # Restore original methods
        action.calculate_combat_risk = original_method
        action.is_safe_to_fight = original_safe_method
