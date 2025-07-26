# GOAPy
# Generic GOAP implementation.
# flags - https://github.com/flags

# The MIT License (MIT)
#
# Copyright (c) 2014 Luke Martin (flags)
# Copyright (c) 2024 Brett Lentz
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import logging
from collections.abc import Iterator
from typing import Any


class World:
    """GOAP World containing multiple planners and their calculated plans.

    The World class orchestrates multiple GOAP planners and manages their
    calculated plans, providing functionality to find the optimal plan
    across all planners based on cost.

    Attributes:
        planners: List of Planner instances for different planning scenarios
        plans: List of calculated plans from all planners
    """

    _log: logging.Logger | None

    def __init__(self) -> None:
        """Initialize a new GOAP World with empty planners and plans."""
        self.planners: list[Planner] = []
        self.plans: list[list[dict[str, Any]]] = []
        self._log: logging.Logger = logging.getLogger()

    def __iter__(self) -> Iterator[tuple[str, list[Any]]]:
        """Iterate over world attributes as key-value pairs.

        Yields:
            Tuple of (attribute_name, attribute_value) pairs
        """
        yield "planners", self.planners
        yield "plans", self.plans

    def __repr__(self) -> str:
        """Return string representation of the World.

        Returns:
            String representation of the world's state
        """
        return str(self._asdict())

    def _asdict(self) -> dict[str, list[Any]]:
        """Convert World to dictionary representation.

        Returns:
            Dictionary containing planners and plans
        """
        return {"planners": self.planners, "plans": self.plans}

    def add_planner(self, planner: "Planner") -> None:
        """Add a planner to the world.

        Args:
            planner: Planner instance to add to the world
        """
        self.planners.append(planner)

    def calculate(self) -> None:
        """Calculate plans for all planners in the world.

        Clears existing plans and recalculates plans for all planners.
        Each planner's calculate() method returns a list of actions.
        """
        self.plans = []

        for planner in self.planners:
            plan = planner.calculate()
            if plan:  # Only add non-empty plans
                self.plans.append(plan)

    def get_plan(self, debug: bool = False) -> list[list[dict[str, Any]]]:
        """Get the optimal plans sorted by cost.

        Args:
            debug: If True, log detailed plan information

        Returns:
            List of plans sorted by total cost (lowest cost first)
            Each plan is a list of action dictionaries
        """
        _plans: dict[int, list[list[dict[str, Any]]]] = {}
        for plan in self.plans:
            if not plan:  # Skip empty plans
                continue

            _plan_cost = sum([action["g"] for action in plan])

            if _plan_cost in _plans:
                _plans[_plan_cost].append(plan)
            else:
                _plans[_plan_cost] = [plan]

        _sorted_plans = sorted(_plans.keys())

        if debug and self._log:
            _i = 1
            for plan_score in _sorted_plans:
                for plan in _plans[plan_score]:
                    self._log.debug(f"Plan step: {_i}")
                    for action in plan:
                        self._log.debug(f"\t{action['name']}")
                    _i += 1
                    self._log.debug(f"Total cost: {plan_score}")

        return [_plans[p][0] for p in _sorted_plans if p in _plans and _plans[p]]


