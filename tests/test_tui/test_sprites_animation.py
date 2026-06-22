from artifactsmmo_cli.tui.sprites import (
    BLANK_SPRITE, FIGHT_HEAD, GATHER_HEAD, PLANNING_SPRITE, PLAYER_SPRITE,
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


def test_heads_valid_8x8():
    validate_sprite("gather_head", GATHER_HEAD)
    validate_sprite("fight_head", FIGHT_HEAD)


def test_grip_points_toward_direction():
    # head to the right (+1,0): handle pixels march right along row 4
    right = grip_overlay(1, 0)
    validate_sprite("grip_right", right)
    assert {c for c, ch in enumerate(right.rows[4]) if ch == "h"} == {5, 6, 7}
    # head up (0,-1): handle pixels march up column 4
    up = grip_overlay(0, -1)
    assert {r for r in range(SPRITE_SIZE) if up.rows[r][4] == "h"} == {1, 2, 3}
    # head down-right (+1,+1): diagonal toward bottom-right corner
    dr = grip_overlay(1, 1)
    assert [(r, c) for r in range(SPRITE_SIZE) for c in range(SPRITE_SIZE)
            if dr.rows[r][c] == "h"] == [(5, 5), (6, 6), (7, 7)]


def test_grip_is_mostly_transparent():
    g = grip_overlay(1, 0)
    opaque = sum(ch != TRANSPARENT for row in g.rows for ch in row)
    assert opaque == 3


def test_planning_bubble_upper_right_and_keeps_player_body():
    # bubble ('p') appears in the top-right; body rows still match the player
    bubble = {(r, c) for r, row in enumerate(PLANNING_SPRITE.rows)
              for c, ch in enumerate(row) if ch == "p"}
    assert bubble and all(r <= 1 and c >= SPRITE_SIZE - 2 for (r, c) in bubble)
    assert PLANNING_SPRITE.rows[6] == PLAYER_SPRITE.rows[6]   # legs unchanged
