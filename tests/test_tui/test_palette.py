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
