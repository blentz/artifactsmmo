"""
Tests for tests.fixtures.__init__ module

This module validates that all fixture classes and convenience functions
are properly imported and re-exported from the fixtures package.
"""

import inspect

import pytest

import tests.fixtures as fixtures


class TestFixturesInit:
    """Test suite for the fixtures.__init__ module"""

    def test_all_api_response_fixtures_available(self):
        """Test that all API response fixture classes are available"""
        assert hasattr(fixtures, 'APIResponseFixtures')
        assert hasattr(fixtures, 'APIResponseSequences')
        assert hasattr(fixtures, 'ErrorResponseFixtures')
        assert hasattr(fixtures, 'GameDataFixtures')

        # Verify they are classes
        assert inspect.isclass(fixtures.APIResponseFixtures)
        assert inspect.isclass(fixtures.APIResponseSequences)
        assert inspect.isclass(fixtures.ErrorResponseFixtures)
        assert inspect.isclass(fixtures.GameDataFixtures)

    def test_all_character_state_fixtures_available(self):
        """Test that all character state fixture classes are available"""
        assert hasattr(fixtures, 'CharacterStateFixtures')
        assert hasattr(fixtures, 'CharacterStateJSON')
        assert hasattr(fixtures, 'CooldownFixtures')

        # Verify they are classes
        assert inspect.isclass(fixtures.CharacterStateFixtures)
        assert inspect.isclass(fixtures.CharacterStateJSON)
        assert inspect.isclass(fixtures.CooldownFixtures)

    def test_all_planning_scenario_fixtures_available(self):
        """Test that all planning scenario fixture classes are available"""
        assert hasattr(fixtures, 'PlanningScenarioFixtures')
        assert hasattr(fixtures, 'PlanningChallengeFixtures')
        assert hasattr(fixtures, 'PlanningTestSuite')
        assert hasattr(fixtures, 'PlanningExpectedResults')

        # Verify they are classes
        assert inspect.isclass(fixtures.PlanningScenarioFixtures)
        assert inspect.isclass(fixtures.PlanningChallengeFixtures)
        assert inspect.isclass(fixtures.PlanningTestSuite)
        assert inspect.isclass(fixtures.PlanningExpectedResults)

    def test_all_convenience_functions_available(self):
        """Test that all convenience functions are available"""
        # API response convenience functions
        assert hasattr(fixtures, 'get_mock_character')
        assert hasattr(fixtures, 'get_mock_action_response')
        assert hasattr(fixtures, 'get_mock_error')

        # Character state convenience functions
        assert hasattr(fixtures, 'get_test_character_state')
        assert hasattr(fixtures, 'get_test_cooldown')
        assert hasattr(fixtures, 'get_state_transition_sequence')

        # Planning scenario convenience functions
        assert hasattr(fixtures, 'get_planning_scenario')
        assert hasattr(fixtures, 'get_scenarios_for_testing')
        assert hasattr(fixtures, 'validate_planning_result')

        # Verify they are functions
        assert callable(fixtures.get_mock_character)
        assert callable(fixtures.get_mock_action_response)
        assert callable(fixtures.get_mock_error)
        assert callable(fixtures.get_test_character_state)
        assert callable(fixtures.get_test_cooldown)
        assert callable(fixtures.get_state_transition_sequence)
        assert callable(fixtures.get_planning_scenario)
        assert callable(fixtures.get_scenarios_for_testing)
        assert callable(fixtures.validate_planning_result)

    def test_all_defined_items_in_all_list(self):
        """Test that __all__ contains all expected items"""
        expected_items = {
            # API Response Classes
            "APIResponseFixtures",
            "APIResponseSequences",
            "ErrorResponseFixtures",
            "GameDataFixtures",

            # Character State Classes
            "CharacterStateFixtures",
            "CharacterStateJSON",
            "CooldownFixtures",

            # Planning Scenario Classes
            "PlanningScenarioFixtures",
            "PlanningChallengeFixtures",
            "PlanningTestSuite",
            "PlanningExpectedResults",

            # Convenience Functions
            "get_mock_character",
            "get_mock_action_response",
            "get_mock_error",
            "get_test_character_state",
            "get_test_cooldown",
            "get_state_transition_sequence",
            "get_planning_scenario",
            "get_scenarios_for_testing",
            "validate_planning_result",
        }

        assert hasattr(fixtures, '__all__')
        assert isinstance(fixtures.__all__, list)
        assert set(fixtures.__all__) == expected_items

    def test_all_listed_items_are_accessible(self):
        """Test that all items in __all__ are actually accessible"""
        for item_name in fixtures.__all__:
            assert hasattr(fixtures, item_name), f"Item '{item_name}' is in __all__ but not accessible"

    def test_no_extra_public_items(self):
        """Test that no unexpected public items are exposed"""
        public_items = {name for name in dir(fixtures)
                       if not name.startswith('_')}
        expected_items = set(fixtures.__all__)

        # Allow for some standard module attributes and imported modules
        allowed_extra = {
            'typing', 'Any', 'inspect',
            'api_responses', 'character_states', 'planning_scenarios'  # Imported modules
        }

        extra_items = public_items - expected_items - allowed_extra
        assert not extra_items, f"Unexpected public items found: {extra_items}"


