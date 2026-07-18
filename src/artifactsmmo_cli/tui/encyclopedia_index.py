"""Pure enumeration of browseable game-data entities for the encyclopaedia.

No Textual import — logic only, unit-tested in isolation. Every category is a
plain projection over the static `GameData` catalogs; nothing is fabricated.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from artifactsmmo_cli.ai.game_data import GameData

CATEGORY_ORDER: tuple[str, ...] = (
    "item",
    "monster",
    "resource",
    "recipe",
    "npc",
    "location",
    "task",
)


@dataclass(frozen=True)
class IndexEntry:
    """One browseable row: an entity of a given kind."""

    kind: str
    code: str
    display: str
    search_text: str  # lowercased haystack (code + display + subtype/type)


@dataclass(frozen=True)
class EncyclopediaIndex:
    """Immutable per-category catalog projection built once when the modal opens."""

    _by_category: dict[str, tuple[IndexEntry, ...]]
    _lookup: dict[tuple[str, str], IndexEntry]

    def categories(self) -> list[tuple[str, int]]:
        return [(k, len(self._by_category.get(k, ()))) for k in CATEGORY_ORDER]

    def entries(self, kind: str) -> tuple[IndexEntry, ...]:
        return self._by_category.get(kind, ())

    def lookup(self, kind: str, code: str) -> IndexEntry | None:
        return self._lookup.get((kind, code))


def _entry(kind: str, code: str, extra: str = "") -> IndexEntry:
    haystack = f"{code} {extra}".strip().lower()
    return IndexEntry(kind=kind, code=code, display=code, search_text=haystack)


def build_index(game_data: GameData) -> EncyclopediaIndex:
    by_category: dict[str, tuple[IndexEntry, ...]] = {}

    items = [
        _entry("item", code, f"{s.type_} {s.subtype}")
        for code, s in game_data.items.stats.items()
    ]
    by_category["item"] = tuple(sorted(items, key=lambda e: e.code))

    monsters = [_entry("monster", code) for code in game_data.monsters.levels]
    by_category["monster"] = tuple(sorted(monsters, key=lambda e: e.code))

    resources = [_entry("resource", code) for code in game_data.recipes_catalog.resource_skill]
    by_category["resource"] = tuple(sorted(resources, key=lambda e: e.code))

    recipes = [_entry("recipe", code) for code in game_data.recipes_catalog.crafting_recipes]
    by_category["recipe"] = tuple(sorted(recipes, key=lambda e: e.code))

    npcs = [_entry("npc", code) for code in game_data.world.npc_tiles]
    by_category["npc"] = tuple(sorted(npcs, key=lambda e: e.code))

    locations = [
        _entry("location", f"workshop:{skill}", "workshop")
        for skill in game_data.world.workshop_locations
    ]
    locations += [_entry("location", f"raid:{code}", "raid") for code in game_data.world.raid_locations]
    by_category["location"] = tuple(sorted(locations, key=lambda e: e.code))

    tasks = [_entry("task", code) for code in game_data.task_codes]
    by_category["task"] = tuple(sorted(tasks, key=lambda e: e.code))

    lookup = {(e.kind, e.code): e for group in by_category.values() for e in group}
    return EncyclopediaIndex(_by_category=by_category, _lookup=lookup)


def rank_entries(entries: Sequence[IndexEntry], query: str) -> list[IndexEntry]:
    q = query.strip().lower()
    if not q:
        return list(entries)
    prefix: list[IndexEntry] = []
    contains: list[IndexEntry] = []
    for e in entries:
        if e.search_text.startswith(q) or e.code.lower().startswith(q):
            prefix.append(e)
        elif q in e.search_text:
            contains.append(e)
    return prefix + contains
