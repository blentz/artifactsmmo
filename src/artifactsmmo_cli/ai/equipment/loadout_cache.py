"""Memoized front-end for `loadout_picker.pick_loadout` on GOAP-hot paths.

The planner expands thousands of nodes per arbitration cycle, and
`OptimizeLoadoutAction` ran a FULL loadout solve from `is_applicable`, `cost`
AND `apply` on every expansion (`GatherAction.cost` re-ran it per node too).
Live profile 2026-07-06 (py-spy, 10s, planner thread pegged): 86% of samples
inside `pick_loadout`. Within one search almost every node shares the same
(purpose, level, equipment, inventory), so a memo turns those solves into
lookups.

The key is exactly pick_loadout's determinants: purpose, `state.level`,
`state.equipment`, and `state.inventory` WITH counts (the ring/artifact
occupancy cap is physical ownership, so quantities change the answer).
Entries are scoped per-GameData by `CatalogueScope` — a GameData's cache
dies with it, and distinct instances (test fixtures) never collide.
"""

from collections import OrderedDict

from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.catalogue_scope import CatalogueScope
from artifactsmmo_cli.ai.equipment.loadout_picker import pick_loadout
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_value_core import Combat, Gather, Rank
from artifactsmmo_cli.ai.world_state import WorldState

CACHE_MAX_ENTRIES = 4096
"""Per-GameData LRU bound: comfortably holds one arbitration cycle's distinct
search states while capping long-run growth (inventory churns every action, so
unbounded keys would accumulate for the life of the process)."""

_CacheKey = tuple[tuple[object, ...], int, tuple[tuple[str, str | None], ...],
                  tuple[tuple[str, int], ...]]

_CACHES: "CatalogueScope[_CacheKey, dict[str, str | None]]" = CatalogueScope(CACHE_MAX_ENTRIES)
"""Scoped per GameData — see `ai/catalogue_scope`, which owns the whole argument
about why a cache may not name a catalogue by a bare `id()`."""

_EQUIPPABLE_MEMO: "CatalogueScope[str, bool]" = CatalogueScope(CACHE_MAX_ENTRIES)
"""Per-GameData `code -> can this code ever occupy a slot`. Catalog-static, so
memoized once per code, and scoped exactly like the loadout cache. The bound is
shared with it and never binds in practice: the answer set is one entry per item
code the planner has ever asked about."""


def _equippable(code: str, memo: "OrderedDict[str, bool]", game_data: GameData) -> bool:
    """Is `code` a type that can occupy a slot at all?

    The memo is passed IN rather than looked up here: this runs once per bag code
    on every key build, and re-resolving the catalogue's sub-cache per code cost
    4 % of the memo's own hit path (measured 2026-08-25, 2.33 -> 2.23 us/hit)."""
    known = memo.get(code)
    if known is None:
        stats = game_data.item_stats(code)
        known = stats is not None and stats.type_ in ITEM_TYPE_TO_SLOTS
        _EQUIPPABLE_MEMO.remember(memo, code, known)
    return known


def _purpose_key(purpose: object) -> tuple[object, ...]:
    """Hashable canonical key for the closed purpose set (gear_value_core)."""
    if isinstance(purpose, Combat):
        # player_attack is part of the key: armor_score prices a piece's damage-%
        # and crit-% against the fighter's own attack, so two states sharing
        # (level, equipment, inventory) but not attack CAN pick different armor.
        return ("combat",
                tuple(sorted(purpose.monster_attack.items())),
                tuple(sorted(purpose.monster_resistance.items())),
                tuple(sorted(purpose.player_attack.items())))
    if isinstance(purpose, Gather):
        return ("gather", purpose.skill)
    if isinstance(purpose, Rank):
        return ("rank",)
    raise TypeError(f"unknown pick_loadout purpose: {purpose!r}")


def pick_loadout_cached(
    purpose: object, state: WorldState, game_data: GameData,
) -> dict[str, str | None]:
    """`pick_loadout` with a per-GameData LRU memo — bit-identical results.

    Both the stored entry and the returned dict are private copies, so a
    caller mutating its result can never poison later hits.
    """
    cache = _CACHES.cache_for(game_data)
    equippable_memo = _EQUIPPABLE_MEMO.cache_for(game_data)
    # Inventory enters the key PROJECTED onto equippable codes: pick_loadout
    # reads the inventory only through the candidate pool (qty>0, item type in
    # ITEM_TYPE_TO_SLOTS) and the dup-cap ownership of those same candidates,
    # so gathered-material churn (the planner mutates it every search node)
    # cannot change the answer and must not miss the cache — whole-inventory
    # keys left 68% of planner CPU as misses (profile 2026-07-06).
    key: _CacheKey = (
        _purpose_key(purpose),
        state.level,
        tuple(sorted(state.equipment.items())),
        tuple(sorted(
            (code, qty) for code, qty in state.inventory.items()
            if qty > 0 and _equippable(code, equippable_memo, game_data)
        )),
    )
    hit = cache.get(key)
    if hit is not None:
        cache.move_to_end(key)
        return dict(hit)
    result = pick_loadout(purpose, state, game_data)
    _CACHES.remember(cache, key, dict(result))
    return result
