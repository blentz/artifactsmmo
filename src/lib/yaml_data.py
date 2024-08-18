import logging
import os.path

from yaml import safe_load, safe_dump, SafeDumper

from .goap import Planner, Action_List, World


def represent_world(dumper: SafeDumper, data: World):
    return dumper.represent_dict(data._asdict())


def represent_planner(dumper: SafeDumper, data: Planner):
    return dumper.represent_dict(data._asdict())


def represent_actions_list(dumper: SafeDumper, data: Action_List):
    return dumper.represent_dict(data._asdict())


SafeDumper.add_representer(World, represent_world)
SafeDumper.add_representer(Planner, represent_planner)
SafeDumper.add_representer(Action_List, represent_actions_list)


class YamlData(object):
    """Data stored in YAML."""

    data: dict[str, dict] = None
    filename: str = None
    _log: logging.Logger = None

    def __init__(self, filename: str = "data.yaml"):
        self._log = logging.getLogger()
        self.filename = filename
        self.data = self.load()
        self._log.debug(f"YamlData({self.filename}): {self.data}")

    def __repr__(self):
        return f"YamlData({self.filename}): {self.data}"

    def __iter__(self):
        yield "data", self.data

    def __getitem__(self, key):
        return self.data[key]

    def _load_yaml(self, filename: str) -> dict[str, dict]:
        doc: dict[str, dict] = {}
        if not os.path.exists(filename):
            self._log.debug(f"YamlData({filename}): file not found. creating...")
            self._save_yaml(doc)
            return doc

        with open(filename, "r") as fn:
            self._log.debug(f"YamlData({filename}): file found. loading...")
            doc = safe_load(fn)
            if doc:
                return doc
            return {}

    def _save_yaml(self, data: dict[str, dict]):
        self._log.debug(f"YamlData({self.filename}): saving...")
        with open(self.filename, "w") as fn:
            safe_dump(data, fn)

    def load(self) -> dict[str, object]:
        """public interface for loading data from disk"""
        return self._load_yaml(self.filename)

    def save(self, **kwargs):
        """public interface for saving data to disk"""
        if not self.data or "data" not in self.data:
            self._save_yaml({"data": self.data, **kwargs})
        else:
            self._save_yaml({**self.data, **kwargs})


class GoapData(YamlData):
    """Goal-Oriented YAML data."""

    planners: list[Planner] = []

    def __repr__(self):
        out = 'GoapData({}): { "actions": {}, "data": {}, "planners": {}, }'
        return out.format(self.filename, self.actions, self.data, self.planners)

    def __iter__(self):
        yield "data", self.data
        yield "planners", self.planners

    def _load_actions(self, actions: dict[str, dict]) -> Action_List:
        action_list: Action_List = Action_List()
        for key, val in actions.items():
            action_name: str = key
            conditions: dict = val.get("conditions", {})
            if not conditions:
                self._log.error("conditions not found in actions list.")

            reactions: dict = val.get("reactions", {})
            if not reactions:
                self._log.error("reactions not found in actions list.")

            action_list.add_condition(action_name, **conditions)
            action_list.add_reaction(action_name, **reactions)
        return action_list

    def _load_planners(self, planners: dict[str, dict]):
        for plan in planners:
            start_state: dict = plan.get("start_state", {})
            if not start_state:
                self._log.error("start_state not found in planner.")

            goal_state: dict = plan.get("goal_state", {})
            if not goal_state:
                self._log.error("goal_state not found in planner.")

            keys: set[str] = set(list(start_state.keys()) + list(goal_state.keys()))

            planner: Planner = Planner(*keys)
            planner.set_start_state(**start_state)
            planner.set_goal_state(**goal_state)

            actions: dict = plan.get("actions_list", {})
            if not actions:
                self._log.error("actions_list not found in planner.")
            actions_list: Action_List = self._load_actions(actions)

            actions_weights: dict[str, float] = plan.get("actions_weights", {})
            if not actions_weights:
                self._log.error("actions_weights not found in planner.")
            for k, v in actions_weights.items():
                actions_list.set_weight(k, v)
            planner.set_action_list(action_list=actions_list)

            self.planners.append(planner)

    def load(self):
        data = YamlData.load(self)
        self._load_planners(data.get("planners", {}))
        self.data = data.get("data", {})

    def save(self, **kwargs):
        """public interface for saving data to disk"""
        super().save(**{"planners": self.planners, **kwargs})
