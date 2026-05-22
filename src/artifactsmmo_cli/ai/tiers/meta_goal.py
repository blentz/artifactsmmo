"""Tier-2 meta-goal nodes: concrete progression conditions for the
prerequisite graph. Frozen + hashable so P3 traversal can use visited-sets."""

from dataclasses import dataclass
from typing import Protocol

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState


def owned_count(state: WorldState, code: str) -> int:
    """How many of `code` the character has across inventory, bank, and the
    equipped slots (an equipped item counts as one)."""
    count = state.inventory.get(code, 0)
    if state.bank_items:
        count += state.bank_items.get(code, 0)
    if code in state.equipment.values():
        count += 1
    return count


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


@dataclass(frozen=True)
class ObtainItem:
    code: str
    quantity: int = 1

    def is_satisfied(self, state: WorldState, game_data: GameData) -> bool:
        return owned_count(state, self.code) >= self.quantity
