"""The one answer to "how does a cache key a `GameData`?".

`GameData` is an eq-dataclass, so `__hash__` is None and it cannot be a dict key
or a `WeakKeyDictionary` key. Every per-catalogue memo therefore reached for
`id(game_data)` — and an `id()` is unique only among LIVE objects. CPython hands
the freed address straight to the next allocation, so a cache that names an
address it does not keep alive is a cache keyed on nothing: a second `GameData`
at the recycled address reads the first one's answers.

NOT THEORETICAL, AND NOT RARE. A 200,000-iteration probe (2026-08-25,
`allocate GameData-shaped object -> cache under id() -> free`) saw the address
recycled 199,983 times and, with no reference and no finalizer, served a stale
entry on every one of them. It bit production code twice before this module
existed: `kit_selection._tool_caches` (a state-only key served one test's items
to another — six `formal/diff/test_bank_selection_diff` failures that passed in
isolation), and `weapon_winnability.beatable_count`, which returned 0 for a
weapon that unlocks a monster at 97 % of a SERIAL `tests/test_ai/` run and passed
run-alone and under xdist.

THE MECHANISM. One `weakref.finalize` per catalogue drops that catalogue's whole
sub-cache when the catalogue dies. The same 200,000-iteration probe with the
finalizer in place served ZERO stale entries, and that is not luck: CPython
invokes weakref callbacks from `PyObject_ClearWeakRefs` during deallocation —
before the memory returns to the allocator — and, for cyclic garbage, from the
collector's `handle_weakrefs` pass before it frees the cycle. Either way the
entry is gone before the address can be handed out again, so a recycled address
can only ever mint a FRESH sub-cache.

WHY NOT A STRONG REFERENCE. Holding the catalogue alive beside the entry also
closes the hole (`weapon_winnability` did exactly that from 2026-08-25 until this
module replaced it), but it PINS the catalogue: `GameData` carries every item,
monster, recipe, resource and map in the game, and a memo that outlives its
catalogue's real owner keeps that whole table resident. The finalizer costs one
weakref per catalogue instead — a fixed handful of bytes — and reclaims the
sub-cache at exactly the moment the catalogue itself is reclaimed.

WHY THIS IS A MODULE AND NOT A HABIT. `loadout_cache`, `kit_selection`,
`tiers/skill_grind_target` and `weapon_winnability` each hand-rolled their own
`_cache_for`, and the fifth site (`unlock_boost`) hand-rolled it WRONG — no
reference, no finalizer, no purge. Four copies of an argument about CPython
deallocation order is four chances to drop the load-bearing line. There is one
copy now, and one test that fails the moment it is dropped.
"""

import weakref
from collections import OrderedDict

from artifactsmmo_cli.ai.game_data import GameData


class CatalogueScope[K, V]:
    """A bounded LRU memo private to each `GameData` instance.

    `cache_for` hands back the sub-cache for one catalogue, minting it (and its
    finalizer) on first use; `remember` inserts under the LRU bound. Callers keep
    their own hit handling because the value types differ — some caches legally
    store `None`, so they test membership rather than a sentinel.
    """

    def __init__(self, max_entries: int) -> None:
        self.max_entries = max_entries
        """LRU bound PER CATALOGUE. Public so a test can shrink it to exercise
        eviction without reaching into the dict."""
        self._caches: dict[int, OrderedDict[K, V]] = {}

    def cache_for(self, game_data: GameData) -> OrderedDict[K, V]:
        """The LRU private to `game_data`, created on first use.

        THE `weakref.finalize` CALL IS THE WHOLE SAFETY ARGUMENT — see the module
        docstring. Deleting it as "an unused return value" reopens the
        recycled-address hole at every call site at once, which is what
        `test_catalogue_scope.py` exists to catch.
        """
        key = id(game_data)
        cache = self._caches.get(key)
        if cache is None:
            cache = OrderedDict()
            self._caches[key] = cache
            weakref.finalize(game_data, self._caches.pop, key, None)
        return cache

    def remember(self, cache: OrderedDict[K, V], key: K, value: V) -> V:
        """Insert `key -> value`, evicting the least-recently-used entry past the
        bound. Returns `value` so a caller can `return scope.remember(...)`."""
        cache[key] = value
        if len(cache) > self.max_entries:
            cache.popitem(last=False)
        return value

    def clear(self) -> None:
        """Drop every catalogue's sub-cache. For test isolation only — production
        never needs it, because a catalogue's entries die with the catalogue."""
        self._caches.clear()

    def live_catalogues(self) -> int:
        """How many catalogues currently hold a sub-cache. The finalizer's
        observable effect, and what the purge test asserts on."""
        return len(self._caches)
