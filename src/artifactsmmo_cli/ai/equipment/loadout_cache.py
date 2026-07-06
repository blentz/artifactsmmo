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
Entries are scoped per-GameData via weak references — a GameData's cache
dies with it, and distinct instances (test fixtures) never collide.
"""

import weakref
from collections import OrderedDict

from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
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

_caches: dict[int, "OrderedDict[_CacheKey, dict[str, str | None]]"] = {}
"""Keyed by id(game_data) — GameData is an eq-dataclass (unhashable), so a
WeakKeyDictionary can't hold it. A `weakref.finalize` purges the entry the
moment its GameData is collected, which also makes id-reuse impossible: the
old id is evicted before the allocator can hand it out again."""

_equippable_memo: dict[int, dict[str, bool]] = {}
"""Per-GameData `code -> can this code ever occupy a slot`. Catalog-static, so
memoized once per code; purged together with the loadout cache."""


def _cache_for(game_data: GameData) -> "OrderedDict[_CacheKey, dict[str, str | None]]":
    key = id(game_data)
    cache = _caches.get(key)
    if cache is None:
        cache = OrderedDict()
        _caches[key] = cache
        _equippable_memo[key] = {}
        weakref.finalize(game_data, _caches.pop, key, None)
        weakref.finalize(game_data, _equippable_memo.pop, key, None)
    return cache


def _equippable(code: str, game_data: GameData) -> bool:
    memo = _equippable_memo[id(game_data)]
    known = memo.get(code)
    if known is None:
        stats = game_data.item_stats(code)
        known = stats is not None and stats.type_ in ITEM_TYPE_TO_SLOTS
        memo[code] = known
    return known


def _purpose_key(purpose: object) -> tuple[object, ...]:
    """Hashable canonical key for the closed purpose set (gear_value_core)."""
    if isinstance(purpose, Combat):
        return ("combat",
                tuple(sorted(purpose.monster_attack.items())),
                tuple(sorted(purpose.monster_resistance.items())))
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
    cache = _cache_for(game_data)
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
            if qty > 0 and _equippable(code, game_data)
        )),
    )
    hit = cache.get(key)
    if hit is not None:
        cache.move_to_end(key)
        return dict(hit)
    result = pick_loadout(purpose, state, game_data)
    cache[key] = dict(result)
    if len(cache) > CACHE_MAX_ENTRIES:
        cache.popitem(last=False)
    return result
