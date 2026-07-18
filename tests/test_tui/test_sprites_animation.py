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
    # Each frame carries a doubled dark swirl inside a larger light body.
    for left, right in ((CLOUD_LEFT_A, CLOUD_RIGHT_A), (CLOUD_LEFT_B, CLOUD_RIGHT_B)):
        cells = [ch for s in (left, right) for row in s.rows for ch in row]
        dark = sum(ch == "d" for ch in cells)
        light = sum(ch == "l" for ch in cells)
        assert dark >= 6 and light >= dark
