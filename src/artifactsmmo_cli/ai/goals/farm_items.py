"""FarmItemsGoal: gather/craft items required by an items-type task."""

from artifactsmmo_cli.ai.actions.bank import DepositAllAction
from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.actions.task_trade import TaskTradeAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState


class FarmItemsGoal(Goal):
    """Gather or craft the items required by the current items-type task.

    Per-cycle horizon: satisfied when task_progress advances by at least one
    submission from the value observed at goal construction. Keeps planner
    plans short (gather + craft + trade) so the outer loop re-plans after
    every submission and big tasks (e.g. 23 ash_planks) don't explode the
    A* search space.
    """

    def __init__(self, initial_progress: int = 0) -> None:
        self._initial_progress = initial_progress

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if self.is_satisfied(state):
            return 0.0
        if state.task_type != "items" or not state.task_code or state.task_total == 0:
            return 0.0
        remaining = state.task_total - state.task_progress
        fraction_remaining = remaining / state.task_total
        return max(1.0, 35.0 * fraction_remaining)

    def priority(self, state: WorldState, game_data: GameData,
                 history: LearningStore | None = None) -> float:
        if self.is_satisfied(state):
            return 0.0
        if state.task_type != "items" or not state.task_code or state.task_total == 0:
            return 0.0
        # Outranks FarmMonster base (30) so the active task is pursued first.
        return 35.0

    def is_satisfied(self, state: WorldState) -> bool:
        if state.task_total > 0 and state.task_progress >= state.task_total:
            return True
        return state.task_progress > self._initial_progress

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"task_progress": self._initial_progress + 1}

    def relevant_actions(self, actions: list[Action], state: WorldState, game_data: GameData) -> list[Action]:
        if not state.task_code:
            return []
        needed_resources: set[str] = set()
        craftable_mats: set[str] = set()

        def collect(material: str, visited: set[str]) -> None:
            if material in visited:
                return
            visited.add(material)
            for resource_code, drop_item in game_data._resource_drops.items():
                if drop_item == material:
                    needed_resources.add(resource_code)
            recipe = game_data._crafting_recipes.get(material) or {}
            if recipe:
                craftable_mats.add(material)
                for sub_mat in recipe:
                    collect(sub_mat, visited)

        collect(state.task_code, set())

        result: list[Action] = []
        for action in actions:
            if isinstance(action, RestAction):
                result.append(action)
            elif isinstance(action, DepositAllAction):
                result.append(action)
            elif isinstance(action, GatherAction) and action.resource_code in needed_resources:
                result.append(action)
            elif isinstance(action, CraftAction) and action.code in craftable_mats:
                result.append(action)
            elif isinstance(action, TaskTradeAction) and action.code == state.task_code:
                result.append(action)
        return result

    @property
    def max_depth(self) -> int:
        return 200

    def __repr__(self) -> str:
        return "FarmItems"
