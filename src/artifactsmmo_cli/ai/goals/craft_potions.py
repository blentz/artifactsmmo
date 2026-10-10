"""CraftPotionsGoal: stock the chosen loadout's utility potions to their carry and
equip them (docs/PLAN_consumable_utility.md increment 5). The batch is
`potion_supply.potion_batch` over the chosen loadout: the bag's and bank's
copies first, then crafted runs sized by the supply ladder; the goal is the
potions in the bag, then ONE equip into the utility slot `utility_slot_for`
names. Preemptive guard-tier goal (wired in tiers/guards.py)."""

from artifactsmmo_cli.ai.actions.equip import EquipAction
from artifactsmmo_cli.ai.chosen_loadout import ChosenLoadout
from artifactsmmo_cli.ai.equipped_potion import equipped_potion_qty
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.potion_supply import potion_batch
from artifactsmmo_cli.ai.utility_slot import utility_slot_for
from artifactsmmo_cli.ai.world_state import WorldState


class CraftPotionsGoal(Goal):
    """Stock and wear the chosen loadout's next potion short of its carry."""

    preemptive = True

    def __init__(self, loadout: ChosenLoadout | None = None,
                 game_data: GameData | None = None,
                 state: WorldState | None = None) -> None:
        self._loadout = loadout
        self._game_data = game_data
        # ── the plan's FROZEN target ────────────────────────────────────────
        # The batch is sized ONCE, against the seed state (`batch_obtain` /
        # `batch_equip`, which the walk decomposes since Phase 2e), so a plan
        # covers exactly ONE potion at ONE batch size and `is_satisfied` is a
        # predicate over what THAT batch reaches. Re-resolving per node would
        # re-target the moment the seed potion's deficit closes (the next
        # chosen potion), demanding a target the frozen action set never
        # provides — A* exhausted the space with no plan on every cycle it was
        # selected (live: 285/285). Re-targeting happens on the NEXT cycle,
        # whose goal seeds from the post-batch state.
        self._seed_target = (potion_batch(state, game_data, loadout)
                             if state is not None and game_data is not None else None)
        self._seed_equipped = (
            equipped_potion_qty(state, self._seed_target[0])
            if state is not None and self._seed_target is not None else 0)

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        """The batch this goal will close, read off `potion_batch` — the one
        place that decides it (the guard fires on the same call)."""
        plan = potion_batch(state, game_data, self._loadout)
        if plan is None:
            return 0.0
        _code, _runs, equip_qty = plan
        return float(max(1, equip_qty))

    def is_satisfied(self, state: WorldState) -> bool:
        # Seeded (production): "this plan's BATCH has landed" — the frozen
        # target equipped up by the quantity `batch_equip` sized its equip for,
        # the only form the admitted action set can reach.
        if self._seed_target is not None:
            code, _runs, equip_qty = self._seed_target
            return equipped_potion_qty(state, code) >= self._seed_equipped + equip_qty
        # Unseeded: no batch is defined, so the honest question is the
        # arbiter's pre-plan one — is there anything to stock at all? Without
        # game data nothing can be sized, so nothing is owed.
        if self._game_data is None:
            return True
        return potion_batch(state, self._game_data, self._loadout) is None

    def batch_equip(self, state: WorldState) -> EquipAction | None:
        """The equip that lands this plan's batch, sized to what is still
        unequipped, or None when the goal is unseeded or already satisfied.
        The slot keeps the loadout's other potion: `utility_slot_for` never
        displaces a chosen code while an unchosen one can go."""
        if self._seed_target is None:
            return None
        code, _runs, equip_qty = self._seed_target
        remaining = self._seed_equipped + equip_qty - equipped_potion_qty(state, code)
        if remaining <= 0:
            return None
        keep = self._loadout.potion_codes() if self._loadout is not None else frozenset()
        return EquipAction(code=code, slot=utility_slot_for(code, state, keep), quantity=remaining)

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
        # The planner goal-tests via is_satisfied once the slot is topped up.
        return {}
