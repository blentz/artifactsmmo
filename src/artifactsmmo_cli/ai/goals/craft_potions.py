"""CraftPotionsGoal: preemptively stock the equipped utility-slot potion stack
toward a level-scaled baseline. Craft from held ingredients > buy optimal mix >
gather a 5-potion batch and replan, then EQUIP the crafted potions into
utility1_slot. Preemptive guard-tier goal (wired in tiers/guards.py, Task 7).

is_satisfied / game_data split: ``Goal.is_satisfied(state)`` has no GameData, so
it carries only the STATE-ONLY signal — a utility slot stocked to this level's
baseline. The producibility/target half (is there an alchemy-craftable utility
heal at all?) lives in the Task-7 guard ``_fires`` predicate, which DOES have
GameData. The guard not firing == the goal effectively satisfied for the cycle.
"""

import dataclasses

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.equip import EquipAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.actions.npc import NpcBuyAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.equipped_potion import equipped_potion_qty
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.max_batch_from_held import max_batch_from_held_pure
from artifactsmmo_cli.ai.optimal_buy_mix import optimal_buy_mix_pure
from artifactsmmo_cli.ai.potion_baseline import potion_baseline_pure
from artifactsmmo_cli.ai.recipe_closure import closure_demand, recipe_closure
from artifactsmmo_cli.ai.thresholds import (
    POTION_GATHER_BATCH,
    POTION_HIGH_LEVEL,
    POTION_HIGH_QTY,
    POTION_LOW_LEVEL,
    POTION_LOW_QTY,
)
from artifactsmmo_cli.ai.world_state import WorldState

_TARGET_SLOT = "utility1_slot"


