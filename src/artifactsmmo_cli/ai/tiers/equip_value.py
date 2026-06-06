"""Shared equippable-item value: combat score + per-skill tool score."""

from artifactsmmo_cli.ai.game_data import ItemStats


def equip_value(stats: ItemStats) -> float:
    """Combat/utility value of an equippable — ranks combat gear so genuinely
    better items beat alphabetical accidents AND non-tool weapons rank above
    tools that score the same on raw attack. Single source shared by the
    UpgradeEquipment goal and the Tier-1 objective.

    Combat score: 2 * (attack + resistance + hp_restore) + nonToolBonus,
    where nonToolBonus = 0 if subtype == 'tool' else 1. Augmented for
    composition with the kernel-checked combat scorer
    (Formal/PurposeRouting.combatScore): a non-tool weapon strictly
    outranks an attack-equivalent tool, and any strict attack inequality
    is preserved (the 2x factor protects the tiebreaker). Without the
    augmentation, copper_dagger (5 earth atk, non-tool) tied fishing_net
    (5 water atk, tool, -10 fishing skill effect) at equip_value=5 → gain
    against current fishing_net was 0 → marginal 0 → root invisible in
    ranking — the bot never prioritized crafting it. Trace 2026-06-06
    session 09:59 cycles 56-110: Robby level 4 hp 135/135, no winnable
    monster at his level, ObtainItem(copper_dagger) scored 0 → no gear
    progression visible to the ranker → 50+ cycles of pure PursueTask.
    """
    attack = sum(stats.attack.values()) if stats.attack else 0
    resistance = sum(stats.resistance.values()) if stats.resistance else 0
    raw = attack + resistance + stats.hp_restore
    non_tool_bonus = 0 if stats.subtype == "tool" else 1
    return float(2 * raw + non_tool_bonus)


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
