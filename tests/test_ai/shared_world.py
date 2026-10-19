"""One bundle `GameData` per test process, and one gear objective per
(scenario state, world) — the test harness's answer to ruling AD.

WHY. The gear objective is computed cold for every `GameData` object: the
per-catalogue memos it leans on (`ai/catalogue_scope.py`) are keyed on the
catalogue's identity, so a test that loads its own copy of the committed bundle
pays the whole fixed point again (measured: 53.5 s for 45 scenarios on a new
`GameData` against 17.5 s on a reused one). Production builds ONE `GameData`
per process and one objective per cycle; this module gives the offline sweeps
the same shape. Production code is untouched.

THE WORLD MEMO HOLDS ITS OBJECT (feedback_cache_key_must_pin_its_object): the
dict value IS the `GameData`, so its `id()` cannot be recycled while the entry
lives. A shared world is handed out with its per-cycle overlay cleared
(`active_event_codes` / `active_raid_codes`), exactly as a freshly loaded one
reads: `GamePlayer.seed_offline` writes the overlay from the state it seeds,
the way the live player does every cycle on its one `GameData`, so a test that
seeds an event cannot leak it into the next test that does not.

ONLY FOR TESTS THAT DO NOT MUTATE THE CATALOGUE. A test that assigns to a
`GameData` attribute (other than the overlay above) or monkeypatches one must
load its own instance with `load_bundle_game_data`. Each hand-out checks it:
the catalogue's dicts, sets and lists are fingerprinted `{attr: (id, len)}` on
first load and must read the same at every later hand-out (a rebind changes the
id, an in-place add or delete changes the len), so a mutating test fails loudly
in whichever test next asks for the world instead of leaking into it. Exempt:
the lazy memos (`cached_property` boxes, `LocationCatalog._region_cache`), which
fill in as the world is read, and the two overlay fields cleared at hand-out.

THE OBJECTIVE MEMO compares the full input, not a name: an entry is reused only
for the same world object, an EQUAL state, an EQUAL context and the same
overlay, and only without a learning store (history changes the rates)."""

from functools import cached_property
from pathlib import Path

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_objective_context import attach_gear_objective
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.scenario import load_bundle_game_data
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.world_state import WorldState

_WORLDS: dict[tuple[Path, bool, frozenset[str]], GameData] = {}

_FINGERPRINTS: dict[tuple[Path, bool, frozenset[str]], dict[str, tuple[int, int]]] = {}

_CATALOGUES = ("items", "monsters", "recipes_catalog", "world")

_OVERLAY = frozenset({"world.active_event_codes", "world.active_raid_codes"})

_LAZY_MEMOS = frozenset({"world._region_cache"})


def _lazy(owner: object, name: str) -> bool:
    """A `cached_property` box: absent until first read, then filled by its
    readers (e.g. `GameData.reserved_targets_memo`)."""
    return isinstance(getattr(type(owner), name, None), cached_property)


def fingerprint(world: GameData) -> dict[str, tuple[int, int]]:
    """`{attr: (id, len)}` over the world's and its catalogues' dicts, sets and
    lists, minus the lazy memos and the overlay fields."""
    owners: list[tuple[str, object]] = [("", world)]
    owners += [(f"{name}.", getattr(world, name)) for name in _CATALOGUES]
    out: dict[str, tuple[int, int]] = {}
    for prefix, owner in owners:
        for name, value in vars(owner).items():
            attr = prefix + name
            if (isinstance(value, (dict, set, list)) and attr not in _OVERLAY
                    and attr not in _LAZY_MEMOS and not _lazy(owner, name)):
                out[attr] = (id(value), len(value))
    return out

_ATTACHED: dict[tuple[str, int], list[tuple[GameData, WorldState, SelectionContext,
                                            frozenset[str], frozenset[str],
                                            SelectionContext]]] = {}


def shared_world(path: Path, *, with_ge_orders: bool = False,
                 completed_achievements: frozenset[str] = frozenset()) -> GameData:
    """The committed bundle's `GameData` for this (market, achievements)
    declaration, loaded once per process, its event and raid overlay cleared.
    Same signature as `load_bundle_game_data`, so it can stand in for it."""
    key = (path.resolve(), with_ge_orders, frozenset(completed_achievements))
    world = _WORLDS.get(key)
    if world is None:
        world = load_bundle_game_data(path, with_ge_orders=with_ge_orders,
                                      completed_achievements=completed_achievements)
        _WORLDS[key] = world
        _FINGERPRINTS[key] = fingerprint(world)
    now = fingerprint(world)
    changed = sorted(attr for attr in _FINGERPRINTS[key].keys() | now.keys()
                     if _FINGERPRINTS[key].get(attr) != now.get(attr))
    if changed:
        raise AssertionError(
            f"a test mutated the shared world (changed: {changed}); a test that "
            "mutates the catalogue must load its own with load_bundle_game_data")
    world.active_event_codes = set()
    world.active_raid_codes = set()
    return world


def attached(state: WorldState, game_data: GameData, ctx: SelectionContext,
             history: LearningStore | None) -> SelectionContext:
    """`attach_gear_objective`, memoized on its whole input for store-less
    calls. Same signature, so it can stand in for it.

    The key ignores the clock: `gear_objective` reads `datetime.now`
    (`gear_objective.py:240`) and a reused entry keeps the first call's
    instant, which is harmless within one test process."""
    if history is not None:
        return attach_gear_objective(state, game_data, ctx, history)
    events = frozenset(game_data.active_event_codes)
    raids = frozenset(game_data.active_raid_codes)
    entries = _ATTACHED.setdefault((state.character, id(game_data)), [])
    for world, seen_state, seen_ctx, seen_events, seen_raids, result in entries:
        if (world is game_data and seen_state == state and seen_ctx == ctx
                and seen_events == events and seen_raids == raids):
            return result
    result = attach_gear_objective(state, game_data, ctx, None)
    entries.append((game_data, state, ctx, events, raids, result))
    return result
