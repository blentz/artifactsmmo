from dataclasses import astuple

from artifactsmmo_cli.tui.palette import CLOUD_RAMP
from artifactsmmo_cli.tui.sprites import (
    AXE,
    AXE_HEAD,
    AXE_NE,
    BLANK_SPRITE,
    CLOUD_LEFT_A,
    CLOUD_LEFT_B,
    CLOUD_RIGHT_A,
    CLOUD_RIGHT_B,
    FIGHT_HEAD,
    FIGHT_NE,
    HAMMER,
    HAMMER_HEAD,
    HAMMER_NE,
    PICKAXE,
    PICKAXE_HEAD,
    PICKAXE_NE,
    PLANNING_SPRITE,
    PLAYER_SPRITE,
    SPRITE_SIZE,
    SWORD,
    TRANSPARENT,
    Sprite,
    ToolHeads,
    gather_head,
    grip_overlay,
    oriented_head,
    overlay_sprites,
    rot90cw,
    validate_sprite,
)


def test_overlay_top_pixel_wins_else_base_shows():
    base = PLAYER_SPRITE
    top = Sprite(rows=("Z.......",) + ("........",) * 7, palette={"Z": "#ff0000"})
    merged = overlay_sprites(base, top)
    validate_sprite("merged", merged)
    assert merged.rows[0][0] == "Z"                       # top wins where opaque
    assert merged.rows[0][1] == base.rows[0][1]           # base shows where top transparent
    assert merged.palette["Z"] == "#ff0000"               # top palette merged in
    assert merged.palette["o"] == base.palette["o"]       # base palette preserved


def _pixel_colors(sprite: Sprite) -> list[list[str | None]]:
    return [[None if ch == TRANSPARENT else sprite.palette[ch] for ch in row] for row in sprite.rows]


def test_overlay_key_collision_never_recolours_the_base():
    # The swung sword uses key 'h' (BARK handle); the vampire uses 'h' for its
    # hair. Merging palettes key-for-key repainted the hair in BARK every swing
    # frame. Every pixel must keep the colour of the sprite it came from.
    base = Sprite(rows=("hhhhhhhh",) * 8, palette={"h": "#111111"})
    top = Sprite(rows=("h.......",) + ("........",) * 7, palette={"h": "#222222"})
    merged = overlay_sprites(base, top)
    validate_sprite("merged", merged)
    colors = _pixel_colors(merged)
    assert colors[0][0] == "#222222"                      # top pixel keeps top colour
    assert colors[0][1] == "#111111"                      # base pixels keep base colour
    assert colors[7][7] == "#111111"


def test_overlay_shared_key_with_same_colour_is_kept():
    base = Sprite(rows=("hhhhhhhh",) * 8, palette={"h": "#111111"})
    top = Sprite(rows=("h.......",) + ("........",) * 7, palette={"h": "#111111"})
    assert overlay_sprites(base, top).rows == base.rows


def test_overlay_with_blank_top_is_base_pixels():
    merged = overlay_sprites(PLAYER_SPRITE, BLANK_SPRITE)
    assert merged.rows == PLAYER_SPRITE.rows


def test_tool_heads_valid_8x8():
    for name, s in [("axe", AXE_HEAD), ("pickaxe", PICKAXE_HEAD),
                    ("hammer", HAMMER_HEAD), ("sword", FIGHT_HEAD)]:
        validate_sprite(name, s)


def test_hammer_has_no_light_grey():
    # hammer = pickaxe minus all light-grey ('l') pixels
    assert all("l" not in row for row in HAMMER_HEAD.rows)
    assert any("m" in row for row in HAMMER_HEAD.rows)


