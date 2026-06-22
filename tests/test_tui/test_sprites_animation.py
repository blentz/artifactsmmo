from artifactsmmo_cli.tui.sprites import (
    AXE_HEAD, PICKAXE_HEAD, HAMMER_HEAD, FIGHT_HEAD, gather_head,
    BLANK_SPRITE, PLANNING_SPRITE, PLAYER_SPRITE,
    SPRITE_SIZE, Sprite, TRANSPARENT, grip_overlay, overlay_sprites, validate_sprite,
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
    assert gather_head("woodcutting") is AXE_HEAD
    assert gather_head("mining") is PICKAXE_HEAD
    assert gather_head("fishing") is PICKAXE_HEAD          # fallback
    assert gather_head(None) is PICKAXE_HEAD               # fallback


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
