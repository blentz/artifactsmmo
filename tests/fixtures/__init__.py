"""
Test fixtures and mock data

This module provides comprehensive test fixtures including character states,
planning scenarios, API responses, and mock game data for testing the
ArtifactsMMO AI Player system.

This module exposes all fixture classes and convenience functions from:
- api_responses: API response fixtures, game data, and error responses
- character_states: Character state scenarios and cooldown fixtures
- planning_scenarios: GOAP planning scenarios and test suites
"""

# API Response Fixtures
from .api_responses import (
    APIResponseFixtures,
    APIResponseSequences,
    ErrorResponseFixtures,
    GameDataFixtures,
    get_mock_action_response,
    get_mock_character,
    get_mock_error,
)

# Character State Fixtures
from .character_states import (
    CharacterStateFixtures,
    CharacterStateJSON,
    CooldownFixtures,
    get_state_transition_sequence,
    get_test_character_state,
    get_test_cooldown,
)

# Planning Scenario Fixtures
from .planning_scenarios import (
    PlanningChallengeFixtures,
    PlanningExpectedResults,
    PlanningScenarioFixtures,
    PlanningTestSuite,
    get_planning_scenario,
    get_scenarios_for_testing,
    validate_planning_result,
)

__all__ = [
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
]
