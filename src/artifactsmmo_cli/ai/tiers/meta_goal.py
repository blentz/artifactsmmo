"""Tier-2 meta-goal nodes: concrete progression conditions for the
prerequisite graph. Frozen + hashable so P3 traversal can use visited-sets."""

from dataclasses import dataclass
from typing import Protocol

from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.tiers.owned_count import owned_count_pure
from artifactsmmo_cli.ai.world_state import WorldState


def owned_count(state: WorldState, code: str) -> int:
    """How many of `code` the character has across inventory, bank, and the
    equipped slots (an equipped item counts as one).

    `state.inventory` counts only UNEQUIPPED (spare) copies: the API stores
    equipped items in dedicated equipment slots, separate from the inventory
    list, and `EquipAction.apply` decrements inventory by 1 when equipping. So
    the equipped `+1` counts the worn copy, which is not in the inventory count;
    spare copies of an equipped item may still sit in inventory and are summed
    correctly (1 worn + 1 spare = 2 owned). There is no disjointness-of-codes
    invariant. See `owned_count_pure` and `EquipAction.apply`.
    """
    equipped_codes = [c for c in state.equipment.values() if c is not None]
    return owned_count_pure(state.inventory, state.bank_items, equipped_codes, code)


class MetaGoal(Protocol):
    """A concrete progression condition that is either satisfied or not."""

    def is_satisfied(self, state: WorldState, game_data: GameData) -> bool: ...


@dataclass(frozen=True)
class ReachCharLevel:
    level: int

    def is_satisfied(self, state: WorldState, game_data: GameData) -> bool:
        return state.level >= self.level


@dataclass(frozen=True)
class ReachSkillLevel:
    skill: str
    level: int

    def is_satisfied(self, state: WorldState, game_data: GameData) -> bool:
        return state.skills.get(self.skill, 1) >= self.level


@dataclass(frozen=True, repr=False)
class ObtainItem:
    code: str
    quantity: int = 1
    slot: str | None = None

    def __repr__(self) -> str:
        if self.slot is not None:
            return (f"ObtainItem(code={self.code!r}, quantity={self.quantity}, "
                    f"slot={self.slot!r})")
        return f"ObtainItem(code={self.code!r}, quantity={self.quantity})"

    def is_satisfied(self, state: WorldState, game_data: GameData) -> bool:
        # Per-slot gear root: satisfied iff THIS slot holds the code, so the
        # objective can target the same item in multiple slots (two copper_rings
        # in ring1_slot + ring2_slot). slot=None keeps the legacy semantics below.
        if self.slot is not None:
            return state.equipment.get(self.slot) == self.code
        # Equippable items: owning isn't the end-state — the meta-objective
        # is to WEAR them. Trace 2026-06-05T03:37: Robby crafted wooden_shield
        # but never equipped it; root dropped from candidates because owned >=
        # 1, the UpgradeEquipmentGoal never re-fired, and the shield sat
        # in inventory forever. Require occupancy of an equipment slot.
        # EXCEPT TOOLS (subtype='tool', e.g. copper_pickaxe, copper_axe,
        # fishing_net): owning is the goal because tools ROTATE through
        # weapon_slot per the active gathering task (OptimizeLoadout swaps
        # the right tool in per-fight / per-gather). Recipe-input codes
        # (ash_plank, copper_bar, ash_wood) stay on the owned-count rule —
        # they're consumed by crafts and never enter equipment.
        stats = game_data.item_stats(self.code)
        if stats is not None and ITEM_TYPE_TO_SLOTS.get(stats.type_):
            if stats.subtype == "tool":
                return owned_count(state, self.code) >= self.quantity
            return self.code in state.equipment.values()
        return owned_count(state, self.code) >= self.quantity
