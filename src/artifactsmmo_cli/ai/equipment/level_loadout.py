"""Catalog-wide best-equipment-by-level proxy for the WinnableAcrossBand sweep.

The sweep (docs/PLAN_faithfulness_modeling.md Workstream B) needs, per character
level L, the strongest gear the bot could wield at L, so production's real
`is_winnable` can run against the live monster catalog at that band. The existing
`scoring.pick_loadout` only scans items the character already OWNS; this helper
scans the WHOLE catalog — an optimistic upper-bound proxy: the best obtainable
weapon with ``item.level <= L``. (The soundness caveat — that the bot actually
obtains this gear — is the gear-progression residual the sweep makes explicit.)
"""

from artifactsmmo_cli.ai.elements import ELEMENTS
from artifactsmmo_cli.ai.item_catalog import ItemStats

WEAPON_TYPE = "weapon"


def _total_attack(weapon: ItemStats) -> int:
    """Monster-independent raw weapon power: summed attack across elements."""
    return sum(weapon.attack.get(e, 0) for e in ELEMENTS)


def best_weapon_for_level(
    stats_by_code: dict[str, ItemStats], level: int,
) -> ItemStats | None:
    """Strongest weapon (max total attack) with ``item.level <= level``.

    Optimistic catalog-wide proxy for the bot's weapon at `level`. Ties are
    broken deterministically by ``(total_attack, item_level, code)`` — highest
    attack, then highest item level, then last code lexicographically. Returns
    ``None`` when no weapon is obtainable at `level`.
    """
    candidates = [
        stats
        for stats in stats_by_code.values()
        if stats.type_ == WEAPON_TYPE and stats.level <= level
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda s: (_total_attack(s), s.level, s.code))