def test_pickaxe_has_light_grey_triangles_both_sides():
    cols = {c for r, row in enumerate(PICKAXE_HEAD.rows)
            for c, ch in enumerate(row) if ch == "l"}
    assert any(c < SPRITE_SIZE // 2 for c in cols)        # left triangle
    assert any(c >= SPRITE_SIZE // 2 for c in cols)       # right triangle


def test_sword_tip_is_light_grey_blade_medium():
    assert "l" in FIGHT_HEAD.rows[0]                       # light-grey tip
    assert "m" in FIGHT_HEAD.rows[3] and "l" not in FIGHT_HEAD.rows[3]  # medium blade


def test_gather_head_selects_by_skill():
    assert gather_head("woodcutting") is AXE
    assert gather_head("mining") is PICKAXE
    assert gather_head("fishing") is PICKAXE               # fallback
    assert gather_head(None) is PICKAXE                    # fallback


def test_grip_haft_is_two_pixels():
    # haft shortened 15%: grip drops from 3px to 2px
    g = grip_overlay(1, 0)
    assert sum(ch != TRANSPARENT for row in g.rows for ch in row) == 2
    assert {c for c, ch in enumerate(g.rows[4]) if ch == "h"} == {5, 6}


def test_planning_bubble_upper_right_and_keeps_player_body():
    # bubble ('p') appears in the top-right; body rows still match the player
    bubble = {(r, c) for r, row in enumerate(PLANNING_SPRITE.rows)
              for c, ch in enumerate(row) if ch == "p"}
    assert bubble and all(r <= 1 and c >= SPRITE_SIZE - 2 for (r, c) in bubble)
    assert PLANNING_SPRITE.rows[6] == PLAYER_SPRITE.rows[6]   # legs unchanged


def test_rot90cw_four_turns_is_identity():
    s = AXE_HEAD
    r = s
    for _ in range(4):
        r = rot90cw(r)
    assert r.rows == s.rows


def test_rot90cw_moves_top_row_to_right_column():
    # a sprite with only its top row filled -> after one CW turn only the right column is filled
    s = Sprite(rows=("mmmmmmmm",) + ("........",) * 7, palette={"m": "#888a85"})
    r = rot90cw(s)
    assert all(row[7] == "m" for row in r.rows)
    assert all(row[:7] == "......." for row in r.rows)


def test_oriented_head_cardinals_and_diagonals():
    t = AXE
    assert oriented_head(t, 0, -1).rows == AXE_HEAD.rows               # up = base
    assert oriented_head(t, 1, 0).rows == rot90cw(AXE_HEAD).rows       # right = 1 CW
    assert oriented_head(t, 0, 1).rows == rot90cw(rot90cw(AXE_HEAD)).rows   # down = 2
    assert oriented_head(t, -1, 0).rows == rot90cw(rot90cw(rot90cw(AXE_HEAD))).rows  # left = 3
    assert oriented_head(t, 1, -1).rows == AXE_NE.rows                 # NE = ne base
    assert oriented_head(t, 1, 1).rows == rot90cw(AXE_NE).rows         # SE = ne 1 CW
    assert oriented_head(t, -1, 1).rows == rot90cw(rot90cw(AXE_NE)).rows            # SW = ne 2
    assert oriented_head(t, -1, -1).rows == rot90cw(rot90cw(rot90cw(AXE_NE))).rows  # NW = ne 3


def test_ne_heads_and_bundles_valid():
    for name, s in [("axe_ne", AXE_NE), ("pick_ne", PICKAXE_NE),
                    ("ham_ne", HAMMER_NE), ("sword_ne", FIGHT_NE)]:
        validate_sprite(name, s)
    assert ToolHeads(AXE_HEAD, AXE_NE) == AXE
    assert ToolHeads(PICKAXE_HEAD, PICKAXE_NE) == PICKAXE
    assert ToolHeads(HAMMER_HEAD, HAMMER_NE) == HAMMER
    assert ToolHeads(FIGHT_HEAD, FIGHT_NE) == SWORD


def test_cloud_halves_valid_and_conjoined():
    halves = (CLOUD_LEFT_A, CLOUD_RIGHT_A, CLOUD_LEFT_B, CLOUD_RIGHT_B)
    for i, sprite in enumerate(halves):
        validate_sprite(f"cloud{i}", sprite)
    # The seam conjoins: across the body rows the left half fills its right edge
    # (col 7) and the right half its left edge (col 0) -- no gap between tiles.
    for left, right in ((CLOUD_LEFT_A, CLOUD_RIGHT_A), (CLOUD_LEFT_B, CLOUD_RIGHT_B)):
        for y in range(1, 7):
            assert left.rows[y][7] != "." and right.rows[y][0] != "."


def _cloud(left: Sprite, right: Sprite) -> list[str]:
    return [a + b for a, b in zip(left.rows, right.rows, strict=True)]


def test_cloud_is_shaded_from_the_cloud_ramp():
    for left, right in ((CLOUD_LEFT_A, CLOUD_RIGHT_A), (CLOUD_LEFT_B, CLOUD_RIGHT_B)):
        assert set(left.palette.values()) | set(right.palette.values()) == set(astuple(CLOUD_RAMP))
        cells = "".join(_cloud(left, right))
        # light (H) and shadow (D) both present around a mid-tone body (l)
        assert {"o", "D", "l", "H"} <= set(cells)
        assert cells.count("l") > cells.count("H") and cells.count("l") > cells.count("D")


def test_cloud_shimmer_is_a_growing_ellipsis_and_nothing_else():
    a = _cloud(CLOUD_LEFT_A, CLOUD_RIGHT_A)
    b = _cloud(CLOUD_LEFT_B, CLOUD_RIGHT_B)
    dots_a = {(r, c) for r, row in enumerate(a) for c, ch in enumerate(row) if ch == "d"}
    dots_b = {(r, c) for r, row in enumerate(b) for c, ch in enumerate(row) if ch == "d"}
    # frame A: "..", frame B: "..." -- the same row, one more dot to the right
    assert len(dots_a) == 2 and len(dots_b) == 3 and dots_a < dots_b
    assert len({r for r, _ in dots_b}) == 1
    # outside the dots the two frames are the same cloud
    for (r, c) in dots_b:
        a[r] = a[r][:c] + "l" + a[r][c + 1:]
        b[r] = b[r][:c] + "l" + b[r][c + 1:]
    assert a == b


def test_cloud_trail_bubble_leads_to_the_planning_bubble():
    # The cloud's lower-left corner pixel is the trail bubble, coloured like the
    # small bubble painted beside the player's head (which sits diagonally below it).
    assert CLOUD_LEFT_A.rows[7][0] != TRANSPARENT and CLOUD_LEFT_A.rows[7][1] == TRANSPARENT
    assert CLOUD_LEFT_A.rows[6][0] == TRANSPARENT
    assert PLANNING_SPRITE.palette["p"] in astuple(CLOUD_RAMP)
