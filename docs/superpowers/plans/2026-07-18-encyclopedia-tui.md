# Encyclopaedia TUI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a browseable, searchable game-data encyclopaedia as a pushed modal in the watch-mode TUI.

**Architecture:** Two pure modules (`encyclopedia_index`, `encyclopedia_detail`) hold all logic — enumerating catalog entities and rendering per-entity detail with navigable cross-links — and are unit-tested to 100% without importing Textual. A thin `EncyclopediaScreen` wires three panes + a search box + a nav-stack to those pure modules, mirroring the existing `build_character_detail` / `CharacterScreen` split.

**Tech Stack:** Python 3.13, `uv`, Textual, Rich, pytest.

## Global Constraints

- All Python commands prefixed with `uv run` (e.g. `uv run pytest`).
- Imports at top of file only. No inline imports. No `...` (triple-dot) imports — absolute imports only.
- No `if TYPE_CHECKING`.
- Never `catch Exception`. No multi-level error handling.
- One behavioral class per file. Pure value objects (dataclasses) may share a module with the pure functions that produce them.
- Use only game-API data or fail with an error — never fabricate or default-fill missing catalog data.
- Tests: 0 errors, 0 warnings, 0 skipped, 100% coverage. All tests in `tests/`.
- Follow the existing TUI modal pattern: `Screen[None]` subclass with `DEFAULT_CSS` + `BINDINGS`, pushed/popped via `WatchApp._open_modal`.

## Categories (final)

`item`, `monster`, `resource`, `recipe`, `npc`, `location`, `task`. Fixed display order. NPC data confirmed present (`LocationCatalog.npc_tiles` / `npc_stock` / `npc_sell_prices`).

## File Structure

- Create `src/artifactsmmo_cli/tui/encyclopedia_index.py` — `IndexEntry`, `EncyclopediaIndex` value objects; `build_index(game_data)`; `rank_entries(entries, query)`. Pure.
- Create `src/artifactsmmo_cli/tui/encyclopedia_detail.py` — `Ref`, `DetailView` value objects; `build_detail(game_data, kind, code)`. Pure.
- Create `src/artifactsmmo_cli/tui/screens/encyclopedia_screen.py` — `EncyclopediaScreen(Screen[None])`. Behavioral shell.
- Modify `src/artifactsmmo_cli/tui/app.py` — import + `e` binding + `action_toggle_encyclopedia` + `_open_modal` wiring.
- Create tests: `tests/tui/test_encyclopedia_index.py`, `tests/tui/test_encyclopedia_detail.py`, `tests/tui/test_encyclopedia_screen.py`, and a case in the app test for the binding.

---

### Task 1: Pure index module

**Files:**
- Create: `src/artifactsmmo_cli/tui/encyclopedia_index.py`
- Test: `tests/tui/test_encyclopedia_index.py`

**Interfaces:**
- Consumes: `artifactsmmo_cli.ai.game_data.GameData`, `artifactsmmo_cli.ai.item_catalog.ItemStats`.
- Produces:
  - `IndexEntry` — frozen dataclass `(kind: str, code: str, display: str, search_text: str)`.
  - `EncyclopediaIndex` — frozen dataclass with methods `categories() -> list[tuple[str, int]]` (fixed order, with counts), `entries(kind: str) -> tuple[IndexEntry, ...]`, `lookup(kind: str, code: str) -> IndexEntry | None`.
  - `build_index(game_data: GameData) -> EncyclopediaIndex`.
  - `rank_entries(entries: Sequence[IndexEntry], query: str) -> list[IndexEntry]`.
  - Module constant `CATEGORY_ORDER: tuple[str, ...] = ("item", "monster", "resource", "recipe", "npc", "location", "task")`.

- [ ] **Step 1: Write the failing test**

Create `tests/tui/test_encyclopedia_index.py`:

```python
"""Unit tests for the pure encyclopaedia index."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.item_catalog import ItemStats
from artifactsmmo_cli.tui.encyclopedia_index import (
    CATEGORY_ORDER,
    EncyclopediaIndex,
    IndexEntry,
    build_index,
    rank_entries,
)


def _seed() -> GameData:
    gd = GameData()
    gd.items.stats["copper_dagger"] = ItemStats(
        code="copper_dagger", level=1, type_="weapon", subtype="dagger"
    )
    gd.items.stats["copper_ore"] = ItemStats(code="copper_ore", level=1, type_="resource")
    gd.monsters.levels["chicken"] = 1
    gd.monsters.hp["chicken"] = 60
    gd.recipes_catalog.resource_skill["copper_rocks"] = ("mining", 1)
    gd.recipes_catalog.crafting_recipes["copper_dagger"] = {"copper": 6}
    gd.recipes_catalog.craft_yields["copper_dagger"] = 1
    gd.world.npc_tiles["ge_trader"] = (5, 1)
    gd.world.workshop_locations["mining"] = (1, 2)
    gd._task_coin_rewards["kill_chickens"] = 25
    return gd


def test_categories_fixed_order_with_counts() -> None:
    idx = build_index(_seed())
    cats = idx.categories()
    assert [c for c, _ in cats] == list(CATEGORY_ORDER)
    counts = dict(cats)
    assert counts["item"] == 2
    assert counts["monster"] == 1
    assert counts["resource"] == 1
    assert counts["recipe"] == 1
    assert counts["npc"] == 1
    assert counts["location"] == 1  # mining workshop
    assert counts["task"] == 1


def test_entries_sorted_by_code() -> None:
    idx = build_index(_seed())
    items = idx.entries("item")
    assert [e.code for e in items] == ["copper_dagger", "copper_ore"]
    assert all(isinstance(e, IndexEntry) for e in items)


def test_lookup_hit_and_miss() -> None:
    idx = build_index(_seed())
    assert idx.lookup("item", "copper_dagger").kind == "item"
    assert idx.lookup("item", "no_such") is None
    assert idx.lookup("monster", "chicken").code == "chicken"


def test_rank_prefix_before_contains_case_insensitive() -> None:
    idx = build_index(_seed())
    ranked = rank_entries(idx.entries("item"), "COPPER_O")
    assert [e.code for e in ranked] == ["copper_ore"]
    ranked2 = rank_entries(idx.entries("item"), "dagger")  # contains-only match
    assert [e.code for e in ranked2] == ["copper_dagger"]


def test_rank_empty_query_returns_all_in_order() -> None:
    idx = build_index(_seed())
    ranked = rank_entries(idx.entries("item"), "   ")
    assert [e.code for e in ranked] == ["copper_dagger", "copper_ore"]


def test_search_text_covers_subtype() -> None:
    idx = build_index(_seed())
    ranked = rank_entries(idx.entries("item"), "dagger")
    assert ranked and ranked[0].code == "copper_dagger"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tui/test_encyclopedia_index.py -q`
Expected: FAIL — `ModuleNotFoundError: ...encyclopedia_index`.

- [ ] **Step 3: Write minimal implementation**

Create `src/artifactsmmo_cli/tui/encyclopedia_index.py`:

```python
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

    task_codes = set(game_data._task_coin_rewards) | set(game_data._task_gold_rewards)
    tasks = [_entry("task", code) for code in task_codes]
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
```

Note: `game_data._task_coin_rewards` / `_task_gold_rewards` are the existing dataclass fields (keyed by task code). Reading them here is the same access pattern the AI layer uses.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/tui/test_encyclopedia_index.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/tui/encyclopedia_index.py tests/tui/test_encyclopedia_index.py
git commit -m "feat(tui): pure encyclopaedia index over game-data catalogs"
```

---

### Task 2: Detail module — framework + item branch

**Files:**
- Create: `src/artifactsmmo_cli/tui/encyclopedia_detail.py`
- Test: `tests/tui/test_encyclopedia_detail.py`

**Interfaces:**
- Consumes: `GameData`, `EncyclopediaIndex` / `build_index` (for the soundness test), `rich.console.RenderableType`, `rich.table.Table`.
- Produces:
  - `Ref` — frozen dataclass `(kind: str, code: str, label: str)`.
  - `DetailView` — frozen dataclass `(renderable: RenderableType, links: tuple[Ref, ...])`.
  - `build_detail(game_data: GameData, kind: str, code: str) -> DetailView`.
  - `EncyclopediaDetailError(Exception)` raised for an unknown `kind`.

- [ ] **Step 1: Write the failing test**

Create `tests/tui/test_encyclopedia_detail.py`:

```python
"""Unit tests for pure encyclopaedia detail rendering + link soundness."""

import pytest
from rich.console import Console

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.item_catalog import ItemStats
from artifactsmmo_cli.tui.encyclopedia_detail import (
    EncyclopediaDetailError,
    Ref,
    build_detail,
)
from artifactsmmo_cli.tui.encyclopedia_index import build_index


def _seed() -> GameData:
    gd = GameData()
    gd.items.stats["copper_dagger"] = ItemStats(
        code="copper_dagger",
        level=1,
        type_="weapon",
        subtype="dagger",
        crafting_skill="weaponcrafting",
        crafting_level=1,
        attack={"fire": 6},
    )
    gd.items.stats["copper"] = ItemStats(code="copper", level=1, type_="resource")
    gd.recipes_catalog.crafting_recipes["copper_dagger"] = {"copper": 6}
    gd.recipes_catalog.craft_yields["copper_dagger"] = 1
    return gd


def _render(view) -> str:
    console = Console(width=80, record=True)
    console.print(view.renderable)
    return console.export_text()


def test_item_detail_shows_stats_and_links_to_recipe() -> None:
    view = build_detail(_seed(), "item", "copper_dagger")
    text = _render(view)
    assert "copper_dagger" in text
    assert "weapon" in text
    assert "fire" in text
    # craftable -> link to its recipe; input 'copper' surfaced via the recipe branch
    assert Ref("recipe", "copper_dagger", "recipe") in view.links


def test_item_used_in_links_back() -> None:
    view = build_detail(_seed(), "item", "copper")
    # 'copper' is an input of copper_dagger's recipe -> used-in link
    assert Ref("recipe", "copper_dagger", "used in") in view.links


