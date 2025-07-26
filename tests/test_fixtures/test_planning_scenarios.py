"""
Comprehensive tests for tests.fixtures.planning_scenarios module

This module provides complete test coverage for all planning scenario fixtures,
validating that they generate proper test data for GOAP planning scenarios.
"""

import pytest
from typing import Any

from src.ai_player.state.game_state import GameState
from tests.fixtures.planning_scenarios import (
    PlanningScenarioFixtures,
    PlanningChallengeFixtures, 
    PlanningTestSuite,
    PlanningExpectedResults,
    get_planning_scenario,
    get_scenarios_for_testing,
    validate_planning_result
)


class TestPlanningScenarioFixtures:
    """Test suite for PlanningScenarioFixtures class"""

    def test_get_basic_leveling_scenario(self) -> None:
        """Test basic leveling scenario generation"""
        scenario = PlanningScenarioFixtures.get_basic_leveling_scenario()
        
        assert scenario["name"] == "basic_leveling"
        assert scenario["description"] == "Character needs to gain experience to level up"
        assert scenario["difficulty"] == "easy"
        assert scenario["estimated_cost"] == 15
        assert scenario["expected_plan_length"] == 4
        
        # Validate start state
        start_state = scenario["start_state"]
        assert start_state[GameState.CHARACTER_LEVEL] == 5
        assert start_state[GameState.CHARACTER_XP] == 1200
        assert start_state[GameState.HP_CURRENT] == 100
        assert start_state[GameState.HP_MAX] == 100
        assert start_state[GameState.CURRENT_X] == 0
        assert start_state[GameState.CURRENT_Y] == 0
        assert start_state[GameState.COOLDOWN_READY] is True
        assert start_state[GameState.CAN_FIGHT] is True
        assert start_state[GameState.CAN_MOVE] is True
        assert start_state[GameState.WEAPON_EQUIPPED] == "iron_sword"
        assert start_state[GameState.AT_SAFE_LOCATION] is True
        
        # Validate goal state
        goal_state = scenario["goal_state"]
        assert goal_state[GameState.CHARACTER_LEVEL] == 6
        assert goal_state[GameState.CHARACTER_XP] == 1500
        
        # Validate expected actions
        expected_actions = scenario["expected_actions"]
        assert len(expected_actions) == 4
        assert "move_to_forest" in expected_actions
        assert "fight_goblin" in expected_actions
        assert "rest" in expected_actions

    def test_get_resource_gathering_scenario(self) -> None:
        """Test resource gathering scenario generation"""
        scenario = PlanningScenarioFixtures.get_resource_gathering_scenario()
        
        assert scenario["name"] == "resource_gathering"
        assert scenario["description"] == "Character needs to gather specific resources"
        assert scenario["difficulty"] == "easy"
        assert scenario["estimated_cost"] == 18
        assert scenario["expected_plan_length"] == 6
        
        # Validate start state
        start_state = scenario["start_state"]
        assert start_state[GameState.CHARACTER_LEVEL] == 8
        assert start_state[GameState.MINING_LEVEL] == 6
        assert start_state[GameState.CURRENT_X] == 10
        assert start_state[GameState.CURRENT_Y] == 15
        assert start_state[GameState.TOOL_EQUIPPED] == "iron_pickaxe"
        assert start_state[GameState.INVENTORY_SPACE_AVAILABLE] == 15
        assert start_state[GameState.ITEM_QUANTITY] == 0
        
        # Validate goal state
        goal_state = scenario["goal_state"]
        assert goal_state[GameState.ITEM_QUANTITY] == 10
        assert goal_state[GameState.AT_RESOURCE_LOCATION] is True
        
        # Validate expected actions
        expected_actions = scenario["expected_actions"]
        assert "move_to_mine" in expected_actions
        assert expected_actions.count("gather_copper") == 5

    def test_get_complex_crafting_scenario(self) -> None:
        """Test complex crafting scenario generation"""
        scenario = PlanningScenarioFixtures.get_complex_crafting_scenario()
        
        assert scenario["name"] == "complex_crafting"
        assert scenario["difficulty"] == "medium"
        assert scenario["estimated_cost"] == 45
        assert scenario["expected_plan_length"] == 10
        
        # Validate start state
        start_state = scenario["start_state"]
        assert start_state[GameState.CHARACTER_LEVEL] == 15
        assert start_state[GameState.WEAPONCRAFTING_LEVEL] == 12
        assert start_state[GameState.MINING_LEVEL] == 10
        assert start_state[GameState.TOOL_EQUIPPED] == "steel_pickaxe"
        assert start_state[GameState.HAS_CRAFTING_MATERIALS] is False
        
        # Validate goal state
        goal_state = scenario["goal_state"]
        assert goal_state[GameState.WEAPON_EQUIPPED] == "mithril_sword"
        assert goal_state[GameState.HAS_CRAFTING_MATERIALS] is True
        assert goal_state[GameState.ITEM_QUANTITY] == 1
        
        # Validate complex action sequence
        expected_actions = scenario["expected_actions"]
        assert "move_to_mithril_mine" in expected_actions
        assert "gather_mithril_ore" in expected_actions
        assert "move_to_smelter" in expected_actions
        assert "smelt_mithril_bar" in expected_actions
        assert "move_to_forge" in expected_actions
        assert "craft_mithril_sword" in expected_actions
        assert "equip_mithril_sword" in expected_actions

    def test_get_emergency_survival_scenario(self) -> None:
        """Test emergency survival scenario generation"""
        scenario = PlanningScenarioFixtures.get_emergency_survival_scenario()
        
        assert scenario["name"] == "emergency_survival"
        assert scenario["difficulty"] == "hard"
        assert scenario["estimated_cost"] == 8
        assert scenario["expected_plan_length"] == 3
        assert scenario["priority"] == "critical"
        
        # Validate critical start state
        start_state = scenario["start_state"]
        assert start_state[GameState.HP_CURRENT] == 8  # Critically low
        assert start_state[GameState.HP_MAX] == 140
        assert start_state[GameState.HP_CRITICAL] is True
        assert start_state[GameState.SAFE_TO_FIGHT] is False
        assert start_state[GameState.AT_SAFE_LOCATION] is False
        assert start_state[GameState.ENEMY_NEARBY] is True
        
        # Validate survival goal state
        goal_state = scenario["goal_state"]
        assert goal_state[GameState.HP_CURRENT] == 100
        assert goal_state[GameState.HP_CRITICAL] is False
        assert goal_state[GameState.AT_SAFE_LOCATION] is True
        assert goal_state[GameState.SAFE_TO_FIGHT] is True
        
        # Validate emergency actions
        expected_actions = scenario["expected_actions"]
        assert "move_to_safe_area" in expected_actions
        assert "use_health_potion" in expected_actions
        assert "rest" in expected_actions

    def test_get_inventory_management_scenario(self) -> None:
        """Test inventory management scenario generation"""
        scenario = PlanningScenarioFixtures.get_inventory_management_scenario()
        
        assert scenario["name"] == "inventory_management"
        assert scenario["difficulty"] == "medium"
        assert scenario["estimated_cost"] == 20
        assert scenario["expected_plan_length"] == 5
        
        # Validate inventory full start state
        start_state = scenario["start_state"]
        assert start_state[GameState.INVENTORY_FULL] is True
        assert start_state[GameState.INVENTORY_SPACE_AVAILABLE] == 0
        assert start_state[GameState.INVENTORY_SPACE_USED] == 20
        assert start_state[GameState.AT_BANK_LOCATION] is False
        assert start_state[GameState.INVENTORY_OPTIMIZED] is False
        
        # Validate inventory management goal
        goal_state = scenario["goal_state"]
        assert goal_state[GameState.INVENTORY_SPACE_AVAILABLE] == 10
        assert goal_state[GameState.INVENTORY_OPTIMIZED] is True
        assert goal_state[GameState.INVENTORY_FULL] is False
        
        # Validate inventory actions
        expected_actions = scenario["expected_actions"]
        assert "move_to_bank" in expected_actions
        assert "deposit_items" in expected_actions
        assert "move_to_grand_exchange" in expected_actions
        assert "sell_excess_items" in expected_actions
        assert "organize_inventory" in expected_actions

    def test_get_economic_optimization_scenario(self) -> None:
        """Test economic optimization scenario generation"""
        scenario = PlanningScenarioFixtures.get_economic_optimization_scenario()
        
        assert scenario["name"] == "economic_optimization"
        assert scenario["difficulty"] == "hard"
        assert scenario["estimated_cost"] == 30
        assert scenario["expected_plan_length"] == 7
        
        # Validate economic start state
        start_state = scenario["start_state"]
        assert start_state[GameState.CHARACTER_GOLD] == 5000
        assert start_state[GameState.PORTFOLIO_VALUE] == 8000
        assert start_state[GameState.PROFITABLE_TRADE_AVAILABLE] is True
        assert start_state[GameState.ARBITRAGE_OPPORTUNITY] is True
        
        # Validate profit goal state
        goal_state = scenario["goal_state"]
        assert goal_state[GameState.CHARACTER_GOLD] == 8000  # 60% increase
        assert goal_state[GameState.PORTFOLIO_VALUE] == 12000
        assert goal_state[GameState.PROFITABLE_TRADE_AVAILABLE] is False

    def test_get_skill_specialization_scenario(self) -> None:
        """Test skill specialization scenario generation"""
        scenario = PlanningScenarioFixtures.get_skill_specialization_scenario()
        
        assert scenario["name"] == "skill_specialization"
        assert scenario["difficulty"] == "medium"
        assert scenario["estimated_cost"] == 35
        assert scenario["expected_plan_length"] == 8
        
        # Validate skill start state
        start_state = scenario["start_state"]
        assert start_state[GameState.ALCHEMY_LEVEL] == 15
        assert start_state[GameState.ALCHEMY_XP] == 5500
        assert start_state[GameState.TOOL_EQUIPPED] == "master_alembic"
        
        # Validate skill advancement goal
        goal_state = scenario["goal_state"]
        assert goal_state[GameState.ALCHEMY_LEVEL] == 18
        assert goal_state[GameState.ALCHEMY_XP] == 7200

    def test_get_impossible_scenario(self) -> None:
        """Test impossible scenario generation"""
        scenario = PlanningScenarioFixtures.get_impossible_scenario()
        
        assert scenario["name"] == "impossible_scenario"
        assert scenario["difficulty"] == "impossible"
        assert scenario["estimated_cost"] == float('inf')
        assert scenario["expected_plan_length"] == 0
        assert scenario["expected_actions"] == []
        
        # Validate impossible start state
        start_state = scenario["start_state"]
        assert start_state[GameState.HP_CURRENT] == 0  # Dead
        assert start_state[GameState.CAN_MOVE] is False
        assert start_state[GameState.CAN_FIGHT] is False
        
        # Validate impossible goal state
        goal_state = scenario["goal_state"]
        assert goal_state[GameState.CHARACTER_LEVEL] == 45
        assert goal_state[GameState.HP_CURRENT] == 300
        assert goal_state[GameState.ALCHEMY_LEVEL] == 45

    def test_get_multi_goal_scenario(self) -> None:
        """Test multi-goal scenario generation"""
        scenario = PlanningScenarioFixtures.get_multi_goal_scenario()
        
        assert scenario["name"] == "multi_goal_progression"
        assert scenario["difficulty"] == "hard"
        assert scenario["estimated_cost"] == 55
        assert scenario["expected_plan_length"] == 12
        
        # Validate complex goal state
        goal_state = scenario["goal_state"]
        assert goal_state[GameState.CHARACTER_LEVEL] == 18
        assert goal_state[GameState.MINING_LEVEL] == 15
        assert goal_state[GameState.WEAPONCRAFTING_LEVEL] == 13
        assert goal_state[GameState.CHARACTER_GOLD] == 4000
        assert goal_state[GameState.WEAPON_EQUIPPED] == "mithril_sword"