class TestAPIResponseFixtures:
    """Test suite for API response fixture functionality"""

    def test_get_mock_character_function(self):
        """Test get_mock_character convenience function"""
        # Test with default parameters
        character = fixtures.get_mock_character()
        assert character is not None
        assert hasattr(character, 'level')
        assert character.level == 10  # Default level

        # Test with custom level
        character_level_5 = fixtures.get_mock_character(level=5)
        assert character_level_5.level == 5

        # Test with custom attributes
        character_custom = fixtures.get_mock_character(level=15, name="test_char")
        assert character_custom.level == 15
        assert character_custom.name == "test_char"

    def test_get_mock_action_response_function(self):
        """Test get_mock_action_response convenience function"""
        # Test fight action
        fight_response = fixtures.get_mock_action_response("fight")
        assert fight_response is not None
        assert hasattr(fight_response, 'data')

        # Test move action
        move_response = fixtures.get_mock_action_response("move", x=10, y=15)
        assert move_response is not None
        assert move_response.data.x == 10
        assert move_response.data.y == 15

        # Test invalid action type
        with pytest.raises(ValueError, match="Unknown action type"):
            fixtures.get_mock_action_response("invalid_action")

    def test_get_mock_error_function(self):
        """Test get_mock_error convenience function"""
        # Test cooldown error
        cooldown_error = fixtures.get_mock_error("cooldown")
        assert cooldown_error is not None
        assert hasattr(cooldown_error, 'status_code')

        # Test custom cooldown seconds
        cooldown_error_custom = fixtures.get_mock_error("cooldown", seconds=60)
        assert cooldown_error_custom.cooldown.remaining_seconds == 60

        # Test invalid error type
        with pytest.raises(ValueError, match="Unknown error type"):
            fixtures.get_mock_error("invalid_error")


class TestCharacterStateFixtures:
    """Test suite for character state fixture functionality"""

    def test_get_test_character_state_function(self):
        """Test get_test_character_state convenience function"""
        # Test with default scenario
        state = fixtures.get_test_character_state()
        assert state is not None
        assert isinstance(state, dict)

        # Test with specific scenario
        state_level_1 = fixtures.get_test_character_state("level_1_starter")
        assert state_level_1 is not None

        # Test invalid scenario
        with pytest.raises(ValueError, match="Unknown scenario"):
            fixtures.get_test_character_state("invalid_scenario")

    def test_get_test_cooldown_function(self):
        """Test get_test_cooldown convenience function"""
        # Test with default scenario
        cooldown = fixtures.get_test_cooldown()
        assert cooldown is not None
        assert hasattr(cooldown, 'character_name')

        # Test with specific scenario
        short_cooldown = fixtures.get_test_cooldown("short_cooldown")
        assert short_cooldown is not None
        assert short_cooldown.remaining_seconds == 5

        # Test invalid scenario
        with pytest.raises(ValueError, match="Unknown cooldown scenario"):
            fixtures.get_test_cooldown("invalid_cooldown")

    def test_get_state_transition_sequence_function(self):
        """Test get_state_transition_sequence convenience function"""
        transition_sequence = fixtures.get_state_transition_sequence()
        assert transition_sequence is not None
        assert isinstance(transition_sequence, list)
        assert len(transition_sequence) == 4  # Level 1, 10, 25, max level


class TestPlanningScenarioFixtures:
    """Test suite for planning scenario fixture functionality"""

    def test_get_planning_scenario_function(self):
        """Test get_planning_scenario convenience function"""
        # Test with valid scenario
        scenario = fixtures.get_planning_scenario("basic_leveling")
        assert scenario is not None
        assert isinstance(scenario, dict)
        assert scenario["name"] == "basic_leveling"

        # Test invalid scenario
        with pytest.raises(ValueError, match="Unknown scenario"):
            fixtures.get_planning_scenario("invalid_scenario")

    def test_get_scenarios_for_testing_function(self):
        """Test get_scenarios_for_testing convenience function"""
        # Test with default difficulty
        easy_scenarios = fixtures.get_scenarios_for_testing()
        assert easy_scenarios is not None
        assert isinstance(easy_scenarios, list)

        # Test with specific difficulty
        hard_scenarios = fixtures.get_scenarios_for_testing("hard")
        assert hard_scenarios is not None
        assert isinstance(hard_scenarios, list)

    def test_validate_planning_result_function(self):
        """Test validate_planning_result convenience function"""
        # Test with valid scenario and plan
        mock_plan = [{"name": "move_action", "cost": 5}]
        result = fixtures.validate_planning_result("basic_leveling", mock_plan)
        assert isinstance(result, bool)

        # Test with empty plan
        empty_result = fixtures.validate_planning_result("basic_leveling", [])
        assert isinstance(empty_result, bool)


