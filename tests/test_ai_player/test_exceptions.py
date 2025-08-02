"""
Tests for Custom Exceptions

This module tests the custom exception classes used in the unified sub-goal architecture
for recursive sub-goal execution with proper depth tracking and error context.
"""

import pytest

from src.ai_player.exceptions import (
    InfeasibleGoalError,
    MaxDepthExceededError,
    NoValidGoalError,
    StateConsistencyError,
    SubGoalExecutionError,
)


class TestSubGoalExecutionError:
    """Test SubGoalExecutionError exception class."""

    def test_basic_exception_creation(self):
        """Test creating SubGoalExecutionError with basic parameters."""
        error = SubGoalExecutionError(
            depth=3,
            sub_goal_type="CombatGoal",
            message="Action failed during combat"
        )

        assert error.depth == 3
        assert error.sub_goal_type == "CombatGoal"
        assert str(error) == "Sub-goal 'CombatGoal' failed at depth 3: Action failed during combat"

    def test_exception_inheritance(self):
        """Test that SubGoalExecutionError inherits from Exception."""
        error = SubGoalExecutionError(1, "TestGoal", "Test message")

        assert isinstance(error, Exception)
        assert isinstance(error, SubGoalExecutionError)

    def test_depth_tracking(self):
        """Test depth tracking in exception."""
        for depth in [0, 1, 5, 10]:
            error = SubGoalExecutionError(depth, "TestGoal", "Test")
            assert error.depth == depth

    def test_sub_goal_type_tracking(self):
        """Test sub-goal type tracking in exception."""
        goal_types = ["MovementGoal", "CombatGoal", "RestGoal", "GatheringGoal"]

        for goal_type in goal_types:
            error = SubGoalExecutionError(1, goal_type, "Test")
            assert error.sub_goal_type == goal_type

    def test_message_formatting(self):
        """Test message formatting in exception string representation."""
        test_cases = [
            (2, "MovementGoal", "Failed to reach target location",
             "Sub-goal 'MovementGoal' failed at depth 2: Failed to reach target location"),
            (0, "RootGoal", "Initial goal failed",
             "Sub-goal 'RootGoal' failed at depth 0: Initial goal failed"),
            (5, "ComplexGoal", "Multiple sub-goals failed in chain",
             "Sub-goal 'ComplexGoal' failed at depth 5: Multiple sub-goals failed in chain")
        ]

        for depth, goal_type, message, expected_str in test_cases:
            error = SubGoalExecutionError(depth, goal_type, message)
            assert str(error) == expected_str

    def test_exception_attributes(self):
        """Test that exception attributes are accessible."""
        error = SubGoalExecutionError(4, "TestGoal", "Test message")

        # Test that attributes are accessible
        assert hasattr(error, 'depth')
        assert hasattr(error, 'sub_goal_type')

        # Test that they can be modified (though not recommended)
        error.depth = 6
        assert error.depth == 6

    def test_exception_with_empty_message(self):
        """Test exception with empty message."""
        error = SubGoalExecutionError(2, "TestGoal", "")
        assert str(error) == "Sub-goal 'TestGoal' failed at depth 2: "

    def test_exception_with_special_characters(self):
        """Test exception with special characters in goal type and message."""
        error = SubGoalExecutionError(
            depth=1,
            sub_goal_type="Goal-With-Hyphens_And_Underscores",
            message="Message with 'quotes' and \"double quotes\" and newlines\n"
        )

        expected = "Sub-goal 'Goal-With-Hyphens_And_Underscores' failed at depth 1: Message with 'quotes' and \"double quotes\" and newlines\n"
        assert str(error) == expected

    def test_exception_raising_and_catching(self):
        """Test raising and catching SubGoalExecutionError."""
        with pytest.raises(SubGoalExecutionError) as exc_info:
            raise SubGoalExecutionError(3, "TestGoal", "Test failure")

        error = exc_info.value
        assert error.depth == 3
        assert error.sub_goal_type == "TestGoal"
        assert "Test failure" in str(error)


