# tests/test_tui/test_map_pane_animation.py
from artifactsmmo_cli.tui.widgets.map_pane import MapPane, select_swing_head
from artifactsmmo_cli.tui.sprites import (
    PLAYER_SPRITE, PLANNING_SPRITE, AXE, PICKAXE, HAMMER, SWORD, oriented_head,
    CLOUD_SPRITE, CLOUD_SPRITE_R,
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


class _Stats:
    def __init__(self, crafting_skill):
        self.crafting_skill = crafting_skill


class _GD:
    def __init__(self, skills=None, items=None):
        self._skills = skills or {}
        self._items = items or {}            # code -> crafting_skill
    def resource_skill_level(self, code):
        return self._skills.get(code)
    def item_stats(self, code):
        return _Stats(self._items[code]) if code in self._items else None


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


def test_select_head_gather_by_skill_returns_bundle():
    gd = _GD(skills={"ash_tree": ("woodcutting", 1), "copper_rocks": ("mining", 1)})
    assert select_swing_head(Mode.GATHER_SWING, "ash_tree", gd) is AXE
    assert select_swing_head(Mode.GATHER_SWING, "copper_rocks", gd) is PICKAXE
    assert select_swing_head(Mode.GATHER_SWING, "shrimp", gd) is PICKAXE          # fallback
    assert select_swing_head(Mode.GATHER_SWING, None, gd) is PICKAXE


def test_select_head_fight_is_sword_bundle():
    assert select_swing_head(Mode.FIGHT_SWING, "chicken", _GD()) is SWORD


def test_select_head_craft_cooking_sword_else_hammer():
    gd = _GD(items={"cooked_chicken": "cooking", "copper_bar": "mining",
                    "copper_boots": "gearcrafting"})
    assert select_swing_head(Mode.CRAFT_SWING, "cooked_chicken", gd) is SWORD
    assert select_swing_head(Mode.CRAFT_SWING, "copper_bar", gd) is HAMMER
    assert select_swing_head(Mode.CRAFT_SWING, "copper_boots", gd) is HAMMER
    assert select_swing_head(Mode.CRAFT_SWING, "unknown", gd) is None             # no stats
    assert select_swing_head(Mode.IDLE, "copper_bar", gd) is None


def test_no_tool_overlay_while_gliding():
    p = _pane()
    p._anim_start = 0.0
    p._game_data = _GD(skills={"ash_tree": ("woodcutting", 1)})
    p.snapshot = _snap(action_kind="gather", action_target="ash_tree", cooldown_remaining=5.0)
    p._anim_frames = [(1, 0), (2, 0)]                      # glide in progress
    assert p._swing_overlay(now=0.5) == {}                # walking -> no tool
    # after the glide window (cooldown elapsed -> idle anyway), still no tool
    assert p._swing_overlay(now=6.0) == {}


def test_swing_overlay_gather_axe_when_not_gliding():
    p = _pane()
    p._game_data = _GD(skills={"ash_tree": ("woodcutting", 1)})
    p.snapshot = _snap(action_kind="gather", action_target="ash_tree", cooldown_remaining=5.0)
    p._anim_start = 0.0
    p._anim_frames = []                                    # not gliding
    ov = p._swing_overlay(now=0.35)                        # frame 2 -> (1,0)
    assert ov[(1, 0)].rows == oriented_head(AXE, 1, 0).rows


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
    swung = p._render_viewport(snap, 80, 41, None, PLAYER_SPRITE, {(1, 0): oriented_head(AXE, 1, 0)})
    # styled markup differs (the head pixels land in the right-neighbor tile)
    assert plain.markup != swung.markup


def test_planning_overlay_two_tiles_swap_each_second():
    p = _pane()
    p.snapshot = _snap(action_kind="gather", cooldown_remaining=5.0)
    p._planning_active = True
    p._planning_start = 0.0
    f0 = p._planning_overlay(now=0.5)                 # second 0
    assert f0 == {(1, -1): CLOUD_SPRITE, (2, -1): CLOUD_SPRITE_R}
    f1 = p._planning_overlay(now=1.5)                 # second 1 -> swapped
    assert f1 == {(1, -1): CLOUD_SPRITE_R, (2, -1): CLOUD_SPRITE}
    f2 = p._planning_overlay(now=2.5)                 # second 2 -> back
    assert f2 == f0


def test_planning_overlay_empty_when_not_planning():
    p = _pane()
    p.snapshot = _snap(action_kind="gather", cooldown_remaining=5.0)
    p._planning_active = False
    assert p._planning_overlay(now=1.0) == {}


def test_set_planning_stamps_start_once(monkeypatch):
    p = _pane()
    monkeypatch.setattr("artifactsmmo_cli.tui.widgets.map_pane.time.monotonic", lambda: 10.0)
    p.set_planning(True)
    assert p._planning_start == 10.0
    monkeypatch.setattr("artifactsmmo_cli.tui.widgets.map_pane.time.monotonic", lambda: 20.0)
    p.set_planning(True)                              # already planning -> not re-stamped
    assert p._planning_start == 10.0
    p.set_planning(False)


def test_active_overlay_picks_planning_then_swing():
    p = _pane()
    p._game_data = _GD(skills={"ash_tree": ("woodcutting", 1)})
    p.snapshot = _snap(action_kind="gather", action_target="ash_tree", cooldown_remaining=5.0)
    p._anim_start = 0.0
    p._anim_frames = []
    # planning active -> cloud
    p._planning_active = True
    p._planning_start = 0.0
    assert (1, -1) in p._active_overlay(now=0.5)
    # planning off -> swing head
    p._planning_active = False
    ov = p._active_overlay(now=0.35)
    assert (1, 0) in ov
