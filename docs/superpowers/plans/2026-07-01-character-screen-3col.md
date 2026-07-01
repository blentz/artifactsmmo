# Character Screen 3-Column Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the TUI character modal (`c`) from one scrolling sheet into three equal scrolling columns: character sheet | inventory | bank.

**Architecture:** Extract the item-table rendering into shared pure builders in a new `tui/item_tables.py` module. `InventoryPane` and the modal both consume those builders (single source, no duplicate table loops). `CharacterScreen.compose` yields a `Horizontal` of three `VerticalScroll` columns.

**Tech Stack:** Python 3.13, Textual, Rich, pytest. Run everything with `uv run`.

## Global Constraints

- All Python commands prefixed with `uv run` (e.g. `uv run pytest`).
- Imports at top of file only — no inline, no `...` imports, no `if TYPE_CHECKING`.
- One behavioral class per file; pure render functions may share a module.
- Tests live under `tests/`; use existing snapshot-fixture pattern, no ad-hoc "simple" tests.
- Success criteria: 0 errors, 0 warnings, 0 skipped, 100% coverage.
- Never catch `Exception`.

---

### Task 1: Shared item-table builders

**Files:**
- Create: `src/artifactsmmo_cli/tui/item_tables.py`
- Test: `tests/test_tui/test_item_tables.py`

**Interfaces:**
- Consumes: `CycleSnapshot` (fields `inventory: dict[str,int]`, `inventory_max: int`, `bank_items: dict[str,int] | None`).
- Produces:
  - `build_inventory_items(snap: CycleSnapshot) -> RenderableType` — `Group` of a colored `Inventory {used}/{max}` header + qty/code table sorted qty-desc. Items only, no equipment.
  - `build_bank_items(snap: CycleSnapshot) -> RenderableType` — `Text("Bank — waiting for sync…")` when `bank_items is None`; else `Group` of `Bank {n} items` header + qty/code table sorted qty-desc.

- [ ] **Step 1: Write the failing test**

```python
"""Shared item-table builder tests (no Textual app needed)."""

from rich.console import Console

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.tui.item_tables import build_bank_items, build_inventory_items


def _snap(**overrides) -> CycleSnapshot:
    base = dict(
        cycle_index=1, timestamp="2026-05-21T12:00:00Z", character="hero",
        x=0, y=0, level=5, xp=50, max_xp=500, hp=100, max_hp=100, gold=10,
        selected_goal="g", action="a", outcome="ok",
        inventory={"iron_ore": 5, "ash_wood": 2}, inventory_max=20,
    )
    base.update(overrides)
    return CycleSnapshot(**base)


def _text(renderable) -> str:
    console = Console(no_color=True, width=100)
    with console.capture() as cap:
        console.print(renderable)
    return cap.get()


class TestBuildInventoryItems:
    def test_header_shows_counts(self):
        assert "7/20" in _text(build_inventory_items(_snap()))  # 5 + 2 = 7

    def test_items_listed(self):
        out = _text(build_inventory_items(_snap()))
        assert "iron_ore" in out and "ash_wood" in out

    def test_items_sorted_qty_desc(self):
        out = _text(build_inventory_items(_snap(inventory={"gem": 1, "iron": 10, "wood": 5})))
        assert out.find("iron") < out.find("wood") < out.find("gem")

    def test_no_equipment_section(self):
        assert "Equipment" not in _text(build_inventory_items(_snap()))

    def test_zero_max_no_error(self):
        _text(build_inventory_items(_snap(inventory={}, inventory_max=0)))

    def test_empty_inventory(self):
        _text(build_inventory_items(_snap(inventory={}, inventory_max=20)))


class TestBuildBankItems:
    def test_none_shows_waiting(self):
        out = _text(build_bank_items(_snap(bank_items=None)))
        assert "waiting" in out.lower() and "Bank" in out

    def test_populated_lists_items_and_count(self):
        out = _text(build_bank_items(_snap(bank_items={"gold_ore": 3, "topaz": 1})))
        assert "gold_ore" in out and "topaz" in out
        assert "2 items" in out

    def test_sorted_qty_desc(self):
        out = _text(build_bank_items(_snap(bank_items={"a": 1, "b": 9, "c": 5})))
        assert out.find(" b") < out.find(" c") < out.find(" a")

    def test_empty_dict_zero_items(self):
        out = _text(build_bank_items(_snap(bank_items={})))
        assert "0 items" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tui/test_item_tables.py -v`