class TestMaxDepthExceededError:
    """Test MaxDepthExceededError exception class."""

    def test_max_depth_exceeded_creation(self):
        """Test creating MaxDepthExceededError."""
        error = MaxDepthExceededError(max_depth=10)

        # Should inherit from SubGoalExecutionError
        assert isinstance(error, SubGoalExecutionError)
        assert isinstance(error, MaxDepthExceededError)

        # Should set appropriate values
        assert error.depth == 10
        assert error.sub_goal_type == "depth_limit"
        assert str(error) == "Sub-goal 'depth_limit' failed at depth 10: Maximum recursion depth 10 exceeded"

    def test_different_max_depths(self):
        """Test MaxDepthExceededError with different max depth values."""
        test_depths = [1, 5, 10, 15, 20]

        for max_depth in test_depths:
            error = MaxDepthExceededError(max_depth)
            assert error.depth == max_depth
            expected_message = f"Sub-goal 'depth_limit' failed at depth {max_depth}: Maximum recursion depth {max_depth} exceeded"
            assert str(error) == expected_message

    def test_max_depth_exceeded_inheritance(self):
        """Test inheritance hierarchy of MaxDepthExceededError."""
        error = MaxDepthExceededError(5)

        assert isinstance(error, Exception)
        assert isinstance(error, SubGoalExecutionError)
        assert isinstance(error, MaxDepthExceededError)

    def test_max_depth_exceeded_raising(self):
        """Test raising and catching MaxDepthExceededError."""
        with pytest.raises(MaxDepthExceededError) as exc_info:
            raise MaxDepthExceededError(8)

        error = exc_info.value
        assert error.depth == 8
        assert "Maximum recursion depth 8 exceeded" in str(error)

    def test_max_depth_caught_as_parent_exception(self):
        """Test that MaxDepthExceededError can be caught as SubGoalExecutionError."""
        with pytest.raises(SubGoalExecutionError) as exc_info:
            raise MaxDepthExceededError(3)

        error = exc_info.value
        assert isinstance(error, MaxDepthExceededError)
        assert error.depth == 3

    def test_zero_max_depth(self):
        """Test MaxDepthExceededError with zero max depth."""
        error = MaxDepthExceededError(0)
        assert error.depth == 0
        assert "Maximum recursion depth 0 exceeded" in str(error)


class TestNoValidGoalError:
    """Test NoValidGoalError exception class."""

    def test_no_valid_goal_error_creation(self):
        """Test creating NoValidGoalError."""
        error = NoValidGoalError()

        assert isinstance(error, Exception)
        assert isinstance(error, NoValidGoalError)

    def test_no_valid_goal_error_with_message(self):
        """Test NoValidGoalError with custom message."""
        message = "No feasible goals found for current character state"
        error = NoValidGoalError(message)

        assert str(error) == message

    def test_no_valid_goal_error_raising(self):
        """Test raising and catching NoValidGoalError."""
        with pytest.raises(NoValidGoalError):
            raise NoValidGoalError("No goals available")

    def test_no_valid_goal_error_empty_message(self):
        """Test NoValidGoalError with empty message."""
        error = NoValidGoalError("")
        assert str(error) == ""

    def test_no_valid_goal_error_default(self):
        """Test NoValidGoalError with default message."""
        error = NoValidGoalError()
        # Exception should have default message
        assert "No valid goals are available" in str(error)


class TestInfeasibleGoalError:
    """Test InfeasibleGoalError exception class."""

    def test_infeasible_goal_error_creation(self):
        """Test creating InfeasibleGoalError."""
        error = InfeasibleGoalError("test_goal", "Goal cannot be achieved")

        assert isinstance(error, Exception)
        assert isinstance(error, InfeasibleGoalError)
        assert error.goal_type == "test_goal"
        assert error.message == "Goal cannot be achieved"

    def test_infeasible_goal_error_with_message(self):
        """Test InfeasibleGoalError with custom message."""
        goal_type = "level_up"
        message = "Goal cannot be achieved with current character capabilities"
        error = InfeasibleGoalError(goal_type, message)

        assert f"Goal '{goal_type}' is infeasible: {message}" == str(error)

    def test_infeasible_goal_error_raising(self):
        """Test raising and catching InfeasibleGoalError."""
        with pytest.raises(InfeasibleGoalError):
            raise InfeasibleGoalError("combat", "Character level too low for goal")

    def test_infeasible_goal_error_detailed_message(self):
        """Test InfeasibleGoalError with detailed explanatory message."""
        goal_type = "reach_level_50"
        message = "character level 5 cannot reach level 50 directly"
        error = InfeasibleGoalError(goal_type, message)

        expected = f"Goal '{goal_type}' is infeasible: {message}"
        assert str(error) == expected

    def test_infeasible_goal_error_attributes(self):
        """Test InfeasibleGoalError attributes."""
        goal_type = "test_goal"
        message = "Test message"
        error = InfeasibleGoalError(goal_type, message)

        assert error.goal_type == goal_type
        assert error.message == message


