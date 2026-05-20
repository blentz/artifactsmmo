# Typed Map Glyphs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the TUI map typed, category-colored glyphs — uppercase letters for NPCs, lowercase letters for monsters, box-drawing glyphs for structures, and `+` for doors.

**Architecture:** `glyphs.py` becomes the single source of truth: per-category color constants, curated code→letter tables, and resolver functions with first-letter fallback. `map_pane._build_tile_index` calls the resolvers per tile. `game_data._load_maps` starts capturing `grand_exchange`.

**Tech Stack:** Python 3.13, `uv`, pytest, Rich/Textual (map renders a Rich `Text`).

---

## File Structure

- `src/artifactsmmo_cli/tui/glyphs.py` — replace `CONTENT_GLYPHS` with category constants, `NPC_GLYPHS`/`MONSTER_GLYPHS`/`STRUCTURE_GLYPHS`/`RESOURCE_GLYPHS` tables, door constants, and `npc_glyph`/`monster_glyph`/`structure_glyph` resolvers.
- `src/artifactsmmo_cli/ai/game_data.py` — add `_grand_exchange_location` field; `_load_maps` captures it.
- `src/artifactsmmo_cli/tui/widgets/map_pane.py` — `_build_tile_index` uses resolvers + structure/door glyphs + grand_exchange; `_render_viewport` legend updated.
- Tests: `tests/test_tui/test_glyphs.py`, `tests/test_tui/test_map_pane.py`, `tests/test_ai/test_game_data.py`.

---

## Task 1: Restructure `glyphs.py` with typed tables and resolvers

**Files:**
- Modify: `src/artifactsmmo_cli/tui/glyphs.py`
- Test: `tests/test_tui/test_glyphs.py`

- [ ] **Step 1: Write the failing tests**

Replace the contents of `tests/test_tui/test_glyphs.py` with (inspect the existing file first; keep any existing assertions about `PLAYER_GLYPH`/`WALKABLE_GLYPH` that still hold, and add these):

```python
from artifactsmmo_cli.tui.glyphs import (
    DOOR_COLOR,
    DOOR_GLYPH,
    MONSTER_COLOR,
    NPC_COLOR,
    RESOURCE_GLYPHS,
    STRUCTURE_COLOR,
    monster_glyph,
    npc_glyph,
    structure_glyph,
)


def test_npc_glyph_curated():
    assert npc_glyph("archaeologist") == ("A", NPC_COLOR)
    assert npc_glyph("tasks_trader") == ("K", NPC_COLOR)


def test_npc_glyph_fallback_first_letter_upper():
    assert npc_glyph("new_vendor") == ("N", NPC_COLOR)


def test_monster_glyph_family_collapses_to_one_letter():
    for code in ("blue_slime", "green_slime", "red_slime", "yellow_slime", "king_slime"):
        assert monster_glyph(code) == ("s", MONSTER_COLOR)
    assert monster_glyph("chicken") == ("c", MONSTER_COLOR)
    assert monster_glyph("goblin") == ("g", MONSTER_COLOR)
    assert monster_glyph("goblin_wolfrider") == ("g", MONSTER_COLOR)


def test_monster_glyph_fallback_first_letter_lower():
    assert monster_glyph("Dragon") == ("d", MONSTER_COLOR)


def test_structure_glyph_curated_and_fallback():
    assert structure_glyph("bank") == ("╣", STRUCTURE_COLOR)
    assert structure_glyph("grand_exchange") == ("╠", STRUCTURE_COLOR)
    assert structure_glyph("workshop") == ("╬", STRUCTURE_COLOR)
    assert structure_glyph("tasks_master") == ("╤", STRUCTURE_COLOR)
    assert structure_glyph("unknown_struct") == ("▢", STRUCTURE_COLOR)


def test_door_constants():
    assert DOOR_GLYPH == "+"
    assert DOOR_COLOR == "magenta"


def test_resource_glyphs_unchanged():
    assert RESOURCE_GLYPHS["resource_woodcutting"] == ("T", "green")
    assert RESOURCE_GLYPHS["resource_mining"] == ("*", "yellow")
    assert RESOURCE_GLYPHS["resource_fishing"] == ("~", "blue")
    assert RESOURCE_GLYPHS["resource_alchemy"] == ("%", "magenta")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_tui/test_glyphs.py -q`
