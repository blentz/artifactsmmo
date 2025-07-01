
from yaml import SafeDumper

from src.lib.goap import Action_List, Planner, World
from src.lib.yaml_data import YamlData


def represent_world(dumper, data):
    return dumper.represent_dict(data._asdict())


def represent_planner(dumper, data):
    return dumper.represent_dict(data._asdict())


def represent_actions_list(dumper, data):
    return dumper.represent_dict(data._asdict())


SafeDumper.add_representer(World, represent_world)
SafeDumper.add_representer(Planner, represent_planner)
SafeDumper.add_representer(Action_List, represent_actions_list)


class GoapData(YamlData):
    """Goal-Oriented YAML data."""

    def __init__(self, filename="goap_data.yaml"):
        # Ensure these attributes are initialized properly before calling super()
        object.__setattr__(self, 'planners', [])
        object.__setattr__(self, 'actions', None)
        super().__init__(filename=filename)

    def __repr__(self):
        out = 'GoapData({}): data={}, planners={}'
        return out.format(self.filename, self.data or {}, len(self.planners))

    def __iter__(self):
        yield "data", self.data
        yield "planners", self.planners

    def _load_actions(self, actions):
        action_list = Action_List()
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
        # Clear existing planners to avoid duplication on reload
        self.planners = []
        data = YamlData.load(self) or {}
        if isinstance(data, dict):
            self._load_planners(data.get("planners", {}))
            self.data = data.get("data", {})
        else:
            self.data = {}

    def save(self, **kwargs):
        """public interface for saving data to disk"""
        super().save(**{"planners": self.planners, **kwargs})