class TestFixtureClassFunctionality:
    """Test suite to verify fixture classes have expected methods"""

    def test_api_response_fixtures_methods(self):
        """Test that APIResponseFixtures has expected static methods"""
        assert hasattr(fixtures.APIResponseFixtures, 'get_character_response')
        assert hasattr(fixtures.APIResponseFixtures, 'get_character_on_cooldown')
        assert hasattr(fixtures.APIResponseFixtures, 'get_fight_response')
        assert hasattr(fixtures.APIResponseFixtures, 'get_move_response')
        assert hasattr(fixtures.APIResponseFixtures, 'get_gather_response')
        assert hasattr(fixtures.APIResponseFixtures, 'get_craft_response')
        assert hasattr(fixtures.APIResponseFixtures, 'get_rest_response')

    def test_game_data_fixtures_methods(self):
        """Test that GameDataFixtures has expected static methods"""
        assert hasattr(fixtures.GameDataFixtures, 'get_items_data')
        assert hasattr(fixtures.GameDataFixtures, 'get_monsters_data')
        assert hasattr(fixtures.GameDataFixtures, 'get_resources_data')
        assert hasattr(fixtures.GameDataFixtures, 'get_maps_data')

    def test_character_state_fixtures_methods(self):
        """Test that CharacterStateFixtures has expected static methods"""
        assert hasattr(fixtures.CharacterStateFixtures, 'get_level_1_starter')
        assert hasattr(fixtures.CharacterStateFixtures, 'get_level_10_experienced')
        assert hasattr(fixtures.CharacterStateFixtures, 'get_level_25_advanced')
        assert hasattr(fixtures.CharacterStateFixtures, 'get_emergency_low_hp')
        assert hasattr(fixtures.CharacterStateFixtures, 'get_inventory_full')
        assert hasattr(fixtures.CharacterStateFixtures, 'get_character_on_cooldown')

    def test_planning_scenario_fixtures_methods(self):
        """Test that PlanningScenarioFixtures has expected static methods"""
        assert hasattr(fixtures.PlanningScenarioFixtures, 'get_basic_leveling_scenario')
        assert hasattr(fixtures.PlanningScenarioFixtures, 'get_resource_gathering_scenario')
        assert hasattr(fixtures.PlanningScenarioFixtures, 'get_complex_crafting_scenario')
        assert hasattr(fixtures.PlanningScenarioFixtures, 'get_emergency_survival_scenario')


class TestFixtureIntegration:
    """Integration tests to verify fixtures work together properly"""

    def test_character_state_with_api_response(self):
        """Test that character states work with API responses"""
        # Get a character state
        character_state = fixtures.get_test_character_state("level_10_experienced")
        assert character_state is not None

        # Get corresponding API response
        character_response = fixtures.get_mock_character(level=10)
        assert character_response is not None

        # Verify they have compatible data
        assert character_response.level == 10

    def test_planning_scenario_with_character_state(self):
        """Test that planning scenarios work with character states"""
        # Get a planning scenario
        scenario = fixtures.get_planning_scenario("basic_leveling")
        assert scenario is not None
        assert "start_state" in scenario
        assert "goal_state" in scenario

        # Verify start state has required structure
        start_state = scenario["start_state"]
        assert isinstance(start_state, dict)
        assert len(start_state) > 0

    def test_comprehensive_fixture_usage(self):
        """Test comprehensive usage of multiple fixture types"""
        # Character progression workflow
        character = fixtures.get_mock_character(level=5)
        character_state = fixtures.get_test_character_state("level_1_starter")
        scenario = fixtures.get_planning_scenario("basic_leveling")
        cooldown = fixtures.get_test_cooldown("no_cooldown")

        # Verify all fixtures are properly created
        assert character is not None
        assert character_state is not None
        assert scenario is not None
        assert cooldown is not None

        # Verify they have expected structures
        assert hasattr(character, 'level')
        assert isinstance(character_state, dict)
        assert isinstance(scenario, dict)
        assert hasattr(cooldown, 'character_name')