Expected: FAIL — `ImportError` (resolvers/constants not defined).

- [ ] **Step 3: Rewrite `glyphs.py`**

Replace the entire contents of `src/artifactsmmo_cli/tui/glyphs.py` with:

```python
"""Map (x,y) tile content → glyph + color for the TUI map pane.

Each content category has its own color so glyphs that share a letter across
categories (tailor 'T' cyan vs woodcutting-resource 'T' green) stay distinct.
NPCs are uppercase letters, monsters lowercase, structures box-drawing glyphs,
doors '+'. Unknown NPC/monster codes fall back to their first letter.
"""

PLAYER_GLYPH = "@"
PLAYER_COLOR = "bright_yellow"

NPC_COLOR = "cyan"
MONSTER_COLOR = "red"
STRUCTURE_COLOR = "white"
DOOR_COLOR = "magenta"

DOOR_GLYPH = "+"
GENERIC_STRUCTURE_GLYPH = "▢"

# NPC code → uppercase letter (color is always NPC_COLOR).
NPC_GLYPHS: dict[str, str] = {
    "archaeologist": "A",
    "cultist_wizard": "C",
    "rune_vendor": "R",
    "sandwhisper_trader": "S",
    "tailor": "T",
    "tasks_trader": "K",
}

# Monster code → lowercase letter (color is always MONSTER_COLOR). Families
# collapse to one letter (all slimes → 's', both goblins → 'g').
MONSTER_GLYPHS: dict[str, str] = {
    "blue_slime": "s", "green_slime": "s", "red_slime": "s",
    "yellow_slime": "s", "king_slime": "s",
    "chicken": "c", "cow": "o", "cyclops": "y", "cultist_acolyte": "u",
    "cursed_tree": "t", "death_knight": "d", "desert_scorpion": "x",
    "flying_snake": "f", "goblin": "g", "goblin_wolfrider": "g",
    "hellhound": "h", "highwayman": "j", "imp": "i", "mushmush": "m",
    "ogre": "r", "orc": "q", "owlbear": "b", "pig": "p", "sand_snake": "n",
    "sandwarden": "l", "sheep": "e", "skeleton": "k", "spider": "a",
    "vampire": "v", "wolf": "w",
}

# Structure code → box-drawing glyph (color is always STRUCTURE_COLOR).
STRUCTURE_GLYPHS: dict[str, str] = {
    "bank": "╣",
    "grand_exchange": "╠",
    "workshop": "╬",
    "tasks_master": "╤",
}

# Resource skill key → (glyph, color). Unchanged from the original scheme.
RESOURCE_GLYPHS: dict[str, tuple[str, str]] = {
    "resource_woodcutting": ("T", "green"),
    "resource_mining": ("*", "yellow"),
    "resource_fishing": ("~", "blue"),
    "resource_alchemy": ("%", "magenta"),
}

UNMAPPED_GLYPH = " "
WALKABLE_GLYPH = "·"
WALKABLE_COLOR = "grey50"


def npc_glyph(code: str) -> tuple[str, str]:
    """Glyph+color for an NPC code: curated, else uppercased first letter."""
    return (NPC_GLYPHS.get(code) or code[:1].upper(), NPC_COLOR)


def monster_glyph(code: str) -> tuple[str, str]:
    """Glyph+color for a monster code: curated, else lowercased first letter."""
    return (MONSTER_GLYPHS.get(code) or code[:1].lower(), MONSTER_COLOR)


def structure_glyph(code: str) -> tuple[str, str]:
    """Glyph+color for a structure code: curated, else a generic box."""
    return (STRUCTURE_GLYPHS.get(code, GENERIC_STRUCTURE_GLYPH), STRUCTURE_COLOR)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_tui/test_glyphs.py -q`
