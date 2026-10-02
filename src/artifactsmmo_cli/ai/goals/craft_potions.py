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

from artifactsmmo_cli.ai.actions.equip import EquipAction
from artifactsmmo_cli.ai.equipped_potion import equipped_potion_qty
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.potion_supply import (
    heal_stock_target,
    potion_batch,
    primary_combat_target,
    target_potion_pure,
)
from artifactsmmo_cli.ai.unlock_boost import unlock_boost_target
from artifactsmmo_cli.ai.utility_slot import utility_slot_for
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
        # The batch is sized ONCE, against the seed state (`batch_obtain` /
        # `batch_equip`, which the walk decomposes since Phase 2e; the A*-era
        # `relevant_actions` read the same seed), so a plan covers exactly ONE
        # craft target at ONE batch size. `is_satisfied` must therefore be a predicate over what
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
        """Combat-projected potion target, capped by the level ramp: the SAME
        stock target `potion_supply.potion_batch` sizes from (so guard and goal
        cannot disagree), for the monster this goal was built for (the guard's
        `primary_combat_target` when none was forwarded). 0 with no state, no
        game data, no combat monster or no target potion: no in-combat
        consumption to stock for. `level` is the state's own and kept for the
        existing callers."""
        if game_data is None or state is None:
            return 0
        target_potion = self._target_potion(state, game_data)
        if target_potion is None:
            return 0
        return heal_stock_target(state, game_data, history,
                                 self._combat_monster or primary_combat_target(state, game_data),
                                 target_potion)

    def _active_craft(self, state: WorldState, game_data: GameData) -> tuple[str, int, int] | None:
        """`(target_code, runs, equip_qty)` for the craft this cycle, or None
        when there is nothing the ladder can supply: `potion_supply.potion_batch`,
        the one place that decision is made (the guard fires on the same call)."""
        return potion_batch(state, game_data, self._history, self._combat_monster, self._effect)

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
        # stated over the same batch quantity, and `batch_equip` sizes its
        # equip from it — so all three now agree by construction instead of by
        # inspection.
        _code, _runs, equip_qty = plan
        return float(max(1, equip_qty))

    def is_satisfied(self, state: WorldState) -> bool:
        # Seeded (production): satisfaction is "this plan's BATCH has landed" —
        # the frozen target equipped up by the quantity `batch_equip` sized
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

    def batch_equip(self, state: WorldState) -> EquipAction | None:
        """The equip that lands this plan's batch, sized to what is still
        unequipped, or None when the goal is unseeded or already satisfied.

        What decomposition serves (Phase 2c-1 of
        docs/PLAN_decision_architecture_redesign.md): the frozen batch is
        `equip_qty` of the target in the utility slot, so the goal is the
        potions in the bag, then this one equip."""
        if self._seed_target is None:
            return None
        code, _runs, equip_qty = self._seed_target
        remaining = self._seed_equipped + equip_qty - equipped_potion_qty(state, code)
        if remaining <= 0:
            return None
        return EquipAction(code=code, slot=utility_slot_for(code, state), quantity=remaining)

    def batch_obtain(self, state: WorldState) -> GatherMaterialsGoal | None:
        """The potions the bag still lacks for `batch_equip`, as an obtain goal,
        or None when the bag already holds them (or there is nothing to equip).

        The bag, not the bank: an equip takes from the inventory, and the walk
        withdraws a banked copy of the potion before it crafts more."""
        equip = self.batch_equip(state)
        if equip is None or state.inventory.get(equip.code, 0) >= equip.quantity:
            return None
        return GatherMaterialsGoal(target_item=equip.code, needed={equip.code: equip.quantity})

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        pair = unlock_boost_target(state, game_data)
        if pair is not None:
            return {"have": {pair[0]: 1}}
        # Heal path: planner goal-tests via is_satisfied once the slot is topped up.
        return {}
