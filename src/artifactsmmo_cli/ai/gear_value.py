"""ItemStats adapter + dispatch for the unified gear value ruler."""

from artifactsmmo_cli.ai.equipment.scoring import armor_score, gather_score, weapon_score
from artifactsmmo_cli.ai.gear_value_core import Combat, Gather, Rank, combat_raw, rank_value
from artifactsmmo_cli.ai.item_catalog import ItemStats


def combat_raw_of(stats: ItemStats) -> int:
    attack = sum(stats.attack.values()) if stats.attack else 0
    resistance = sum(stats.resistance.values()) if stats.resistance else 0
    return combat_raw(attack, resistance, stats.hp_restore, stats.hp_bonus,
                      stats.dmg, stats.critical_strike, stats.lifesteal,
                      stats.combat_buff)


def gear_value(stats: ItemStats, purpose: object) -> int:
    """Unified gear value over a purpose (Rank / Combat / Gather).

    LAYERING DIRECTION: gear_value -> scoring. The Combat/Gather branches
    DELEGATE to the proven per-monster scorers in ``equipment/scoring.py``
    (`weapon_score`/`armor_score`/`gather_score`). That module must NOT import
    this one (it would cycle). ``pick_loadout(Gather(...))`` in
    ``equipment/loadout_picker.py`` selects gear using the `*_score` functions
    this module delegates to. The "scorers are specializations of gear_value"
    framing is realized by gear_value calling them, one direction only.
    """
    if purpose is Rank or isinstance(purpose, Rank):
        return rank_value(combat_raw_of(stats), stats.wisdom, stats.prospecting,
                          stats.inventory_space, stats.haste, stats.subtype)
    if isinstance(purpose, Combat):
        # gear_value(Combat) mirrors pick_loadout's per-slot scorer: the weapon
        # slot maximizes weapon_score against the monster's resistance; every
        # other (armor) slot maximizes armor_score against the monster's attack.
        if stats.type_ == "weapon":
            return weapon_score(stats, dict(purpose.monster_resistance))
        return armor_score(stats, dict(purpose.monster_attack))
    if isinstance(purpose, Gather):
        return gather_score(stats, purpose.skill)
    raise ValueError(f"unsupported purpose: {purpose!r}")
