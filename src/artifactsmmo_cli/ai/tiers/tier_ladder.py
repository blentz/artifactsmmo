"""The progression ladder, DERIVED from game data.

Every equippable item in the game sits on one of a small set of levels, and the
craft-skill breakpoints use the same set. Against the live catalogue that set is
`(1, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50)` — but it is read from the data on
every call, never written down, so a content patch moves the ladder without a
code change.

A tier's BAND is the monsters from that rung up to (not including) the next. The
bands partition the whole monster table.

NOT `audit/content_tiers.py`. That module buckets content into fixed ten-level
windows (`level // 10`) as the journey axis of the behavioural-completeness
matrix document, and its production consumer is `scripts/gen_content_tiers.py`
(which renders `docs/behavioral_completeness/content_tiers.md`), not the
planner. This ladder is uneven, derived, and is what the planner descends. The
two are different axes over the same world and must not be merged without the
matrix owner's agreement.
"""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_taxonomy import ITEM_TYPE_TO_SLOTS

NON_FARMABLE_TYPES = frozenset({"boss", "elite", "raid_boss"})
"""Monster types excluded from a tier's clear condition.

The API publishes `monster.type` on every record (`MonsterCatalog.types`,
already read by `xp_per_kill`). Boss, elite and raid content is optional and
carries its own objectives; gating the ladder on it stalls progression. Live
case: `king_slime` is a level-15 boss with 1000 hp and 20 resistance on all four
elements, and it blocks a level-30 character out of the level-15 rung.
"""


def ladder(game_data: GameData) -> tuple[int, ...]:
    """The ascending distinct levels of every EQUIPPABLE item."""
    return tuple(sorted({
        stats.level for stats in game_data.all_item_stats.values()
        if stats.type_ in ITEM_TYPE_TO_SLOTS and stats.level > 0
    }))


def tier_of_level(game_data: GameData, level: int) -> int:
    """The highest rung at or below `level`; the first rung when below it all."""
    rungs = ladder(game_data)
    if not rungs:
        raise ValueError("no equippable items in game data — cannot derive a ladder")
    at_or_below = [rung for rung in rungs if rung <= level]
    return at_or_below[-1] if at_or_below else rungs[0]


def band(game_data: GameData, tier: int) -> tuple[str, ...]:
    """Monster codes from `tier` up to the next rung, sorted. Every monster
    falls in exactly one band."""
    rungs = ladder(game_data)
    higher = [rung for rung in rungs if rung > tier]
    ceiling = higher[0] if higher else None
    return tuple(sorted(
        code for code, level in game_data.monster_levels.items()
        if level >= tier and (ceiling is None or level < ceiling)
    ))


def normal_band(game_data: GameData, tier: int) -> tuple[str, ...]:
    """`band`, minus boss / elite / raid_boss — the monsters a rung is cleared on."""
    types = game_data.monsters.types
    return tuple(code for code in band(game_data, tier)
                 if types[code] not in NON_FARMABLE_TYPES)