class TestPlanningChallengeFixtures:
    """Test suite for PlanningChallengeFixtures class"""

    def test_get_resource_scarcity_challenge(self) -> None:
        """Test resource scarcity challenge generation"""
        challenge = PlanningChallengeFixtures.get_resource_scarcity_challenge()
        
        assert challenge["name"] == "resource_scarcity"
        assert challenge["difficulty"] == "very_hard"
        
        # Validate scarcity conditions
        start_state = challenge["start_state"]
        assert start_state[GameState.INVENTORY_SPACE_AVAILABLE] == 5  # Very limited
        assert start_state[GameState.CHARACTER_GOLD] == 50  # Very limited
        assert start_state[GameState.RESOURCE_AVAILABLE] is False
        assert start_state[GameState.RESOURCE_DEPLETED] is True
        
        # Validate constraints
        constraints = challenge["constraints"]
        assert constraints["max_moves"] == 10
        assert "distant_mine" in constraints["resource_locations"]
        assert "expensive_vendor" in constraints["resource_locations"]
        assert constraints["gold_cost_per_item"] == 30

    def test_get_time_pressure_challenge(self) -> None:
        """Test time pressure challenge generation"""
        challenge = PlanningChallengeFixtures.get_time_pressure_challenge()
        
        assert challenge["name"] == "time_pressure"
        assert challenge["difficulty"] == "extreme"
        
        # Validate pressure conditions
        start_state = challenge["start_state"]
        assert start_state[GameState.HP_CURRENT] == 30  # Low HP
        assert start_state[GameState.ENEMY_NEARBY] is True
        assert start_state[GameState.AT_SAFE_LOCATION] is False
        
        # Validate time constraints
        constraints = challenge["constraints"]
        assert constraints["max_actions"] == 8
        assert constraints["hp_degrades"] is True
        assert constraints["enemy_pursuit"] is True

    def test_get_circular_dependency_challenge(self) -> None:
        """Test circular dependency challenge generation"""
        challenge = PlanningChallengeFixtures.get_circular_dependency_challenge()
        
        assert challenge["name"] == "circular_dependency"
        assert challenge["difficulty"] == "puzzle"
        
        # Validate circular dependency constraints
        constraints = challenge["constraints"]
        assert "legendary_materials_require" in constraints
        assert "legendary_weapon_requires" in constraints
        assert "break_cycle_via" in constraints
        assert constraints["break_cycle_via"] == "quest_reward_or_rare_drop"