Expected: FAIL — `ModuleNotFoundError: artifactsmmo_cli.tui.item_tables`

- [ ] **Step 3: Write minimal implementation**

```python
"""Shared item-table renderers used by the inventory pane and character modal."""

from rich.console import Group, RenderableType
from rich.table import Table
from rich.text import Text

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot


def _item_table(items: dict[str, int]) -> Table:
    table = Table(box=None, padding=(0, 1), show_header=False)
    table.add_column("qty", justify="right", style="cyan")
    table.add_column("code")
    for code, qty in sorted(items.items(), key=lambda kv: -kv[1]):
        table.add_row(str(qty), code)
    return table


def build_inventory_items(snap: CycleSnapshot) -> RenderableType:
    """Colored inventory header + qty/code table (qty-desc). Items only."""
    used = sum(snap.inventory.values())
    max_ = snap.inventory_max
    fill = used / max_ if max_ else 0.0
    color = "red" if fill > 0.9 else ("yellow" if fill > 0.7 else "white")
    header = Text(f"Inventory  {used}/{max_}", style=f"bold {color}")
    return Group(header, _item_table(snap.inventory))


def build_bank_items(snap: CycleSnapshot) -> RenderableType:
    """Bank header + qty/code table (qty-desc), or a waiting placeholder when
    the bank has not been synced yet (bank_items is None)."""
    if snap.bank_items is None:
        return Text("Bank — waiting for sync…")
    header = Text(f"Bank  {len(snap.bank_items)} items", style="bold")
    return Group(header, _item_table(snap.bank_items))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_tui/test_item_tables.py -v`
Expected: PASS (all cases)

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/tui/item_tables.py tests/test_tui/test_item_tables.py
git commit -m "feat(tui): shared inventory/bank item-table builders"
```

---

### Task 2: Refactor InventoryPane onto the shared builder

**Files:**
- Modify: `src/artifactsmmo_cli/tui/widgets/inventory_pane.py:24-47` (`_render_inventory`)
- Test: `tests/test_tui/test_inventory_pane.py` (unchanged — must stay green)

**Interfaces:**
- Consumes: `build_inventory_items` from Task 1.
- Produces: no new interface; `InventoryPane` external behavior unchanged (items header + items + Equipment section).

- [ ] **Step 1: Run the existing pane tests to confirm the current green baseline**

Run: `uv run pytest tests/test_tui/test_inventory_pane.py -v`
Expected: PASS (baseline before refactor)

- [ ] **Step 2: Replace the items-building block with the shared builder**

Rewrite the file body so the import block and `_render_inventory` read:

```python
"""Inventory pane: sorted item counts + equipped slots."""

from rich.console import Group, RenderableType
from rich.table import Table
from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.tui.item_tables import build_inventory_items


class InventoryPane(Static):
    snapshot: reactive[CycleSnapshot | None] = reactive(None)

    def update_snapshot(self, snap: CycleSnapshot) -> None:
        self.snapshot = snap

    def render(self) -> RenderableType:
        snap = self.snapshot
        if snap is None:
            return Text("Waiting...")
        return self._render_inventory(snap)

    def _render_inventory(self, s: CycleSnapshot) -> Group:
        items = build_inventory_items(s)

        equip_section = Text("\nEquipment", style="bold")
        equip = Table(box=None, padding=(0, 1), show_header=False)
        equip.add_column("slot", style="dim")
        equip.add_column("item")
        for slot, equipped in s.equipment.items():
            if equipped:
                equip.add_row(slot.replace("_slot", ""), equipped)

        return Group(items, equip_section, equip)
```

- [ ] **Step 3: Run pane tests to verify still green**

Run: `uv run pytest tests/test_tui/test_inventory_pane.py -v`
Expected: PASS (header counts, sort order, equipment section, empty cases all still pass)

- [ ] **Step 4: Commit**

```bash
git add src/artifactsmmo_cli/tui/widgets/inventory_pane.py
git commit -m "refactor(tui): InventoryPane reuses shared item-table builder"
```

---

### Task 3: Three-column character modal

**Files:**
- Modify: `src/artifactsmmo_cli/tui/screens/character_screen.py:43-64` (CSS, `compose`, `update_snapshot`, imports)
- Test: `tests/test_tui/test_character_screen.py` (add column-builder wiring test)
- Modify test: `tests/test_tui/test_app.py:204-213` (`test_character_screen_fills_terminal` — `#char-scroll` no longer exists)

