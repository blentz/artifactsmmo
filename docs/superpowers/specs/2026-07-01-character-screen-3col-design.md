# Character Screen 3-Column Expansion

## Goal

Expand the TUI's full-screen character modal (`CharacterScreen`, toggled with `c`)
from a single scrolling character sheet into a 3-column display:
**[character sheet | inventory | bank]**. Each column scrolls independently.

## Current State

- `src/artifactsmmo_cli/tui/screens/character_screen.py`
  - `build_character_detail(snap)` — Rich `Table` of vitals, skills, equipment, task.
  - `CharacterScreen.compose()` — one `VerticalScroll` wrapping one `Static`.
  - `CharacterScreen.update_snapshot(snap)` — updates the single `#char-detail` Static.
- `src/artifactsmmo_cli/tui/widgets/inventory_pane.py`
  - `InventoryPane._render_inventory(s)` — builds items table (qty-desc) + equipment
    table, returns a `Group`. This item-table logic is what col 2 needs.
- `src/artifactsmmo_cli/ai/cycle_snapshot.py`
  - `CycleSnapshot` carries `inventory: dict[str,int]`, `inventory_max: int`,
    `equipment: dict[str,str|None]`, and `bank_items: dict[str,int] | None`
    (`None` until the bot syncs the bank). All data needed is already present.

## Decisions (locked)

- **Equipment placement:** character-sheet column only. Inventory column shows
  carried items only (no equipment sub-table).
- **Empty bank (`bank_items is None`):** show placeholder "Bank — waiting for sync…".
- **Column widths:** equal thirds (`1fr / 1fr / 1fr`).

## Design

### Layout

`CharacterScreen.compose()` yields a `Horizontal` container holding three
`VerticalScroll` columns, each `width: 1fr`, each wrapping one `Static`:

| id           | content                                             |
|--------------|-----------------------------------------------------|
| `char-detail`| `build_character_detail(snap)` (unchanged)          |
| `char-inv`   | `build_inventory_items(snap)`                       |
| `char-bank`  | `build_bank_items(snap)`                            |

### Shared item-render builders (DRY)

Add two pure functions to `character_detail.py` (module already hosts
`build_character_detail`; pure render functions, no new behavioral class):

- `build_inventory_items(snap: CycleSnapshot) -> RenderableType`
  - Header `Inventory  {used}/{max}` with the existing fill-color thresholds
    (>0.9 red, >0.7 yellow, else white).
  - Table: columns `qty` (right, cyan) + `code`, rows sorted by qty desc.
  - Items only — no equipment.
- `build_bank_items(snap: CycleSnapshot) -> RenderableType`
  - If `snap.bank_items is None` → `Text("Bank — waiting for sync…")`.
  - Else header `Bank  {n} items` (n = count of distinct codes) + table
    `qty`/`code` sorted qty desc. Empty dict → header with `0 items`, empty body.

### InventoryPane refactor

`InventoryPane._render_inventory` is refactored to call
`build_inventory_items(s)` for the items portion, then append its own
`Equipment` header + equipment table (unchanged behavior in the main grid).
This makes `build_inventory_items` the single source for item-table rendering,
removing the duplicate table-building loop.

### update_snapshot

`CharacterScreen.update_snapshot(snap)` re-renders all three Statics via
`query_one(id, Static).update(builder(snap))`.

### CSS

`CharacterScreen.DEFAULT_CSS` updated: the `Horizontal` fills the modal
(`width/height: 1fr`), each `VerticalScroll` column `width: 1fr` with padding.

## Testing

Tests under `tests/`, using existing snapshot fixtures (no ad-hoc "simple" tests):

- `build_inventory_items`: rows present, sorted qty-desc, header count correct.
- `build_bank_items`: (a) `None` → waiting placeholder; (b) populated → sorted
  rows + count header; (c) empty dict → `0 items` header, no rows.
- `CharacterScreen` composes 3 columns with ids `char-detail`, `char-inv`,
  `char-bank`; `update_snapshot` refreshes all three.
- Existing `InventoryPane` test stays green (equipment still shown in main grid).

Success criteria unchanged from repo standard: 0 errors, 0 warnings, 0 skipped,
100% coverage.

## Out of Scope

- No new bank pane in the main 3×3 grid (bank stays modal-only + map marker).
- No combat stats (not in snapshot, matches existing omission).
- No filtering/search within columns.
