"""Composites 8x8 sprites into half-block character rows for the map pane.

Each char cell is two vertical pixels: '▀' with fg = top pixel, bg = bottom
pixel. An 8px-tall sprite becomes 4 char-rows. Transparent pixels resolve to
the terrain color so sprites composite over terrain. Results are memoized by
(rows, palette, terrain_color) since the art is static.

Rows are emitted as ready-styled Rich Segments, not Text: the map pane joins
them straight into Textual Strips. Routing a line of per-cell Text spans
through Console.render_lines cost ~75% of a full-viewport repaint (profiled),
which is what made a glide frame re-render expensive. Adjacent cells with the
same colors are merged into one Segment, so a flat terrain row is one run —
fewer segments for Textual to process and fewer SGR codes written to the
terminal.
"""

from rich.segment import Segment
from rich.style import Style

from artifactsmmo_cli.tui.sprites import SPRITE_SIZE, TRANSPARENT, Sprite

HALF_BLOCK = "▀"  # ▀ UPPER HALF BLOCK

TileRow = tuple[Segment, ...]
TileRows = tuple[TileRow, TileRow, TileRow, TileRow]


class HalfBlockCompositor:
    """Turns sprites into cached tuples of 4 half-block Segment rows."""

    def __init__(self) -> None:
        self._cache: dict[tuple[object, ...], TileRows] = {}

    def compose(self, sprite: Sprite, terrain_color: str) -> TileRows:
        key = (sprite.key, terrain_color)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        built = self._build(sprite, terrain_color)
        self._cache[key] = built
        return built

    @staticmethod
    def _pixel_color(sprite: Sprite, row: int, col: int, terrain_color: str) -> str:
        ch = sprite.rows[row][col]
        if ch == TRANSPARENT:
            return terrain_color
        return sprite.palette[ch]

    def _build(self, sprite: Sprite, terrain_color: str) -> TileRows:
        out: list[TileRow] = []
        for top in range(0, SPRITE_SIZE, 2):
            cells = [
                (self._pixel_color(sprite, top, col, terrain_color),
                 self._pixel_color(sprite, top + 1, col, terrain_color))
                for col in range(SPRITE_SIZE)
            ]
            runs: list[Segment] = []
            start = 0
            for col in range(1, SPRITE_SIZE + 1):
                if col == SPRITE_SIZE or cells[col] != cells[start]:
                    fg, bg = cells[start]
                    # Style.parse is lru-cached, so equal colors share one Style.
                    runs.append(Segment(HALF_BLOCK * (col - start), Style.parse(f"{fg} on {bg}")))
                    start = col
            out.append(tuple(runs))
        return (out[0], out[1], out[2], out[3])
