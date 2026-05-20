# Typed map glyphs for the TUI map

Date: 2026-05-20
Status: Approved (design)

## Goal

Make the TUI map legible by giving each content category a distinct, typed glyph
and a category color:

- **NPCs** → an uppercase letter identifying the NPC (e.g. `A` = archaeologist).
- **Monsters** → a lowercase letter identifying the creature/family (e.g. `s` = slime, `c` = chicken).
- **Structures** (bank, grand_exchange, workshop, tasks_master) → box-drawing glyphs.
- **Doors** (map transition tiles) → `+`.

Each category renders in one assigned color so glyphs that happen to share a
letter across categories (e.g. tailor `T` vs the woodcutting-resource `T`) stay
visually distinct.

## Data facts (from the live API)

- `MapContentType` values: `bank`, `grand_exchange`, `monster`, `npc`,
  `resource`, `tasks_master`, `workshop`.
- The map is single-tile content — there are **no wall/room/building footprints**.
  Structures occupy one tile each, so they render as one box-drawing glyph, not
  connected ANSI walls.
- NPC codes (6): archaeologist, cultist_wizard, rune_vendor, sandwhisper_trader,
  tailor, tasks_trader.
- Monster codes (30): blue/green/red/yellow/king_slime, chicken, cow, cyclops,
  cultist_acolyte, cursed_tree, death_knight, desert_scorpion, flying_snake,
  goblin, goblin_wolfrider, hellhound, highwayman, imp, mushmush, ogre, orc,
  owlbear, pig, sand_snake, sandwarden, sheep, skeleton, spider, vampire, wolf.
- `_load_maps` currently handles monster/resource/bank/tasks_master/npc/workshop
  but **not** `grand_exchange` — it must be added.

## Category colors

| Category   | Color           |
|------------|-----------------|
| player     | `bright_yellow` (unchanged) |
| npc        | `cyan`          |
| monster    | `red`           |
| structure  | `white`         |
| door       | `magenta`       |
| resource   | per-skill, **unchanged** (green/yellow/blue/magenta) — out of scope |

## Glyph tables (curated, in `glyphs.py`)

### NPCs — uppercase, cyan (`NPC_GLYPHS`)

| code               | glyph |
|--------------------|-------|
| archaeologist      | `A`   |
| cultist_wizard     | `C`   |
| rune_vendor        | `R`   |
| sandwhisper_trader | `S`   |
| tailor             | `T`   |
| tasks_trader       | `K`   |

### Monsters — lowercase, red (`MONSTER_GLYPHS`)

Families collapse to one letter; otherwise each creature gets a distinct letter.

| code              | glyph | | code            | glyph |
|-------------------|-------|-|-----------------|-------|
| blue_slime        | `s`   | | imp             | `i`   |
| green_slime       | `s`   | | mushmush        | `m`   |
| red_slime         | `s`   | | ogre            | `r`   |
| yellow_slime      | `s`   | | orc             | `q`   |
| king_slime        | `s`   | | owlbear         | `b`   |
| chicken           | `c`   | | pig             | `p`   |
| cow               | `o`   | | sand_snake      | `n`   |
| cyclops           | `y`   | | sandwarden      | `l`   |
| cultist_acolyte   | `u`   | | sheep           | `e`   |
| cursed_tree       | `t`   | | skeleton        | `k`   |
| death_knight      | `d`   | | spider          | `a`   |
| desert_scorpion   | `x`   | | vampire         | `v`   |
| flying_snake      | `f`   | | wolf            | `w`   |
| goblin            | `g`   | | highwayman      | `j`   |
| goblin_wolfrider  | `g`   | | hellhound       | `h`   |

All 25 distinct letters are unique (slime ×5 → `s`, goblin ×2 → `g`).

### Structures — box-drawing, white (`STRUCTURE_GLYPHS`)

| code           | glyph |
|----------------|-------|
| bank           | `╣`   |
| grand_exchange | `╠`   |
| workshop       | `╬`   |
| tasks_master   | `╤`   |

### Door — `+`, magenta

Transition tiles render `+` (replaces the old `>`).

## Fallback for unknown codes

The API can add NPCs/monsters. `glyphs.py` exposes resolver functions:

- `npc_glyph(code) -> (glyph, color)`: curated `NPC_GLYPHS` if present, else the
  uppercased first character of `code`; color always `cyan`.
- `monster_glyph(code) -> (glyph, color)`: curated `MONSTER_GLYPHS` if present,
  else the lowercased first character of `code`; color always `red`.

Structures and doors are a fixed closed set; an unknown structure code (none
expected) falls back to a generic box glyph `▢` white.

## Rendering changes

`map_pane._build_tile_index` already iterates per code, so it stores the
per-code resolved glyph instead of a single shared `CONTENT_GLYPHS["npc"]` /
`["monster"]`:

- NPC tiles → `npc_glyph(code)`
- Monster tiles → `monster_glyph(code)` (monsters still indexed last so they win
  shared tiles, preserving current precedence)
- bank / grand_exchange / workshop / tasks_master → `STRUCTURE_GLYPHS[...]`
- transition tiles → door glyph `+`
- resources → unchanged per-skill glyphs

`game_data._load_maps` gains a branch capturing `grand_exchange` into a new
`_grand_exchange_location: tuple[int,int] | None`, and `_build_tile_index`
indexes it.

## Legend

The header legend cannot list 30 monsters. Replace the long per-glyph legend
with a compact category key:

` (x,y)  @ you  A-Z npc  a-z monster  ╬ structure  + door  T/*/~/% resource`

(rendered no_wrap/crop, as already implemented). The full code→letter mapping
lives in `glyphs.py` and this spec.

## Components / files

- `src/artifactsmmo_cli/tui/glyphs.py` — replace `CONTENT_GLYPHS` with
  `NPC_GLYPHS`, `MONSTER_GLYPHS`, `STRUCTURE_GLYPHS`, door + resource constants,
  category colors, and `npc_glyph` / `monster_glyph` resolvers.
- `src/artifactsmmo_cli/tui/widgets/map_pane.py` — `_build_tile_index` uses the
  resolvers + structure/door glyphs; `_render_viewport` legend updated; index
  grand_exchange.
- `src/artifactsmmo_cli/ai/game_data.py` — `_load_maps` captures
  `grand_exchange`; add `_grand_exchange_location` field.
- `tests/test_tui/test_glyphs.py`, `tests/test_tui/test_map_pane.py`,
  `tests/test_ai/test_game_data.py` — coverage below.

## Testing (0 errors, 0 warnings, 0 skipped, 100% on changed code)

- `npc_glyph`: curated hit (`archaeologist→('A','cyan')`); fallback for unknown
  (`foo_npc→('F','cyan')`).
- `monster_glyph`: family collapse (all five slimes → `('s','red')`); curated
  singles; fallback for unknown (`foo_beast→('f','red')`).
- Structure glyphs map bank/grand_exchange/workshop/tasks_master to their box
  glyphs; unknown structure → generic box.
- `map_pane`: NPC tile renders `A`; monster tile renders `s`; bank tile renders
  `╣`; transition tile renders `+`; resources still render `T`/`*`/`~`/`%`.
- `game_data._load_maps`: a `grand_exchange` tile sets
  `_grand_exchange_location`.

## Out of scope

- Resource glyphs/colors (unchanged).
- Multi-tile walls / room outlines (no data).
- Per-structure unique colors (all structures share `white`).