def test_unknown_kind_raises() -> None:
    with pytest.raises(EncyclopediaDetailError):
        build_detail(_seed(), "spaceship", "x")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tui/test_encyclopedia_detail.py -q`
Expected: FAIL — `ModuleNotFoundError: ...encyclopedia_detail`.

- [ ] **Step 3: Write minimal implementation**

Create `src/artifactsmmo_cli/tui/encyclopedia_detail.py`:

```python
"""Pure per-entity detail views for the encyclopaedia, with navigable links.

Each `build_detail` branch reads only static `GameData` catalogs and returns a
Rich renderable plus the cross-reference `Ref`s the shell turns into a
navigable list. No Textual import; no fabricated data.
"""

from dataclasses import dataclass

from rich.console import RenderableType
from rich.table import Table

from artifactsmmo_cli.ai.game_data import GameData


class EncyclopediaDetailError(Exception):
    """Raised when asked to render a detail for an unknown category kind."""


@dataclass(frozen=True)
class Ref:
    """A navigable cross-reference to another encyclopaedia entity."""

    kind: str
    code: str
    label: str


@dataclass(frozen=True)
class DetailView:
    """A rendered detail plus its outbound navigable links."""

    renderable: RenderableType
    links: tuple[Ref, ...]


def _kv_table(title: str) -> Table:
    t = Table(box=None, padding=(0, 2), show_header=False, title=title)
    t.add_column("k", style="dim")
    t.add_column("v")
    return t


def _item_detail(game_data: GameData, code: str) -> DetailView:
    stats = game_data.items.stats.get(code)
    if stats is None:
        raise EncyclopediaDetailError(f"unknown item: {code}")
    t = _kv_table(code)
    t.add_row("level", str(stats.level))
    t.add_row("type", f"{stats.type_} / {stats.subtype}" if stats.subtype else stats.type_)
    if stats.attack:
        t.add_row("attack", ", ".join(f"{el} {v}" for el, v in sorted(stats.attack.items())))
    if stats.resistance:
        t.add_row("resist", ", ".join(f"{el} {v}" for el, v in sorted(stats.resistance.items())))
    if stats.hp_restore:
        t.add_row("heals", str(stats.hp_restore))
    if stats.hp_bonus:
        t.add_row("hp", f"+{stats.hp_bonus}")

    links: list[Ref] = []
    if code in game_data.recipes_catalog.crafting_recipes:
        links.append(Ref("recipe", code, "recipe"))
    for out, inputs in sorted(game_data.recipes_catalog.crafting_recipes.items()):
        if code in inputs:
            links.append(Ref("recipe", out, "used in"))
    return DetailView(renderable=t, links=tuple(links))