class CraftPotionsGoal(Goal):
    """Stock the utility-slot potion stack toward a level-scaled baseline."""

    preemptive = True

    def __init__(self, effect: str = "hp_restore") -> None:
        self._effect = effect

    def _target_potion(self, state: WorldState, game_data: GameData) -> str | None:
        """Highest-`effect`, alchemy-craftable-now, utility-slot-equippable potion
        (deterministic smallest-code tie-break); None when none qualifies.

        Mirrors `consumable_supply.best_craftable_heal`, but REQUIRES the item be
        a utility-slot type (so the EquipAction is applicable) crafted by the
        `alchemy` skill at a level the bot has reached. Materials are NOT required
        on hand — the relevant-actions ladder gathers/buys/withdraws them."""
        best_code: str | None = None
        best_restore = 0
        for code in sorted(game_data.crafting_recipes):
            stats = game_data.item_stats(code)
            if stats is None or stats.type_ != "utility":
                continue
            restore = getattr(stats, self._effect)
            if restore <= 0 or restore <= best_restore:
                continue
            if stats.crafting_skill != "alchemy":
                continue
            if state.skills.get("alchemy", 1) < stats.crafting_level:
                continue
            best_code, best_restore = code, restore
        return best_code

    def _equipped(self, state: WorldState, game_data: GameData) -> int:
        code = self._target_potion(state, game_data)
        return equipped_potion_qty(state, code) if code else 0

    def _baseline(self, level: int) -> int:
        return potion_baseline_pure(level, POTION_LOW_LEVEL, POTION_LOW_QTY,
                                    POTION_HIGH_LEVEL, POTION_HIGH_QTY)

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if self.is_satisfied(state):
            return 0.0
        deficit = self._baseline(state.level) - self._equipped(state, game_data)
        return float(max(0, deficit))

    def is_satisfied(self, state: WorldState) -> bool:
        # State-only signal (no GameData here): a utility slot at this level's
        # baseline. Producibility lives in the Task-7 guard `_fires` (see module
        # docstring).
        baseline = self._baseline(state.level)
        return (state.utility1_slot_quantity >= baseline
                or state.utility2_slot_quantity >= baseline)

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        # The planner goal-tests via is_satisfied once the equip tops the slot up.
        return {}

    def _ladder_runs(self, state: WorldState, game_data: GameData, recipe: dict[str, int],
                     runs_needed: int, craft_yield: int) -> int:
        """Craft RUNS to attempt this cycle, chosen by the supply ladder:
        (1) the most this many craft-runs held ingredients already cover, else
        (2) the largest buyable batch affordable in gold, else
        (3) a single gather-and-replan batch bounded to POTION_GATHER_BATCH."""
        ingredients = list(recipe.items())
        needs = [qty for _code, qty in ingredients]
        held = [self._held(code, state) for code, _qty in ingredients]

        from_held = max_batch_from_held_pure(needs, held, craft_yield)
        if from_held > 0:
            return min(runs_needed, from_held // craft_yield)

        prices = [self._gold_price(code, game_data) for code, _qty in ingredients]
        if all(p is not None for p in prices):
            bought = optimal_buy_mix_pure(needs, held, [p for p in prices if p is not None],
                                          state.gold, runs_needed)
            if bought > 0:
                return bought

        return min(runs_needed, POTION_GATHER_BATCH)

    @staticmethod
    def _held(code: str, state: WorldState) -> int:
        """Units of `code` on hand for crafting: inventory plus bank."""
        return state.inventory.get(code, 0) + (state.bank_items or {}).get(code, 0)

    @staticmethod
    def _gold_price(code: str, game_data: GameData) -> int | None:
        """Cheapest gold buy price for `code`, or None when no NPC sells it for gold."""
        gold = [price for _npc, price, currency in game_data.npc_purchases(code)
                if currency == "gold"]
        return min(gold) if gold else None

    def relevant_actions(self, actions: list[Action], state: WorldState,
                         game_data: GameData) -> list[Action]:
        """Recipe-closure actions for the target potion sized by the supply
        ladder, plus the EquipAction that tops up utility1_slot. Mirrors
        `MaintainConsumablesGoal`: the target Craft is rebatched to the chosen
        run count; its intermediates, gathers, buys, withdraws, and moves pass
        through; the equip quantity is the batch's potion output (capped at the
        deficit) so it is applicable after the craft."""
        code = self._target_potion(state, game_data)
        if code is None:
            return []
        # `_target_potion` only returns codes drawn from `crafting_recipes`, so
        # the recipe is always present (no None guard needed).
        recipe = dict(game_data.crafting_recipes[code])

        craft_yield = game_data.craft_yield(code)
        deficit = max(1, self._baseline(state.level) - self._equipped(state, game_data))
        runs_needed = -(-deficit // craft_yield)  # ⌈deficit / yield⌉
        runs = max(1, self._ladder_runs(state, game_data, recipe, runs_needed, craft_yield))
        equip_qty = min(deficit, runs * craft_yield)

        needed_resources, craftable_mats = recipe_closure(game_data, [code])
        withdrawable: set[str] = set(craftable_mats) | {code}
        for res in needed_resources:
            drop = game_data.resource_drop_item(res)
            if drop is not None:
                withdrawable.add(drop)
        chain: dict[str, int] = {}
        closure_demand(code, 1, game_data, chain, frozenset())
        withdrawable |= set(chain)

        result: list[Action] = []
        have_craft = False
        for a in actions:
            if isinstance(a, CraftAction) and a.code == code:
                if not have_craft:
                    have_craft = True
                    result.append(a if a.quantity == runs
                                  else dataclasses.replace(a, quantity=runs))
            elif isinstance(a, CraftAction) and a.code in craftable_mats:
                result.append(a)
            elif isinstance(a, GatherAction) and a.resource_code in needed_resources:
                result.append(a)
            elif isinstance(a, NpcBuyAction) and a.item_code in chain:
                result.append(a)
            elif isinstance(a, WithdrawItemAction) and a.code in withdrawable:
                result.append(a)
            elif isinstance(a, MoveAction):
                result.append(a)
        result.append(EquipAction(code=code, slot=_TARGET_SLOT, quantity=equip_qty))
        return result