class TestPlanningTestSuite:
    """Test suite for PlanningTestSuite class"""

    def test_get_all_basic_scenarios(self) -> None:
        """Test retrieval of all basic scenarios"""
        basic_scenarios = PlanningTestSuite.get_all_basic_scenarios()
        
        assert isinstance(basic_scenarios, list)
        assert len(basic_scenarios) == 4
        
        scenario_names = [s["name"] for s in basic_scenarios]
        assert "basic_leveling" in scenario_names
        assert "resource_gathering" in scenario_names
        assert "emergency_survival" in scenario_names
        assert "inventory_management" in scenario_names

    def test_get_all_advanced_scenarios(self) -> None:
        """Test retrieval of all advanced scenarios"""
        advanced_scenarios = PlanningTestSuite.get_all_advanced_scenarios()
        
        assert isinstance(advanced_scenarios, list)
        assert len(advanced_scenarios) == 4
        
        scenario_names = [s["name"] for s in advanced_scenarios]
        assert "complex_crafting" in scenario_names
        assert "economic_optimization" in scenario_names
        assert "skill_specialization" in scenario_names
        assert "multi_goal_progression" in scenario_names

    def test_get_all_challenge_scenarios(self) -> None:
        """Test retrieval of all challenge scenarios"""
        challenge_scenarios = PlanningTestSuite.get_all_challenge_scenarios()
        
        assert isinstance(challenge_scenarios, list)
        assert len(challenge_scenarios) == 3
        
        scenario_names = [s["name"] for s in challenge_scenarios]
        assert "resource_scarcity" in scenario_names
        assert "time_pressure" in scenario_names
        assert "circular_dependency" in scenario_names

    def test_get_scenarios_by_difficulty_easy(self) -> None:
        """Test filtering scenarios by easy difficulty"""
        easy_scenarios = PlanningTestSuite.get_scenarios_by_difficulty("easy")
        
        assert isinstance(easy_scenarios, list)
        assert len(easy_scenarios) == 2  # basic_leveling and resource_gathering
        
        for scenario in easy_scenarios:
            assert scenario["difficulty"] == "easy"

    def test_get_scenarios_by_difficulty_medium(self) -> None:
        """Test filtering scenarios by medium difficulty"""
        medium_scenarios = PlanningTestSuite.get_scenarios_by_difficulty("medium")
        
        assert isinstance(medium_scenarios, list)
        assert len(medium_scenarios) >= 2
        
        for scenario in medium_scenarios:
            assert scenario["difficulty"] == "medium"

    def test_get_scenarios_by_difficulty_hard(self) -> None:
        """Test filtering scenarios by hard difficulty"""
        hard_scenarios = PlanningTestSuite.get_scenarios_by_difficulty("hard")
        
        assert isinstance(hard_scenarios, list)
        assert len(hard_scenarios) >= 2
        
        for scenario in hard_scenarios:
            assert scenario["difficulty"] == "hard"

    def test_get_scenarios_by_difficulty_impossible(self) -> None:
        """Test filtering scenarios by impossible difficulty"""
        impossible_scenarios = PlanningTestSuite.get_scenarios_by_difficulty("impossible")
        
        assert isinstance(impossible_scenarios, list)
        assert len(impossible_scenarios) == 1
        assert impossible_scenarios[0]["name"] == "impossible_scenario"

    def test_get_scenario_by_name_valid(self) -> None:
        """Test retrieval of scenario by valid name"""
        scenario = PlanningTestSuite.get_scenario_by_name("basic_leveling")
        
        assert scenario["name"] == "basic_leveling"
        assert isinstance(scenario, dict)
        assert "start_state" in scenario
        assert "goal_state" in scenario

    def test_get_scenario_by_name_invalid(self) -> None:
        """Test retrieval of scenario by invalid name"""
        with pytest.raises(ValueError, match="Unknown scenario"):
            PlanningTestSuite.get_scenario_by_name("nonexistent_scenario")

    def test_all_scenario_names_mappable(self) -> None:
        """Test that all scenarios can be retrieved by name"""
        all_scenarios = (
            PlanningTestSuite.get_all_basic_scenarios() +
            PlanningTestSuite.get_all_advanced_scenarios() +
            PlanningTestSuite.get_all_challenge_scenarios() +
            [PlanningScenarioFixtures.get_impossible_scenario()]
        )
        
        for scenario in all_scenarios:
            name = scenario["name"]
            retrieved_scenario = PlanningTestSuite.get_scenario_by_name(name)
            assert retrieved_scenario["name"] == name


