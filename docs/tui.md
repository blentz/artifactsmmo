# Live TUI watcher

Run the player with a live terminal UI that shows its state without changing
its behavior:

```sh
uv run artifactsmmo play <name> --learn --tui
```

Quit with `q` or `Ctrl+C`.

## Layout

A four-pane Textual interface (3×3 grid): status and inventory stacked on the
left, a large map spanning the right, a full-width log strip along the bottom.

```
┌────────┬────────────────────────┐
│ Status │                        │
│ L3 HP  │   Map — 8×8 sprite     │
│ XP     │   tiles, player-       │
├────────┤   centered             │
│ Inv    │                        │
├────────┴────────────────────────┤
│ Log  21:08 c2 Fight          ok │
└──────────────────────────────────┘
```

## Sprite map

The map renders each tile as an **8×8 sprite** drawn with Unicode half-block
characters (`▀` — two color pixels per cell), centered on the player. Sprites
are outline-only pixel art composited over the terrain color, defined as pure
data in `tui/palette.py` (shared hex palette) and `tui/sprites.py` (the
tileset):

- the player, monsters, NPCs, structures (bank, grand exchange, workshop,
  taskmaster), resources (tree / ore / fish / herb), and doors.
- Any code the API exposes without a curated sprite falls back to a
  deterministic, category-tinted silhouette — so the map never breaks as the
  game adds content; new sprites just ship as more data.

Preview the whole tileset in the terminal without launching the game:

```sh
uv run python scripts/preview_sprites.py
```
