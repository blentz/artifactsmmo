"""PURE proved core for the unified gear value ruler (extracted; mirrors
Formal/GearValue.lean). No GameData/IO — plain data only. See
docs/superpowers/specs/2026-06-28-gear-unified-ruler-design.md."""

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class Rank:
    """Monster-independent ranking purpose (the unified equip_value)."""


@dataclass(frozen=True)
class Combat:
    """Per-monster combat purpose."""

    monster_attack: Mapping[str, int]
    monster_resistance: Mapping[str, int]


@dataclass(frozen=True)
class Gather:
    """Per-skill gather purpose."""

    skill: str


def combat_raw(attack: int, resistance: int, hp_restore: int, hp_bonus: int,
               dmg: int, critical_strike: int, lifesteal: int,
               combat_buff: int) -> int:
    """The genuine-combat signal shared by Rank and strategic_value. Mirrors
    Formal.GearValue.combatRaw. (`_equip_value` omitted exactly dmg+crit.)"""
    return (attack + resistance + hp_restore + hp_bonus + dmg + critical_strike
            + lifesteal + combat_buff)


def rank_value(combat_raw_value: int, wisdom: int, prospecting: int,
               inventory_space: int, haste: int, subtype: str) -> int:
    """The unified Rank ruler. Bit-identical to legacy equip_value:
    2*(combat_raw + efficiency) + nonToolBonus. Mirrors Formal.GearValue.rankValue."""
    non_tool_bonus = 0 if subtype == "tool" else 1
    return 2 * (combat_raw_value + wisdom + prospecting + inventory_space + haste) + non_tool_bonus