def build_detail(game_data: GameData, kind: str, code: str) -> DetailView:
    if kind == "item":
        return _item_detail(game_data, code)
    raise EncyclopediaDetailError(f"unknown kind: {kind}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/tui/test_encyclopedia_detail.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/tui/encyclopedia_detail.py tests/tui/test_encyclopedia_detail.py
git commit -m "feat(tui): encyclopaedia detail framework + item branch"
```

---

### Task 3: Detail branches — monster + resource + recipe

**Files:**
- Modify: `src/artifactsmmo_cli/tui/encyclopedia_detail.py`
- Modify: `tests/tui/test_encyclopedia_detail.py`

**Interfaces:**
- Consumes: `MonsterCatalog.drops` (`dict[code, list[(item, rate, min, max)]]`), `MonsterCatalog.levels/hp/attack/resistance/critical_strike/lifesteal`, `RecipeCatalog.resource_skill` / `resource_drops_full` / `resource_locations(code)` / `crafting_recipes` / `craft_yields`, `ItemStats.crafting_skill/crafting_level`.
- Produces: extends `build_detail` to handle `"monster"`, `"resource"`, `"recipe"`.

- [ ] **Step 1: Write the failing test**

Append to `tests/tui/test_encyclopedia_detail.py`:

```python
def _seed_world() -> GameData:
    gd = _seed()
    gd.monsters.levels["chicken"] = 1
    gd.monsters.hp["chicken"] = 60
    gd.monsters.attack["chicken"] = {"fire": 4}
    gd.monsters.resistance["chicken"] = {"water": 2}
    gd.monsters.critical_strike["chicken"] = 5
    gd.monsters.lifesteal["chicken"] = 0
    gd.monsters.drops["chicken"] = [("copper", 100, 1, 1)]
    gd.recipes_catalog.resource_skill["copper_rocks"] = ("mining", 1)
    gd.recipes_catalog.resource_drops_full["copper_rocks"] = [("copper", 80, 1, 1)]
    gd.recipes_catalog.locations["copper_rocks"] = [(2, 0)]
    return gd


def test_monster_detail_links_to_drops() -> None:
    view = build_detail(_seed_world(), "monster", "chicken")
    text = _render(view)
    assert "chicken" in text
    assert "60" in text  # hp
    assert Ref("item", "copper", "drops") in view.links


def test_resource_detail_links_to_drops() -> None:
    view = build_detail(_seed_world(), "resource", "copper_rocks")
    text = _render(view)
    assert "mining" in text
    assert Ref("item", "copper", "drops") in view.links


def test_recipe_detail_links_inputs_and_output() -> None:
    view = build_detail(_seed_world(), "recipe", "copper_dagger")
    text = _render(view)
    assert "weaponcrafting" in text
    assert Ref("item", "copper_dagger", "makes") in view.links
    assert Ref("item", "copper", "needs 6") in view.links
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tui/test_encyclopedia_detail.py -q`
Expected: FAIL — `EncyclopediaDetailError: unknown kind: monster`.

- [ ] **Step 3: Write minimal implementation**

Add these branch functions to `encyclopedia_detail.py` (above `build_detail`):

```python
def _monster_detail(game_data: GameData, code: str) -> DetailView:
    m = game_data.monsters
    if code not in m.levels:
        raise EncyclopediaDetailError(f"unknown monster: {code}")
    t = _kv_table(code)
    t.add_row("level", str(m.levels[code]))
    t.add_row("hp", str(m.hp.get(code, 0)))
    if m.attack.get(code):
        t.add_row("attack", ", ".join(f"{el} {v}" for el, v in sorted(m.attack[code].items())))
    if m.resistance.get(code):
        t.add_row("resist", ", ".join(f"{el} {v}" for el, v in sorted(m.resistance[code].items())))
    if m.critical_strike.get(code):
        t.add_row("crit", f"{m.critical_strike[code]}%")
    if m.lifesteal.get(code):
        t.add_row("lifesteal", f"{m.lifesteal[code]}%")
    locs = m.locations.get(code, [])
    if locs:
        t.add_row("locations", ", ".join(f"({x},{y})" for x, y in locs))
    links = tuple(
        Ref("item", item, "drops")
        for item, _rate, _lo, _hi in m.drops.get(code, [])
    )
    return DetailView(renderable=t, links=links)


def _resource_detail(game_data: GameData, code: str) -> DetailView:
    rc = game_data.recipes_catalog
    skill = rc.resource_skill.get(code)
    if skill is None:
        raise EncyclopediaDetailError(f"unknown resource: {code}")
    t = _kv_table(code)
    t.add_row("skill", f"{skill[0]} L{skill[1]}")
    locs = rc.resource_locations(code)
    if locs:
        t.add_row("locations", ", ".join(f"({x},{y})" for x, y in locs))
    links = tuple(
        Ref("item", item, "drops")
        for item, _rate, _lo, _hi in rc.resource_drops_full.get(code, [])
    )
    return DetailView(renderable=t, links=links)


def _recipe_detail(game_data: GameData, code: str) -> DetailView:
    rc = game_data.recipes_catalog
    inputs = rc.crafting_recipes.get(code)
    if inputs is None:
        raise EncyclopediaDetailError(f"unknown recipe: {code}")
    stats = game_data.items.stats.get(code)
    t = _kv_table(code)
    if stats is not None and stats.crafting_skill:
        t.add_row("skill", f"{stats.crafting_skill} L{stats.crafting_level}")
    t.add_row("yields", str(rc.craft_yields.get(code, 1)))
    for item, qty in sorted(inputs.items()):
        t.add_row("needs", f"{qty} {item}")
    links = [Ref("item", code, "makes")]
    links += [Ref("item", item, f"needs {qty}") for item, qty in sorted(inputs.items())]
    return DetailView(renderable=t, links=tuple(links))
```

Extend `build_detail`:

```python
def build_detail(game_data: GameData, kind: str, code: str) -> DetailView:
    if kind == "item":
        return _item_detail(game_data, code)
    if kind == "monster":
        return _monster_detail(game_data, code)
    if kind == "resource":
        return _resource_detail(game_data, code)
    if kind == "recipe":
        return _recipe_detail(game_data, code)
    raise EncyclopediaDetailError(f"unknown kind: {kind}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/tui/test_encyclopedia_detail.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/tui/encyclopedia_detail.py tests/tui/test_encyclopedia_detail.py
git commit -m "feat(tui): encyclopaedia detail branches for monster/resource/recipe"
```

---

### Task 4: Detail branches — npc + location + task + link soundness

**Files:**
- Modify: `src/artifactsmmo_cli/tui/encyclopedia_detail.py`
- Modify: `tests/tui/test_encyclopedia_detail.py`

**Interfaces:**
- Consumes: `LocationCatalog.npc_tiles` / `npc_stock` / `npc_sell_prices` / `workshop_locations` / `raid_locations` / `raid_location_tiles(code)`, `GameData._task_coin_rewards` / `_task_gold_rewards`.
- Produces: extends `build_detail` for `"npc"`, `"location"`, `"task"`; a parametrized soundness test proving every `Ref` resolves against `build_index`.

- [ ] **Step 1: Write the failing test**

Append to `tests/tui/test_encyclopedia_detail.py`:

```python
def _seed_full() -> GameData:
    gd = _seed_world()
    gd.world.npc_tiles["smith"] = (4, 1)
    gd.world.npc_stock["smith"] = {"copper_dagger": 50}
    gd.world.npc_sell_prices["smith"] = {"copper": 2}
    gd.world.workshop_locations["mining"] = (1, 2)
    gd.world.raid_locations["dragon_raid"] = [(9, 9)]
    gd._task_coin_rewards["kill_chickens"] = 25
    gd._task_gold_rewards["kill_chickens"] = 100
    return gd


def test_npc_detail_links_stock_and_sells() -> None:
    view = build_detail(_seed_full(), "npc", "smith")
    text = _render(view)
    assert "(4,1)" in text
    assert Ref("item", "copper_dagger", "buy 50") in view.links
    assert Ref("item", "copper", "sell 2") in view.links


def test_location_workshop_detail() -> None:
    view = build_detail(_seed_full(), "location", "workshop:mining")
    text = _render(view)
    assert "(1,2)" in text


def test_location_raid_detail() -> None:
    view = build_detail(_seed_full(), "location", "raid:dragon_raid")
    text = _render(view)
    assert "(9,9)" in text


def test_task_detail_shows_rewards() -> None:
    view = build_detail(_seed_full(), "task", "kill_chickens")
    text = _render(view)
    assert "25" in text
    assert "100" in text
    assert view.links == ()  # per-task item rewards are not in the catalog


def test_every_link_resolves_no_dangling() -> None:
    gd = _seed_full()
    idx = build_index(gd)
    for kind, _count in idx.categories():
        for entry in idx.entries(kind):
            view = build_detail(gd, kind, entry.code)
            for ref in view.links:
                assert idx.lookup(ref.kind, ref.code) is not None, (
                    f"dangling link {ref} from {kind}:{entry.code}"
                )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tui/test_encyclopedia_detail.py -q`
Expected: FAIL — `EncyclopediaDetailError: unknown kind: npc`.

- [ ] **Step 3: Write minimal implementation**

Add branch functions to `encyclopedia_detail.py`:

```python
def _npc_detail(game_data: GameData, code: str) -> DetailView:
    w = game_data.world
    tile = w.npc_tiles.get(code)
    if tile is None:
        raise EncyclopediaDetailError(f"unknown npc: {code}")
    t = _kv_table(code)
    t.add_row("location", f"({tile[0]},{tile[1]})")
    links: list[Ref] = []
    for item, price in sorted(w.npc_stock.get(code, {}).items()):
        t.add_row("sells", f"{item} @ {price}")
        links.append(Ref("item", item, f"buy {price}"))
    for item, price in sorted(w.npc_sell_prices.get(code, {}).items()):
        t.add_row("buys", f"{item} @ {price}")
        links.append(Ref("item", item, f"sell {price}"))
    return DetailView(renderable=t, links=tuple(links))


def _location_detail(game_data: GameData, code: str) -> DetailView:
    w = game_data.world
    t = _kv_table(code)
    kind, _, name = code.partition(":")
    if kind == "workshop":
        tile = w.workshop_locations.get(name)
        if tile is None:
            raise EncyclopediaDetailError(f"unknown workshop: {name}")
        t.add_row("workshop", name)
        t.add_row("location", f"({tile[0]},{tile[1]})")
    elif kind == "raid":
        tiles = w.raid_location_tiles(name)
        if not tiles:
            raise EncyclopediaDetailError(f"unknown raid: {name}")
        t.add_row("raid", name)
        t.add_row("tiles", ", ".join(f"({x},{y})" for x, y in tiles))
    else:
        raise EncyclopediaDetailError(f"unknown location: {code}")
    return DetailView(renderable=t, links=())


def _task_detail(game_data: GameData, code: str) -> DetailView:
    coin = game_data._task_coin_rewards.get(code)
    gold = game_data._task_gold_rewards.get(code)
    if coin is None and gold is None:
        raise EncyclopediaDetailError(f"unknown task: {code}")
    t = _kv_table(code)
    if coin is not None:
        t.add_row("task coins", str(coin))
    if gold is not None:
        t.add_row("gold", str(gold))
    return DetailView(renderable=t, links=())
```

Extend `build_detail` with the three new kinds:

```python
    if kind == "npc":
        return _npc_detail(game_data, code)
    if kind == "location":
        return _location_detail(game_data, code)
    if kind == "task":
        return _task_detail(game_data, code)
```

(Insert before the final `raise EncyclopediaDetailError(f"unknown kind: {kind}")`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/tui/test_encyclopedia_detail.py -q`
Expected: PASS (11 passed).

Also confirm full coverage of both pure modules:

Run: `uv run pytest tests/tui/test_encyclopedia_detail.py tests/tui/test_encyclopedia_index.py --cov=src/artifactsmmo_cli/tui/encyclopedia_index --cov=src/artifactsmmo_cli/tui/encyclopedia_detail --cov-report=term-missing -q`
Expected: 100% for both modules. If any line is uncovered, add a targeted test before committing.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/tui/encyclopedia_detail.py tests/tui/test_encyclopedia_detail.py
git commit -m "feat(tui): encyclopaedia npc/location/task branches + link soundness test"
```

---

### Task 5: EncyclopediaScreen shell

**Files:**
- Create: `src/artifactsmmo_cli/tui/screens/encyclopedia_screen.py`
- Test: `tests/tui/test_encyclopedia_screen.py`

**Interfaces:**
- Consumes: `build_index`, `rank_entries`, `EncyclopediaIndex`, `IndexEntry`, `build_detail`, `Ref`, `DetailView`, `GameData`. Textual: `Screen`, `ListView`, `ListItem`, `Label`, `Input`, `Static`, `Horizontal`, `Vertical`, `VerticalScroll`.
- Produces: `EncyclopediaScreen(Screen[None])` with `__init__(self, game_data: GameData)`; pushed by `WatchApp`.

Design notes for the implementer:
- Three columns in a `Horizontal`: category `ListView` (`#enc-cats`), a `Vertical` holding the search `Input` (`#enc-search`) + entity `ListView` (`#enc-entities`), and a `Vertical` holding a detail `Static` (`#enc-detail`) + a links `ListView` (`#enc-links`).
- State: `self._index`, `self._active_kind: str`, `self._nav: list[Ref]`.
- `on_mount`: build index, fill categories, select the first category, render its entities with an empty query.
- Category highlighted → set `_active_kind`, clear the search box, clear `_nav`, refill entities.
- Search `Input.Changed` → refill entities via `rank_entries(self._index.entries(self._active_kind), value)`.
- Entity `ListView.Selected` → `self._navigate(Ref(kind, code, "")) ` pushing onto `_nav`.
- Links `ListView.Selected` → `self._navigate(ref)` for the selected `Ref`.
- `_navigate(ref)` appends to `_nav` and calls `_render_detail(ref)`; `_render_detail` calls `build_detail`, updates the `Static`, and repopulates `#enc-links` (each `ListItem` carries its `Ref`).
- `action_back` (Backspace): pop `_nav`; render the new top, or clear the detail if empty.
- `BINDINGS = [("escape", "dismiss", "Back"), ("e", "dismiss", "Back"), ("backspace", "back", "Back")]`.
- Store the entity `code`/`kind` and link `Ref` on each `ListItem` as attributes so the `Selected` handler recovers them without parsing labels (never use label text as a key — matches "no alphabetical/string tiebreak" and "use only API data").
- `id="encyclopedia-modal"` so the App CSS resets it to vertical layout like the other modals (`app.py` resets `#character-modal, #log-modal, #plan-modal`; add `#encyclopedia-modal` to that selector in Task 6).

- [ ] **Step 1: Write the failing test**

Create `tests/tui/test_encyclopedia_screen.py`:

```python
"""Pilot tests for the encyclopaedia modal shell."""

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Input, ListView

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.item_catalog import ItemStats
from artifactsmmo_cli.tui.encyclopedia_detail import Ref
from artifactsmmo_cli.tui.screens.encyclopedia_screen import EncyclopediaScreen


def _seed() -> GameData:
    gd = GameData()
    gd.items.stats["copper_dagger"] = ItemStats(
        code="copper_dagger", level=1, type_="weapon", subtype="dagger"
    )
    gd.items.stats["copper"] = ItemStats(code="copper", level=1, type_="resource")
    gd.recipes_catalog.crafting_recipes["copper_dagger"] = {"copper": 6}
    gd.recipes_catalog.craft_yields["copper_dagger"] = 1
    return gd


class _Host(App[None]):
    def __init__(self, gd: GameData) -> None:
        super().__init__()
        self._gd = gd

    def compose(self) -> ComposeResult:  # pragma: no cover - Textual harness
        yield from ()

    async def on_mount(self) -> None:
        await self.push_screen(EncyclopediaScreen(self._gd))


@pytest.mark.asyncio
async def test_search_filters_entities() -> None:
    app = _Host(_seed())
    async with app.run_test() as pilot:
        screen = app.screen
        screen.query_one("#enc-search", Input).value = "dagger"
        await pilot.pause()
        entities = screen.query_one("#enc-entities", ListView)
        codes = [item.enc_code for item in entities.children]
        assert codes == ["copper_dagger"]


@pytest.mark.asyncio
async def test_follow_link_pushes_nav() -> None:
    app = _Host(_seed())
    async with app.run_test() as pilot:
        screen = app.screen
        screen._navigate(Ref("item", "copper_dagger", ""))
        await pilot.pause()
        assert screen._nav[-1] == Ref("item", "copper_dagger", "")
        # detail lists a 'recipe' link for the craftable dagger
        links = screen.query_one("#enc-links", ListView)
        refs = [item.enc_ref for item in links.children]
        assert Ref("recipe", "copper_dagger", "recipe") in refs


@pytest.mark.asyncio
async def test_back_pops_nav() -> None:
    app = _Host(_seed())
    async with app.run_test() as pilot:
        screen = app.screen
        screen._navigate(Ref("item", "copper", ""))
        screen._navigate(Ref("item", "copper_dagger", ""))
        await pilot.pause()
        screen.action_back()
        await pilot.pause()
        assert screen._nav[-1] == Ref("item", "copper", "")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tui/test_encyclopedia_screen.py -q`
Expected: FAIL — `ModuleNotFoundError: ...encyclopedia_screen`.

- [ ] **Step 3: Write minimal implementation**

Create `src/artifactsmmo_cli/tui/screens/encyclopedia_screen.py`:

```python
"""Browseable, searchable game-data encyclopaedia modal (toggled with 'e')."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Input, Label, ListItem, ListView, Static

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.tui.encyclopedia_detail import DetailView, Ref, build_detail
from artifactsmmo_cli.tui.encyclopedia_index import (
    EncyclopediaIndex,
    IndexEntry,
    build_index,
    rank_entries,
)


class _CategoryItem(ListItem):
    def __init__(self, kind: str, label: str) -> None:
        super().__init__(Label(label))
        self.enc_kind = kind


class _EntityItem(ListItem):
    def __init__(self, entry: IndexEntry) -> None:
        super().__init__(Label(entry.display))
        self.enc_kind = entry.kind
        self.enc_code = entry.code


class _LinkItem(ListItem):
    def __init__(self, ref: Ref) -> None:
        super().__init__(Label(f"{ref.code}  ({ref.label})" if ref.label else ref.code))
        self.enc_ref = ref


class EncyclopediaScreen(Screen[None]):
    """Three-pane catalog browser: categories | search+entities | detail+links."""

    DEFAULT_CSS = """
    #encyclopedia-modal #enc-cols { width: 1fr; height: 1fr; }
    #encyclopedia-modal #enc-cats { width: 24; border: solid white; }
    #encyclopedia-modal #enc-mid { width: 1fr; }
    #encyclopedia-modal #enc-search { border: solid white; }
    #encyclopedia-modal #enc-entities { border: solid white; height: 1fr; }
    #encyclopedia-modal #enc-right { width: 2fr; border: solid white; }
    #encyclopedia-modal #enc-links { height: auto; max-height: 40%; }
    """

    BINDINGS = [
        ("escape", "dismiss", "Back"),
        ("e", "dismiss", "Back"),
        ("backspace", "back", "Back"),
    ]

    def __init__(self, game_data: GameData) -> None:
        super().__init__(id="encyclopedia-modal")
        self._game_data = game_data
        self._index: EncyclopediaIndex = build_index(game_data)
        self._active_kind: str = ""
        self._nav: list[Ref] = []

    def compose(self) -> ComposeResult:
        with Horizontal(id="enc-cols"):
            with ListView(id="enc-cats"):
                for kind, count in self._index.categories():
                    yield _CategoryItem(kind, f"{kind} ({count})")
            with Vertical(id="enc-mid"):
                yield Input(placeholder="search", id="enc-search")
                yield ListView(id="enc-entities")
            with Vertical(id="enc-right"):
                yield VerticalScroll(Static("", id="enc-detail"))
                yield ListView(id="enc-links")

    def on_mount(self) -> None:
        cats = self._index.categories()
        if cats:
            self._active_kind = cats[0][0]
            self._refill_entities("")

    def _refill_entities(self, query: str) -> None:
        entities = self.query_one("#enc-entities", ListView)
        entities.clear()
        for entry in rank_entries(self._index.entries(self._active_kind), query):
            entities.append(_EntityItem(entry))

    def _render_detail(self, ref: Ref) -> None:
        view: DetailView = build_detail(self._game_data, ref.kind, ref.code)
        self.query_one("#enc-detail", Static).update(view.renderable)
        links = self.query_one("#enc-links", ListView)
        links.clear()
        for link in view.links:
            links.append(_LinkItem(link))

    def _navigate(self, ref: Ref) -> None:
        self._nav.append(ref)
        self._render_detail(ref)

    def action_back(self) -> None:
        if not self._nav:
            return
        self._nav.pop()
        if self._nav:
            self._render_detail(self._nav[-1])
        else:
            self.query_one("#enc-detail", Static).update("")
            self.query_one("#enc-links", ListView).clear()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.list_view.id == "enc-cats" and isinstance(event.item, _CategoryItem):
            self._active_kind = event.item.enc_kind
            self._nav.clear()
            self.query_one("#enc-search", Input).value = ""
            self.query_one("#enc-detail", Static).update("")
            self.query_one("#enc-links", ListView).clear()
            self._refill_entities("")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if isinstance(item, _EntityItem):
            self._navigate(Ref(item.enc_kind, item.enc_code, ""))
        elif isinstance(item, _LinkItem):
            self._navigate(item.enc_ref)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "enc-search":
            self._refill_entities(event.value)
```

Note: `pytest-asyncio` is already used by the existing TUI pilot tests; confirm with `grep -rl "run_test" tests/` and match their marker/config. If those tests use a different async runner (e.g. `pytest.mark.asyncio` vs an anyio backend), copy that convention exactly instead of the marker shown above.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/tui/test_encyclopedia_screen.py -q`
Expected: PASS (3 passed).

Then coverage for the shell:

Run: `uv run pytest tests/tui/test_encyclopedia_screen.py --cov=src/artifactsmmo_cli/tui/screens/encyclopedia_screen --cov-report=term-missing -q`
Expected: 100%. Add tests for any uncovered branch (e.g. `action_back` with empty `_nav`, category re-highlight) before committing.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/tui/screens/encyclopedia_screen.py tests/tui/test_encyclopedia_screen.py
git commit -m "feat(tui): EncyclopediaScreen three-pane browser shell"
```

---

### Task 6: Mount in WatchApp

**Files:**
- Modify: `src/artifactsmmo_cli/tui/app.py`
- Modify: existing app test (find with `grep -rl "WatchApp" tests/`); add the binding case there.

**Interfaces:**
- Consumes: `EncyclopediaScreen`, `WatchApp._open_modal`, `WatchApp._game_data`.
- Produces: `action_toggle_encyclopedia` bound to `e`; `#encyclopedia-modal` added to the modal-reset CSS selector.

- [ ] **Step 1: Write the failing test**

Add to the existing WatchApp pilot test module (same file that already drives `WatchApp` with `run_test`; mirror its fixture for constructing the app with a character + `GameData`):

```python
@pytest.mark.asyncio
async def test_e_opens_encyclopedia() -> None:
    app = _make_watch_app()  # reuse the module's existing helper/fixture
    async with app.run_test() as pilot:
        await pilot.press("e")
        await pilot.pause()
        assert app.screen.id == "encyclopedia-modal"
        await pilot.press("e")
        await pilot.pause()
        assert app.screen.id != "encyclopedia-modal"
```

If the module builds the app inline rather than via a helper, construct it the same way the neighbouring tests do (e.g. `WatchApp("char", game_data)` with a seeded `GameData`).

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest <that_test_file>::test_e_opens_encyclopedia -q`
Expected: FAIL — pressing `e` does nothing; screen id is not `encyclopedia-modal`.

- [ ] **Step 3: Write minimal implementation**

In `app.py`:

1. Add the import near the other screen imports:

```python
from artifactsmmo_cli.tui.screens.encyclopedia_screen import EncyclopediaScreen
```

2. Add `e` to the modal-reset CSS selector — change:

```python
    #character-modal, #log-modal, #plan-modal {
        layout: vertical;
    }
```

to:

```python
    #character-modal, #log-modal, #plan-modal, #encyclopedia-modal {
        layout: vertical;
    }
