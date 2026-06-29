"""Catalog-wide best-equipment-by-level proxy for the WinnableAcrossBand sweep.

The sweep (docs/PLAN_faithfulness_modeling.md Workstream B) needs, per character
level L, the strongest gear the bot could wield at L, so production's real
`is_winnable` can run against the live monster catalog at that band. The existing
`loadout_picker.pick_loadout` only scans items the character already OWNS; this helper
scans the WHOLE catalog — an optimistic upper-bound proxy: the best obtainable
FULL LOADOUT with ``item.level <= L`` (best item per equip slot). The soundness
caveat — that the bot actually obtains this gear — is the gear-progression
residual the sweep makes explicit (Task 3 / corner 3). ``best_weapon_for_level``
is retained because it is also used in the Lean C1b-proof layer that mirrors the
weapon-proxy model over the extracted item stats.
"""

from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
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

    Retained for the planned C1b Lean kernel proof (per-level stat model), not
    yet referenced in any Lean file. The sweep itself uses
    ``obtainable_inventory_for_level`` + ``obtainable_hp_bonus_ceiling`` for the
    full-loadout + full-HP model.
    """
    candidates = [
        stats
        for stats in stats_by_code.values()
        if stats.type_ == WEAPON_TYPE and stats.level <= level
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda s: (_total_attack(s), s.level, s.code))


def obtainable_inventory_for_level(
    stats_by_code: dict[str, ItemStats], level: int,
) -> dict[str, int]:
    """Catalog inventory ``{code: 1}`` for every equippable item with ``item.level <= level``.

    This is the optimistic-obtainable item pool the sweep feeds to
    ``pick_loadout`` so production's real loadout picker can select the best
    full gear set (weapon + armor + rings + amulet + …) at level ``level``,
    rather than a weapon-only proxy.

    Only items that map to at least one equip slot (``ITEM_TYPE_TO_SLOTS``) are
    included — consumables, crafting materials, and resources that do not occupy
    an equip slot are excluded because ``pick_loadout / _candidates_for_slot``
    would ignore them anyway.

    SOUNDNESS: the claim "this inventory is obtainable" is the gear-progression
    residual (Task 3 / corner 3). This helper is intentionally optimistic: it
    models the strongest possible full loadout, making ``WinnableAcrossBand``
    harder to satisfy (witness = strongest reachable gear), not easier. Any gap
    it reports is a genuine gap; any witness it finds is a valid witness for the
    real character once the gear is obtained.
    """
    return {
        code: 1
        for code, stats in stats_by_code.items()
        if stats.level <= level and stats.type_ in ITEM_TYPE_TO_SLOTS
    }


def obtainable_hp_bonus_ceiling(
    stats_by_code: dict[str, ItemStats], level: int,
) -> int:
    """Upper bound on total HP bonus from the best obtainable gear at ``level``.

    For each equippable item TYPE, sums the top-N ``hp_bonus`` values where N is
    the number of slots that type occupies (``len(ITEM_TYPE_TO_SLOTS[type_])``).
    Multi-slot types (ring→2, artifact→3, utility→2) thus contribute the SUM of
    their N best items, matching how ``pick_loadout`` fills all N slots
    independently with distinct items.

    Because ``project_loadout_stats`` accumulates ``hp_bonus`` for every slot
    that changes, the projected ``max_hp = state.max_hp + Σ_slot hp_bonus`` is at
    most ``state.max_hp + this ceiling``. Setting ``state.hp = base_max_hp +
    ceiling`` therefore guarantees ``state.hp >= p.max_hp`` for ANY loadout
    ``pick_loadout`` selects — so ``effective_hp = min(state.hp, p.max_hp) ==
    p.max_hp`` and the combat verdict runs at FULL projected HP (faithful to the
    bot resting before fighting).

    The ceiling is a genuine upper bound: it never undercounts, so
    ``state.hp >= p.max_hp`` holds for any per-monster loadout ``pick_loadout``
    can choose.
    """
    hp_bonuses_per_type: dict[str, list[int]] = {}
    for stats in stats_by_code.values():
        if stats.level > level or stats.type_ not in ITEM_TYPE_TO_SLOTS:
            continue
        if stats.hp_bonus > 0:
            hp_bonuses_per_type.setdefault(stats.type_, []).append(stats.hp_bonus)
    total = 0
    for type_, bonuses in hp_bonuses_per_type.items():
        n_slots = len(ITEM_TYPE_TO_SLOTS[type_])
        bonuses.sort(reverse=True)
        total += sum(bonuses[:n_slots])
    return total
