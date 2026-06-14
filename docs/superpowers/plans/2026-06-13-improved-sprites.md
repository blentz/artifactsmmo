# Improved Sprites (Outline-Only Tileset) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Execution-mode caveat:** B1 (Tasks 1–4) is fully-specified concrete data and can run via subagents. B2–B5 (Tasks 5–8) are interactive art authoring — the per-batch sprite pixels are drawn and reviewed in the browser visual companion *with the user* before commit. Run those tasks **inline** (main thread + user + browser), not via autonomous subagents.

**Goal:** Replace the flat 6-sprite tileset + procedural blobs with a cohesive outline-only style across the full live entity roster (~47 sprites), as pure data.

**Architecture:** New `palette.py` holds shared hex art colors. `sprites.py` gains/redraws sprites in outline-only style (near-black `#1c1c1c` ring + flat fill + minimal accents) using palette colors. Everything else (compositor, registry, map_pane, app) is unchanged; uncurated codes keep the procedural fallback. A `scripts/preview_sprites.py` renders a terminal contact sheet.

**Tech Stack:** Python 3.13, `uv`, Rich, pytest (`-W error`, 100% coverage on `src/`), mypy `--strict`.

**Spec:** `docs/superpowers/specs/2026-06-13-improved-sprites-design.md`

**Conventions (CLAUDE.md):** Prefix commands with `uv run`. Imports at top only — no inline, no `...`, no `TYPE_CHECKING`. Never catch `Exception`. Pure-data modules (`palette.py`, `sprites.py`) may group declarations. Tests in `tests/`; 0 errors/warnings/skips, 100% coverage on `src/`. mypy strict: parameterize all generics. Use only API data or fail (roster comes from live `GameData`).

**Sprite authoring rules (apply to every sprite in every batch):**
- Exactly 8 rows × 8 chars. `.` = transparent (shows floor). `#`-style keys map to palette hex in the sprite's `palette` dict.
- Outline-only: trace the silhouette with `o = INK`; fill interior flat; add ≤2 accent colors for recognizability.
- Use palette constants from `palette.py` as the palette values — never raw hex inside `sprites.py`.
- After adding a sprite: register it in its category dict (`MONSTER_SPRITES`/`NPC_SPRITES`/`STRUCTURE_SPRITES`/`RESOURCE_SPRITES`) **and** in `ALL_CURATED_SPRITES` (keyed by its game code). The import-time validation loop + `test_sprites.py` then auto-validate it.

---

## File Structure

| File | Responsibility | New/Modify |
|---|---|---|
| `src/artifactsmmo_cli/tui/palette.py` | Shared hex art-color constants (pure data) | Create (T1), extend (T5–T8 as needed) |
| `tests/test_tui/test_palette.py` | Lock palette constants exist + are hex | Create (T1) |
| `src/artifactsmmo_cli/tui/sprites.py` | Curated sprite data; redraw 6, add roster | Modify (T2,T3,T5–T8) |
| `tests/test_tui/test_half_block.py` | Update slime color-literal assertion | Modify (T2) |
| `tests/test_tui/test_map_pane.py` | Update slime color-literal assertion | Modify (T2) |
| `scripts/preview_sprites.py` | Terminal contact-sheet preview tool | Create (T4) |

No changes to `half_block.py`, `sprite_registry.py`, `widgets/map_pane.py`, `app.py`, `glyphs.py`.

---

## Task 1: Shared palette module

**Files:**
- Create: `src/artifactsmmo_cli/tui/palette.py`
- Test: `tests/test_tui/test_palette.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_tui/test_palette.py`:

```python
"""The shared art palette: named hex constants reused across sprites."""

import re

from artifactsmmo_cli.tui import palette

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def test_ink_is_near_black():
    assert palette.INK == "#1c1c1c"


def test_all_palette_constants_are_hex():
    names = [n for n in dir(palette) if n.isupper()]
    assert names, "palette must define color constants"
    for name in names:
        assert _HEX.match(getattr(palette, name)), f"{name} is not #rrggbb"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tui/test_palette.py -v`
Expected: FAIL with `ModuleNotFoundError: artifactsmmo_cli.tui.palette`

- [ ] **Step 3: Write the implementation**

Create `src/artifactsmmo_cli/tui/palette.py`:

