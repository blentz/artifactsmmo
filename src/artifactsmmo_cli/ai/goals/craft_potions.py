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

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.boost_selection import best_boost_potion
from artifactsmmo_cli.ai.craft_ladder import _held, craft_utility_ladder
from artifactsmmo_cli.ai.equipped_potion import equipped_potion_qty
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.max_batch_from_held import max_batch_from_held_pure
from artifactsmmo_cli.ai.optimal_buy_mix import optimal_buy_mix_pure
from artifactsmmo_cli.ai.potion_baseline import potion_baseline_pure
from artifactsmmo_cli.ai.potion_stock_target import potion_stock_target_pure
from artifactsmmo_cli.ai.potion_supply import primary_combat_target, projected_heal_need_per_fight, target_potion_pure
from artifactsmmo_cli.ai.thresholds import (
    POTION_GATHER_BATCH,
    POTION_HIGH_LEVEL,
    POTION_HIGH_QTY,
    POTION_LOW_LEVEL,
    POTION_LOW_QTY,
)
from artifactsmmo_cli.ai.unlock_boost import unlock_boost_target
from artifactsmmo_cli.ai.world_state import WorldState


class CraftPotionsGoal(Goal):
    """Stock the utility-slot potion stack toward a level-scaled baseline."""

    preemptive = True

    def __init__(self, effect: str = "hp_restore",
                 combat_monster: str | None = None,
                 game_data: GameData | None = None,
                 history: LearningStore | None = None) -> None:
        self._effect = effect
        self._combat_monster = combat_monster
        self._game_data = game_data
        self._history = history

    def _target_potion(self, state: WorldState, game_data: GameData) -> str | None:
        """Highest-`effect`, alchemy-craftable-now, utility-slot-equippable potion.

        Delegates to ``target_potion_pure`` (potion_supply.py) so guard and goal
        always agree on the target — guard/goal divergence is a spin."""
        return target_potion_pure(state, game_data, self._effect)

    def _equipped(self, state: WorldState, game_data: GameData) -> int:
        code = self._target_potion(state, game_data)
        return equipped_potion_qty(state, code) if code else 0

    def _baseline(self, level: int, state: WorldState | None = None,
                  game_data: GameData | None = None,
                  history: LearningStore | None = None) -> int:
        """Combat-projected potion target, capped by the level ramp.

        Delegates to `potion_stock_target_pure` — the SAME core the CRAFT_POTIONS
        guard sizes from, so the two can no longer disagree. They used to: the
        guard fired on the bare level ramp while this method targeted
        ``min(max(level_baseline, monster_demand), stack)``, so the guard could
        fire with nothing for the goal to do.

        The ramp is now a CAP on speculation rather than a FLOOR. Under the old
        ``max(level_baseline, ...)`` a level-45 bot pursued 100 potions whether or
        not it ever drank one, and gather-crafting those is never a time saving
        against resting (which refills to full for ``max(3, ceil(missing%))``
        seconds). Missing context returns 0 rather than the bare ramp for the same
        reason: no combat target means no in-combat consumption to stock for.
        """
        level_baseline = potion_baseline_pure(level, POTION_LOW_LEVEL, POTION_LOW_QTY,
                                              POTION_HIGH_LEVEL, POTION_HIGH_QTY)
        if game_data is None or state is None:
            return 0
        # Derive the monster the way the GUARD does when none was injected. The
        # arbiter can hand this goal a SelectionContext whose combat_monster is
        # None while the guard -- which calls primary_combat_target itself -- has
        # already fired. Trusting only the injected value would make the goal
        # inert in exactly the cycles the guard just selected it for: the same
        # guard/goal divergence, inverted.
        monster = self._combat_monster or primary_combat_target(state, game_data)
        if monster is None:
            return 0
        target_potion = self._target_potion(state, game_data)
        if target_potion is None:
            return 0
        hp_need = projected_heal_need_per_fight(state, game_data, monster, history)
        return potion_stock_target_pure(hp_need, game_data.hp_restore_of(target_potion),
                                        level_baseline)

    def _active_craft(self, state: WorldState, game_data: GameData) -> tuple[str, int, int] | None:
        """Return (target_code, runs, equip_qty) for the craft this cycle, or None
        when no craft is needed (goal satisfied).

        Unlock boost takes precedence when leveling is stalled: if
        ``unlock_boost_target`` returns a (boost, monster) pair, craft one batch
        of the boost (runs=1, equip_qty=craft_yield).  Otherwise fall through to
        the heal-potion baseline plan.  Returns None when the heal deficit is
        already met or no target exists."""
        pair = unlock_boost_target(state, game_data)
        if pair is not None:
            boost = pair[0]
            cy = game_data.craft_yield(boost)
            return (boost, 1, cy)
        code = self._target_potion(state, game_data)
        if code is None:
            return None
        recipe = dict(game_data.crafting_recipes[code])
        craft_yield = game_data.craft_yield(code)
        deficit = self._baseline(state.level, state, game_data, self._history) - self._equipped(state, game_data)
        if deficit <= 0:
            boost_monster = primary_combat_target(state, game_data)
            if boost_monster is not None:
                best_boost = best_boost_potion(state, game_data, boost_monster)
                if best_boost is not None:
                    boost_equipped = equipped_potion_qty(state, best_boost)
                    boost_baseline = potion_baseline_pure(
                        state.level, POTION_LOW_LEVEL, POTION_LOW_QTY,
                        POTION_HIGH_LEVEL, POTION_HIGH_QTY,
                    )
                    if boost_equipped < boost_baseline:
                        boost_yield = game_data.craft_yield(best_boost)
                        boost_deficit = boost_baseline - boost_equipped
                        boost_recipe = dict(game_data.crafting_recipes.get(best_boost, {}))
                        if boost_recipe:
                            boost_runs_needed = -(-boost_deficit // boost_yield)
                            boost_runs = max(1, self._ladder_runs(
                                state, game_data, boost_recipe, boost_runs_needed, boost_yield,
                            ))
                            boost_equip_qty = min(boost_deficit, boost_runs * boost_yield)
                            return (best_boost, boost_runs, boost_equip_qty)
            return None
        runs_needed = -(-deficit // craft_yield)  # ⌈deficit / yield⌉
        runs = max(1, self._ladder_runs(state, game_data, recipe, runs_needed, craft_yield))
        equip_qty = min(deficit, runs * craft_yield)
        return (code, runs, equip_qty)

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        plan = self._active_craft(state, game_data)
        if plan is None:
            return 0.0
        # Unlock-boost path: fixed positive urgency (stall-breaker is at least
        # as urgent as a heal deficit; defer to 1.0 since there is no deficit).
        if unlock_boost_target(state, game_data) is not None:
            return 1.0
        # Heal path: return deficit magnitude (preserves existing behaviour).
        deficit = self._baseline(state.level, state, game_data, history) - self._equipped(state, game_data)
        return float(max(0, deficit))

    def is_satisfied(self, state: WorldState) -> bool:
        # When game_data is set (constructed with game_data=...), delegate to
        # _active_craft so the unlock-boost path is reflected: owning the boost
        # makes unlock_boost_target return None and the heal check applies.
        # Falls back to the state-only slot-quantity check when game_data is absent.
        if self._game_data is not None:
            return self._active_craft(state, self._game_data) is None
        baseline = self._baseline(state.level, state, self._game_data, self._history)
        return (state.utility1_slot_quantity >= baseline
                or state.utility2_slot_quantity >= baseline)

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        pair = unlock_boost_target(state, game_data)
        if pair is not None:
            return {"have": {pair[0]: 1}}
        # Heal path: planner goal-tests via is_satisfied once the slot is topped up.
        return {}

    def _ladder_runs(self, state: WorldState, game_data: GameData, recipe: dict[str, int],
                     runs_needed: int, craft_yield: int) -> int:
        """Craft RUNS to attempt this cycle, chosen by the supply ladder:
        (1) the most this many craft-runs held ingredients already cover, else
        (2) the largest buyable batch affordable in gold, else
        (3) a single gather-and-replan batch bounded to POTION_GATHER_BATCH."""
        ingredients = list(recipe.items())
        needs = [qty for _code, qty in ingredients]
        held = [_held(code, state) for code, _qty in ingredients]

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
    def _gold_price(code: str, game_data: GameData) -> int | None:
        """Cheapest gold buy price for `code`, or None when no NPC sells it for gold."""
        gold = [price for _npc, price, currency in game_data.npc_purchases(code)
                if currency == "gold"]
        return min(gold) if gold else None

    def relevant_actions(self, actions: list[Action], state: WorldState,
                         game_data: GameData) -> list[Action]:
        """Recipe-closure actions for the active craft target (unlock boost or
        heal potion), sized by the supply ladder, plus the EquipAction that tops
        up utility1_slot.  Returns ``[]`` when _active_craft determines the goal
        is already satisfied."""
        plan = self._active_craft(state, game_data)
        return [] if plan is None else craft_utility_ladder(*plan, actions, state, game_data)
