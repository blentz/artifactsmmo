# Improved Sprites: Outline-Only Tileset

**Date:** 2026-06-13
**Status:** Design — pending user review
**Topic:** Upgrade the TUI map sprites from flat 1–2-color art to a cohesive outline-only style, and replace the procedural fallback for the real roster with hand-drawn sprites.

## Goal

The half-block sprite engine shipped with only 6 curated sprites; the ~40 other entity codes render as identical procedural blobs. Establish a single art style (outline-only), define a shared palette, then draw the full live roster in that style so the map reads as a real tileset. Pure data work — no engine changes.

## Decisions (locked during brainstorming)

| Decision | Choice |
|---|---|
| Thrust | Both, style-led — set the style on showcase sprites, then apply roster-wide |
| Art style | **Outline-only**: near-black silhouette ring + flat interior fill + minimal accents |
| Outline color | Near-black `#1c1c1c` (universal), reused as the default eye color |
| Palette | Shared named **hex** palette, reused across sprites for cohesion (not ad-hoc per sprite) |
| Size / engine | Unchanged — 8×8, existing `Sprite` + `HalfBlockCompositor` (hex works through Rich) |
| Preview tool | Add reusable `scripts/preview_sprites.py` (terminal contact sheet) |
| Review | Per-batch colored contact sheet, user approves before commit |

## Art style specification

- **Silhouette ring:** every sprite has a 1-px near-black (`#1c1c1c`) outline tracing its shape against the floor color.
- **Flat fill:** interior is a single base color per region (no shading ramps — that was the rejected option B/C).
- **Accents:** small high-contrast details only where they aid recognition — eyes, beak, ore specks, gold band, door.
- **Transparency:** `.` pixels show terrain, exactly as today; sprites read as objects sitting on the floor.
- **Validated showcase:** player, green_slime, chicken, bank, resource_mining, resource_woodcutting were drawn in this style and confirmed to read across humanoid / blob / bird / building / rock / tree shapes.

## Shared palette

A new pure-data module `src/artifactsmmo_cli/tui/palette.py` holds named hex constants for the art ramp, imported by `sprites.py`. Example families (final values tuned during authoring):

- Outline/ink: `INK = "#1c1c1c"`
- Greens (foliage, slimes): `LEAF`, `MOSS`
- Stone/metal (rocks, structures): `STONE`, `STEEL`
- Golds (treasure, beaks, sand): `GOLD`, `AMBER`
- Browns (wood, hide): `BARK`, `HIDE`
- Reds (combs, blood, fire): `BLOOD`, `EMBER`
- Flesh/whites: `BONE`, `SKIN`
- plus per-need accents

`palette.py` is the single source of art colors. `glyphs.py` keeps the existing ANSI terrain colors (`WALKABLE_COLOR`, `UNMAPPED_COLOR`) and the fallback category colors — the procedural fallback is unchanged and still serves any uncurated code.

> One-class-per-file: `palette.py` is a pure-data module (named constants) — exempt, same as `glyphs.py`/`sprites.py`.

## Roster

Authoritative source is live `GameData` (`all_monster_locations`, `npc_locations`, resource/structure accessors) — per the "use API data or fail" rule, the implementation enumerates codes from `GameData`, not a hardcoded list. Current known codes (≈47 sprites):

- **Redo (6):** player, green_slime, bank, door, resource_woodcutting, archaeologist — in the new style for cohesion.
- **Structures (3):** grand_exchange, workshop, tasks_master.
- **Resources (3):** resource_mining, resource_fishing, resource_alchemy.
- **NPCs (5):** cultist_wizard, rune_vendor, sandwhisper_trader, tailor, tasks_trader.
- **Monsters (~30):** blue_slime, red_slime, yellow_slime, king_slime, chicken, cow, pig, sheep, wolf, owlbear, spider, flying_snake, sand_snake, goblin, goblin_wolfrider, orc, ogre, cyclops, imp, highwayman, cultist_acolyte, skeleton, death_knight, vampire, hellhound, cursed_tree, mushmush, desert_scorpion, sandwarden, … (drawn from the live monster set).

Any code present in `GameData` but not yet drawn keeps using the procedural fallback — the map never breaks, it just upgrades incrementally.

## Batching

Each batch: author sprites → render colored contact sheet in the browser companion → user approves → commit. Order:

- **B1 — Foundation:** `palette.py`; redo the 6 existing; 3 structures; 3 resources. (12 sprites)
- **B2 — NPCs:** the 5 remaining NPCs (humanoid template). (5)
- **B3 — Slimes & beasts:** slime color-variants + farm/animal monsters (chicken redo, cow, pig, sheep, wolf, owlbear, spider, snakes). (~10)
- **B4 — Humanoid monsters:** goblin(+wolfrider), orc, ogre, cyclops, imp, highwayman, cultist_acolyte. (~8)
- **B5 — Undead & special:** skeleton, death_knight, vampire, hellhound, cursed_tree, mushmush, desert_scorpion, sandwarden, king_slime. (~9)

Batches are independent (additive data); B1 first because it sets the palette every later batch imports.

## Components / file changes

- **Create** `src/artifactsmmo_cli/tui/palette.py` — shared hex art-color constants (pure data).
- **Modify** `src/artifactsmmo_cli/tui/sprites.py` — import palette; redraw the 6 existing sprites in outline style using palette colors; add new sprites to `MONSTER_SPRITES`/`NPC_SPRITES`/`STRUCTURE_SPRITES`/`RESOURCE_SPRITES` and `ALL_CURATED_SPRITES`.
- **Create** `scripts/preview_sprites.py` — renders all curated sprites as a Rich half-block contact sheet to the terminal (same compositor/colors as the TUI). Outside `src/`, so outside the coverage gate.
- **No changes** to `half_block.py`, `sprite_registry.py`, `map_pane.py`, `app.py`.

## Testing

- The existing parametrized integrity test in `tests/test_tui/test_sprites.py` iterates `ALL_CURATED_SPRITES`, asserting every sprite is 8×8 with all palette keys defined. Each added sprite is auto-validated by adding it to its category dict + `ALL_CURATED_SPRITES`. No per-sprite test code; the import-time validation loop keeps coverage at 100%.
- **Required test updates (B1):** some current tests assert literal Rich color-name strings tied to the old flat palette:
  - `tests/test_tui/test_half_block.py::test_opaque_pixel_uses_palette_color` asserts `"green"` appears in a `GREEN_SLIME_SPRITE` span.
  - `tests/test_tui/test_map_pane.py::test_monster_sprite_in_view` asserts `"green"` appears in the rendered output (green_slime at (2,0)).
  When the slime is redrawn with hex palette colors, `"green"` is no longer present. These assertions must be updated to the new palette value (e.g. the `LEAF` hex) or, better, asserted against the sprite's own palette value rather than a hardcoded literal — so they stay robust to future color tweaks.
- `scripts/preview_sprites.py` is a dev tool outside `src/`; not coverage-gated. A smoke import/run is optional, not required.
- Full gate per batch: `uv run pytest` → 0 errors, 0 warnings, 0 skipped, 100% coverage; `uv run mypy src/` clean.

## Out of scope (YAGNI)

- Shading/outline+shading styles (rejected — outline-only chosen).
- Larger sprite sizes / engine changes.
- Animation, directional facing (deferred from the prior feature).
- Drawing codes that don't appear in live `GameData`.