class Planner:
    """GOAP Planner for calculating action sequences from start state to goal state.

    The Planner class uses A* pathfinding to find the optimal sequence of actions
    that transforms a start state into a goal state, considering action preconditions,
    effects, and costs.

    Attributes:
        start_state: Dictionary representing the initial world state
        goal_state: Dictionary representing the desired world state
        values: Dictionary of valid state keys with default values
        action_list: Action_List containing available actions and their definitions
    """

    def __init__(self, *keys: str) -> None:
        """Initialize a new GOAP Planner with the specified state keys.

        Args:
            *keys: Variable number of state key names that this planner will track
        """
        self.start_state: dict[str, Any] | None = None
        self.goal_state: dict[str, Any] | None = None
        self.values: dict[str, int] = {k: -1 for k in keys}
        self.action_list: Action_List | None = None

    def __iter__(self) -> Iterator[tuple[str, Any]]:
        """Iterate over planner attributes as key-value pairs.

        Yields:
            Tuple of (attribute_name, attribute_value) pairs
        """
        yield "start_state", self.start_state
        yield "goal_state", self.goal_state
        yield "values", self.values
        yield "actions_list", self.action_list

    def __repr__(self) -> str:
        """Return string representation of the Planner.

        Returns:
            String representation of the planner's state
        """
        return str(self._asdict())

    def _asdict(self) -> dict[str, Any]:
        """Convert Planner to dictionary representation.

        Returns:
            Dictionary containing all planner attributes
        """
        return {
            "start_state": self.start_state,
            "goal_state": self.goal_state,
            "values": self.values,
            "actions_list": self.action_list,
        }

    def state(self, **kwargs: Any) -> dict[str, Any]:
        """Create a new state by updating the default values with provided kwargs.

        Args:
            **kwargs: Key-value pairs to update the state with

        Returns:
            Dictionary representing the new state
        """
        _new_state = self.values.copy()
        _new_state.update(kwargs)
        return _new_state

    def set_start_state(self, **kwargs: Any) -> None:
        """Set the start state for planning.

        Args:
            **kwargs: Key-value pairs representing the initial state

        Raises:
            ValueError: If any state key is not defined in the planner's values
        """
        _invalid_states = set(kwargs.keys()) - set(self.values.keys())

        if _invalid_states:
            raise ValueError(f"Invalid states for world start state: {', '.join(list(_invalid_states))}")

        self.start_state = self.state(**kwargs)

    def set_goal_state(self, **kwargs: Any) -> None:
        """Set the goal state for planning.

        Args:
            **kwargs: Key-value pairs representing the desired end state

        Raises:
            ValueError: If any state key is not defined in the planner's values
        """
        _invalid_states = set(kwargs.keys()) - set(self.values.keys())

        if _invalid_states:
            raise ValueError(f"Invalid states for world goal state: {', '.join(list(_invalid_states))}")

        self.goal_state = self.state(**kwargs)

    def set_action_list(self, action_list: "Action_List") -> None:
        """Set the action list for planning.

        Args:
            action_list: Action_List containing available actions and their definitions
        """
        self.action_list = action_list

    def calculate(self) -> list[dict[str, Any]]:
        """Calculate the optimal action sequence from start state to goal state.

        Returns:
            List of action dictionaries representing the optimal plan

        Raises:
            ValueError: If start_state, goal_state, or action_list is not set
        """
        if self.start_state is None:
            raise ValueError("Start state must be set before calculating")
        if self.goal_state is None:
            raise ValueError("Goal state must be set before calculating")
        if self.action_list is None:
            raise ValueError("Action list must be set before calculating")

        return astar(
            self.start_state,
            self.goal_state,
            {c: self.action_list.conditions[c].copy() for c in self.action_list.conditions},
            {r: self.action_list.reactions[r].copy() for r in self.action_list.reactions},
            self.action_list.weights.copy(),
        )


