# GOAPy
# Generic GOAP implementation.
# flags - https://github.com/flags
#
# IMPORTANT: This GOAP library supports any comparable object type that implements 
# Python's __cmp__() method. This includes nested dictionaries, custom objects, 
# and complex data structures. DO NOT flatten parameters or try to convert 
# everything to basic types - the library handles comparison natively.

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


class World:
    _log = None

    def __init__(self):
        self.planners = []
        self.plans = []
        self._log = logging.getLogger()

    def __iter__(self):
        yield "planners", self.planners
        yield "plans", self.plans

    def __repr__(self):
        return str(self._asdict())

    def _asdict(self) -> dict[str, list]:
        return {"planners": self.planners, "plans": self.plans}

    def add_planner(self, planner):
        self.planners.append(planner)

    def calculate(self):
        self.plans = []

        for planner in self.planners:
            self.plans.append(planner.calculate())

    def get_plan(self, debug=False):
        _plans = {}
        for plan in self.plans:
            _plan_cost = sum([action["g"] for action in plan])

            if _plan_cost in _plans:
                _plans[_plan_cost].append(plan)
            else:
                _plans[_plan_cost] = [plan]

        _sorted_plans = sorted(_plans.keys())

        if debug:
            _i = 1
            for plan_score in _sorted_plans:
                for plan in _plans[plan_score]:
                    self._log.debug(f"Plan step: {_i}")
                    for action in plan:
                        self._log.debug(f"\t{action['name']}")
                    _i += 1
                    self._log.debug("Total cost: %s" % plan_score)

        return [_plans[p][0] for p in _sorted_plans]


class Planner:
    def __init__(self, *keys):
        self.start_state = None
        self.goal_state = None
        self.values = {k: -1 for k in keys}
        self.action_list = None

    def __iter__(self):
        yield "start_state", self.start_state
        yield "goal_state", self.goal_state
        yield "values", self.values
        yield "actions_list", self.action_list

    def __repr__(self):
        return str(self._asdict())

    def _asdict(self) -> dict:
        return {
            "start_state": self.start_state,
            "goal_state": self.goal_state,
            "values": self.values,
            "actions_list": self.action_list,
        }

    def state(self, **kwargs):
        _new_state = self.values.copy()
        _new_state.update(kwargs)

        return _new_state

    def set_start_state(self, **kwargs):
        _invalid_states = set(kwargs.keys()) - set(self.values.keys())

        if _invalid_states:
            raise Exception(
                "Invalid states for world start state: %s"
                % ", ".join(list(_invalid_states))
            )

        self.start_state = self.state(**kwargs)

    def set_goal_state(self, **kwargs):
        _invalid_states = set(kwargs.keys()) - set(self.values.keys())

        if _invalid_states:
            raise Exception(
                "Invalid states for world goal state: %s"
                % ", ".join(list(_invalid_states))
            )

        self.goal_state = self.state(**kwargs)

    def set_action_list(self, action_list):
        self.action_list = action_list

    def calculate(self):
        return astar(
            self.start_state,
            self.goal_state,
            {
                c: self.action_list.conditions[c].copy()
                for c in self.action_list.conditions
            },
            {
                r: self.action_list.reactions[r].copy()
                for r in self.action_list.reactions
            },
            self.action_list.weights.copy(),
        )


class Action_List:
    def __init__(self):
        self.conditions = {}
        self.reactions = {}
        self.weights = {}

    def __iter__(self):
        yield "conditions", self.conditions
        yield "reactions", self.reactions
        yield "weights", self.weights

    def __repr__(self):
        return str(self._asdict())

    def _asdict(self) -> dict[str, dict]:
        return {
            "conditions": self.conditions,
            "reactions": self.reactions,
            "weights": self.weights,
        }

    def add_condition(self, key, **kwargs):
        if key not in self.weights:
            self.weights[key] = 1

        if key not in self.conditions:
            self.conditions[key] = kwargs

            return

        self.conditions[key].update(kwargs)

    def add_reaction(self, key, **kwargs):
        if key not in self.conditions:
            raise Exception(
                "Trying to add reaction '%s' without matching condition." % key
            )

        if key not in self.reactions:
            self.reactions[key] = kwargs

            return

        self.reactions[key].update(kwargs)

    def set_weight(self, key, value):
        if key not in self.conditions:
            raise Exception(
                "Trying to set weight '%s' without matching condition." % key
            )

        self.weights[key] = value


