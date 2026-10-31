"""The shared art palette: named hex constants and shading ramps."""

import re
from dataclasses import astuple

from artifactsmmo_cli.tui import palette
from artifactsmmo_cli.tui.palette import Ramp

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def _ramps() -> dict[str, Ramp]:
    return {n: v for n, v in vars(palette).items() if n.isupper() and isinstance(v, Ramp)}


def _luminance(color: str) -> float:
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def test_ink_is_near_black():
    assert palette.INK == "#1c1c1c"


def test_all_palette_constants_are_hex_or_ramps():
    names = [n for n in vars(palette) if n.isupper()]
    assert names, "palette must define color constants"
    for name in names:
        value = getattr(palette, name)
        shades = astuple(value) if isinstance(value, Ramp) else (value,)
        for shade in shades:
            assert _HEX.match(shade), f"{name}: {shade!r} is not #rrggbb"


def test_every_ramp_runs_dark_to_light():
    # The shading rule (light upper-left, dark lower-right, tinted outline) only
    # reads if each ramp is strictly ordered by brightness.
    assert _ramps()
    for name, ramp in _ramps().items():
        lum = [_luminance(s) for s in astuple(ramp)]
        assert lum == sorted(lum) and len(set(lum)) == 4, f"{name}: {astuple(ramp)}"


def test_flat_constants_are_their_ramps_mid():
    for name, ramp in _ramps().items():
        flat = name.removesuffix("_RAMP")
        assert getattr(palette, flat) == ramp.mid, flat


def test_no_two_ramps_share_a_shade():
    # reramp() swaps colours BY VALUE, so a shade shared by two ramps would be
    # ambiguous to swap.
    seen: dict[str, str] = {}
    for name, ramp in _ramps().items():
        for shade in astuple(ramp):
            assert shade not in seen, f"{shade} in both {seen.get(shade)} and {name}"
            seen[shade] = name