class TestPlanningExpectedResults:
    """Test suite for PlanningExpectedResults class"""

    def test_get_expected_results_structure(self) -> None:
        """Test expected results structure"""
        expected_results = PlanningExpectedResults.get_expected_results()
        
        assert isinstance(expected_results, dict)
        assert len(expected_results) >= 7  # At least 7 scenarios with expected results
        
        # Verify required scenarios have expected results
        required_scenarios = [
            "basic_leveling", "resource_gathering", "complex_crafting",
            "emergency_survival", "inventory_management", 
            "economic_optimization", "impossible_scenario"
        ]
        
        for scenario_name in required_scenarios:
            assert scenario_name in expected_results

    def test_expected_results_format(self) -> None:
        """Test expected results format for each scenario"""
        expected_results = PlanningExpectedResults.get_expected_results()
        
        for scenario_name, result in expected_results.items():
            assert "plan_found" in result
            assert "plan_length_range" in result
            assert "total_cost_range" in result
            assert "contains_actions" in result
            assert "plan_efficiency" in result
            
            # Validate types
            assert isinstance(result["plan_found"], bool)
            assert isinstance(result["plan_length_range"], tuple)
            assert len(result["plan_length_range"]) == 2
            assert isinstance(result["total_cost_range"], tuple)
            assert len(result["total_cost_range"]) == 2
            assert isinstance(result["contains_actions"], list)
            assert isinstance(result["plan_efficiency"], str)

    def test_validate_plan_result_valid_plan(self) -> None:
        """Test plan validation with valid plan"""
        mock_plan = [
            {"name": "move_to_forest", "cost": 5},
            {"name": "fight_goblin", "cost": 3},
            {"name": "fight_goblin", "cost": 3},
            {"name": "rest", "cost": 2}
        ]
        
        validation = PlanningExpectedResults.validate_plan_result("basic_leveling", mock_plan)
        
        assert isinstance(validation, dict)
        assert "plan_found" in validation
        assert "plan_length_valid" in validation
        assert "cost_valid" in validation
        assert "required_actions_present" in validation
        assert "overall_valid" in validation
        
        # Should pass basic validation
        assert validation["plan_found"] is True
        assert validation["plan_length_valid"] is True

    def test_validate_plan_result_empty_plan(self) -> None:
        """Test plan validation with empty plan"""
        validation = PlanningExpectedResults.validate_plan_result("basic_leveling", [])
        
        assert validation["plan_found"] is False
        assert validation["overall_valid"] is False

    def test_validate_plan_result_impossible_scenario(self) -> None:
        """Test plan validation for impossible scenario"""
        validation = PlanningExpectedResults.validate_plan_result("impossible_scenario", [])
        
        assert validation["plan_found"] is True  # Empty plan expected for impossible scenario
        assert validation["overall_valid"] is True

    def test_validate_plan_result_unknown_scenario(self) -> None:
        """Test plan validation for unknown scenario"""
        validation = PlanningExpectedResults.validate_plan_result("unknown_scenario", [])
        
        assert "validation_available" in validation
        assert validation["validation_available"] is False

    def test_validate_plan_result_cost_calculation(self) -> None:
        """Test cost calculation in plan validation"""
        # basic_leveling expects cost range (10, 20)
        expensive_plan = [{"name": "action1", "cost": 100}]  # Too expensive
        good_plan = [{"name": "action1", "cost": 15}]        # Within range
        cheap_plan = [{"name": "action1", "cost": 1}]        # Too cheap
        
        expensive_validation = PlanningExpectedResults.validate_plan_result("basic_leveling", expensive_plan)
        good_validation = PlanningExpectedResults.validate_plan_result("basic_leveling", good_plan)
        cheap_validation = PlanningExpectedResults.validate_plan_result("basic_leveling", cheap_plan)
        
        # Only good plan should pass cost validation
        assert expensive_validation["cost_valid"] is False
        assert good_validation["cost_valid"] is True
        assert cheap_validation["cost_valid"] is False


