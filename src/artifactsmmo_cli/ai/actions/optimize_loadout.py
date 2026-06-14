"""OptimizeLoadoutAction: swap equipment to optimal loadout for a target monster."""

import dataclasses
from dataclasses import dataclass, field
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient

from artifactsmmo_cli.ai.actions.api_action_error import ApiActionError
from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.equip import DUPLICATE_SLOT_TYPES, EquipAction
from artifactsmmo_cli.ai.actions.unequip import UnequipAction
from artifactsmmo_cli.ai.constants import ERROR_CODE_ALREADY_EQUIPPED
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
    game_data: GameData | None = field(default=None, repr=False, compare=False)

    def _swap_plan(self, state: WorldState, game_data: GameData) -> dict[str, str | None]:
        """Slots that would change in the optimal loadout. Empty when nothing to do.

        Empty `target_monster_code` is the documented "no target" sentinel — no
        swap is computed (would raise from the post-Phase-9 monster_attack
        accessor, which only knows real monster codes). This single-locus check
        is the action's precondition, not multi-level error handling."""
        if not self.target_monster_code:
            return {}
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
        # Two-pass apply: unequip-all-first then equip-all. The realizability
        # invariant from pick_loadout is over the whole loadout (count of code
        # C in result ≤ ownership(C, inv, equip)); applying the swaps slot-by-
        # slot can transiently violate that ordering when a peer slot still
        # holds a copy that hasn't been returned to inventory yet. Doing all
        # the unequips first restores every old-equipment copy to inventory
        # before any equip consumes from it, so the per-step assert sees the
        # full ownership pool the invariant accounts for.
        for slot in swaps:
            old_code = new_equipment.get(slot)
            if old_code is not None:
                new_inventory[old_code] = new_inventory.get(old_code, 0) + 1
                new_equipment[slot] = None
        for slot, new_code in swaps.items():
            if new_code is not None:
                cur = new_inventory.get(new_code, 0)
                assert cur >= 1, (
                    f"OptimizeLoadout.apply: cur=0 for {new_code} — "
                    "pick_loadout produced an impossible (non-realizable) loadout"
                )
                # ONE SLOT PER CODE (server HTTP 485) — except dup-allowed types
                # (rings, HTTP 200 on a duplicate). For a non-dup code, equipping
                # one still worn in another slot is refused by the server
                # regardless of spare copies; pick_loadout enforces this at plan
                # time and the projection mirrors it as a contract assertion.
                # Rings may be worn in two slots up to ownership — the cur>=1
                # check above already guards realizability for them.
                new_stats = game_data.item_stats(new_code)
                dup_allowed = (new_stats is not None
                               and new_stats.type_ in DUPLICATE_SLOT_TYPES)
                assert dup_allowed or all(
                    worn != new_code for worn in new_equipment.values()
                ), (
                    f"OptimizeLoadout.apply: {new_code} is still worn in another "
                    "slot — pick_loadout violated the one-slot-per-code rule"
                )
                if cur <= 1:
                    del new_inventory[new_code]
                else:
                    new_inventory[new_code] = cur - 1
            new_equipment[slot] = new_code
        return dataclasses.replace(
            state,
            inventory=new_inventory,
            equipment=new_equipment,
            cooldown_expires=None,
        )

    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        n = len(self._swap_plan(state, game_data))
        # Each swap is unequip + equip = 2 API calls; combat goals shouldn't
        # over-optimize so we keep the cost honest.
        return SWAP_COST_PER_SLOT * 2 * n

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        if self.game_data is None:
            raise RuntimeError("OptimizeLoadoutAction requires game_data; pass it via __init__")
        swaps = self._swap_plan(state, self.game_data)
        # Two-pass, mirroring apply(): unequip EVERY outgoing slot first, then
        # equip the incoming items. Interleaving unequip/equip per slot could
        # equip a code while a later swap slot still wears it (server HTTP 485
        # one-slot-per-code rule); after the full unequip pass every displaced
        # copy is back in inventory and no incoming code is worn anywhere.
        for slot in swaps:
            if state.equipment.get(slot) is not None:
                state = UnequipAction(slot=slot).execute(state, client)
        refused: list[str] = []
        for slot, new_code in swaps.items():
            if new_code is None:
                continue
            equip = EquipAction(code=new_code, slot=slot)
            if not equip.is_applicable(state, self.game_data):
                # Unreachable in practice: pick_loadout's one-slot-per-code
                # feasibility plus the unequip pass guarantee applicability.
                # If live server state diverged (e.g. an unequip response
                # changed the inventory), skip the doomed equip instead of
                # burning the API call on a guaranteed refusal; finish the
                # remaining swaps and report the action as failed afterward.
                refused.append(f"{new_code}->{slot}")
                continue
            state = equip.execute(state, client)
        if refused:
            # Report through the standard failure channel (the player maps
            # ApiActionError(485) to the recorded outcome
            # "error:already_equipped" and refreshes state) instead of raising
            # a raw error mid-swap or pretending the cycle succeeded.
            raise ApiActionError(
                ERROR_CODE_ALREADY_EQUIPPED,
                f"OptimizeLoadout refused pre-flight: {', '.join(refused)}",
            )
        return state

    def __repr__(self) -> str:
        return f"OptimizeLoadout({self.target_monster_code})"
