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
