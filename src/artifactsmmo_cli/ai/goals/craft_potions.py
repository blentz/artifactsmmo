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
                 history: LearningStore | None = None,
                 state: WorldState | None = None) -> None:
        self._effect = effect
        self._combat_monster = combat_monster
        self._game_data = game_data
        self._history = history
        # ── the plan's FROZEN target ────────────────────────────────────────
        # `GOAPPlanner.plan` evaluates `relevant_actions` ONCE, against the seed
        # state, so the admitted action set covers exactly ONE craft target at
        # ONE batch size. `is_satisfied` must therefore be a predicate over what
        # THAT set can reach. It used to delegate straight to `_active_craft`,
        # which re-resolves per node and re-targets the moment the seed target's
        # deficit closes (heal stocked -> boost potion). The goal test could then
        # demand a target the frozen action set never provides, leaving NO
        # reachable satisfying state: A* exhausted the space and returned no plan
        # on every cycle it was selected (live: 285/285, ~57 nodes, no timeout).
        #
        # Resolving the target here, from the state the goal will be planned
        # from, makes the action set and the goal test agree by construction.
        # Re-targeting still happens — on the NEXT cycle, whose goal instance
        # seeds from the post-batch state. That is the "craft a batch and
        # replan" loop this goal's ladder was always documented to drive.
        self._seed_target = (self._active_craft(state, game_data)
                             if state is not None and game_data is not None else None)
        self._seed_equipped = (
            equipped_potion_qty(state, self._seed_target[0])
            if state is not None and self._seed_target is not None else 0)
        self._seed_depth = (
            self._batch_depth(self._seed_target, game_data)
            if game_data is not None and self._seed_target is not None else 0)

    @staticmethod
    def _batch_depth(plan: tuple[str, int, int], game_data: GameData) -> int:
        """Planning steps the sized batch actually costs: one Gather per unit of
        every ingredient the runs consume, plus the craft and the equip.

        A gather yields ONE unit per action, so `runs * sum(recipe)` is the
        worst-case (nothing held) leg length. Without this the goal inherited
        Goal.max_depth = 15 while its own ladder routinely sized a longer batch —
        POTION_GATHER_BATCH=5 runs of a 3-unit recipe is 5*3 + 2 = 17 — so A*
        exhausted at depth 15 and returned no plan. Live at level 20 that read as
        `CraftPotionsGoal: nodes=54 depth=15 plan_len=0`; the batch became
        reachable the moment the budget covered it.
        """
        code, runs, _equip_qty = plan
        recipe = game_data.crafting_recipes.get(code, {})
        return runs * sum(recipe.values()) + 2

    @property
    def max_depth(self) -> int:
        """The sized batch's own length, never below the inherited default.

        Derived at construction from the FROZEN target, mirroring
        ReachCurrencyGoal's funding-cycle bound: a goal that sizes its own batch
        has to provision the depth that batch needs, or it is unplannable by
        construction. Unseeded (no state/game_data) there is no batch to measure,
        so the default stands."""
        return max(super().max_depth, self._seed_depth)

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
        # ONE MONSTER, AND `craft_potions_fires` NAMES IT. Both arms of this
        # expression resolve to `primary_combat_target(state, game_data)` — the
        # call the GUARD makes — so the goal cannot size for a monster the guard
        # did not fire on. `strategy_driver.map_guard` forwards exactly that call
        # as `combat_monster`; the fall-through covers the goals built by hand in
        # tests and by the differential harness.
        #
        # BOTH HALVES ARE SCAR TISSUE FROM THE SAME DIVERGENCE. The fall-through
        # went in first (2026-07-19): the arbiter could pass `combat_monster=None`
        # while the guard had already fired, leaving the goal inert in exactly the
        # cycles it was selected for. The other half is the same bug not inverted
        # but merely DIFFERENT — `map_guard` used to inject `ctx.combat_monster`,
        # the arbiter's FARM target from `GamePlayer._winnable_farm_target`, and a
        # non-None monster the guard had not fired on silenced the goal just as
        # thoroughly (`is_satisfied() == True`, so `select_pure` never even tried
        # it). Measured 2026-08-25: 14 of 294 offline cells, e.g.
        # `l21_grey_material_grind` sizing for `mushmush` while the guard fired on
        # `pig`. Fixed at the injection site, not here, because
        # `craft_potions_fires(state, game_data, history)` is a 3-arg Bool with a
        # Lean mirror and a differential harness — threading the ctx INTO it would
        # have created a second reading, which is the thing being removed.
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
        # THE BATCH THIS GOAL WILL ACTUALLY CLOSE, read off the plan
        # `_active_craft` just chose — never re-derived here.
        #
        # It used to re-derive the HEAL deficit, which is one of the THREE
        # conditions `craft_potions_fires` fires on. The third
        # (`potion_supply.py:210-220`) is a BOOST-stock deficit, reached only
        # once the heal deficit is closed — so on that arm the re-derivation
        # computed `<= 0` by construction and a goal the ladder had just fired
        # reported 0.0 urgency. Measured on the committed bundle: 1 cell,
        # `l20_boost_stock`, the only one that reaches the arm and the reason
        # the scenario exists.
        #
        # Exactly the defect R4 of the task-horizon residuals found in
        # `TaskCancelGoal.value` (3 of 3 selected cells reporting 0.0) and fixed
        # the same way: delete the second producer. `_active_craft` is the ONE
        # place that decides what this cycle crafts, `is_satisfied` is already
        # stated over the same batch quantity, and `relevant_actions` sizes its
        # equip from it — so all three now agree by construction instead of by
        # inspection.
        _code, _runs, equip_qty = plan
        return float(max(1, equip_qty))

    def is_satisfied(self, state: WorldState) -> bool:
        # Seeded (production): satisfaction is "this plan's BATCH has landed" —
        # the frozen target equipped up by the quantity `relevant_actions` sized
        # its EquipAction for. This is the only form the admitted action set can
        # actually reach, and it is what keeps the goal plannable. Testing the
        # FULL remaining deficit instead made the goal unsatisfiable twice over:
        # once because the batch is capped at POTION_GATHER_BATCH runs while the
        # deficit can be a whole 40-potion stack, and once because closing the
        # heal deficit re-targeted a boost potion the action set never covered.
        if self._seed_target is not None:
            _code, _runs, equip_qty = self._seed_target
            return equipped_potion_qty(state, _code) >= self._seed_equipped + equip_qty
        # Unseeded: no batch is defined, so the honest question is the arbiter's
        # pre-plan one — is there anything to do at all? When game_data is set,
        # delegate to _active_craft so the unlock-boost path is reflected: owning
        # the boost makes unlock_boost_target return None and the heal check
        # applies. Falls back to the state-only slot-quantity check when
        # game_data is absent.
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
        is already satisfied.

        Uses the target frozen at construction when the goal was seeded, so the
        admitted set is the very one `is_satisfied` tests for. Unseeded, it
        resolves from `state` as before."""
        plan = self._seed_target if self._seed_target is not None \
            else self._active_craft(state, game_data)
        return [] if plan is None else craft_utility_ladder(*plan, actions, state, game_data)
