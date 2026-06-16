"""Shared equippable-item value: combat score + per-skill tool score."""

from artifactsmmo_cli.ai.game_data import ItemStats


def equip_value_pure(attack: int, resistance: int, hp_restore: int, hp_bonus: int,
                     dmg: int, critical_strike: int, wisdom: int, prospecting: int,
                     inventory_space: int, subtype: str) -> int:
    """PURE CORE (mechanically extracted, P4b): ``2 * raw + nonToolBonus``.

    The ItemStats reads (and the dict-value sums for attack/resistance) are
    hoisted to plain int parameters by the ``equip_value`` wrapper — the
    same already-summed shape the hand model takes. Extracted to
    ``Formal/Extracted/EquipValue.lean``; the bridge proves it equal to the
    hand ``Formal.EquipValueAugmented.equipValue`` (RawStats + isTool),
    transferring strict-raw preservation and the non-tool tie-break onto
    the extracted definition.
    """
    raw = (attack + resistance + hp_restore
           + hp_bonus + dmg + critical_strike + wisdom + prospecting + inventory_space)
    non_tool_bonus = 0 if subtype == "tool" else 1
    return 2 * raw + non_tool_bonus


def tool_value_pure(skill_effects: dict[str, int], skill: str) -> int:
    """PURE CORE (mechanically extracted, P4b): ``abs(skill_effects[skill])``.

    Definitionally ``|gather_score_pure|`` — the bridge pins the duality:
    on the tool domain (non-positive effects) maximizing this value is
    exactly minimizing the gather score the combat-side picker minimizes.
    """
    effect = skill_effects.get(skill, 0)
    return abs(effect)


def equip_value(stats: ItemStats) -> int:
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
    # 2026-06-06 trace 09:59: copper_boots(hp_bonus=10), copper_helmet
    # (dmg=3, hp_bonus=20), copper_ring(dmg=2) all scored equip_value=0
    # (later =1 after the nonToolBonus augment) because raw summed ONLY
    # attack+resistance+hp_restore. Armor with no per-element resistance
    # but real defensive stats (max-HP bonus, damage bonus %, crit %) was
    # invisible to the ranker → ObtainItem(copper_boots) marginal stuck
    # at 0.05 → ranked below 8 ReachSkillLevel roots → never pursued.
    # Folding hp_bonus, dmg, critical_strike into the raw signal closes
    # the armor-pursuit gap. The mixed units (flat hp vs %) are intentional:
    # only ARGMAX ORDERING matters for ranker decisions, and every modeled
    # contributor is positively correlated with combat capability.
    # P4a: every summand is an int (ItemStats stats are ints) — the value is
    # EXACT integer arithmetic, matching the Lean EquipValueAugmented.equipValue
    # (Int) model directly. The historical float() wrapper added nothing.
    # P4b: the arithmetic lives in the extracted `equip_value_pure` core.
    return equip_value_pure(attack, resistance, stats.hp_restore, stats.hp_bonus,
                            stats.dmg, stats.critical_strike, stats.wisdom,
                            stats.prospecting, stats.inventory_space, stats.subtype)


def tool_value(stats: ItemStats, skill: str) -> int:
    """Tool benefit for a given gathering skill. The API encodes tools as
    `type_="weapon"` with `skill_effects[skill] = -cooldown_reduction_pct`
    (negative because the effect reduces a cost). We score by the absolute
    magnitude — bigger reduction wins. Returns 0 when the item has no
    effect for this skill. P4a: skill_effects values are ints — exact."""
    if not stats.skill_effects:
        return 0
    return tool_value_pure(stats.skill_effects, skill)
