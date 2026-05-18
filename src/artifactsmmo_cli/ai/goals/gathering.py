"""Gathering goal: accumulate materials needed to craft an upgrade."""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState


class GatherMaterialsGoal(Goal):
    """Gather resources needed to craft a specific upgrade item."""

    def __init__(self, target_item: str, needed: dict[str, int]) -> None:
        self._target_item = target_item
        self._needed = needed  # {material_code: quantity_needed}

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        base = self._compute_base_value(state, game_data)
        if history is None:
            return base
        avg_cycles = history.goal_avg_cycles_to_satisfy(repr(self), window=20)
        if avg_cycles is None or avg_cycles == 0:
            return base
        efficiency = min(1.0, 5.0 / avg_cycles)
        return base * efficiency

    def _compute_base_value(self, state: WorldState, game_data: GameData) -> float:
        if self.is_satisfied(state):
            return 0.0
        total_needed = sum(self._needed.values())
        bank = state.bank_items or {}
        total_effective = 0.0
        for mat, qty_needed in self._needed.items():
            have_direct = state.inventory.get(mat, 0) + bank.get(mat, 0)
            total_effective += min(have_direct, qty_needed)
            # Count intermediate materials that can be crafted into mat (float for smooth gradient)
            recipe = game_data._crafting_recipes.get(mat) or {}
            for intermediate, qty_per in recipe.items():
                have_inter = state.inventory.get(intermediate, 0) + bank.get(intermediate, 0)
                if qty_per > 0:
                    craftable = min(have_inter / qty_per, qty_needed - min(have_direct, qty_needed))
                    total_effective += craftable
        fraction_remaining = 1.0 - total_effective / total_needed
        return max(1.0, 40.0 * fraction_remaining)

    def priority(self, state: WorldState, game_data: GameData,
                 history: LearningStore | None = None) -> float:
        """Fixed high priority until satisfied — keeps gathering ahead of farming regardless of XP fraction."""
        if self.is_satisfied(state):
            return 0.0
        return 50.0

    def relevant_actions(self, actions: list[Action], state: WorldState, game_data: GameData) -> list[Action]:
        """Restrict planning to gather/smelt/deposit — excludes combat and unrelated gathers."""
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

        visited: set[str] = set()
        for mat in self._needed:
            collect(mat, visited)

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
        return result

    @property
    def max_depth(self) -> int:
        # Deep chains (3+ levels) can require dozens of steps per unit.
        # Use a generous multiplier so the planner budget (2s) is the real cutoff.
        total_units = sum(self._needed.values())
        return max(100, total_units * 100)

    def is_satisfied(self, state: WorldState) -> bool:
        bank = state.bank_items or {}
        return all(
            state.inventory.get(mat, 0) + bank.get(mat, 0) >= qty
            for mat, qty in self._needed.items()
        )

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"inventory": self._needed}

    def __repr__(self) -> str:
        return f"GatherMaterials({self._target_item})"