Expected: PASS

Then check no other module imports the now-removed `CONTENT_GLYPHS`:
Run: `grep -rn "CONTENT_GLYPHS" src tests`
Expected: only `map_pane.py` (fixed in Task 3). If `map_pane.py` still references it, that's expected until Task 3; do not touch it here.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/tui/glyphs.py tests/test_tui/test_glyphs.py
git commit -m "feat(tui): typed glyph tables + resolvers in glyphs.py"
```

Note: `map_pane.py` still imports `CONTENT_GLYPHS` and will not import until Task 3. Run the map_pane tests only after Task 3.

---

## Task 2: Capture `grand_exchange` location in GameData

**Files:**
- Modify: `src/artifactsmmo_cli/ai/game_data.py`
- Test: `tests/test_ai/test_game_data.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_ai/test_game_data.py` in the `TestGameDataLoadMaps` class (reuse the existing `make_map_tile` / `make_page` helpers and `patch` import already in the file):

```python
    def test_loads_grand_exchange_location(self):
        gd = GameData()
        tile = make_map_tile(3, 4, "grand_exchange", "grand_exchange")
        with patch("artifactsmmo_cli.ai.game_data.get_all_maps", return_value=make_page([tile])):
            gd._load_maps(MagicMock())
        assert gd._grand_exchange_location == (3, 4)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_game_data.py -k grand_exchange -v`
Expected: FAIL — `AttributeError: 'GameData' object has no attribute '_grand_exchange_location'`.

- [ ] **Step 3: Implement**

In `src/artifactsmmo_cli/ai/game_data.py`, add the field next to `_bank_location` / `_taskmaster_location` (around line 42-43):

```python
    _grand_exchange_location: tuple[int, int] | None = None
```

In `_load_maps`, add a branch in the content-type dispatch (next to the `MapContentType.BANK` branch):

```python
                elif ct == MapContentType.GRAND_EXCHANGE:
                    self._grand_exchange_location = loc
```

Verify the enum member name: run `uv run python -c "from artifactsmmo_api_client.models.map_content_type import MapContentType; print([m.name for m in MapContentType])"` and use the exact member whose value is `grand_exchange` (expected `GRAND_EXCHANGE`). If the member name differs, use the correct one.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_game_data.py -k grand_exchange -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/game_data.py tests/test_ai/test_game_data.py
git commit -m "feat(ai): capture grand_exchange location from map scan"
```

---

## Task 3: `_build_tile_index` uses typed resolvers + structures + door

**Files:**
- Modify: `src/artifactsmmo_cli/tui/widgets/map_pane.py`
- Test: `tests/test_tui/test_map_pane.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_tui/test_map_pane.py`. Extend the existing `_gd_with_world` helper to also set NPCs / grand_exchange, or add a new builder. Add:

