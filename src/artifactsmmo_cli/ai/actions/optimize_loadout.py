"""OptimizeLoadoutAction: swap equipment to optimal loadout for a target monster."""

import dataclasses
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient

from artifactsmmo_cli.ai.actions.api_action_error import ApiActionError
from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.equip import DUPLICATE_SLOT_TYPES, EquipAction
from artifactsmmo_cli.ai.actions.unequip import UnequipAction
from artifactsmmo_cli.ai.constants import ERROR_CODE_ALREADY_EQUIPPED
from artifactsmmo_cli.ai.equipment.loadout_cache import pick_loadout_cached
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_value_core import Combat, Gather
from artifactsmmo_cli.ai.inventory_room import has_room
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

SWAP_COST_PER_SLOT = 5.0
"""Approximate cycle cost per equip/unequip API call."""


def _wait_out_cooldown(state: WorldState) -> None:
    """Block until the cooldown the server just set has expired (the MoveAction
    composite-action idiom). Every unequip/equip in the swap starts its own
    cooldown; issuing the next call immediately gets HTTP 499 and strands the
    swap HALF-DONE — live livelock 2026-07-05: the equip leg 499'd, the weapon
    slot sat empty, EquipOwnedGear refilled the dagger by Rank, and the re-arm
    retried forever (~6 wasted calls/min)."""
    if state.cooldown_expires is not None:
        remaining = (state.cooldown_expires - datetime.now(tz=timezone.utc)).total_seconds()
        if remaining > 0:
            time.sleep(remaining + 0.1)


@dataclass
class OptimizeLoadoutAction(Action):
    """Equip the best owned loadout for a target monster or gathering skill.

    The action is the planner's way to spend a few cooldown cycles re-arming
    before a fight or gather. Compares per-fight expected damage (weapon) and
    damage reduction (armor) against the monster's element profile for combat,
    or picks the best gather tool for the skill.
    """

    tags: ClassVar[frozenset[str]] = frozenset({"equip"})

    target_monster_code: str = ""
    target_skill: str = ""
    game_data: GameData | None = field(default=None, repr=False, compare=False)

    def _swap_plan(self, state: WorldState, game_data: GameData) -> dict[str, str | None]:
        """Slots that would change in the optimal loadout. Empty when nothing to do.

        Monster key set → Combat purpose; skill key set → Gather purpose; both
        empty is the documented "no target" sentinel — no swap is computed.
        This single-locus check is the action's precondition, not multi-level
        error handling."""
        purpose: Combat | Gather
        if self.target_monster_code:
            purpose = Combat(
                game_data.monster_attack(self.target_monster_code),
                game_data.monster_resistance(self.target_monster_code),
            )
        elif self.target_skill:
            purpose = Gather(self.target_skill)
        else:
            return {}
        # Memoized: the planner calls _swap_plan from is_applicable, cost AND
        # apply on every node expansion — a fresh solve each time pegged the
        # planner thread at 100% CPU (py-spy 2026-07-06: 78% of samples here).
        optimal = pick_loadout_cached(purpose, state, game_data)
        return {
            slot: new_code
            for slot, new_code in optimal.items()
            if state.equipment.get(slot) != new_code
        }

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        swaps = self._swap_plan(state, game_data)
        if not swaps:
            return False
        # SLOT ROOM: apply()/execute() are TWO-PHASE — every displaced item
        # across ALL swap slots is returned to inventory FIRST (unequip pass),
        # strictly before any incoming code is equipped (equip pass, which
        # only ever shrinks or empties inventory stacks). So the peak slot
        # usage happens right after the unequip pass, and a slot freed by an
        # incoming equip in the SAME action arrives too late to help an
        # outgoing item fit — unlike EquipAction's single atomic swap
        # (equip.py:79-95), there is no "C frees a slot" credit here. A
        # displaced item needs a NEW slot only if its code isn't already a
        # held stack; distinct slots displacing the SAME code (e.g. two
        # identical rings) are deduplicated since inventory is keyed by code,
        # not by slot — this must NOT double-count.
        displaced_codes = {
            state.equipment.get(slot)
            for slot in swaps
            if state.equipment.get(slot) is not None
        }
        total_new_stacks = sum(
            1 for code in displaced_codes if code not in state.inventory
        )
        return has_room(
            total_new_stacks, added_qty=0,
            slots_free=state.inventory_slots_free,
            qty_free=state.inventory_free,
        )

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
                _wait_out_cooldown(state)
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
            _wait_out_cooldown(state)
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
        key = self.target_monster_code or "gather:" + self.target_skill
        return f"OptimizeLoadout({key})"
