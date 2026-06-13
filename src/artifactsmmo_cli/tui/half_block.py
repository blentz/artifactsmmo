"""Composites 8x8 sprites into half-block character rows for the map pane.

Each char cell is two vertical pixels: '▀' with fg = top pixel, bg = bottom
pixel. An 8px-tall sprite becomes 4 char-rows. Transparent pixels resolve to
the terrain color so sprites composite over terrain. Results are memoized by
(rows, palette, terrain_color) since the art is static.
"""

from rich.text import Text

from artifactsmmo_cli.tui.sprites import SPRITE_SIZE, TRANSPARENT, Sprite

HALF_BLOCK = "▀"  # ▀ UPPER HALF BLOCK


class HalfBlockCompositor:
    """Turns sprites into cached tuples of 4 Rich Text rows."""

    def __init__(self) -> None:
        self._cache: dict[tuple[object, ...], tuple[Text, Text, Text, Text]] = {}

    def compose(self, sprite: Sprite, terrain_color: str) -> tuple[Text, Text, Text, Text]:
        key = (sprite.rows, tuple(sorted(sprite.palette.items())), terrain_color)
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

    def _build(self, sprite: Sprite, terrain_color: str) -> tuple[Text, Text, Text, Text]:
        out: list[Text] = []
        for top in range(0, SPRITE_SIZE, 2):
            line = Text(no_wrap=True, overflow="crop")
            for col in range(SPRITE_SIZE):
                fg = self._pixel_color(sprite, top, col, terrain_color)
                bg = self._pixel_color(sprite, top + 1, col, terrain_color)
                line.append(HALF_BLOCK, style=f"{fg} on {bg}")
            out.append(line)
        return (out[0], out[1], out[2], out[3])