```python
def _gd_typed() -> GameData:
    gd = GameData()
    gd._monster_locations = {"green_slime": [(2, 0)], "chicken": [(0, 2)]}
    gd._npc_locations = {"archaeologist": (-1, 0)}
    gd._bank_location = (4, 1)
    gd._taskmaster_location = (1, 2)
    gd._workshop_locations = {"mining": (3, 3)}
    gd._grand_exchange_location = (-2, -2)
    gd._transition_tiles = {(0, -3)}
    gd._resource_locations = {"ash_tree": [(2, 2)]}
    gd._resource_skill = {"ash_tree": ("woodcutting", 1)}
    return gd


class TestMapPaneTypedGlyphs:
    def test_npc_renders_uppercase_letter(self):
        idx = MapPane._build_tile_index(_gd_typed())
        assert idx[(-1, 0)] == ("A", "cyan")

    def test_monster_renders_lowercase_letter(self):
        idx = MapPane._build_tile_index(_gd_typed())
        assert idx[(2, 0)] == ("s", "red")    # green_slime -> s
        assert idx[(0, 2)] == ("c", "red")    # chicken -> c

    def test_structures_render_box_glyphs(self):
        idx = MapPane._build_tile_index(_gd_typed())
        assert idx[(4, 1)] == ("╣", "white")     # bank
        assert idx[(-2, -2)] == ("╠", "white")   # grand_exchange
        assert idx[(3, 3)] == ("╬", "white")     # workshop
        assert idx[(1, 2)] == ("╤", "white")     # tasks_master

    def test_transition_renders_door(self):
        idx = MapPane._build_tile_index(_gd_typed())
        assert idx[(0, -3)] == ("+", "magenta")

    def test_resources_unchanged(self):
        idx = MapPane._build_tile_index(_gd_typed())
        assert idx[(2, 2)] == ("T", "green")     # ash_tree woodcutting
```

The existing `test_index_built_from_game_data` test asserts the OLD glyphs (`("M","red")`, `("$","yellow")`, etc.). Update its expected values to the new scheme: monster→`("M"...)` becomes the typed letter for whatever code that test uses (e.g. `chicken`→`("c","red")`), bank→`("╣","white")`, tree→unchanged `("T","green")`, taskmaster→`("╤","white")`. Adjust those assertions to match the new output.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_tui/test_map_pane.py -q`
Expected: FAIL — new tests fail (old glyphs / `CONTENT_GLYPHS` still in use), and `map_pane.py` may raise `ImportError` for `CONTENT_GLYPHS` removed in Task 1.

- [ ] **Step 3: Rewrite `_build_tile_index` and its imports**

In `src/artifactsmmo_cli/tui/widgets/map_pane.py`, replace the glyphs import block:

```python
from artifactsmmo_cli.tui.glyphs import (
    DOOR_COLOR,
    DOOR_GLYPH,
    PLAYER_COLOR,
    PLAYER_GLYPH,
    RESOURCE_GLYPHS,
    UNMAPPED_GLYPH,
    WALKABLE_COLOR,
    WALKABLE_GLYPH,
    monster_glyph,
    npc_glyph,
    structure_glyph,
)
```

Replace the `_build_tile_index` body with:

```python
    @staticmethod
    def _build_tile_index(gd: GameData) -> dict[tuple[int, int], tuple[str, str]]:
        """Map (x,y) → (glyph, color). Player position resolved at render time."""
        index: dict[tuple[int, int], tuple[str, str]] = {}
        skill_to_key = {
            "woodcutting": "resource_woodcutting",
            "mining": "resource_mining",
            "fishing": "resource_fishing",
            "alchemy": "resource_alchemy",
        }
        for code, locs in gd._resource_locations.items():
            skill_lvl = gd._resource_skill.get(code)
            key = skill_to_key.get(skill_lvl[0], "resource_mining") if skill_lvl else "resource_mining"
            for (x, y) in locs:
                index[(x, y)] = RESOURCE_GLYPHS[key]
        for skill, loc in gd._workshop_locations.items():
            if loc is not None:
                index[loc] = structure_glyph("workshop")
        for npc_code, loc in gd._npc_locations.items():
            index[loc] = npc_glyph(npc_code)
        if gd._bank_location is not None:
            index[gd._bank_location] = structure_glyph("bank")
        if gd._grand_exchange_location is not None:
            index[gd._grand_exchange_location] = structure_glyph("grand_exchange")
        if gd._taskmaster_location is not None:
            index[gd._taskmaster_location] = structure_glyph("tasks_master")
        # Monsters last so monsters at shared tiles win the cell.
        for code, locs in gd._monster_locations.items():
            glyph = monster_glyph(code)
            for (x, y) in locs:
                index[(x, y)] = glyph
        for (x, y) in gd._transition_tiles:
            index[(x, y)] = (DOOR_GLYPH, DOOR_COLOR)
        return index
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_tui/test_map_pane.py tests/test_tui/test_glyphs.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/tui/widgets/map_pane.py tests/test_tui/test_map_pane.py
git commit -m "feat(tui): render typed NPC/monster/structure/door glyphs"
```

---

## Task 4: Update the map legend

**Files:**
- Modify: `src/artifactsmmo_cli/tui/widgets/map_pane.py`
- Test: `tests/test_tui/test_map_pane.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_tui/test_map_pane.py`:

```python
    def test_legend_uses_category_key(self):
        gd = _gd_typed()
        pane = MapPane(gd)
        pane.update_snapshot(_snap(0, 0))
        header = pane.render().plain.split("\n")[0]
        assert "npc" in header and "monster" in header
        assert "structure" in header and "door" in header
        # The old per-glyph legend tokens are gone.
        assert "M=monster" not in header
        assert ">=portal" not in header
