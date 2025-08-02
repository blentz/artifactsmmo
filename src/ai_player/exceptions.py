"""
Unified Sub-Goal Architecture Exceptions

This module defines custom exception classes for the unified sub-goal architecture,
providing type-safe error handling for recursive sub-goal execution and GOAP planning.
"""


class SubGoalExecutionError(Exception):
    """Raised when sub-goal execution fails"""

    def __init__(self, depth: int, sub_goal_type: str, message: str):
        self.depth = depth
        self.sub_goal_type = sub_goal_type
        super().__init__(f"Sub-goal '{sub_goal_type}' failed at depth {depth}: {message}")


class MaxDepthExceededError(SubGoalExecutionError):
    """Raised when max recursion depth is exceeded"""

    def __init__(self, max_depth: int):
        super().__init__(max_depth, "depth_limit", f"Maximum recursion depth {max_depth} exceeded")


class NoValidGoalError(Exception):
    """Raised when no feasible goals are available"""

    def __init__(self, message: str = "No valid goals are available for current state"):
        self.message = message
        super().__init__(message)


class InfeasibleGoalError(Exception):
    """Raised when a goal cannot be achieved with current state"""

    def __init__(self, goal_type: str, message: str):
        self.goal_type = goal_type
        self.message = message
        super().__init__(f"Goal '{goal_type}' is infeasible: {message}")


class StateConsistencyError(Exception):
    """Raised when state consistency validation fails during recursive execution"""

    def __init__(self, depth: int, message: str):
        self.depth = depth
        self.message = message
        super().__init__(f"State consistency error at depth {depth}: {message}")


class PlanningError(Exception):
    """Raised when GOAP planning fails"""

    def __init__(self, message: str, current_state: dict = None, target_state: dict = None):
        self.message = message
        self.current_state = current_state
        self.target_state = target_state
        super().__init__(f"GOAP planning failed: {message}")


class ExecutionTimeoutError(Exception):
    """Raised when execution exceeds timeout limits"""

    def __init__(self, timeout_seconds: int, elapsed_seconds: float):
        self.timeout_seconds = timeout_seconds
        self.elapsed_seconds = elapsed_seconds
        super().__init__(f"Execution timeout: {elapsed_seconds:.1f}s exceeded limit of {timeout_seconds}s")


class GoalFactoryError(Exception):
    """Raised when goal factory cannot create a goal from sub-goal request"""

    def __init__(self, sub_goal_type: str, message: str):
        self.sub_goal_type = sub_goal_type
        self.message = message
        super().__init__(f"Cannot create goal for sub-goal type '{sub_goal_type}': {message}")


class RecursiveSubGoalError(Exception):
    """Raised when recursive sub-goal execution encounters an error"""

    def __init__(self, parent_action: str, sub_goal_type: str, depth: int, message: str):
        self.parent_action = parent_action
        self.sub_goal_type = sub_goal_type
        self.depth = depth
        self.message = message
        super().__init__(
            f"Recursive sub-goal error: {parent_action} -> {sub_goal_type} "
            f"at depth {depth}: {message}"
        )
