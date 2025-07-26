import logging
from typing import Any

from yaml import SafeDumper

from .goap import Action_List, Planner, World
from .yaml_data import YamlData


def represent_world(dumper: SafeDumper, data: World) -> Any:
    return dumper.represent_dict(data._asdict())


def represent_planner(dumper: SafeDumper, data: Planner) -> Any:
    return dumper.represent_dict(data._asdict())


def represent_actions_list(dumper: SafeDumper, data: Action_List) -> Any:
    return dumper.represent_dict(data._asdict())


SafeDumper.add_representer(World, represent_world)
SafeDumper.add_representer(Planner, represent_planner)
SafeDumper.add_representer(Action_List, represent_actions_list)


class GoapData(YamlData):
    """Goal-Oriented YAML data."""

    def __init__(self, filename: str = "data.yaml") -> None:
        self._log: logging.Logger = logging.getLogger()
        self.filename: str = filename
        self.planners: list[Planner] = []
        self.actions: Action_List | None = None
        self.data: dict[str, Any] = {}
        self.load()

    def __repr__(self) -> str:
        return f'GoapData({self.filename}): {{ "data": {self.data}, "planners": {len(self.planners)} }}'

    def __iter__(self) -> Any:
        yield "data", self.data
        yield "planners", self.planners

    def _load_actions(self, actions: dict[str, Any]) -> Action_List | None:
        if not isinstance(actions, dict):
            self._log.error("actions must be a dictionary.")
            return None

        action_list = Action_List()

        for key, val in actions.items():
            if not isinstance(val, dict):
                self._log.error(f"Action '{key}' must be a dictionary configuration.")
                continue

            action_name: str = key
            conditions: dict[str, Any] = val.get("conditions", {})
            if not conditions:
                self._log.error(f"conditions not found in action '{action_name}'.")
                continue

            reactions: dict[str, Any] = val.get("reactions", {})
            if not reactions:
                self._log.error(f"reactions not found in action '{action_name}'.")
                continue

            try:
                action_list.add_condition(action_name, **conditions)
                action_list.add_reaction(action_name, **reactions)
            except ValueError as e:
                self._log.error(f"Failed to add action '{action_name}': {e}")
                continue

        return action_list

    def _load_planners(self, planners: list[dict[str, Any]]) -> None:
        if not isinstance(planners, list):
            self._log.error("planners must be a list of planner configurations.")
            return

        for plan in planners:
            if not isinstance(plan, dict):
                self._log.error("Each planner must be a dictionary configuration.")
                continue

            start_state: dict[str, Any] = plan.get("start_state", {})
            if not start_state:
                self._log.error("start_state not found in planner.")
                continue

            goal_state: dict[str, Any] = plan.get("goal_state", {})
            if not goal_state:
                self._log.error("goal_state not found in planner.")
                continue

            keys: set[str] = set(list(start_state.keys()) + list(goal_state.keys()))

            try:
                planner: Planner = Planner(*keys)
                planner.set_start_state(**start_state)
                planner.set_goal_state(**goal_state)
            except ValueError as e:
                self._log.error(f"Failed to create planner: {e}")
                continue

            actions: dict[str, Any] = plan.get("actions_list", {})
            if not actions:
                self._log.error("actions_list not found in planner.")
                continue

            actions_list: Action_List | None = self._load_actions(actions)
            if not actions_list:
                self._log.error("Failed to load actions list.")
                continue

            actions_weights: dict[str, float] = plan.get("actions_weights", {})
            if not actions_weights:
                self._log.error("actions_weights not found in planner.")
                continue

            try:
                for k, v in actions_weights.items():
                    actions_list.set_weight(k, v)
                planner.set_action_list(action_list=actions_list)
            except ValueError as e:
                self._log.error(f"Failed to set action weights: {e}")
                continue

            self.planners.append(planner)

    def load(self) -> dict[str, Any]:
        data: dict[str, Any] = YamlData.load(self)  # type: ignore
        if not data:
            self._log.warning("No data loaded from YAML file.")
            data = {}

        self.planners.clear()
        planners_data = data.get("planners", [])
        if planners_data:
            self._load_planners(planners_data)

        self.data = data.get("data", {})
        return data

    def save(self, **kwargs: Any) -> None:
        """public interface for saving data to disk"""
        super().save(**{"planners": self.planners, **kwargs})  # type: ignore

