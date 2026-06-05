"""CraftReliefGoal: convert raw materials into a goal item under inventory
pressure, instead of depositing or discarding them.

Fired by the CRAFT_RELIEF guard (tiers/guards.py) when inv >= ~70% AND the
bot can craft a target/gear/tools item from current inventory. Replaces the
default ladder routing of DEPOSIT_FULL / DISCARD_HIGH for that cycle.

The goal is satisfied the moment one unit of the target item appears in
inventory — the planner's shortest path is a single CraftAction (or Move +
Craft), which immediately frees recipe-input slots and advances task /
gear progress in one stroke."""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState


class CraftReliefGoal(Goal):
    """Craft one+ unit of `target_item` to convert raw mats into goal product.

    Value sits at the HP-floor band so a fired CRAFT_RELIEF guard outranks
    PursueTask / GatherMaterials but stays under survival goals. The
    guard-firing predicate is the real gate; once the guard fires the goal
    is unconditionally pursued for the cycle."""

    _GUARD_VALUE = 70.0  # equal to survival floor — guard tier owns the firing decision

    def __init__(self, target_item: str, initial_qty: int, batch: int = 1) -> None:
        self._target_item = target_item
        self._initial_qty = initial_qty
        self._batch = max(1, batch)

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        return 0.0 if self.is_satisfied(state) else self._GUARD_VALUE

    def is_satisfied(self, state: WorldState) -> bool:
        # One additional unit crafted satisfies the goal — the planner then
        # re-decides next cycle (likely fires CRAFT_RELIEF again until inv
        # pressure relaxes or no more craftables remain).
        return state.inventory.get(self._target_item, 0) >= self._initial_qty + 1

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"inventory": {self._target_item: self._initial_qty + 1}}

    def relevant_actions(self, actions: list[Action], state: WorldState,
                         game_data: GameData) -> list[Action]:
        """Move + Craft of the target item + Withdraw of any recipe input
        already in the bank. Withdraw lets the bot pull mats from the bank
        instead of failing the craft when ingredients are split between
        inventory and bank."""
        recipe = game_data.crafting_recipe(self._target_item) or {}
        mat_codes = frozenset(recipe.keys())
        return [
            a for a in actions
            if (isinstance(a, CraftAction) and a.code == self._target_item)
            or isinstance(a, MoveAction)
            or (isinstance(a, WithdrawItemAction) and a.code in mat_codes)
        ]

    @property
    def max_depth(self) -> int:
        # Move + Craft worst case. Two-step ceiling keeps the planner snappy.
        return 5

    def __repr__(self) -> str:
        return f"CraftRelief({self._target_item})"
