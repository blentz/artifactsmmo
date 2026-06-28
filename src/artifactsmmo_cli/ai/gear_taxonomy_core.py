"""PURE proved core for gear taxonomy (extracted, mirrors Formal/GearTaxonomy.lean).

No GameData/IO — operates on plain data so the differential harness can call it
directly. See docs/superpowers/specs/2026-06-28-gear-taxonomy-design.md.
"""

from collections.abc import Mapping, Sequence

# Raw consumable-family effect codes (exact + prefixes). The boost_* family are
# temporary fight buffs (the consumable axis), distinct from durable gear stats.
_CONSUMABLE_EXACT = frozenset({"heal", "restore", "splash_restore", "antipoison",
                               "teleport", "boost_hp"})
_CONSUMABLE_PREFIX = ("boost_dmg_", "boost_res_")


def is_combat_bearing(attack: Mapping[str, int], resistance: Mapping[str, int],
                      hp_bonus: int, dmg: int, dmg_elements: Mapping[str, int],
                      critical_strike: int, initiative: int,
                      lifesteal: int) -> bool:
    """True iff the item carries any DURABLE combat stat (the OR of gear combat
    fields). Mirrors Formal.GearTaxonomy.isCombatBearing."""
    return bool(attack or resistance or hp_bonus or dmg or dmg_elements
                or critical_strike or initiative or lifesteal)


def is_consumable(effect_codes: Sequence[str]) -> bool:
    """True iff any raw effect code is in the consumable family (temporary
    buffs / restores). Mirrors Formal.GearTaxonomy.isConsumable."""
    return any(code in _CONSUMABLE_EXACT or code.startswith(_CONSUMABLE_PREFIX)
               for code in effect_codes)


def combat_gear_types(rows: Sequence[tuple[str, bool, bool]]) -> frozenset[str]:
    """Types that are durable combat gear: have a combat-bearing item AND no
    consumable item. Each row is (type, combat_bearing, consumable). Mirrors
    Formal.GearTaxonomy.combatGearTypes."""
    combat: set[str] = set()
    consumable: set[str] = set()
    for type_, is_combat, is_cons in rows:
        if is_combat:
            combat.add(type_)
        if is_cons:
            consumable.add(type_)
    return frozenset(combat - consumable)
