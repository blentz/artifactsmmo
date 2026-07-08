"""MaintainConsumablesGoal: cook/brew heal consumables to a stock floor (PLAN #6a).

Selected by the MAINTAIN_CONSUMABLES discretionary means when combat is the
active means and the bot is under-stocked on heals. Crafts the best heal its
skills can make (reusing recipe-closure gather/withdraw/craft actions) so the
bot tops up its cupboard instead of falling back on the slow Rest action.
"""

import dataclasses

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.consumable_supply import (
    HEAL_STOCK_FLOOR,
    best_craftable_heal,
    heal_stock,
    maintain_consumables_fires,
)
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.intermediate_batch import size_intermediate_craft
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.recipe_closure import (
    closure_demand,
    gather_serves_closure,
    recipe_closure,
)
from artifactsmmo_cli.ai.world_state import WorldState

MAINTAIN_CONSUMABLES_VALUE = 25.0
"""Discretionary combat-prep value: above the RECYCLE_SURPLUS / WAIT housekeeping
band so the bot stocks heals before idle chores, below GATHER_MATERIALS (50) and
the survival floor so it never preempts objective or survival work."""


class MaintainConsumablesGoal(Goal):
    """Craft heal consumables up to HEAL_STOCK_FLOOR.

    Satisfied when the bot holds enough heals OR can craft nothing better — the
    same predicate the means tier fires on, so one activation drives the
    gather/craft chain until the floor is met."""

    def __init__(self, game_data: GameData) -> None:
        self._gd = game_data

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        return 0.0 if self.is_satisfied(state) else MAINTAIN_CONSUMABLES_VALUE

    def is_satisfied(self, state: WorldState) -> bool:
        return not maintain_consumables_fires(state, self._gd)

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"heal_stock_maintained": True}

    def relevant_actions(self, actions: list[Action], state: WorldState,
                         game_data: GameData) -> list[Action]:
        """Recipe-closure actions for the chosen heal: a batched Craft of the
        heal (sized to the deficit), Crafts of its craftable intermediates,
        Gathers of its needed resources, Withdraws of any closure material in
        the bank, and Moves. Same closure machinery GatherMaterials uses."""
        code = best_craftable_heal(state, game_data)
        if code is None:
            return []
        _needed_resources, craftable_mats = recipe_closure(game_data, [code])
        # Withdraw-eligible codes: craftable intermediates + the heal itself;
        # every leaf material arrives via the closure-demand union below
        # (GAP-7: the per-resource primary-drop loop was redundant and, with
        # the widened needed_resources, would admit junk withdraws).
        withdrawable: set[str] = set(craftable_mats) | {code}
        chain: dict[str, int] = {}
        closure_demand(code, 1, game_data, chain, frozenset())
        withdrawable |= set(chain)

        deficit = max(1, HEAL_STOCK_FLOOR - heal_stock(state, game_data))
        batch_chain: dict[str, int] = {}
        closure_demand(code, deficit, game_data, batch_chain, frozenset())
        result: list[Action] = []
        have_craft = False
        for a in actions:
            if isinstance(a, CraftAction) and a.code == code:
                if not have_craft:
                    have_craft = True
                    result.append(a if a.quantity == deficit
                                  else dataclasses.replace(a, quantity=deficit))
            elif isinstance(a, CraftAction) and a.code in craftable_mats:
                result.append(size_intermediate_craft(a, batch_chain, state, game_data))
            elif isinstance(a, GatherAction) and gather_serves_closure(
                    a.resource_code, a.drop_item_override,
                    game_data.resource_drops, chain):
                # GAP-7 admission precision: EFFECTIVE drop in the closure.
                result.append(a)
            elif isinstance(a, WithdrawItemAction) and a.code in withdrawable:
                result.append(a)
            elif isinstance(a, MoveAction):
                result.append(a)
        return result

    def __repr__(self) -> str:
        return "MaintainConsumables"