class TestConvenienceFunctions:
    """Test suite for convenience functions"""

    def test_get_planning_scenario_function(self) -> None:
        """Test get_planning_scenario convenience function"""
        scenario = get_planning_scenario("basic_leveling")
        
        assert scenario["name"] == "basic_leveling"
        assert isinstance(scenario, dict)

    def test_get_planning_scenario_invalid(self) -> None:
        """Test get_planning_scenario with invalid name"""
        with pytest.raises(ValueError):
            get_planning_scenario("invalid_scenario")

    def test_get_scenarios_for_testing_default(self) -> None:
        """Test get_scenarios_for_testing with default difficulty"""
        scenarios = get_scenarios_for_testing()
        
        assert isinstance(scenarios, list)
        assert len(scenarios) > 0
        
        # Default should be easy
        for scenario in scenarios:
            assert scenario["difficulty"] == "easy"

    def test_get_scenarios_for_testing_specific_difficulty(self) -> None:
        """Test get_scenarios_for_testing with specific difficulty"""
        hard_scenarios = get_scenarios_for_testing("hard")
        
        assert isinstance(hard_scenarios, list)
        for scenario in hard_scenarios:
            assert scenario["difficulty"] == "hard"

    def test_validate_planning_result_function(self) -> None:
        """Test validate_planning_result convenience function"""
        good_plan = [{"name": "move_action", "cost": 5}]
        result = validate_planning_result("basic_leveling", good_plan)
        
        assert isinstance(result, bool)
        
        # Empty plan should fail for most scenarios
        empty_result = validate_planning_result("basic_leveling", [])
        assert isinstance(empty_result, bool)
        assert empty_result is False


