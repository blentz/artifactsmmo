"""Shared equippable-item value: combat score + per-skill tool score."""

from artifactsmmo_cli.ai.game_data import ItemStats


def equip_value(stats: ItemStats) -> float:
    """Combat/utility value of an equippable — ranks combat gear so genuinely
    better items beat alphabetical accidents. Single source shared by the
    UpgradeEquipment goal and the Tier-1 objective.

    Combat-only score: attack + resistance + hp_restore. Does NOT include
    skill_effects (use `tool_value` for that). Combat and tool roles share
    the weapon_slot per the API's flat ItemType enum, but they're scored
    on independent axes — pursued as separate objective roots and swapped
    at run-time by OptimizeLoadout."""
    attack = sum(stats.attack.values()) if stats.attack else 0
    resistance = sum(stats.resistance.values()) if stats.resistance else 0
    return float(attack + resistance + stats.hp_restore)


def tool_value(stats: ItemStats, skill: str) -> float:
    """Tool benefit for a given gathering skill. The API encodes tools as
    `type_="weapon"` with `skill_effects[skill] = -cooldown_reduction_pct`
    (negative because the effect reduces a cost). We score by the absolute
    magnitude — bigger reduction wins. Returns 0 when the item has no
    effect for this skill."""
    if not stats.skill_effects:
        return 0.0
    effect = stats.skill_effects.get(skill, 0)
    return float(abs(effect))