def _states_match(value1, value2):
    """Check if two state values match, supporting complex types.
    
    Args:
        value1: First value to compare
        value2: Second value to compare
        
    Returns:
        bool: True if values match according to type-specific rules
    """
    # Handle -1 (unspecified) values
    if value1 == -1 or value2 == -1:
        return True
    
    # Handle None values
    if value1 is None or value2 is None:
        return value1 == value2
    
    # String comparison - exact match
    if isinstance(value1, str) and isinstance(value2, str):
        return value1 == value2
    
    # List comparison - exact match
    if isinstance(value1, list) and isinstance(value2, list):
        return value1 == value2
    
    # Dict comparison - value2 can be a subset of value1
    if isinstance(value1, dict) and isinstance(value2, dict):
        # Check if all keys in value2 exist in value1 with matching values
        for key, val in value2.items():
            if key not in value1 or value1[key] != val:
                return False
        return True
    
    # Numeric comparison - handle both int and float
    if isinstance(value1, (int, float)) and isinstance(value2, (int, float)):
        return value1 == value2
    
    # Boolean comparison
    if isinstance(value1, bool) and isinstance(value2, bool):
        return value1 == value2
    
    # Default: direct comparison
    return value1 == value2


def distance_to_state(state_1, state_2):
    """Calculate the distance between two states.
    
    Now supports complex types:
    - Strings: exact match required
    - Lists: exact match required
    - Dicts: exact match or subset matching
    - Booleans: traditional true/false matching
    """
    _scored_keys = set()
    _score = 0

    for key in state_2.keys():
        _value = state_2[key]

        if _value == -1:
            continue

        # Get corresponding value from state_1
        state_1_value = state_1.get(key, -1)
        
        # Compare values based on type
        if not _states_match(state_1_value, _value):
            _score += 1

        _scored_keys.add(key)

    for key in state_1.keys():
        if key in _scored_keys:
            continue

        _value = state_1[key]

        if _value == -1:
            continue

        # Get corresponding value from state_2
        state_2_value = state_2.get(key, -1)
        
        # Compare values based on type
        if not _states_match(_value, state_2_value):
            _score += 1

    return _score


def conditions_are_met(state_1, state_2):
    """Check if conditions in state_2 are met by state_1.
    
    Now supports complex types with type-specific matching rules.
    """
    # print state_1, state_2
    for key in state_2.keys():
        _value = state_2[key]

        if _value == -1:
            continue

        # Get corresponding value from state_1
        state_1_value = state_1.get(key, -1)
        
        # Use type-aware matching
        if not _states_match(state_1_value, _value):
            return False

    return True


def node_in_list(node, node_list):
    for next_node in node_list.values():
        if node["state"] == next_node["state"] and node["name"] == next_node["name"]:
            return True

    return False


def create_node(path, state, name=""):
    path["node_id"] += 1
    path["nodes"][path["node_id"]] = {
        "state": state,
        "f": 0,
        "g": 0,
        "h": 0,
        "p_id": None,
        "id": path["node_id"],
        "name": name,
    }

    return path["nodes"][path["node_id"]]


def astar(start_state, goal_state, actions, reactions, weight_table):
    _path = {
        "nodes": {},
        "node_id": 0,
        "goal": goal_state,
        "actions": actions,
        "reactions": reactions,
        "weight_table": weight_table,
        "action_nodes": {},
        "olist": {},
        "clist": {},
    }

    _start_node = create_node(_path, start_state, name="start")
    _start_node["g"] = 0
    _start_node["h"] = distance_to_state(start_state, goal_state)
    _start_node["f"] = _start_node["g"] + _start_node["h"]
    _path["olist"][_start_node["id"]] = _start_node

    for action in actions:
        _path["action_nodes"][action] = create_node(_path, actions[action], name=action)

    return walk_path(_path)


def walk_path(path):
    node = None

    _clist = path["clist"]
    _olist = path["olist"]
    
    # Add iteration limit to prevent infinite loops
    max_iterations = 10000
    iterations = 0
    
    # Log entry to walk_path
    logger = logging.getLogger(__name__)
    logger.debug(f"GOAP A* walk_path started. Goal: {path.get('goal', {})}")

    while len(_olist) and iterations < max_iterations:
        iterations += 1
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
            return

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
            if not conditions_are_met(
                node["state"], path["action_nodes"][action_name]["state"]
            ):
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
            _in_olist, _in_clist = node_in_list(next_node, _olist), node_in_list(
                next_node, _clist
            )

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
    
    # Log if we hit the iteration limit
    if iterations >= max_iterations:
        logger = logging.getLogger(__name__)
        logger.error(f"GOAP A* search hit iteration limit ({max_iterations}). Open list size: {len(_olist)}, Closed list size: {len(_clist)}")
        logger.error(f"Goal state: {path['goal']}")
        # Return empty list to indicate no path found
        return []

    return []