**Interfaces:**
- Consumes: `build_inventory_items`, `build_bank_items` (Task 1); `build_character_detail` (existing, unchanged).
- Produces: `CharacterScreen` with three `Static`s — ids `char-detail`, `char-inv`, `char-bank` — inside `VerticalScroll` columns within a `Horizontal#char-cols`.

- [ ] **Step 1: Write the failing test (screen composes three columns and refreshes all three)**

Add to `tests/test_tui/test_character_screen.py`:

```python
import pytest
from textual.widgets import Static

from artifactsmmo_cli.tui.app import WatchApp
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.tui.screens.character_screen import CharacterScreen


class TestThreeColumnModal:
    @pytest.mark.asyncio
    async def test_modal_has_three_columns(self):
        app = WatchApp("hero", GameData())
        async with app.run_test(size=(120, 50)) as pilot:
            app.update_snapshot(
                _snap(inventory={"iron_ore": 5}, inventory_max=20, bank_items={"gold_ore": 3})
            )
            await pilot.press("c")
            screen = app.screen
            assert isinstance(screen, CharacterScreen)
            det = screen.query_one("#char-detail", Static)
            inv = screen.query_one("#char-inv", Static)
            bank = screen.query_one("#char-bank", Static)
            assert det is not None and inv is not None and bank is not None

    @pytest.mark.asyncio
    async def test_columns_show_expected_content(self):
        app = WatchApp("hero", GameData())
        async with app.run_test(size=(150, 50)) as pilot:
            app.update_snapshot(
                _snap(inventory={"iron_ore": 5}, inventory_max=20, bank_items={"gold_ore": 3})
            )
            await pilot.press("c")
            out = _text(app.screen.query_one("#char-inv", Static).renderable)
            assert "iron_ore" in out
            out_bank = _text(app.screen.query_one("#char-bank", Static).renderable)
            assert "gold_ore" in out_bank

    @pytest.mark.asyncio
    async def test_bank_waiting_when_none(self):
        app = WatchApp("hero", GameData())
        async with app.run_test(size=(150, 50)) as pilot:
            app.update_snapshot(_snap(bank_items=None))
            await pilot.press("c")
            out = _text(app.screen.query_one("#char-bank", Static).renderable)
            assert "waiting" in out.lower()

    @pytest.mark.asyncio
    async def test_update_snapshot_refreshes_all_columns(self):
        app = WatchApp("hero", GameData())
        async with app.run_test(size=(150, 50)) as pilot:
            app.update_snapshot(_snap(bank_items={"gold_ore": 1}))
            await pilot.press("c")
            app.update_snapshot(_snap(inventory={"copper_ore": 9}, inventory_max=20, bank_items={"topaz": 4}))
            inv = _text(app.screen.query_one("#char-inv", Static).renderable)
            bank = _text(app.screen.query_one("#char-bank", Static).renderable)
            assert "copper_ore" in inv and "topaz" in bank
```

Note: `_snap` and `_text` already exist at module top in this file; the `_snap` base must accept `inventory`/`inventory_max`/`bank_items` overrides (it uses `base.update(overrides)`, so they pass through).

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tui/test_character_screen.py::TestThreeColumnModal -v`
Expected: FAIL — `#char-inv` / `#char-bank` not found (only `#char-detail` exists today)

- [ ] **Step 3: Rewrite the screen for three columns**

Replace the imports, `DEFAULT_CSS`, `compose`, and `update_snapshot` in `character_screen.py`. Keep `build_character_detail` unchanged above the class.

```python
"""Full-screen character detail modal (toggled with 'c')."""

from rich.console import RenderableType
from rich.table import Table
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Static

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.tui.item_tables import build_bank_items, build_inventory_items
```

`build_character_detail(snap)` stays exactly as-is. Then the class:

