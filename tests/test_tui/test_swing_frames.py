from artifactsmmo_cli.tui.swing_frames import (
    Mode, current_mode, glide_index, swing_frame_index, swing_overlay,
)
from artifactsmmo_cli.tui.sprites import HAMMER_HEAD, PICKAXE_HEAD


def test_planning_overrides_everything():
    assert current_mode("gather", True, 0.1, 5.0) == Mode.PLANNING


def test_kind_within_cooldown():
    assert current_mode("gather", False, 1.0, 5.0) == Mode.GATHER_SWING
    assert current_mode("fight", False, 1.0, 5.0) == Mode.FIGHT_SWING
    assert current_mode("move", False, 1.0, 5.0) == Mode.GLIDE


def test_idle_after_cooldown_or_rest():
    assert current_mode("gather", False, 6.0, 5.0) == Mode.IDLE   # cooldown elapsed
    assert current_mode("rest", False, 1.0, 5.0) == Mode.IDLE
    assert current_mode("gather", False, 1.0, 0.0) == Mode.IDLE   # no cooldown


def test_swing_loops_and_clamps_into_range():
    # 5 frames, 0.8s sweep -> 0.16s/frame
    assert swing_frame_index(0.0, 5, 0.8) == 0
    assert swing_frame_index(0.16, 5, 0.8) == 1
    assert swing_frame_index(0.8, 5, 0.8) == 0           # wraps to next sweep
    assert 0 <= swing_frame_index(123.4, 5, 0.8) < 5      # always in range


def test_swing_index_degenerate_sweep_is_zero():
    assert swing_frame_index(1.0, 5, 0.0) == 0


def test_glide_reaches_last_frame_at_arrive_fraction():
    # arrive_fraction 0.9 of a 10s cooldown -> done by t=9s
    assert glide_index(0.0, 10.0, 5) == 0
    assert glide_index(9.0, 10.0, 5) == 4                 # last frame (index 4)
    assert glide_index(10.0, 10.0, 5) == 4               # clamps past the end
    assert glide_index(4.5, 10.0, 5) == 2                 # halfway -> middle frame


def test_glide_single_frame_is_zero():
    assert glide_index(5.0, 10.0, 1) == 0


def test_glide_zero_duration_window_returns_last_frame():
    # duration 0 -> window 0 -> the `window <= 0` guard returns the last frame
    assert glide_index(1.0, 0.0, 5) == 4
    # arrive_fraction 0 also collapses the window
    assert glide_index(1.0, 10.0, 5, arrive_fraction=0.0) == 4


def test_non_swing_modes_have_no_overlay():
    for m in (Mode.IDLE, Mode.GLIDE, Mode.PLANNING):
        assert swing_overlay(m, 0, PICKAXE_HEAD) == {}


def test_swing_overlay_places_passed_head_on_right_for_gather_and_craft():
    for mode in (Mode.GATHER_SWING, Mode.CRAFT_SWING):
        ov = swing_overlay(mode, 2, HAMMER_HEAD)   # frame 2 -> (1,0)
        assert ov[(1, 0)] is HAMMER_HEAD
        assert (0, 0) in ov
        assert all(dc >= 0 for (dc, _dr) in ov)    # right side


def test_swing_overlay_fight_on_left():
    ov = swing_overlay(Mode.FIGHT_SWING, 2, PICKAXE_HEAD)
    assert ov[(-1, 0)] is PICKAXE_HEAD
    assert (0, 0) in ov                              # grip in the player tile
    assert any(dc < 0 for (dc, _dr) in ov)


def test_gather_arc_order_and_index_wrap():
    # the head sweeps the 5-offset CW arc in order, and frame_index wraps mod len
    expected = [(0, -1), (1, -1), (1, 0), (1, 1), (0, 1)]
    arc = [
        next(off for off in swing_overlay(Mode.GATHER_SWING, i, PICKAXE_HEAD) if off != (0, 0))
        for i in range(5)
    ]
    assert arc == expected
    assert (swing_overlay(Mode.GATHER_SWING, 5, PICKAXE_HEAD)
            == swing_overlay(Mode.GATHER_SWING, 0, PICKAXE_HEAD))


def test_craft_mode_from_action_kind():
    assert current_mode("craft", False, 1.0, 5.0) == Mode.CRAFT_SWING
    assert current_mode("craft", False, 6.0, 5.0) == Mode.IDLE     # cooldown elapsed
    assert current_mode("craft", True, 1.0, 5.0) == Mode.PLANNING  # planning overrides