```

`_snap` already exists in this test module; `_gd_typed` was added in Task 3.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tui/test_map_pane.py -k legend -v`
Expected: FAIL — old legend still contains `M=monster` / `>=portal`.

- [ ] **Step 3: Update the legend line**

In `src/artifactsmmo_cli/tui/widgets/map_pane.py` `_render_viewport`, replace the header `text.append(...)` call with:

```python
        text.append(
            f" ({cx},{cy})  @ you  A-Z npc  a-z monster  ╬ structure  + door  T/*/~/% resource\n",
            style="dim",
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_tui/test_map_pane.py -k legend -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/tui/widgets/map_pane.py tests/test_tui/test_map_pane.py
git commit -m "feat(tui): compact category legend for the map pane"
```

---

## Task 5: Full-suite + coverage verification

**Files:** none (verification only).

- [ ] **Step 1: Full suite**

Run: `uv run pytest -q`
Expected: all pass, **0 skipped**.

- [ ] **Step 2: Coverage of changed modules**

Run: `uv run pytest --cov=artifactsmmo_cli.tui.glyphs --cov=artifactsmmo_cli.tui.widgets.map_pane --cov-report=term-missing -q`
Expected: 100% on `glyphs.py`; no uncovered new lines in `map_pane.py`. Add targeted tests for any missed line (e.g. an NPC/monster fallback path, the generic structure glyph).

- [ ] **Step 3: Lint + types on changed files**

Run: `uv run ruff check src/artifactsmmo_cli/tui/glyphs.py src/artifactsmmo_cli/tui/widgets/map_pane.py src/artifactsmmo_cli/ai/game_data.py`
Run: `uv run mypy src/artifactsmmo_cli/tui/glyphs.py src/artifactsmmo_cli/tui/widgets/map_pane.py`
Expected: no new errors versus `main` (the repo has some pre-existing findings; introduce none).

- [ ] **Step 4: Commit any coverage fixes**

```bash
git add -A
git commit -m "test(tui): close coverage gaps for typed map glyphs"
```

---

## Self-review notes

- Spec coverage: NPC letters (Task 1/3), monster family letters (Task 1/3), structure box glyphs (Task 1/3), door `+` (Task 1/3), grand_exchange capture (Task 2), per-category colors (Task 1), fallback resolvers (Task 1), legend (Task 4), resources unchanged (Task 1/3). All mapped.
- Type consistency: resolvers return `tuple[str, str]` (glyph, color) everywhere; `_build_tile_index` stores `tuple[str,str]`, matching its existing signature and the renderer's `glyph, color = cell` unpack.
- Placeholder scan: none — all code is concrete; the only conditional instruction is verifying the `MapContentType.GRAND_EXCHANGE` member name, with the exact check command given.
