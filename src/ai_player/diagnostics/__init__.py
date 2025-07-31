"""
Diagnostic System Module

Provides comprehensive diagnostic capabilities for troubleshooting
GOAP planning, state management, and action execution issues.
Essential for debugging and system monitoring.

This module exports all diagnostic classes for use throughout the AI player
system and CLI diagnostic commands:

- StateDiagnostics: State validation and analysis utilities
- ActionDiagnostics: Action registry inspection and validation
- PlanningDiagnostics: GOAP planning process analysis and visualization

Example usage:
    from .diagnostics import StateDiagnostics, ActionDiagnostics, PlanningDiagnostics

    # Create diagnostic instances
    state_diag = StateDiagnostics()
    action_diag = ActionDiagnostics(action_registry)
    planning_diag = PlanningDiagnostics(goal_manager)

    # Validate state
    state_issues = state_diag.detect_invalid_state_values(current_state)

    # Analyze actions
    action_errors = action_diag.validate_action_registry()

    # Test planning
    plan_feasible = planning_diag.test_goal_reachability(start_state, goal_state)
"""

from .action_diagnostics import ActionDiagnostics
from .planning_diagnostics import PlanningDiagnostics
from .state_diagnostics import StateDiagnostics

__all__ = [
    "StateDiagnostics",
    "ActionDiagnostics",
    "PlanningDiagnostics"
]
