# tests/test_tui/test_map_pane_animation.py
from artifactsmmo_cli.tui.widgets.map_pane import MapPane
from artifactsmmo_cli.tui.sprites import (
    PLAYER_SPRITE, PLANNING_SPRITE, GATHER_HEAD, FIGHT_HEAD,
)
from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.ai.game_data import GameData


def _snap(**kw):
    base = dict(cycle_index=0, timestamp="t", character="c", x=0, y=0, level=1,
                xp=0, max_xp=1, hp=1, max_hp=1, gold=0, selected_goal="g",
                action="x", outcome="ok")
    base.update(kw)
    return CycleSnapshot(**base)


def _pane():
    return MapPane(GameData())


def test_idle_shows_player_sprite():
    p = _pane()
    p.snapshot = _snap(action_kind="rest")
    p._anim_start = 0.0
    assert p._player_sprite(now=1.0) is PLAYER_SPRITE


def test_planning_shows_bubble():
    p = _pane()
    p.snapshot = _snap(action_kind="gather", cooldown_remaining=5.0)
    p._anim_start = 0.0
    p._planning_active = True
    assert p._player_sprite(now=1.0) is PLANNING_SPRITE


def test_gather_swing_overlay_has_head_on_right():
    # swing modes keep the base player sprite; the tool comes via the overlay map
    p = _pane()
    p.snapshot = _snap(action_kind="gather", cooldown_remaining=5.0)
    p._anim_start = 0.0
    assert p._player_sprite(now=0.35) is PLAYER_SPRITE
    ov = p._swing_overlay(now=0.35)   # frame 2 of a 0.8s sweep -> (1,0)
    assert ov[(1, 0)] is GATHER_HEAD
    assert (0, 0) in ov


def test_fight_swing_overlay_has_head_on_left():
    p = _pane()
    p.snapshot = _snap(action_kind="fight", cooldown_remaining=5.0)
    p._anim_start = 0.0
    ov = p._swing_overlay(now=0.35)
    assert ov[(-1, 0)] is FIGHT_HEAD


def test_no_overlay_when_idle_or_planning():
    p = _pane()
    p.snapshot = _snap(action_kind="rest", cooldown_remaining=5.0)
    p._anim_start = 0.0
    assert p._swing_overlay(now=1.0) == {}
    p2 = _pane()
    p2.snapshot = _snap(action_kind="gather", cooldown_remaining=5.0)
    p2._anim_start = 0.0
    p2._planning_active = True
    assert p2._swing_overlay(now=1.0) == {}


def test_swing_overlay_empty_without_snapshot():
    p = _pane()
    p.snapshot = None
    p._anim_start = 0.0
    assert p._swing_overlay(now=1.0) == {}


def test_update_snapshot_clears_planning_and_stamps_start(monkeypatch):
    p = _pane()
    p._planning_active = True
    monkeypatch.setattr("artifactsmmo_cli.tui.widgets.map_pane.time.monotonic", lambda: 42.0)
    p.update_snapshot(_snap(action_kind="gather", cooldown_remaining=5.0))
    assert p._planning_active is False
    assert p._anim_start == 42.0


def test_player_sprite_no_snapshot_returns_player():
    """_player_sprite returns the default PLAYER_SPRITE when snapshot is None."""
    p = _pane()
    assert p._player_sprite(now=0.0) is PLAYER_SPRITE


def test_set_planning_sets_flag():
    """set_planning toggles _planning_active (refresh not testable headless)."""
    p = _pane()
    assert p._planning_active is False
    p.set_planning(True)
    assert p._planning_active is True
    p.set_planning(False)
    assert p._planning_active is False


def test_is_animating_true_when_planning():
    """_is_animating returns True when planning is active, even with no snapshot."""
    p = _pane()
    p._planning_active = True
    assert p._is_animating() is True


def test_tick_calls_refresh_when_animating(monkeypatch):
    """_tick calls refresh() when _is_animating() is True."""
    p = _pane()
    refresh_calls = []
    monkeypatch.setattr(p, "refresh", lambda: refresh_calls.append(1))
    p._planning_active = True
    p._tick()
    assert refresh_calls == [1]


def test_tick_no_refresh_when_not_animating(monkeypatch):
    """_tick does not call refresh() when _is_animating() is False."""
    p = _pane()
    refresh_calls = []
    monkeypatch.setattr(p, "refresh", lambda: refresh_calls.append(1))
    # no snapshot, not planning -> _is_animating is False
    p._tick()
    assert refresh_calls == []


def test_render_viewport_applies_tool_overlay_branch():
    # a non-empty overlay must merge the tool onto the arc-neighbor tile (covers
    # the overlay_sprites apply branch in _render_viewport).
    p = _pane()
    snap = _snap(action_kind="gather", x=0, y=0, cooldown_remaining=5.0)
    p.snapshot = snap
    overlay = {(0, 0): GATHER_HEAD, (1, 0): GATHER_HEAD}
    text = p._render_viewport(snap, 80, 41, None, PLAYER_SPRITE, overlay)
    assert text.plain  # rendered without error; the overlay branch executed
