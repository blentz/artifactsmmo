"""ItemStats adapter + dispatch for the unified gear value ruler."""

from artifactsmmo_cli.ai.gear_value_core import Rank, combat_raw, rank_value
from artifactsmmo_cli.ai.item_catalog import ItemStats


def combat_raw_of(stats: ItemStats) -> int:
    attack = sum(stats.attack.values()) if stats.attack else 0
    resistance = sum(stats.resistance.values()) if stats.resistance else 0
    return combat_raw(attack, resistance, stats.hp_restore, stats.hp_bonus,
                      stats.dmg, stats.critical_strike, stats.lifesteal,
                      stats.combat_buff)


def gear_value(stats: ItemStats, purpose: object) -> int:
    """Unified gear value. Rank now; Combat/Gather added in Task 3."""
    if purpose is Rank or isinstance(purpose, Rank):
        return rank_value(combat_raw_of(stats), stats.wisdom, stats.prospecting,
                          stats.inventory_space, stats.haste, stats.subtype)
    raise ValueError(f"unsupported purpose: {purpose!r}")
