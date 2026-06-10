"""CraftReliefGoal: convert raw materials into a goal item under inventory
pressure, instead of depositing or discarding them.

Fired by the CRAFT_RELIEF guard (tiers/guards.py) when inv >= ~70% AND the
bot can craft a target/gear/tools item from current inventory with NET
relief (craft_relief.py gates 1:1 recipes out). Replaces the default ladder
routing of DEPOSIT_FULL / DISCARD_HIGH for that cycle.

The goal is satisfied when `batch` additional units of the target item
appear in inventory. `batch` comes from the ReliefCandidate quantity —
already bounded by what is simultaneously craftable from on-hand inputs and
by what is needed to push pressure back below the firing threshold — so ONE
activation plans ONE batched CraftAction (Move folded in) instead of x1 per
cycle. Trace 2026-06-08: the x1-per-activation shape ping-ponged
gather-spot <-> workshop for 38 single crafts."""

import dataclasses

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState


class CraftReliefGoal(Goal):
    """Craft `batch` units of `target_item` to convert raw mats into goal product.

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
        # `batch` additional units crafted satisfies the goal — sized by the
        # ReliefCandidate so one activation relieves pressure below the
        # guard threshold instead of re-firing every cycle.
        return state.inventory.get(self._target_item, 0) >= self._initial_qty + self._batch

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"inventory": {self._target_item: self._initial_qty + self._batch}}

    def relevant_actions(self, actions: list[Action], state: WorldState,
                         game_data: GameData) -> list[Action]:
        """One batched Craft of the target item + Move + Withdraw of any
        recipe input already in the bank. The factory's CraftActions carry
        quantity=1 (plus a task batch-K variant); we rebatch the first match
        to `batch` so the plan crafts the whole relief amount in one action
        — the cost model already scales with quantity. Withdraw lets the bot
        pull mats from the bank instead of failing the craft when
        ingredients are split between inventory and bank."""
        recipe = game_data.crafting_recipe(self._target_item) or {}
        mat_codes = frozenset(recipe.keys())
        out: list[Action] = []
        have_craft = False
        for a in actions:
            if isinstance(a, CraftAction) and a.code == self._target_item:
                if not have_craft:
                    have_craft = True
                    out.append(a if a.quantity == self._batch
                               else dataclasses.replace(a, quantity=self._batch))
            elif (isinstance(a, MoveAction)
                    or (isinstance(a, WithdrawItemAction) and a.code in mat_codes)):
                out.append(a)
        return out

    @property
    def max_depth(self) -> int:
        # Move + Craft worst case. Two-step ceiling keeps the planner snappy.
        return 5

    def __repr__(self) -> str:
        return f"CraftRelief({self._target_item})"
