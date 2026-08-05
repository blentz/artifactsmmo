"""ItemStats adapter + dispatch for the unified gear value ruler."""

from artifactsmmo_cli.ai.equipment.scoring import (
    armor_score_combat,
    gather_score,
    gear_score_efficiency,
    weapon_score_combat,
)
from artifactsmmo_cli.ai.gear_value_core import (
    Combat,
    Gather,
    Rank,
    rank_adversary,
)
from artifactsmmo_cli.ai.item_catalog import ItemStats


def gear_components(stats: ItemStats, purpose: object) -> tuple[int, int]:
    """`gear_value` split into its (COMBAT, EFFICIENCY) terms, for the Rank and
    Combat purposes. `combat + efficiency == gear_value(stats, purpose)` for
    EVERY item and every purpose this accepts — the split is a partition of the
    one ruler, not a second ruler.

    This exists so the ECONOMICS layer (`tiers/pursuit_value`, which must let
    combat dominate utility CROSS-SLOT) can re-read the ruler's own two terms
    lexicographically rather than re-summing the stats on a scale of its own.
    Before this, that layer ran on a flat 8-stat sum (`combat_raw` = attack +
    resistance + hp_restore + hp_bonus + dmg + critical_strike + lifesteal +
    combat_buff) which added a resistance PERCENTAGE to an HP amount to a
    damage figure 1:1 — the same category error the Rank/Combat unification
    removed from the gear ruler, surviving one layer up.

    BOTH branches read the SAME efficiency function (`scoring.
    gear_score_efficiency`), so a point of wisdom / prospecting / inventory_space
    / haste enters the ruler at the same price no matter which slot carries it.
    The weapon branch used to report efficiency 0 — not because the weapon had
    none but because `weapon_score` had no flat-utility block at all, so those
    stats reached NO purpose. Five live items were affected: the four voidstone
    tools (100 prospecting each) and obsidian_battleaxe (inventory_space −25,
    a penalty it was not paying).

    Neither branch's COMBAT term takes an efficiency stat as a parameter
    (`armor_score_combat_pure` / `weapon_score_combat_pure`), which is the
    mechanical reason utility enters the economics layer exactly once.
    """
    if purpose is Rank or isinstance(purpose, Rank):
        return gear_components(stats, rank_adversary())
    if isinstance(purpose, Combat):
        if stats.type_ == "weapon":
            return (weapon_score_combat(stats, dict(purpose.monster_resistance)),
                    gear_score_efficiency(stats))
        return (armor_score_combat(stats, dict(purpose.monster_attack),
                                   dict(purpose.monster_resistance),
                                   dict(purpose.player_attack)),
                gear_score_efficiency(stats))
    raise ValueError(f"unsupported purpose: {purpose!r}")


def gear_value(stats: ItemStats, purpose: object) -> int:
    """Unified gear value over a purpose (Rank / Combat / Gather).

    ONE ALGORITHM. Rank and Combat are the SAME computation — the weapon slot
    maximizes `weapon_score` against the adversary's resistance, every other
    slot maximizes `armor_score` against the adversary's attack, resistance and
    the wearer's own attack. They differ ONLY in what the caller supplies:
    Combat is handed the monster it is about to fight and the character that
    will fight it; Rank has neither, so it substitutes the catalog-median
    adversary (`gear_value_core.rank_adversary`). The Rank branch below is
    literally a re-entry into the Combat branch.

    This replaced a separate flat stat sum (`rank_value` = `2 * (combat_raw +
    wisdom + prospecting + inventory_space + haste) + nonToolBonus`). That sum
    weighted `wisdom` 1:1 against every combat stat and could not see the
    monster-relative shape of `dmg` / `dmg_elements` / `critical_strike` at all,
    so it disagreed with `armor_score` about which piece was better — the
    2026-08-04 amulet equip loop and the `adventurer_vest` > `mushmush_jacket`
    inversion were the same defect seen from two call sites.

    The Rank/Combat branches are the SUM of `gear_components`' two terms, so
    the ruler and the (COMBAT, EFFICIENCY) split the economics layer reads are
    one definition, not two that must be kept in agreement.

    LAYERING DIRECTION: gear_value -> scoring. All three branches DELEGATE to
    the proven scorers in ``equipment/scoring.py``
    (`weapon_score_combat`/`armor_score_combat`, each plus the shared
    `gear_score_efficiency`, whose sums ARE `weapon_score` / `armor_score`, and
    `gather_score`). That module must NOT import this one
    (it would cycle). ``pick_loadout(Gather(...))`` in
    ``equipment/loadout_picker.py`` selects gear using the `*_score` functions
    this module delegates to. The "scorers are specializations of gear_value"
    framing is realized by gear_value calling them, one direction only.
    """
    if isinstance(purpose, Gather):
        return gather_score(stats, purpose.skill)
    combat, efficiency = gear_components(stats, purpose)
    return combat + efficiency