```python
"""Shared hex art-color palette for the outline-only sprite tileset.

Single source of art colors. Sprites in sprites.py reference these constants
as palette values so the tileset stays cohesive. Distinct from glyphs.py,
which holds ANSI terrain/fallback colors.
"""

INK = "#1c1c1c"        # universal silhouette outline + default eye
LEAF = "#4e9a06"       # foliage / slime green
STONE = "#babdb6"      # light stone (walls)
SLATE = "#6b6f6a"      # dark rock
STEEL = "#888a85"      # metal
GOLD = "#fce94f"       # treasure / gold roof
AMBER = "#fcaf3e"      # beak / orange / fish
COPPER = "#c17d11"     # ore veins
BARK = "#8f5902"       # wood / hide brown
DOORWOOD = "#5c3a0a"   # dark door wood
KHAKI = "#8a7f3d"      # explorer cloth
BLOOD = "#cc0000"      # comb / red
BONE = "#eeeeec"       # white / parchment / feathers
SKIN = "#fce0b0"       # flesh
TUNIC = "#3465a4"      # blue cloth
WATER = "#2a7fb8"      # water surface
BREW = "#75507b"       # alchemy / cloth purple
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_tui/test_palette.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/tui/palette.py tests/test_tui/test_palette.py
git commit -m "feat(tui): shared hex art palette for sprite tileset"
```

---

## Task 2: Redraw the 6 existing sprites in outline style

**Files:**
- Modify: `src/artifactsmmo_cli/tui/sprites.py`
- Modify: `tests/test_tui/test_half_block.py`, `tests/test_tui/test_map_pane.py`

The 6 shipped sprites are flat and use ANSI color names. Redraw them outline-only with palette hex. Two existing tests assert the literal `"green"` against the slime and must move to the palette value first (TDD: update assertion → fails against old flat sprite → redraw → passes).

- [ ] **Step 1: Update the color-literal assertions (failing test)**

In `tests/test_tui/test_half_block.py`, change `test_opaque_pixel_uses_palette_color`. Replace the body's literal check:

```python
def test_opaque_pixel_uses_palette_color():
    comp = HalfBlockCompositor()
    rows = comp.compose(GREEN_SLIME_SPRITE, "grey50")
    styles = [span.style for row in rows for span in row.spans]
    # The slime body uses the LEAF palette color (hex), not the ANSI name.
    assert any(LEAF in style for style in styles)
```

Add the import at the top of `test_half_block.py`:

```python
from artifactsmmo_cli.tui.palette import LEAF
```

In `tests/test_tui/test_map_pane.py`, change `test_monster_sprite_in_view`:

```python
    def test_monster_sprite_in_view(self):
        # green_slime at (2,0) is in view from (0,0) -> LEAF pixels present.
        pane = MapPane(_gd_typed())
        out = pane._render_viewport(_snap(0, 0), 80, 41)
        assert any(LEAF in s for s in _styles(out))
```

Add the import at the top of `test_map_pane.py`:

```python
from artifactsmmo_cli.tui.palette import LEAF
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_tui/test_half_block.py::test_opaque_pixel_uses_palette_color tests/test_tui/test_map_pane.py -v`
Expected: FAIL — old slime palette is `{"#": "green", ...}`, so `LEAF` (`#4e9a06`) is absent.

- [ ] **Step 3: Redraw the 6 sprites**

In `src/artifactsmmo_cli/tui/sprites.py`, add the palette import at top (only the colors Task 2 uses — ruff F401 fails the gate on unused imports; Task 3 extends this list):

```python
from artifactsmmo_cli.tui.palette import (
    BARK, DOORWOOD, GOLD, INK, KHAKI, LEAF, SKIN, STONE, TUNIC,
)
```

Replace the six sprite definitions (`PLAYER_SPRITE`, `GREEN_SLIME_SPRITE`, `BANK_SPRITE`, `DOOR_SPRITE`, `WOODCUTTING_SPRITE`, `ARCHAEOLOGIST_SPRITE`) with:

```python
PLAYER_SPRITE = Sprite(
    rows=(
        "..oooo..",
        ".oyyyyo.",
        ".oeyyeo.",
        ".oyyyyo.",
        "..oooo..",
        ".obbbbo.",
        ".ob..bo.",
        ".oo..oo.",
    ),
    palette={"o": INK, "y": SKIN, "e": INK, "b": TUNIC},
)

GREEN_SLIME_SPRITE = Sprite(
    rows=(
        "..oooo..",
        ".oggggo.",
        "oggggggo",
        "ogeggego",
        "oggggggo",
        "oggggggo",
        ".oggggo.",
        "..oooo..",
    ),
    palette={"o": INK, "g": LEAF, "e": INK},
)

BANK_SPRITE = Sprite(
    rows=(
        "oooooooo",
        "oyyyyyyo",
        "oooooooo",
        "osssssso",
        "ossddsso",
        "ossddsso",
        "ossddsso",
        "oooooooo",
    ),
    palette={"o": INK, "y": GOLD, "s": STONE, "d": DOORWOOD},
)

DOOR_SPRITE = Sprite(
    rows=(
        "..oooo..",
        ".oddddo.",
        ".oddddo.",
        ".oddddo.",
        ".odddko.",
        ".oddddo.",
        ".oddddo.",
        "..oooo..",
    ),
    palette={"o": INK, "d": DOORWOOD, "k": GOLD},
)

WOODCUTTING_SPRITE = Sprite(
    rows=(
        "..oooo..",
        ".oggggo.",
        "oggggggo",
        "oggggggo",
        ".oggggo.",
        "..otto..",
        "..otto..",
        "..oooo..",
    ),
    palette={"o": INK, "g": LEAF, "t": BARK},
)

ARCHAEOLOGIST_SPRITE = Sprite(
    rows=(
        "..oooo..",
        ".obbbbo.",
        ".osssso.",
        ".oseeso.",
        ".osssso.",
        "..oooo..",
        ".okkkko.",
        ".ok..ko.",
    ),
    palette={"o": INK, "b": BARK, "s": SKIN, "e": INK, "k": KHAKI},
)
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/test_tui/test_half_block.py tests/test_tui/test_map_pane.py tests/test_tui/test_sprites.py -v`
Expected: PASS (integrity test still green — all 6 remain 8×8 with defined palette keys).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/tui/sprites.py tests/test_tui/test_half_block.py tests/test_tui/test_map_pane.py
git commit -m "feat(tui): redraw 6 base sprites in outline style w/ shared palette"
```

---

## Task 3: Structures + resources (3 + 3)

**Files:**
- Modify: `src/artifactsmmo_cli/tui/sprites.py`

Add grand_exchange, workshop, tasks_master (structures) and resource_mining, resource_fishing, resource_alchemy (resources). All concrete below.

- [ ] **Step 1: Add a failing test for curated resolution**

Append to `tests/test_tui/test_sprite_registry.py`:

```python
def test_b1_structures_and_resources_are_curated():
    reg = SpriteRegistry()
    from artifactsmmo_cli.tui.sprites import (
        GRAND_EXCHANGE_SPRITE, WORKSHOP_SPRITE, TASKS_MASTER_SPRITE,
        MINING_SPRITE, FISHING_SPRITE, ALCHEMY_SPRITE,
    )
    assert reg.sprite_for("grand_exchange", SpriteCategory.STRUCTURE) is GRAND_EXCHANGE_SPRITE
    assert reg.sprite_for("workshop", SpriteCategory.STRUCTURE) is WORKSHOP_SPRITE
    assert reg.sprite_for("tasks_master", SpriteCategory.STRUCTURE) is TASKS_MASTER_SPRITE
    assert reg.sprite_for("resource_mining", SpriteCategory.RESOURCE) is MINING_SPRITE
    assert reg.sprite_for("resource_fishing", SpriteCategory.RESOURCE) is FISHING_SPRITE
    assert reg.sprite_for("resource_alchemy", SpriteCategory.RESOURCE) is ALCHEMY_SPRITE
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_tui/test_sprite_registry.py::test_b1_structures_and_resources_are_curated -v`
Expected: FAIL — `ImportError` (sprites not defined).

- [ ] **Step 3: Add the sprites + register them**

In `src/artifactsmmo_cli/tui/sprites.py`, extend the Task-2 palette import to add the colors Task 3 uses, so the full import line becomes:

```python
from artifactsmmo_cli.tui.palette import (
    AMBER, BARK, BLOOD, BONE, BREW, COPPER, DOORWOOD, GOLD, INK, KHAKI,
    LEAF, SKIN, SLATE, STEEL, STONE, TUNIC, WATER,
)
```

Then add these definitions (after `ARCHAEOLOGIST_SPRITE`):

```python
GRAND_EXCHANGE_SPRITE = Sprite(
    rows=(
        "oooooooo",
        "oawawawo",
        "oooooooo",
        "osssssso",
        "osgssgso",
        "osssssso",
        "ossddsso",
        "oooooooo",
    ),
    palette={"o": INK, "a": BLOOD, "w": BONE, "s": STONE, "g": GOLD, "d": DOORWOOD},
)