class Action_List:
    """Container for GOAP actions with their conditions, reactions, and weights.

    The Action_List class manages the definitions of available actions in the GOAP
    system, including their preconditions (conditions), effects (reactions), and
    planning costs (weights).

    Attributes:
        conditions: Dictionary mapping action names to their precondition states
        reactions: Dictionary mapping action names to their effect states
        weights: Dictionary mapping action names to their planning costs
    """

    def __init__(self) -> None:
        """Initialize a new empty Action_List."""
        self.conditions: dict[str, dict[str, Any]] = {}
        self.reactions: dict[str, dict[str, Any]] = {}
        self.weights: dict[str, int | float] = {}

    def __iter__(self) -> Iterator[tuple[str, dict[str, Any]]]:
        """Iterate over action list attributes as key-value pairs.

        Yields:
            Tuple of (attribute_name, attribute_value) pairs
        """
        yield "conditions", self.conditions
        yield "reactions", self.reactions
        yield "weights", self.weights

    def __repr__(self) -> str:
        """Return string representation of the Action_List.

        Returns:
            String representation of the action list's state
        """
        return str(self._asdict())

    def _asdict(self) -> dict[str, dict[str, Any]]:
        """Convert Action_List to dictionary representation.

        Returns:
            Dictionary containing conditions, reactions, and weights
        """
        return {
            "conditions": self.conditions,
            "reactions": self.reactions,
            "weights": self.weights,
        }

    def add_condition(self, key: str, **kwargs: Any) -> None:
        """Add or update preconditions for an action.

        Args:
            key: Action name/identifier
            **kwargs: Key-value pairs representing the precondition states
        """
        if key not in self.weights:
            self.weights[key] = 1

        if key not in self.conditions:
            self.conditions[key] = kwargs
            return

        self.conditions[key].update(kwargs)

    def add_reaction(self, key: str, **kwargs: Any) -> None:
        """Add or update effects for an action.

        Args:
            key: Action name/identifier (must have matching condition)
            **kwargs: Key-value pairs representing the effect states

        Raises:
            ValueError: If the action has no matching condition
        """
        if key not in self.conditions:
            raise ValueError(f"Trying to add reaction '{key}' without matching condition.")

        if key not in self.reactions:
            self.reactions[key] = kwargs
            return

        self.reactions[key].update(kwargs)

    def set_weight(self, key: str, value: int | float) -> None:
        """Set the planning cost/weight for an action.

        Args:
            key: Action name/identifier (must have matching condition)
            value: Planning cost (lower values are preferred)

        Raises:
            ValueError: If the action has no matching condition
        """
        if key not in self.conditions:
            raise ValueError(f"Trying to set weight '{key}' without matching condition.")

        self.weights[key] = value


def distance_to_state(state_1: dict[str, Any], state_2: dict[str, Any]) -> int:
    """Calculate the heuristic distance between two states for A* pathfinding.

    The distance is calculated as the number of state variables that differ
    between the two states. This serves as the heuristic function for A* search.

    Args:
        state_1: First state dictionary
        state_2: Second state dictionary

    Returns:
        Integer representing the heuristic distance between states
    """
    _scored_keys = set()
    _score = 0

    for key in state_2.keys():
        _value = state_2[key]

        if _value == -1:  # Skip wildcard values
            continue

        if key not in state_1 or state_1[key] != _value:
            _score += 1

        _scored_keys.add(key)

    for key in state_1.keys():
        if key in _scored_keys:
            continue

        _value = state_1[key]

        if _value == -1:  # Skip wildcard values
            continue

        if key not in state_2 or state_2[key] != _value:
            _score += 1

    return _score


def conditions_are_met(state_1: dict[str, Any], state_2: dict[str, Any]) -> bool:
    """Check if all conditions in state_2 are satisfied by state_1.

    This function determines if state_1 satisfies all the non-wildcard
    conditions specified in state_2. Used to check action preconditions.

    Args:
        state_1: Current state dictionary
        state_2: Required conditions dictionary

    Returns:
        True if all conditions are met, False otherwise
    """
    for key in state_2.keys():
        _value = state_2[key]

        if _value == -1:  # Skip wildcard values
            continue

        if key not in state_1 or state_1[key] != state_2[key]:
            return False

    return True


def node_in_list(node: dict[str, Any], node_list: dict[int, dict[str, Any]]) -> bool:
    """Check if a node with the same state and name exists in the node list.

    Used by the A* algorithm to avoid duplicate nodes in the open/closed lists.

    Args:
        node: Node dictionary to search for
        node_list: Dictionary of nodes to search in

    Returns:
        True if a matching node is found, False otherwise
    """
    for next_node in node_list.values():
        if node["state"] == next_node["state"] and node["name"] == next_node["name"]:
            return True

    return False


def create_node(path: dict[str, Any], state: dict[str, Any], name: str = "") -> dict[str, Any]:
    """Create a new node for the A* pathfinding algorithm.

    Args:
        path: Path context containing node tracking information
        state: State dictionary for the new node
        name: Optional name/identifier for the node

    Returns:
        Dictionary representing the new node with A* algorithm fields
    """
    path["node_id"] += 1
    new_node: dict[str, Any] = {
        "state": state,
        "f": 0,  # Total cost (g + h)
        "g": 0,  # Cost from start
        "h": 0,  # Heuristic cost to goal
        "p_id": None,  # Parent node ID
        "id": path["node_id"],
        "name": name,
    }
    path["nodes"][path["node_id"]] = new_node

    return new_node