```python
class CharacterScreen(Screen[None]):
    """Modal character detail in three columns: sheet | inventory | bank.
    Dismiss with 'c' or Escape."""

    DEFAULT_CSS = """
    #character-modal #char-cols {
        width: 1fr;
        height: 1fr;
    }
    #character-modal #char-cols > VerticalScroll {
        width: 1fr;
        height: 1fr;
        padding: 1 2;
    }
    """

    BINDINGS = [("escape", "dismiss", "Back"), ("c", "dismiss", "Back")]

    def __init__(self, snapshot: CycleSnapshot) -> None:
        super().__init__(id="character-modal")
        self._snapshot = snapshot

    def compose(self) -> ComposeResult:
        with Horizontal(id="char-cols"):
            with VerticalScroll(id="char-sheet-col"):
                yield Static(build_character_detail(self._snapshot), id="char-detail")
            with VerticalScroll(id="char-inv-col"):
                yield Static(build_inventory_items(self._snapshot), id="char-inv")
            with VerticalScroll(id="char-bank-col"):
                yield Static(build_bank_items(self._snapshot), id="char-bank")

    def update_snapshot(self, snap: CycleSnapshot) -> None:
        self._snapshot = snap
        self.query_one("#char-detail", Static).update(build_character_detail(snap))
        self.query_one("#char-inv", Static).update(build_inventory_items(snap))
        self.query_one("#char-bank", Static).update(build_bank_items(snap))
```

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `uv run pytest tests/test_tui/test_character_screen.py -v`
Expected: PASS (existing `build_character_detail` tests + new `TestThreeColumnModal`)

- [ ] **Step 5: Fix the stale `#char-scroll` app test**

`#char-scroll` no longer exists. Update `test_character_screen_fills_terminal` in `tests/test_tui/test_app.py` to assert the columns container fills the screen and columns split into thirds:

```python
    @pytest.mark.asyncio
    async def test_character_screen_fills_terminal(self):
        """The three-column container fills the modal; columns split the width."""
        app = _make_app()
        async with app.run_test(size=(120, 50)) as pilot:
            app.update_snapshot(_snap())
            await pilot.press("c")
            cols = app.screen.query_one("#char-cols")
            assert cols.size.width == 120
            assert cols.size.height == 50
            sheet = app.screen.query_one("#char-sheet-col")
            # equal thirds — each column roughly a third of 120
            assert 35 <= sheet.size.width <= 45
```

- [ ] **Step 6: Run the full app + character test modules**

Run: `uv run pytest tests/test_tui/test_app.py tests/test_tui/test_character_screen.py -v`
Expected: PASS (including the updated fills-terminal test and existing modal-toggle tests)

- [ ] **Step 7: Commit**

```bash
git add src/artifactsmmo_cli/tui/screens/character_screen.py tests/test_tui/test_character_screen.py tests/test_tui/test_app.py
git commit -m "feat(tui): 3-column character modal (sheet | inventory | bank)"
```

---

### Task 4: Full-suite verification

**Files:** none (verification only).

- [ ] **Step 1: Run the full test suite with coverage**

Run: `uv run pytest`
Expected: 0 errors, 0 warnings, 0 skipped, 100% coverage. `item_tables.py` fully covered by Task 1 tests; the new modal lines covered by Task 3 tests.

- [ ] **Step 2: Type-check**

Run: `uv run mypy src/artifactsmmo_cli/tui`
Expected: no errors.

- [ ] **Step 3: If coverage < 100%, add the missing-line test and re-run**

Identify the uncovered line from the coverage report, add a targeted test in the matching `tests/test_tui/` file using the existing fixture pattern, re-run `uv run pytest`. Do not lower the coverage bar.

---

## Self-Review

- **Spec coverage:** 3-column layout (Task 3); equal thirds CSS (Task 3 Step 3/5); char-sheet-only equipment (Task 1 `build_inventory_items` has no equipment; Task 3 sheet column uses unchanged `build_character_detail`); bank waiting placeholder (Task 1 `build_bank_items` None branch, Task 3 test); DRY shared builder + InventoryPane refactor (Tasks 1-2); update_snapshot refreshes all three (Task 3); tests incl. bank-None + empty-inventory + coverage (Tasks 1,3,4). All spec sections mapped.
- **Placeholder scan:** none — every code/test step shows full content.
- **Type consistency:** builder names `build_inventory_items` / `build_bank_items` identical across Tasks 1, 2, 3; Static ids `char-detail`/`char-inv`/`char-bank` consistent between compose, update_snapshot, and tests; column ids `char-cols`/`char-sheet-col` consistent between CSS and the app test.
- **Note vs spec:** spec named the shared module `character_detail.py`; plan uses `tui/item_tables.py` so the `InventoryPane` widget imports downward from a neutral module rather than from a screen module (cleaner dependency direction). Same functions, same behavior.