class TestStateConsistencyError:
    """Test StateConsistencyError exception class."""

    def test_state_consistency_error_creation(self):
        """Test creating StateConsistencyError with depth."""
        error = StateConsistencyError(
            depth=2,
            message="Character HP exceeds maximum HP after sub-goal execution"
        )

        assert error.depth == 2
        assert str(error) == "State consistency error at depth 2: Character HP exceeds maximum HP after sub-goal execution"

    def test_state_consistency_error_inheritance(self):
        """Test StateConsistencyError inheritance."""
        error = StateConsistencyError(1, "Test message")

        assert isinstance(error, Exception)
        assert isinstance(error, StateConsistencyError)

    def test_depth_tracking_in_state_error(self):
        """Test depth tracking in StateConsistencyError."""
        for depth in [0, 3, 7, 12]:
            error = StateConsistencyError(depth, "Consistency check failed")
            assert error.depth == depth
            assert f"at depth {depth}" in str(error)

    def test_state_consistency_different_messages(self):
        """Test StateConsistencyError with different state consistency issues."""
        test_cases = [
            (1, "Character position invalid after movement",
             "State consistency error at depth 1: Character position invalid after movement"),
            (3, "Inventory state corrupted during item transfer",
             "State consistency error at depth 3: Inventory state corrupted during item transfer"),
            (0, "Initial state validation failed",
             "State consistency error at depth 0: Initial state validation failed"),
            (5, "Character level decreased unexpectedly",
             "State consistency error at depth 5: Character level decreased unexpectedly")
        ]

        for depth, message, expected_str in test_cases:
            error = StateConsistencyError(depth, message)
            assert str(error) == expected_str

    def test_state_consistency_error_raising(self):
        """Test raising and catching StateConsistencyError."""
        with pytest.raises(StateConsistencyError) as exc_info:
            raise StateConsistencyError(4, "State validation failed")

        error = exc_info.value
        assert error.depth == 4
        assert "State validation failed" in str(error)

    def test_state_consistency_error_attributes(self):
        """Test StateConsistencyError attributes accessibility."""
        error = StateConsistencyError(6, "Attribute test")

        assert hasattr(error, 'depth')
        assert error.depth == 6

        # Test attribute modification
        error.depth = 8
        assert error.depth == 8

    def test_state_consistency_empty_message(self):
        """Test StateConsistencyError with empty message."""
        error = StateConsistencyError(3, "")
        assert str(error) == "State consistency error at depth 3: "

    def test_state_consistency_negative_depth(self):
        """Test StateConsistencyError with negative depth (edge case)."""
        error = StateConsistencyError(-1, "Negative depth test")
        assert error.depth == -1
        assert "at depth -1" in str(error)