```

3. Add the binding to `BINDINGS` (after the `p` plan binding):

```python
        ("e", "toggle_encyclopedia", "Encyclopedia"),
```

4. Add the action method next to `action_toggle_plan`:

```python
    def action_toggle_encyclopedia(self) -> None:
        self._open_modal(
            EncyclopediaScreen,
            lambda: EncyclopediaScreen(self._game_data),
        )
```

Confirm `_open_modal`'s signature matches this call shape by reading the existing `action_toggle_plan` — replicate it exactly (first arg = screen class for the is-open check, second = factory).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest <that_test_file>::test_e_opens_encyclopedia -q`
Expected: PASS.

- [ ] **Step 5: Full gate**

Run the TUI suite + lint + types on the touched files:

```
uv run pytest tests/tui/ -q
uv run ruff check src/artifactsmmo_cli/tui/
uv run mypy src/artifactsmmo_cli/tui/encyclopedia_index.py src/artifactsmmo_cli/tui/encyclopedia_detail.py src/artifactsmmo_cli/tui/screens/encyclopedia_screen.py src/artifactsmmo_cli/tui/app.py
```

Expected: all green, 0 warnings. Fix anything before committing.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/tui/app.py tests/<that_test_file>
git commit -m "feat(tui): bind 'e' to open the encyclopaedia modal"
```

---

## Manual verification

After Task 6, drive it live per the `superpowers:verification-before-completion` / `run` conventions:

```
uv run artifactsmmo watch <character>
```

Press `e`; confirm: categories list with counts, search filters the middle list, selecting an entity renders detail + links, selecting a link jumps, Backspace goes back, `e`/Escape closes. (If no live character/token is available, note that and rely on the pilot tests as the executable evidence.)

## Self-Review notes

- **Spec coverage:** access model (Task 6), three-pane layout (Task 5), all seven categories including confirmed NPC data (Tasks 1–4), navigable cross-links + back-stack (Tasks 4–5), search ranking (Task 1), dangling-link soundness (Task 4), pure/shell split + 100% coverage (all). The spec's "Maps/Locations" category is realised as POI entities (workshops + raids + singletons) rather than a raw tile grid, since per-tile browsing is noise and monster/resource tiles already surface as detail text — this is the "scoped to what GameData exposes" clause. Per-task reward *items* are intentionally not linked (the catalog stores only a global reward-item set, not a per-task mapping); Task 4's `test_task_detail_shows_rewards` asserts `links == ()` to lock that honesty.
- **Type consistency:** `Ref(kind, code, label)`, `DetailView(renderable, links)`, `IndexEntry(kind, code, display, search_text)`, `EncyclopediaIndex.{categories,entries,lookup}`, `build_index`, `build_detail`, `rank_entries` used identically across tasks.
- **Placeholder scan:** none — every code step is complete. The two "match the existing convention" notes (async marker in Task 5; app-test fixture in Task 6) point at real existing code the implementer must read, not unwritten work.
