"""Shared equippable-item value: total attack + resistance + hp restore."""

from artifactsmmo_cli.ai.game_data import ItemStats


def equip_value(stats: ItemStats) -> float:
    """Crude combat/utility value of an equippable — ranks gear so genuinely
    better items beat alphabetical accidents. Single source shared by the
    UpgradeEquipment goal and the Tier-1 objective."""
    attack = sum(stats.attack.values()) if stats.attack else 0
    resistance = sum(stats.resistance.values()) if stats.resistance else 0
    return float(attack + resistance + stats.hp_restore)