class TestExceptionInteractions:
    """Test interactions between different exception types."""

    def test_exception_hierarchy_catching(self):
        """Test catching different exceptions with appropriate handlers."""
        # Test that MaxDepthExceededError can be caught as SubGoalExecutionError
        with pytest.raises(SubGoalExecutionError):
            raise MaxDepthExceededError(5)

        # Test that specific exceptions can be caught specifically
        with pytest.raises(MaxDepthExceededError):
            raise MaxDepthExceededError(3)

    def test_multiple_exception_types_in_sequence(self):
        """Test raising different exception types in sequence."""
        exceptions_to_test = [
            SubGoalExecutionError(1, "TestGoal", "Test"),
            MaxDepthExceededError(10),
            NoValidGoalError("No goals"),
            InfeasibleGoalError("test_goal", "Infeasible"),
            StateConsistencyError(2, "Consistency failed")
        ]

        for exception in exceptions_to_test:
            with pytest.raises(type(exception)):
                raise exception

    def test_exception_chaining(self):
        """Test exception chaining for error context."""
        try:
            try:
                raise StateConsistencyError(2, "Original error")
            except StateConsistencyError as e:
                raise SubGoalExecutionError(3, "WrapperGoal", "Wrapping original error") from e
        except SubGoalExecutionError as final_error:
            assert final_error.depth == 3
            assert final_error.sub_goal_type == "WrapperGoal"
            assert final_error.__cause__ is not None
            assert isinstance(final_error.__cause__, StateConsistencyError)

    def test_exception_context_preservation(self):
        """Test that exception context is preserved through re-raising."""
        original_error = MaxDepthExceededError(5)

        try:
            raise original_error
        except MaxDepthExceededError as caught_error:
            # Verify that caught error maintains original attributes
            assert caught_error.depth == 5
            assert caught_error is original_error

    def test_exception_message_consistency(self):
        """Test that all exceptions provide consistent string representations."""
        exceptions = [
            SubGoalExecutionError(1, "TestGoal", "Test message"),
            MaxDepthExceededError(10),
            NoValidGoalError("No goals available"),
            InfeasibleGoalError("test_goal", "Goal infeasible"),
            StateConsistencyError(3, "State error")
        ]

        for exception in exceptions:
            # All exceptions should have non-empty string representations
            # (except for those explicitly created with empty messages)
            error_str = str(exception)
            assert isinstance(error_str, str)

            # Test that __repr__ works
            repr_str = repr(exception)
            assert isinstance(repr_str, str)
            assert type(exception).__name__ in repr_str


class TestExceptionUsagePatterns:
    """Test common usage patterns for exceptions in the unified sub-goal architecture."""

    def test_depth_limit_detection_pattern(self):
        """Test typical pattern for detecting depth limit exceeded."""
        def simulate_recursive_execution(current_depth, max_depth):
            if current_depth > max_depth:
                raise MaxDepthExceededError(max_depth)
            return f"Executing at depth {current_depth}"

        # Normal execution should work
        result = simulate_recursive_execution(5, 10)
        assert "Executing at depth 5" in result

        # Exceeding depth should raise exception
        with pytest.raises(MaxDepthExceededError):
            simulate_recursive_execution(15, 10)

    def test_state_validation_pattern(self):
        """Test typical pattern for state consistency validation."""
        def simulate_state_validation(character_hp, max_hp, depth):
            if character_hp > max_hp:
                raise StateConsistencyError(depth, f"HP {character_hp} exceeds max HP {max_hp}")
            return True

        # Valid state should pass
        assert simulate_state_validation(80, 100, 2) is True

        # Invalid state should raise exception
        with pytest.raises(StateConsistencyError) as exc_info:
            simulate_state_validation(120, 100, 3)

        error = exc_info.value
        assert error.depth == 3
        assert "HP 120 exceeds max HP 100" in str(error)

    def test_goal_feasibility_checking_pattern(self):
        """Test typical pattern for goal feasibility checking."""
        def simulate_goal_feasibility_check(character_level, required_level):
            if character_level < required_level:
                raise InfeasibleGoalError("level_check", f"Character level {character_level} < required level {required_level}")
            return True

        # Feasible goal should pass
        assert simulate_goal_feasibility_check(10, 5) is True

        # Infeasible goal should raise exception
        with pytest.raises(InfeasibleGoalError) as exc_info:
            simulate_goal_feasibility_check(3, 10)

        assert "level 3 < required level 10" in str(exc_info.value)

    def test_error_recovery_pattern(self):
        """Test error recovery patterns in recursive execution."""
        def simulate_sub_goal_execution_with_recovery(depth, should_fail=False):
            try:
                if should_fail:
                    raise SubGoalExecutionError(depth, "TestGoal", "Simulated failure")
                return {"success": True, "depth": depth}
            except SubGoalExecutionError as e:
                # Log error and attempt recovery
                recovery_result = {"success": False, "error": str(e), "depth": e.depth}
                return recovery_result

        # Successful execution
        success_result = simulate_sub_goal_execution_with_recovery(2, False)
        assert success_result["success"] is True
        assert success_result["depth"] == 2

        # Failed execution with recovery
        failure_result = simulate_sub_goal_execution_with_recovery(3, True)
        assert failure_result["success"] is False
        assert failure_result["depth"] == 3
        assert "TestGoal" in failure_result["error"]
