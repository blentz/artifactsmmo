# Encyclopaedia TUI — Design

**Date:** 2026-07-18
**Status:** Approved (design), pending implementation plan

## Goal

Expose the static game-data catalog (`GameData`) as a browseable, searchable
encyclopaedia inside the watch-mode TUI: a pushed modal, like the existing
character / log / plan screens, bound to a key. Read-only reference — no
decision logic, so no formal/Lean gate applies.

## Access model

New pushed `Screen` in `WatchApp`, toggled with `e` (mirrors the `c`/`l`/`p`
modal pattern in `app.py::_open_modal`). `GameData` is already held by the app
and passed to modals (see `PlanScreen(self._last_snapshot, self._game_data)`);
the encyclopaedia takes `game_data` the same way. No new CLI command; no
standalone app.

## Layout

Three panes side by side, plus a search box:

```
┌Categories┐┌Entities──────────┐┌Detail──────────────┐
│>Items    ││ search: cop_     ││ copper_dagger      │
│ Monsters ││ copper_dagger    ││ lvl 1  weapon      │
│ Resources││ copper_ring      ││ atk_fire 6         │
│ Recipes  ││ copper_boots     ││ craft: 6 copper    │
│ Maps     ││ copper_helm      ││ ── links ──        │
│ Tasks    ││                  ││  > copper (item)   │
└──────────┘└──────────────────┘└────────────────────┘
```

- **Left (categories):** `ListView`, one row per category, with entity count
  (`Items (312)`). Highlight drives the middle pane. Switching category clears
  the nav-stack.
- **Middle (entities):** `Input` search box above a `ListView`. Search filters
  the active category by case-insensitive substring over `search_text`
  (code + display name + subtype). Ranking: prefix matches first, then
  contains. Empty box = full sorted list. No fuzzy-match dependency.
- **Right (detail):** a `Static` rendering the `build_detail` table, above a
  `ListView` of navigable cross-reference links.

## Architecture

Split pure logic from the Textual shell, mirroring the existing
`build_character_detail` pure-function pattern. One behavioral class per file
(CLAUDE.md); the pure modules hold only functions and small value objects.

### `encyclopedia_index.py` (pure)

`build_index(game_data) -> EncyclopediaIndex`. For each category, a sorted
`list[IndexEntry]` where `IndexEntry = (kind, code, display, search_text)`.
Built once when the modal opens. `EncyclopediaIndex` also answers
`lookup(kind, code) -> IndexEntry | None` for link resolution.

### `encyclopedia_detail.py` (pure)

`build_detail(game_data, kind, code) -> DetailView`, where
`DetailView = (renderable: RenderableType, links: list[Ref])` and
`Ref = (kind, code, label)`. One builder branch per category. This module owns
**all** cross-link wiring. No Textual import — unit-testable in isolation.

### `encyclopedia_screen.py` (behavioral)

`EncyclopediaScreen(Screen[None])`. Owns the three panes, the search `Input`,
and the nav-stack. Thin: translates widget events into calls on the two pure
modules and re-renders. `DEFAULT_CSS` + `BINDINGS` per the existing screen
convention.

## Categories and detail contents

Scoped to what `GameData` actually exposes (`items`, `monsters`,
`recipes_catalog`, `world`, task-reward fields). Cross-links in **bold**.

- **Items** (`ItemStats`): level, type/subtype, effects/combat stats
  (attack, resistance, dmg, crit, hp_bonus, wisdom, prospecting, haste,
  lifesteal, …), conditions, tradeable. Links: **crafted-from** recipe inputs,
  **drops-from** monsters/resources, **used-in** recipes.
- **Monsters** (`MonsterCatalog`): level, HP, per-element attack/resistance,
  crit, lifesteal. Links: **drops** items, **locations** (map refs).
- **Resources**: gather skill + level, drop table, locations. Links: **drop**
  items, **locations**.
- **Recipes** (`RecipeCatalog`): skill + level, inputs, yield, workshop.
  Links: **input** items, **yielded** item.
- **Maps / Locations** (`LocationCatalog`): coordinate, content —
  **monster** / **resource** / workshop / bank / taskmaster / grand-exchange.
- **Tasks**: reward items, coin/gold rewards. Links: reward **items**.

NPC-vendor category included **only if** vendor data exists in the catalog at
implementation time; if absent, drop the tab rather than fabricate it
("use only API data or fail with an error").

## Navigation

- Nav-stack: `list[Ref]`. Selecting an entity in the middle list, or a link in
  the detail list, pushes a `Ref` and re-renders the detail pane.
- **Backspace** pops the stack (back). **Escape** / **e** dismiss the modal.
- Category switch clears the stack.
- **Tab** cycles focus: categories → search → entities → links.

## Error handling

- Every `Ref` produced by `build_detail` must resolve to a real
  `IndexEntry`. A dangling link is a bug, surfaced by test, not swallowed.
- Missing catalog data fails loudly (no silent defaulting), consistent with
  the API-interaction guidelines. A category with zero entries is shown as
  empty, not hidden — except the conditional NPC tab above.

## Testing

Per CLAUDE.md: 0 errors, 0 warnings, 0 skipped, 100% coverage.

- `build_index` and `build_detail` are pure → unit-tested against seeded
  `GameData` fixtures from the existing suite.
- Cross-link soundness test: for every category and entity, assert each `Ref`
  from `build_detail` resolves via `EncyclopediaIndex.lookup` (no dangling
  links).
- Search test: prefix-before-contains ranking, case-insensitivity, empty-box
  full list.
- Screen wiring: Textual `run_test()` pilot — open modal, type a search,
  select an entity, follow a link, Backspace, close. Asserts focus order and
  nav-stack behaviour.

## Out of scope (YAGNI)

- Standalone CLI command / separate app.
- Fuzzy-match library.
- Editing, favouriting, or persistence.
- Live/dynamic data (character state, market prices) — this is the static
  catalog only.