WORKSHOP_SPRITE = Sprite(
    rows=(
        "oooooooo",
        "obbbbbbo",
        "obbbbbbo",
        "oooooooo",
        "osaaaaso",
        "ossaasso",
        "osaaaaso",
        "oooooooo",
    ),
    palette={"o": INK, "b": BARK, "a": STEEL, "s": STONE},
)

TASKS_MASTER_SPRITE = Sprite(
    rows=(
        "oooooooo",
        "owwwwwwo",
        "owllllwo",
        "owllllwo",
        "owllllwo",
        "oooooooo",
        ".ob..bo.",
        ".oo..oo.",
    ),
    palette={"o": INK, "w": BONE, "l": SLATE, "b": BARK},
)

MINING_SPRITE = Sprite(
    rows=(
        "........",
        "..oooo..",
        ".osccso.",
        "osssssso",
        "oscsscso",
        "osssssso",
        ".oosso..",
        "........",
    ),
    palette={"o": INK, "s": SLATE, "c": COPPER},
)

FISHING_SPRITE = Sprite(
    rows=(
        "........",
        "..oooo..",
        ".owwwwo.",
        "owwffwwo",
        "owffffwo",
        "owwffwwo",
        ".owwwwo.",
        "..oooo..",
    ),
    palette={"o": INK, "w": WATER, "f": AMBER},
)

ALCHEMY_SPRITE = Sprite(
    rows=(
        "...oo...",
        "...oo...",
        "..o..o..",
        ".o....o.",
        ".obbbbo.",
        ".obbbbo.",
        ".obbbbo.",
        "..oooo..",
    ),
    palette={"o": INK, "b": BREW},
)
```

Then extend the registry dicts and `ALL_CURATED_SPRITES`:

```python
STRUCTURE_SPRITES: dict[str, Sprite] = {
    "bank": BANK_SPRITE,
    "door": DOOR_SPRITE,
    "grand_exchange": GRAND_EXCHANGE_SPRITE,
    "workshop": WORKSHOP_SPRITE,
    "tasks_master": TASKS_MASTER_SPRITE,
}
RESOURCE_SPRITES: dict[str, Sprite] = {
    "resource_woodcutting": WOODCUTTING_SPRITE,
    "resource_mining": MINING_SPRITE,
    "resource_fishing": FISHING_SPRITE,
    "resource_alchemy": ALCHEMY_SPRITE,
}
```

And add the six to `ALL_CURATED_SPRITES`:

```python
    "grand_exchange": GRAND_EXCHANGE_SPRITE,
    "workshop": WORKSHOP_SPRITE,
    "tasks_master": TASKS_MASTER_SPRITE,
    "resource_mining": MINING_SPRITE,
    "resource_fishing": FISHING_SPRITE,
    "resource_alchemy": ALCHEMY_SPRITE,
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/test_tui/test_sprite_registry.py tests/test_tui/test_sprites.py -v`
Expected: PASS (integrity test auto-validates the 6 new sprites).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/tui/sprites.py tests/test_tui/test_sprite_registry.py
git commit -m "feat(tui): outline sprites for 3 structures + 3 resources"
```

---

## Task 4: Terminal preview tool

**Files:**
- Create: `scripts/preview_sprites.py`

A dev tool that prints every curated sprite as a half-block contact sheet to the terminal, using the real `HalfBlockCompositor` + palette. Lives in `scripts/` (outside `src/`), so it is not coverage-gated.

- [ ] **Step 1: Write the script**

Create `scripts/preview_sprites.py`:

```python
"""Print every curated sprite as a half-block contact sheet to the terminal.

Dev tool for reviewing the tileset without launching the TUI. Usage:
    uv run python scripts/preview_sprites.py
"""

from rich.console import Console
from rich.text import Text

from artifactsmmo_cli.tui.glyphs import WALKABLE_COLOR
from artifactsmmo_cli.tui.half_block import HalfBlockCompositor
from artifactsmmo_cli.tui.sprites import ALL_CURATED_SPRITES


def main() -> None:
    console = Console()
    comp = HalfBlockCompositor()
    for name, sprite in sorted(ALL_CURATED_SPRITES.items()):
        rows = comp.compose(sprite, WALKABLE_COLOR)
        console.print(Text(name, style="bold"))
        for row in rows:
            console.print(row)
        console.print()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it**

Run: `uv run python scripts/preview_sprites.py`
Expected: a vertical contact sheet of all curated sprites rendered in color; no errors. Confirm the B1 sprites read correctly.

- [ ] **Step 3: Verify the full gate still passes**

Run: `uv run pytest && uv run mypy src/`
Expected: 0 fail, 0 warn, 0 skip, 100% coverage; mypy clean. (The script is outside `src/`, so it neither needs coverage nor breaks the gate.)

- [ ] **Step 4: Commit**

```bash
git add scripts/preview_sprites.py
git commit -m "feat(tui): terminal sprite contact-sheet preview tool"
```

---

## Tasks 5–8: Monster & NPC batches (interactive authoring)

**Run inline with browser review — not autonomous subagents.** Each batch follows the SAME loop; only the code list and worked example differ.

### Per-batch loop (apply to every batch below)

1. **Confirm the live roster.** Codes are authoritative from `GameData`, not this plan. Before drawing a batch, list the relevant codes actually present:
   ```bash
   uv run python -c "from artifactsmmo_cli.ai.game_data import GameData; g=GameData.load(); print(sorted(g.all_monster_locations)); print(sorted(g.npc_locations))"
   ```
   Draw only codes that appear; any listed-here-but-absent code is skipped, any present-but-unlisted code is added to the batch. Anything left undrawn keeps the procedural fallback.
2. **Author** each sprite per the global authoring rules (8×8, outline-only, palette colors, ≤2 accents). Add a new constant to `palette.py` only if a needed color is missing (and extend `test_palette.py` is automatic — it scans all uppercase names).
3. **Register** each: add `<CODE>_SPRITE = Sprite(...)`, insert into the category dict, and add to `ALL_CURATED_SPRITES` keyed by the exact game code.
4. **Review in browser:** render the batch as a colored contact sheet in the visual companion (`.superpowers/brainstorm/.../content/<batch>.html`, pixel grids from the sprite data over `#808080` floor). Get explicit user approval; iterate sprites until approved.
5. **Add a curated-resolution test** for the batch (mirror `test_b1_structures_and_resources_are_curated`): assert `reg.sprite_for(code, category) is <CODE>_SPRITE` for each new code.
6. **Verify gate:** `uv run pytest && uv run mypy src/` → all green (integrity test auto-validates each new sprite).
7. **Commit:** `git commit -m "feat(tui): outline sprites for <batch> (<N> codes)"`.

The integrity test in `tests/test_tui/test_sprites.py` (parametrized over `ALL_CURATED_SPRITES`) guarantees every added sprite is 8×8 with defined palette keys, keeping coverage at 100% with no per-sprite test beyond the resolution assertion in step 5.

---

### Task 5 — B2: NPCs (5)

Codes: `cultist_wizard`, `rune_vendor`, `sandwhisper_trader`, `tailor`, `tasks_trader`. Humanoid template (see `ARCHAEOLOGIST_SPRITE`): head + eyes + body, distinguished by cloth color / accessory.

**Worked example — `tailor` (purple cloth):**
```python
TAILOR_SPRITE = Sprite(
    rows=(
        "..oooo..",
        ".osssso.",
        ".oseeso.",
        ".osssso.",
        "..oooo..",
        ".ommmmo.",
        ".om..mo.",
        ".oo..oo.",
    ),
    palette={"o": INK, "s": SKIN, "e": INK, "m": BREW},
)
```
Register in `NPC_SPRITES["tailor"]` and `ALL_CURATED_SPRITES["tailor"]`. Author the other 4 NPCs by varying cloth color + one accessory (e.g. wizard = `BREW` robe + pointed `INK` hat; rune_vendor = `TUNIC` robe; sandwhisper_trader = `AMBER` desert garb; tasks_trader = `KHAKI`). Then run the per-batch loop.

### Task 6 — B3: Slimes & beasts (~10)

