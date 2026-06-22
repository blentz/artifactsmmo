# tests/test_tui/test_map_pane_animation.py
from artifactsmmo_cli.tui.widgets.map_pane import MapPane, select_swing_head, _is_bar
from artifactsmmo_cli.tui.sprites import (
    PLAYER_SPRITE, PLANNING_SPRITE, AXE_HEAD, PICKAXE_HEAD, HAMMER_HEAD, FIGHT_HEAD,
)
from artifactsmmo_cli.tui.swing_frames import Mode
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


class _GD:
    """Minimal game_data double for head selection."""
    def __init__(self, skills=None, items=()):
        self._skills = skills or {}
        self._items = set(items)

    def resource_skill_level(self, code):
        return self._skills.get(code)

    def item_stats(self, code):
        return object() if code in self._items else None


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


def test_select_head_gather_by_skill():
    gd = _GD(skills={"ash_tree": ("woodcutting", 1), "copper_rocks": ("mining", 1)})
    assert select_swing_head(Mode.GATHER_SWING, "ash_tree", gd) is AXE_HEAD
    assert select_swing_head(Mode.GATHER_SWING, "copper_rocks", gd) is PICKAXE_HEAD
    assert select_swing_head(Mode.GATHER_SWING, "shrimp_spot", gd) is PICKAXE_HEAD  # fallback
    assert select_swing_head(Mode.GATHER_SWING, None, gd) is PICKAXE_HEAD


def test_select_head_fight_is_sword():
    assert select_swing_head(Mode.FIGHT_SWING, "chicken", _GD()) is FIGHT_HEAD


def test_select_head_craft_hammer_only_for_bars():
    gd = _GD(items=("copper_bar", "copper_boots"))
    assert select_swing_head(Mode.CRAFT_SWING, "copper_bar", gd) is HAMMER_HEAD
    assert select_swing_head(Mode.CRAFT_SWING, "copper_boots", gd) is None
    assert select_swing_head(Mode.IDLE, "copper_bar", gd) is None


def test_is_bar():
    gd = _GD(items=("copper_bar",))
    assert _is_bar("copper_bar", gd) is True
    assert _is_bar("copper_boots", gd) is False
    assert _is_bar(None, gd) is False
    assert _is_bar("ghost_bar", gd) is False              # endswith _bar but no item


def test_no_tool_overlay_while_gliding():
    p = _pane()
    p.snapshot = _snap(action_kind="gather", x=0, y=0, cooldown_remaining=5.0)
    p._anim_start = 0.0
    p._anim_frames = [(1, 0), (2, 0)]                      # glide in progress
    p._game_data = _GD(skills={"ash_tree": ("woodcutting", 1)})
    p.snapshot = _snap(action_kind="gather", action_target="ash_tree", cooldown_remaining=5.0)
    p._anim_frames = [(1, 0), (2, 0)]
    assert p._swing_overlay(now=0.5) == {}                # walking -> no tool
    # after the glide window, the tool returns
    assert p._swing_overlay(now=6.0) == {}                # cooldown elapsed -> idle anyway


def test_swing_overlay_gather_axe_when_not_gliding():
    p = _pane()
    p._game_data = _GD(skills={"ash_tree": ("woodcutting", 1)})
    p.snapshot = _snap(action_kind="gather", action_target="ash_tree", cooldown_remaining=5.0)
    p._anim_start = 0.0
    p._anim_frames = []                                    # not gliding
    ov = p._swing_overlay(now=0.35)                        # frame 2 -> (1,0)
    assert ov[(1, 0)] is AXE_HEAD


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


def test_render_viewport_overlay_changes_neighbor_tile():
    # the tool overlay must actually CHANGE the rendered output, not merely run:
    # rendering the arc-neighbor tile with the head overlaid differs from plain.
    p = _pane()
    snap = _snap(action_kind="gather", x=0, y=0, cooldown_remaining=5.0)
    p.snapshot = snap
    plain = p._render_viewport(snap, 80, 41, None, PLAYER_SPRITE, {})
    swung = p._render_viewport(snap, 80, 41, None, PLAYER_SPRITE, {(1, 0): AXE_HEAD})
    # styled markup differs (the head pixels land in the right-neighbor tile)
    assert plain.markup != swung.markup
