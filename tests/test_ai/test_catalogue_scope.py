"""`CatalogueScope` — the one answer to "how does a cache key a `GameData`?".

The bug this module exists to make impossible: `id()` is unique only among LIVE
objects, so a cache that names a catalogue by a bare address and does nothing to
outlive-or-purge it serves the DEAD catalogue's answers to whatever gets
allocated at that address next. These tests assert the invariant directly and
then exhibit the collision, because an invariant assertion is deterministic and
a collision hunt is exactly as luck-dependent as the bug.
"""

import ast
import gc
import weakref
from pathlib import Path

from artifactsmmo_cli.ai import catalogue_scope
from artifactsmmo_cli.ai.catalogue_scope import CatalogueScope
from artifactsmmo_cli.ai.game_data import GameData


def test_each_catalogue_gets_its_own_sub_cache() -> None:
    """Two live catalogues never share an entry — the whole point of the scope."""
    scope: CatalogueScope[str, int] = CatalogueScope(max_entries=8)
    first, second = GameData(), GameData()

    scope.remember(scope.cache_for(first), "k", 1)
    scope.remember(scope.cache_for(second), "k", 2)

    assert scope.cache_for(first)["k"] == 1
    assert scope.cache_for(second)["k"] == 2
    assert scope.live_catalogues() == 2


def test_a_collected_catalogue_takes_its_sub_cache_with_it() -> None:
    """THE LOAD-BEARING INVARIANT. Delete the `weakref.finalize` line in
    `cache_for` and this fails: the sub-cache outlives its catalogue, so its
    `id()` key now names a free address."""
    scope: CatalogueScope[str, int] = CatalogueScope(max_entries=8)
    game_data = GameData()
    scope.remember(scope.cache_for(game_data), "k", 1)
    assert scope.live_catalogues() == 1

    ref = weakref.ref(game_data)
    del game_data
    gc.collect()

    assert ref() is None, "the scope pinned the catalogue — it must not"
    assert scope.live_catalogues() == 0, (
        "a freed catalogue left its sub-cache behind; the next GameData "
        "allocated at that address will read this one's answers")


def test_a_recycled_address_never_reads_the_previous_catalogues_answer() -> None:
    """THE BUG ITSELF, exhibited. CPython hands a freed address straight back:
    over 200,000 allocate/free rounds of a `GameData`-shaped object the address
    was recycled 199,983 times, and an unguarded `id()` cache served a stale
    entry on every single one.

    2,000 rounds is far more than enough to hit the collision — the failure this
    test reproduces (`weapon_winnability` returning 0 for a weapon that unlocks a
    monster) landed within one test FILE."""
    scope: CatalogueScope[str, int] = CatalogueScope(max_entries=8)

    for round_ in range(2000):
        game_data = GameData()
        cache = scope.cache_for(game_data)
        assert "k" not in cache, (
            f"round {round_}: a fresh catalogue was served a previous "
            f"catalogue's entry from the recycled address {id(game_data)}")
        scope.remember(cache, "k", round_)
        del game_data


def test_the_lru_bound_evicts_the_least_recently_used_entry() -> None:
    """Bounded per catalogue: an unbounded memo on a per-node key is a leak."""
    scope: CatalogueScope[str, int] = CatalogueScope(max_entries=2)
    game_data = GameData()
    cache = scope.cache_for(game_data)

    scope.remember(cache, "a", 1)
    scope.remember(cache, "b", 2)
    scope.remember(cache, "c", 3)

    assert list(cache) == ["b", "c"], "the oldest entry was not evicted"


def test_remember_hands_back_the_value_it_stored() -> None:
    """Callers `return scope.remember(...)`, so the return value is load-bearing."""
    scope: CatalogueScope[str, int] = CatalogueScope(max_entries=2)
    assert scope.remember(scope.cache_for(GameData()), "a", 7) == 7


def test_clear_drops_every_catalogues_sub_cache() -> None:
    """Test isolation only: production never needs it."""
    scope: CatalogueScope[str, int] = CatalogueScope(max_entries=2)
    held = GameData()
    scope.remember(scope.cache_for(held), "a", 1)

    scope.clear()

    assert scope.live_catalogues() == 0
    assert "a" not in scope.cache_for(held)


def test_no_other_module_keys_a_catalogue_by_a_bare_id() -> None:
    """THE CENSUS THAT CATCHES THE NEXT INSTANCE.

    This defect is invisible to every CI lane the project runs, because whether
    a fresh `GameData` lands on a freed predecessor's address is allocator luck:
    the `weapon_winnability` failure showed up at 97 % of a SERIAL run, vanished
    under xdist and run-alone, and could not be reproduced at all on 2026-08-25
    once the memory churn ahead of it changed. A lane that detects a bug only
    sometimes is not a gate.

    What IS deterministic is the source: an `id()` of a catalogue must appear in
    exactly one place, `catalogue_scope.cache_for`, where a `weakref.finalize`
    stands beside it. Parsed with `ast`, so the prose in these modules'
    docstrings — which deliberately quotes the old key while explaining the bug
    — can neither pass nor fail it.
    """
    scope_module = Path(catalogue_scope.__file__).resolve()
    src_root = scope_module.parents[2]
    catalogue_names = {"game_data", "gd", "gamedata", "catalog", "catalogue"}
    offenders: list[str] = []

    for path in sorted(src_root.rglob("*.py")):
        if path.resolve() == scope_module:
            continue
        for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id != "id" or len(node.args) != 1:
                continue
            arg = node.args[0]
            named = arg.id if isinstance(arg, ast.Name) else (
                arg.attr if isinstance(arg, ast.Attribute) else "")
            if named.lower() in catalogue_names:
                offenders.append(f"{path}:{node.lineno}: id({named})")

    assert offenders == [], (
        "a module names a GameData by a bare id(); an id() is unique only among "
        "LIVE objects, so the entry must be scoped by CatalogueScope (which "
        "registers the weakref.finalize that makes the address safe):\n  "
        + "\n  ".join(offenders))