Codes (confirm live): `blue_slime`, `red_slime`, `yellow_slime`, `chicken` (redo), `cow`, `pig`, `sheep`, `wolf`, `owlbear`, `spider`, `flying_snake`, `sand_snake`. Slime variants reuse the `GREEN_SLIME_SPRITE` shape with a different body color (add `SLIME_BLUE`/`SLIME_RED`/`SLIME_YELLOW` palette constants, e.g. `#3465a4`/`#cc0000`/`#fce94f`).

**Worked example — `cow`:**
```python
COW_SPRITE = Sprite(
    rows=(
        "..o..o..",
        ".owwwwo.",
        "owwwwwwo",
        "oweewweo",
        "owsppswo",
        "owwwwwwo",
        ".ow..wo.",
        ".oo..oo.",
    ),
    palette={"o": INK, "w": BONE, "e": INK, "s": BARK, "p": "PINK_CONST"},
)
```
This needs a pink accent — add `PINK = "#f5a9b8"` to `palette.py` and use `PINK` (not the placeholder above). Register `MONSTER_SPRITES["cow"]` + `ALL_CURATED_SPRITES["cow"]`. Author the rest; run the per-batch loop.

### Task 7 — B4: Humanoid monsters (~8)

Codes (confirm live): `goblin`, `goblin_wolfrider`, `orc`, `ogre`, `cyclops`, `imp`, `highwayman`, `cultist_acolyte`. Humanoid template with monster skin tones; add palette constants as needed (e.g. `GOBLIN_SKIN = "#73a946"`, `OGRE_SKIN = "#8aa37b"`, `IMP_SKIN = "#cc0000"`).

**Worked example — `goblin`:**
```python
GOBLIN_SPRITE = Sprite(
    rows=(
        "..oooo..",
        ".oggggo.",
        ".ogeego.",
        ".oggggo.",
        "..oooo..",
        ".obbbbo.",
        ".ob..bo.",
        ".oo..oo.",
    ),
    palette={"o": INK, "g": "GOBLIN_SKIN_CONST", "e": BLOOD, "b": BARK},
)
```
Add `GOBLIN_SKIN = "#73a946"` to `palette.py` and use it (red eyes via `BLOOD`). Register + run the per-batch loop.

### Task 8 — B5: Undead & special (~9)

Codes (confirm live): `skeleton`, `death_knight`, `vampire`, `hellhound`, `cursed_tree`, `mushmush`, `desert_scorpion`, `sandwarden`, `king_slime`. Add palette constants as needed (e.g. `EMBER = "#ef2929"` for hellhound, `GRAVE = "#5b6770"` for undead).

**Worked example — `skeleton`:**
```python
SKELETON_SPRITE = Sprite(
    rows=(
        "..oooo..",
        ".owwwwo.",
        ".oweewo.",
        ".owwwwo.",
        "..oooo..",
        ".owwwwo.",
        ".ow..wo.",
        ".oo..oo.",
    ),
    palette={"o": INK, "w": BONE, "e": INK},
)
```
Register + run the per-batch loop. After B5, run `uv run python scripts/preview_sprites.py` for a final full-tileset eyeball.

---

## Final verification

- [ ] **Full gate:** `uv run pytest` → 0 errors, 0 warnings, 0 skipped, 100% coverage on `src/`.
- [ ] **Types:** `uv run mypy src/` → clean.
- [ ] **Visual:** `uv run python scripts/preview_sprites.py` shows the whole tileset; run the TUI watch mode for the in-context check.
- [ ] **Fallback intact:** any live code without a curated sprite still renders the procedural blob (no crash, no blank tile).

## Notes

- **No engine changes** anywhere in this plan — all work is data in `palette.py`/`sprites.py` plus the preview script and test updates.
- **Coverage:** new sprites are data covered by the import-time validation loop; the only new test code per batch is the curated-resolution assertion. `palette.py` constants are covered by `test_palette.py` (which scans all uppercase names, so new constants need no new test).
- **Placeholder constants** like `"PINK_CONST"`/`"GOBLIN_SKIN_CONST"` in the B3/B4 worked examples are signposts: replace each with a real `palette.py` constant added in that task. They must NOT survive into committed code — the import-time validator would still pass (the value is a string), but the color would be a literal name, violating the "palette constants only" rule; the reviewer must reject any literal-string palette value.
```
