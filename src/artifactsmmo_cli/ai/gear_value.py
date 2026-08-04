"""ItemStats adapter + dispatch for the unified gear value ruler."""

from artifactsmmo_cli.ai.equipment.scoring import armor_score, gather_score, weapon_score
from artifactsmmo_cli.ai.gear_value_core import Combat, Gather, Rank, combat_raw, rank_value
from artifactsmmo_cli.ai.item_catalog import ItemStats


def combat_raw_of(stats: ItemStats) -> int:
    """ItemStats -> the pure `combat_raw` core's eight ints.

    Every per-ELEMENT dict is hoisted to ONE int here — that hoist is this
    adapter's whole job, and `dmg_elements` is hoisted exactly like `attack`
    and `resistance`: summed into the scalar the core already takes. The
    global `dmg` percentage and the per-element `dmg_<elem>` percentages are
    the SAME quantity expressed at two granularities (game_data parses `dmg`
    and `dmg_fire`/`dmg_earth`/… from one `effects` list; `armor_score` adds
    them per element as `dmg + dmg_elements[e]`), so summing them into the
    core's `dmg` argument is a change of REPRESENTATION, not of the ruler.

    Live 2026-08-04 (Robby, level 21) is what forced it: `dmg_elements` was
    the one stat the two authorities disagreed about EXISTING. The monster-
    relative `armor_score` counts it (since 170ed8d8); `combat_raw` did not,
    so `pursuit_value(life_amulet)=30000` beat
    `pursuit_value(fire_and_earth_amulet)=20000` while
    `armor_score(life_amulet)=6000` lost to `armor_score(fire_and_earth)=48000`
    vs wolf — the progression tree equipped the amulet the combat picker
    immediately swapped back out, one API call and one cooldown per cycle,
    forever. With the hoist both amulets score 30 raw and the tree's gain is 0.
    """
    attack = sum(stats.attack.values()) if stats.attack else 0
    resistance = sum(stats.resistance.values()) if stats.resistance else 0
    dmg = stats.dmg + (sum(stats.dmg_elements.values()) if stats.dmg_elements else 0)
    return combat_raw(attack, resistance, stats.hp_restore, stats.hp_bonus,
                      dmg, stats.critical_strike, stats.lifesteal,
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
        return armor_score(stats, dict(purpose.monster_attack),
                           dict(purpose.monster_resistance),
                           dict(purpose.player_attack))
    if isinstance(purpose, Gather):
        return gather_score(stats, purpose.skill)
    raise ValueError(f"unsupported purpose: {purpose!r}")