def astar(
    start_state: dict[str, Any],
    goal_state: dict[str, Any],
    actions: dict[str, dict[str, Any]],
    reactions: dict[str, dict[str, Any]],
    weight_table: dict[str, int | float],
) -> list[dict[str, Any]]:
    """A* pathfinding algorithm for GOAP action planning.

    Finds the optimal sequence of actions to transform the start state
    into the goal state using A* search with action costs and heuristics.

    Args:
        start_state: Initial state dictionary
        goal_state: Target state dictionary
        actions: Dictionary mapping action names to their preconditions
        reactions: Dictionary mapping action names to their effects
        weight_table: Dictionary mapping action names to their costs

    Returns:
        List of action dictionaries representing the optimal plan
    """
    _path: dict[str, Any] = {
        "nodes": {},
        "node_id": 0,
        "goal": goal_state,
        "actions": actions,
        "reactions": reactions,
        "weight_table": weight_table,
        "action_nodes": {},
        "olist": {},  # Open list for A*
        "clist": {},  # Closed list for A*
    }

    _start_node = create_node(_path, start_state, name="start")
    _start_node["g"] = 0
    _start_node["h"] = distance_to_state(start_state, goal_state)
    _start_node["f"] = _start_node["g"] + _start_node["h"]
    _path["olist"][_start_node["id"]] = _start_node

    for action in actions:
        _path["action_nodes"][action] = create_node(_path, actions[action], name=action)

    return walk_path(_path)


def walk_path(path: dict[str, Any]) -> list[dict[str, Any]]:
    """Execute the A* pathfinding algorithm to find the optimal action sequence.

    This is the main A* search loop that explores nodes and builds the optimal
    path from start state to goal state.

    Args:
        path: Path context containing all A* algorithm state

    Returns:
        List of action dictionaries representing the optimal plan, or empty list if no path found
    """
    node = None

    _clist = path["clist"]  # Closed list
    _olist = path["olist"]  # Open list

    while len(_olist):
        ####################
        ##Find lowest node##
        ####################

        _lowest = {"node": None, "f": 9000000}

        for next_node in _olist.values():
            if not _lowest["node"] or next_node["f"] < _lowest["f"]:
                _lowest["node"] = next_node["id"]
                _lowest["f"] = next_node["f"]

        if _lowest["node"]:
            node = path["nodes"][_lowest["node"]]

        else:
            return []  # No path found

        ################################
        ##Remove node with lowest rank##
        ################################

        del _olist[node["id"]]

        #######################################
        ##If it matches the goal, we are done##
        #######################################

        if conditions_are_met(node["state"], path["goal"]):
            _path = []

            while node["p_id"]:
                _path.append(node)

                node = path["nodes"][node["p_id"]]

            _path.reverse()

            return _path

        ####################
        ##Add it to closed##
        ####################

        _clist[node["id"]] = node

        ##################
        ##Find neighbors##
        ##################

        _neighbors = []

        for action_name in path["action_nodes"]:
            if not conditions_are_met(node["state"], path["action_nodes"][action_name]["state"]):
                continue

            path["node_id"] += 1

            _c_node = node.copy()
            _c_node["state"] = node["state"].copy()
            _c_node["id"] = path["node_id"]
            _c_node["name"] = action_name

            for key in path["reactions"][action_name]:
                _value = path["reactions"][action_name][key]

                if _value == -1:
                    continue

                _c_node["state"][key] = _value

            path["nodes"][_c_node["id"]] = _c_node
            _neighbors.append(_c_node)

        for next_node in _neighbors:
            _g_cost = node["g"] + path["weight_table"][next_node["name"]]
            _in_olist, _in_clist = node_in_list(next_node, _olist), node_in_list(next_node, _clist)

            if _in_olist and _g_cost < next_node["g"]:
                del _olist[next_node]

            if _in_clist and _g_cost < next_node["g"]:
                del _clist[next_node["id"]]

            if not _in_olist and not _in_clist:
                next_node["g"] = _g_cost
                next_node["h"] = distance_to_state(next_node["state"], path["goal"])
                next_node["f"] = next_node["g"] + next_node["h"]
                next_node["p_id"] = node["id"]

                _olist[next_node["id"]] = next_node

    return []
