"""HalfBlockCompositor: sprite -> 4 half-block Segment rows, memoized."""

from rich.style import Style

from artifactsmmo_cli.tui.half_block import HALF_BLOCK, HalfBlockCompositor
from artifactsmmo_cli.tui.palette import LEAF
from artifactsmmo_cli.tui.sprites import BLANK_SPRITE, GREEN_SLIME_SPRITE, Sprite


def _text(row) -> str:
    return "".join(seg.text for seg in row)


def test_compose_returns_four_rows_of_eight():
    comp = HalfBlockCompositor()
    rows = comp.compose(GREEN_SLIME_SPRITE, "grey50")
    assert len(rows) == 4
    assert all(_text(row) == HALF_BLOCK * 8 for row in rows)


def test_transparent_pixels_show_terrain_both_fg_and_bg():
    comp = HalfBlockCompositor()
    rows = comp.compose(BLANK_SPRITE, "grey50")
    # Blank sprite: every pixel transparent -> fg and bg are the terrain color.
    for row in rows:
        assert all(seg.style == Style.parse("grey50 on grey50") for seg in row)


def test_uniform_row_is_one_merged_run():
    # A flat terrain row is ONE Segment of 8 cells, not 8 one-cell Segments:
    # fewer segments to join and fewer SGR codes written to the terminal.
    comp = HalfBlockCompositor()
    rows = comp.compose(BLANK_SPRITE, "grey50")
    assert all(len(row) == 1 and row[0].text == HALF_BLOCK * 8 for row in rows)


def test_runs_split_exactly_where_the_color_changes():
    sprite = Sprite(rows=("aabbbcc.",) * 8, palette={"a": "#111111", "b": "#222222", "c": "#333333"})
    row = HalfBlockCompositor().compose(sprite, "grey50")[0]
    assert [len(seg.text) for seg in row] == [2, 3, 2, 1]
    assert [str(seg.style) for seg in row] == [
        "#111111 on #111111", "#222222 on #222222", "#333333 on #333333", "grey50 on grey50",
    ]


def test_top_and_bottom_pixels_are_fg_and_bg():
    sprite = Sprite(rows=("aaaaaaaa", "bbbbbbbb") * 4, palette={"a": "#111111", "b": "#222222"})
    row = HalfBlockCompositor().compose(sprite, "grey50")[0]
    assert row[0].style == Style.parse("#111111 on #222222")


def test_opaque_pixel_uses_palette_color():
    comp = HalfBlockCompositor()
    rows = comp.compose(GREEN_SLIME_SPRITE, "grey50")
    styles = [str(seg.style) for row in rows for seg in row]
    # The slime body uses the LEAF palette color (hex), not the ANSI name.
    assert any(LEAF in style for style in styles)


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
    assert a[0][0].style == Style.parse("grey50 on grey50")
    assert b[0][0].style == Style.parse("grey15 on grey15")
