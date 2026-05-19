"""FarmItemsGoal: gather/craft items required by an items-type task."""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.task_trade import TaskTradeAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai import priorities
from artifactsmmo_cli.ai.learning.dynamic_priority import learned_priority_bonus
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState


BATCH_SIZE = 30
"""Max items per task-trade trip. Trading one item per round-trip to the
taskmaster wastes ~22s per fish in movement; batching cuts that to ~22s
per batch of 30 = ~5x speedup. Capped by bag headroom and task_remaining."""


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
        return max(1.0, priorities.FARM_ITEMS_BASE * fraction_remaining)

    def priority(self, state: WorldState, game_data: GameData,
                 history: LearningStore | None = None) -> float:
        if self.is_satisfied(state):
            return 0.0
        if state.task_type != "items" or not state.task_code or state.task_total == 0:
            return 0.0
        # G-F: base 35 (outranks FarmMonster cold-start) + projection-driven
        # bonus when observed throughput exceeds defaults. Bonus scaled by
        # sample-count confidence so we don't react to early noise.
        base = priorities.FARM_ITEMS_BASE
        bonus = learned_priority_bonus(repr(self), state, game_data, history)
        return base + bonus

    def is_satisfied(self, state: WorldState) -> bool:
        if state.task_total > 0 and state.task_progress >= state.task_total:
            return True
        return state.task_progress > self._initial_progress

    def _batch_target(self, state: WorldState) -> int:
        """How many task items to submit per trip to the taskmaster.

        Caps:
          - BATCH_SIZE (configured ceiling)
          - task_remaining (don't aim past task_total)
          - available slots + current count (don't plan to gather past bag)
        """
        if not state.task_code:
            return 1
        task_remaining = max(0, state.task_total - state.task_progress)
        current_count = state.inventory.get(state.task_code, 0)
        free_slots = max(0, state.inventory_max - state.inventory_used)
        achievable = current_count + free_slots
        return max(1, min(BATCH_SIZE, task_remaining, achievable))

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
            if "recovery" in action.tags:
                result.append(action)
            elif "deposit" in action.tags:
                result.append(action)
            elif isinstance(action, GatherAction) and action.resource_code in needed_resources:
                result.append(action)
            elif isinstance(action, CraftAction) and action.code in craftable_mats:
                result.append(action)
            elif isinstance(action, TaskTradeAction) and action.code == state.task_code:
                # Substitute the qty=1 prebuilt with a batch-sized variant.
                # Forces the planner to gather batch_target items before
                # trading — eliminates the per-fish round-trip to the
                # taskmaster.
                batch_qty = self._batch_target(state)
                result.append(TaskTradeAction(
                    code=action.code,
                    quantity=batch_qty,
                    taskmaster_location=action.taskmaster_location,
                ))
        return result

    @property
    def max_depth(self) -> int:
        return 200

    def __repr__(self) -> str:
        return "FarmItems"