class TestScenarioDataIntegrity:
    """Test suite to validate scenario data integrity"""

    def test_all_scenarios_have_required_fields(self) -> None:
        """Test that all scenarios have required fields"""
        all_scenarios = (
            PlanningTestSuite.get_all_basic_scenarios() +
            PlanningTestSuite.get_all_advanced_scenarios() +
            PlanningTestSuite.get_all_challenge_scenarios() +
            [PlanningScenarioFixtures.get_impossible_scenario()]
        )
        
        required_fields = ["name", "description", "start_state", "goal_state", "difficulty"]
        
        for scenario in all_scenarios:
            for field in required_fields:
                assert field in scenario, f"Scenario {scenario.get('name', 'unknown')} missing field: {field}"

    def test_all_scenarios_have_valid_game_states(self) -> None:
        """Test that all scenarios use valid GameState enums"""
        all_scenarios = (
            PlanningTestSuite.get_all_basic_scenarios() +
            PlanningTestSuite.get_all_advanced_scenarios() +
            PlanningTestSuite.get_all_challenge_scenarios() +
            [PlanningScenarioFixtures.get_impossible_scenario()]
        )
        
        for scenario in all_scenarios:
            # Check start_state uses valid GameState keys
            for state_key in scenario["start_state"].keys():
                assert hasattr(GameState, state_key.name), f"Invalid GameState key: {state_key}"
            
            # Check goal_state uses valid GameState keys
            for state_key in scenario["goal_state"].keys():
                assert hasattr(GameState, state_key.name), f"Invalid GameState key: {state_key}"

    def test_scenario_costs_are_reasonable(self) -> None:
        """Test that scenario costs are reasonable values"""
        all_scenarios = (
            PlanningTestSuite.get_all_basic_scenarios() +
            PlanningTestSuite.get_all_advanced_scenarios() +
            PlanningTestSuite.get_all_challenge_scenarios()
        )
        
        for scenario in all_scenarios:
            cost = scenario.get("estimated_cost", 0)
            assert isinstance(cost, (int, float))
            assert cost >= 0
            assert cost <= 1000  # Reasonable upper bound

    def test_plan_lengths_are_reasonable(self) -> None:
        """Test that expected plan lengths are reasonable"""
        all_scenarios = (
            PlanningTestSuite.get_all_basic_scenarios() +
            PlanningTestSuite.get_all_advanced_scenarios() +
            PlanningTestSuite.get_all_challenge_scenarios()
        )
        
        for scenario in all_scenarios:
            plan_length = scenario.get("expected_plan_length", 0)
            assert isinstance(plan_length, int)
            assert plan_length >= 0
            assert plan_length <= 50  # Reasonable upper bound

    def test_expected_actions_are_strings(self) -> None:
        """Test that expected actions are properly formatted strings"""
        all_scenarios = (
            PlanningTestSuite.get_all_basic_scenarios() +
            PlanningTestSuite.get_all_advanced_scenarios() +
            PlanningTestSuite.get_all_challenge_scenarios()
        )
        
        for scenario in all_scenarios:
            expected_actions = scenario.get("expected_actions", [])
            assert isinstance(expected_actions, list)
            
            for action in expected_actions:
                assert isinstance(action, str)
                assert len(action) > 0

    def test_difficulty_levels_are_valid(self) -> None:
        """Test that difficulty levels are from valid set"""
        all_scenarios = (
            PlanningTestSuite.get_all_basic_scenarios() +
            PlanningTestSuite.get_all_advanced_scenarios() +
            PlanningTestSuite.get_all_challenge_scenarios() +
            [PlanningScenarioFixtures.get_impossible_scenario()]
        )
        
        valid_difficulties = {"easy", "medium", "hard", "very_hard", "extreme", "impossible", "puzzle"}
        
        for scenario in all_scenarios:
            difficulty = scenario.get("difficulty")
            assert difficulty in valid_difficulties, f"Invalid difficulty: {difficulty}"


