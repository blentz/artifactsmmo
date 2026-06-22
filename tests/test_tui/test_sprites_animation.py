from artifactsmmo_cli.tui.sprites import (
    GATHER_SWING_FRAMES, FIGHT_SWING_FRAMES, PLANNING_SPRITE,
    PLAYER_SPRITE, validate_sprite, SPRITE_SIZE,
)


def test_frames_nonempty_and_valid_8x8():
    assert len(GATHER_SWING_FRAMES) >= 3
    assert len(FIGHT_SWING_FRAMES) == len(GATHER_SWING_FRAMES)
    for i, s in enumerate(GATHER_SWING_FRAMES + FIGHT_SWING_FRAMES + (PLANNING_SPRITE,)):
        validate_sprite(f"anim{i}", s)           # raises if not 8x8 / bad key


def test_gather_arc_is_on_the_right_fight_on_the_left():
    # the tool pixel ('t') sits in the right half for gather, left half for fight
    def tool_cols(sprite):
        return {c for row in sprite.rows for c, ch in enumerate(row) if ch == "t"}
    g = set().union(*[tool_cols(s) for s in GATHER_SWING_FRAMES])
    f = set().union(*[tool_cols(s) for s in FIGHT_SWING_FRAMES])
    assert min(g) >= SPRITE_SIZE // 2            # gather tool on right half
    assert max(f) < SPRITE_SIZE // 2             # fight tool on left half


def test_planning_bubble_upper_right_and_keeps_player_body():
    # bubble ('p') appears in the top-right; body rows still match the player
    bubble = {(r, c) for r, row in enumerate(PLANNING_SPRITE.rows)
              for c, ch in enumerate(row) if ch == "p"}
    assert bubble and all(r <= 1 and c >= SPRITE_SIZE - 2 for (r, c) in bubble)
    assert PLANNING_SPRITE.rows[6] == PLAYER_SPRITE.rows[6]   # legs unchanged
