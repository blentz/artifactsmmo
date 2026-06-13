"""HalfBlockCompositor: sprite -> 4 half-block Text rows, memoized."""

from artifactsmmo_cli.tui.half_block import HALF_BLOCK, HalfBlockCompositor
from artifactsmmo_cli.tui.sprites import BLANK_SPRITE, GREEN_SLIME_SPRITE


def test_compose_returns_four_rows_of_eight():
    comp = HalfBlockCompositor()
    rows = comp.compose(BLANK_SPRITE, "grey50")
    assert len(rows) == 4
    assert all(row.plain == HALF_BLOCK * 8 for row in rows)


def test_transparent_pixels_show_terrain_both_fg_and_bg():
    comp = HalfBlockCompositor()
    rows = comp.compose(BLANK_SPRITE, "grey50")
    # Blank sprite: every pixel transparent -> fg and bg are the terrain color.
    for row in rows:
        assert all(span.style == "grey50 on grey50" for span in row.spans)


def test_opaque_pixel_uses_palette_color():
    comp = HalfBlockCompositor()
    rows = comp.compose(GREEN_SLIME_SPRITE, "grey50")
    styles = [span.style for row in rows for span in row.spans]
    # The slime body is green; at least one half-block carries a green pixel.
    assert any("green" in style for style in styles)


def test_memoized_same_args_returns_identical_object():
    comp = HalfBlockCompositor()
    a = comp.compose(GREEN_SLIME_SPRITE, "grey50")
    b = comp.compose(GREEN_SLIME_SPRITE, "grey50")
    assert a is b


def test_different_terrain_color_is_a_distinct_entry():
    comp = HalfBlockCompositor()
    a = comp.compose(BLANK_SPRITE, "grey50")
    b = comp.compose(BLANK_SPRITE, "grey15")
    assert a is not b
    assert a[0].spans[0].style == "grey50 on grey50"
    assert b[0].spans[0].style == "grey15 on grey15"
