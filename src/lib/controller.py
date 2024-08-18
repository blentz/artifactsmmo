from artifacts_openapi import APIConfig

from .character import CharacterState
from .map import MapState
from .world import WorldState
from .yaml_data import GoapData

ARTIFACTS_BASE_URL: str = "https://api.artifactsmmo.com"
API_CONFIG: APIConfig = APIConfig(base_path=ARTIFACTS_BASE_URL)


class GameController(GoapData):
    """This class is this game's joystick."""

    character: CharacterState = None
    map: MapState = None
    world_state: WorldState = None

    def __init__(self, character: str, filename: str = "controller.yaml"):
        GoapData.__init__(self, filename=filename)
        self.character: CharacterState = CharacterState(name=character, api_config_override=API_CONFIG)
        self.character.save()  # persist current state

        self.map: MapState = MapState(api_config_override=API_CONFIG)
        self.map.scan(self.character["x"], self.character["y"])
        self.map.save()  # persist current state
        
        # fetch goals
        goals: dict = self._get_goals()
        goal_met: bool = False
        self.world_state: WorldState = WorldState()
        while not goal_met:
            self.world_state.world.calculate()
            self.world_state.save()  # persist current state

            plan: list[dict] = self.world_state.world.get_plan(debug=True)[0]
            self._log.debug(f"PLAN: {plan}")

            # run each step in the plan
            results = []
            for step in plan:
                name: str = step.get("name", None)
                state: dict = step.get("state", {})
                results.append(self.execute_plans(name, state))

            goal_met = self.check_goal_met(results)
            if not goal_met:
                # update planners w/ execution results
                self.update_plans(results)

    def _get_goals(self) -> dict:
        goals: dict = {}
        for plan in self.planners:
            for goal, value in plan.goal_state.items():
                if value != -1:
                    goals[goal] = value
        self._log.debug(f"GOALS: {goals}")
        return goals

    def check_goal_met(self, state: dict) -> bool:
        """ TODO """
        return True

    def execute_plans(self, name: str, state: list[dict]) -> dict:
        """ TODO Run actions against API. """
        return {}

    def update_plans(self, updates: dict):
        """ TODO Update actions with API response data. """
        # todo: do updates to self.planners
        self.world_state.planners = self.planners
        self.world_state.save()  # persist current state

class ActionsRunner(object):
    """ Base class for actions_runners. """