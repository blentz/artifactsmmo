"""OptimizeLoadoutAction: swap equipment to optimal loadout for a target monster."""

from dataclasses import dataclass
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.equipment import EquipAction, UnequipAction
from artifactsmmo_cli.ai.equipment.scoring import pick_loadout
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState


SWAP_COST_PER_SLOT = 5.0
"""Approximate cycle cost per equip/unequip API call."""


@dataclass
class OptimizeLoadoutAction(Action):
    """Equip the best owned loadout for fighting `target_monster_code`.

    The action is the planner's way to spend a few cooldown cycles re-arming
    before a fight. Compares per-fight expected damage (weapon) and damage
    reduction (armor) against the monster's element profile.
    """

    tags: ClassVar[frozenset[str]] = frozenset({"equip"})

    target_monster_code: str = ""

    def _swap_plan(self, state: WorldState, game_data: GameData) -> dict[str, str | None]:
        """Slots that would change in the optimal loadout. Empty when nothing to do."""
        optimal = pick_loadout(self.target_monster_code, state, game_data)
        return {
            slot: new_code
            for slot, new_code in optimal.items()
            if state.equipment.get(slot) != new_code
        }

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        return bool(self._swap_plan(state, game_data))

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        swaps = self._swap_plan(state, game_data)
        if not swaps:
            return state
        new_equipment = dict(state.equipment)
        new_inventory = dict(state.inventory)
        for slot, new_code in swaps.items():
            old_code = new_equipment.get(slot)
            if old_code is not None:
                new_inventory[old_code] = new_inventory.get(old_code, 0) + 1
            if new_code is not None:
                cur = new_inventory.get(new_code, 0)
                if cur <= 1:
                    new_inventory.pop(new_code, None)
                else:
                    new_inventory[new_code] = cur - 1
            new_equipment[slot] = new_code
        return WorldState(
            character=state.character,
            level=state.level,
            xp=state.xp,
            max_xp=state.max_xp,
            hp=state.hp,
            max_hp=state.max_hp,
            gold=state.gold,
            skills=state.skills,
            x=state.x,
            y=state.y,
            inventory=new_inventory,
            inventory_max=state.inventory_max,
            equipment=new_equipment,
            cooldown_expires=None,
            task_code=state.task_code,
            task_type=state.task_type,
            task_progress=state.task_progress,
            task_total=state.task_total,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
            skill_xp=state.skill_xp,
        )

    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        n = len(self._swap_plan(state, game_data))
        # Each swap is unequip + equip = 2 API calls; combat goals shouldn't
        # over-optimize so we keep the cost honest.
        return SWAP_COST_PER_SLOT * 2 * n

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        swaps = self._swap_plan(state, self._game_data_for_execute(state))
        # Note: at execute time we need GameData. Stash via closure or
        # lookup via ClientManager singleton. Simpler: re-derive from
        # the action's stored target — but pick_loadout needs game_data.
        # For now, just sequentially unequip then equip each.
        for slot, new_code in swaps.items():
            old_code = state.equipment.get(slot)
            if old_code is not None:
                state = UnequipAction(slot=slot).execute(state, client)
            if new_code is not None:
                state = EquipAction(code=new_code, slot=slot).execute(state, client)
        return state

    def _game_data_for_execute(self, state: WorldState) -> GameData:
        """Execute-path access to GameData. Loaded once by player, stashed via class attribute."""
        # Placeholder — patched at runtime by player._build_actions.
        if not hasattr(self.__class__, "_shared_game_data") or self.__class__._shared_game_data is None:
            raise RuntimeError("OptimizeLoadoutAction needs game_data injected via class attribute")
        return self.__class__._shared_game_data  # type: ignore[attr-defined]

    def __repr__(self) -> str:
        return f"OptimizeLoadout({self.target_monster_code})"
