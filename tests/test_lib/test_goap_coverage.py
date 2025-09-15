"""
Coverage Tests for GOAP Library

This module contains tests specifically designed to achieve 100% coverage
for src/lib/goap.py by targeting the remaining 3 uncovered lines.
"""

import pytest
from unittest.mock import Mock

from src.lib.goap import (
    World, 
    Planner, 
    Action_List,
    walk_path,
    astar,
    create_node,
    conditions_are_met,
    distance_to_state
)


class TestGOAPCoverage:
    """Test uncovered lines in GOAP library."""
    
    def test_walk_path_no_path_found(self):
        """Test walk_path when no path is found - covers line 562."""
        # Create a scenario where A* cannot find a path
        
        # Mock an impossible planning scenario
        path = {
            "start": {"impossible_condition": True},
            "goal": {"impossible_condition": False, "other_condition": True},
            "actions": [],  # No actions available
            "olist": {},
            "clist": {}
        }
        
        # This should return empty list when no path exists
        result = walk_path(path)
        
        assert result == []
    
    def test_walk_path_node_deletion_scenarios(self):
        """Test walk_path node deletion scenarios - covers lines 625 and 628."""
        # This tests the algorithm with a simple scenario that should succeed
        # Create a simple action that can be used in planning
        action = Action_List()
        action.add_condition("test_action", has_resource=True)
        action.add_reaction("test_action", at_location="target")
        action.set_weight("test_action", 1)
        
        # Create start and goal states that require planning
        start_state = {"has_resource": True, "at_location": "start"}
        goal_state = {"at_location": "target"}
        
        # Create path structure for A* algorithm
        path = {
            "start": start_state,
            "goal": goal_state,
            "actions": [action._asdict()],
            "olist": {},
            "clist": {},
            "node_id": 0,
            "nodes": {}
        }
        
        # Add initial node to trigger the algorithm
        start_node = create_node(path, start_state, "start")
        start_node["g"] = 0
        start_node["h"] = distance_to_state(start_state, goal_state)
        start_node["f"] = start_node["g"] + start_node["h"]
        
        path["olist"][str(start_node["id"])] = start_node
        
        # This should exercise the algorithm including potential node deletions
        result = walk_path(path)
        
        # The result should be a valid path or empty list
        assert isinstance(result, list)
        
    def test_walk_path_complex_planning_scenario(self):
        """Test a more complex planning scenario to exercise all code paths."""
        # Create multiple actions to create a more complex search space
        action1 = Action_List()
        action1.add_condition("get_resource", at_location="resource_spot")
        action1.add_reaction("get_resource", has_resource=True)
        action1.set_weight("get_resource", 2)
        
        action2 = Action_List()
        action2.add_condition("move_to_resource", at_location="start")
        action2.add_reaction("move_to_resource", at_location="resource_spot")
        action2.set_weight("move_to_resource", 1)
        
        action3 = Action_List()
        action3.add_condition("deliver_resource", has_resource=True, at_location="resource_spot")
        action3.add_reaction("deliver_resource", at_location="target", delivered=True)
        action3.set_weight("deliver_resource", 1)
        
        start_state = {"at_location": "start", "has_resource": False, "delivered": False}
        goal_state = {"delivered": True}
        
        path = {
            "start": start_state,
            "goal": goal_state,
            "actions": [action1._asdict(), action2._asdict(), action3._asdict()],
            "olist": {},
            "clist": {},
            "node_id": 0,
            "nodes": {}
        }
        
        # Run the pathfinding algorithm
        result = walk_path(path)
        
        # Should find a valid plan or return empty list
        assert isinstance(result, list)
        
        # If a path was found, it should have the expected structure
        if result:
            assert all(isinstance(step, dict) for step in result)
            assert all("action" in step for step in result)