class TestPlanningScenarioUsability:
    """Test suite to validate scenarios are usable for actual planning"""

    def test_scenarios_have_achievable_transitions(self) -> None:
        """Test that start states can logically transition to goal states"""
        basic_scenarios = PlanningTestSuite.get_all_basic_scenarios()
        
        for scenario in basic_scenarios:
            start_state = scenario["start_state"]
            goal_state = scenario["goal_state"]
            
            # Basic sanity checks
            for goal_key, goal_value in goal_state.items():
                if goal_key in start_state:
                    start_value = start_state[goal_key]
                    
                    # Level progression should be reasonable
                    if "LEVEL" in goal_key.name and isinstance(goal_value, int) and isinstance(start_value, int):
                        assert goal_value >= start_value, f"Goal level should be >= start level in {scenario['name']}"
                        assert goal_value - start_value <= 10, f"Level jump too large in {scenario['name']}"

    def test_impossible_scenario_is_truly_impossible(self) -> None:
        """Test that impossible scenario has contradictory requirements"""
        impossible = PlanningScenarioFixtures.get_impossible_scenario()
        
        start_state = impossible["start_state"]
        goal_state = impossible["goal_state"]
        
        # Dead character cannot achieve high-level goals
        assert start_state[GameState.HP_CURRENT] == 0
        assert goal_state[GameState.HP_CURRENT] > 0
        assert start_state[GameState.CAN_MOVE] is False
        assert start_state[GameState.CAN_FIGHT] is False
        assert start_state[GameState.CAN_GATHER] is False
        assert start_state[GameState.CAN_CRAFT] is False

    def test_emergency_scenario_has_urgency(self) -> None:
        """Test that emergency scenario reflects urgent conditions"""
        emergency = PlanningScenarioFixtures.get_emergency_survival_scenario()
        
        start_state = emergency["start_state"]
        
        assert start_state[GameState.HP_CURRENT] < 10  # Very low HP
        assert start_state[GameState.HP_CRITICAL] is True
        assert start_state[GameState.SAFE_TO_FIGHT] is False
        assert start_state[GameState.ENEMY_NEARBY] is True
        assert emergency["priority"] == "critical"

    def test_resource_scenarios_have_logical_requirements(self) -> None:
        """Test that resource scenarios have logical tool/skill requirements"""
        gathering = PlanningScenarioFixtures.get_resource_gathering_scenario()
        
        start_state = gathering["start_state"]
        
        # Should have appropriate tool for gathering
        assert GameState.TOOL_EQUIPPED in start_state
        assert "pickaxe" in start_state[GameState.TOOL_EQUIPPED]
        
        # Should have gathering capability
        assert start_state[GameState.CAN_GATHER] is True
        
        # Should have inventory space
        assert start_state[GameState.INVENTORY_SPACE_AVAILABLE] > 0