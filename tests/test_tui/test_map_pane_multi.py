"""MapPane draws non-focused characters at their own tiles."""

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.tui.character_roster import CharacterRoster
from artifactsmmo_cli.tui.widgets.map_pane import TILE_H, TILE_W, MapPane


def _snap(x: int = 0, y: int = 0) -> CycleSnapshot:
    return CycleSnapshot(
        cycle_index=1, timestamp="2026-07-30T12:00:00Z", character="alice",
        x=x, y=y, level=1, xp=0, max_xp=150, hp=120, max_hp=120, gold=0,
        selected_goal="ReachLevel(50)", action="Rest()", outcome="ok",
    )


def _pane() -> MapPane:
    return MapPane(GameData())


def test_others_default_to_empty():
    assert _pane()._others == {}


def test_a_second_character_renders_at_its_own_tile():
    # NOTE: every tile is composited from the same half-block glyphs (only
    # foreground/background COLOR differs between sprites), so `.plain`
    # (glyph text only, no style) is identical whether or not bob is drawn —
    # asserting on it can never distinguish correct from broken behaviour.
    # Compare `.spans` instead, which carries the per-cell style runs.
    roster = CharacterRoster(["alice", "bob"])
    pane = _pane()
    pane.update_snapshot(_snap(0, 0))
    plain = pane._render_viewport(_snap(0, 0), TILE_W * 5, TILE_H * 5 + 1)
    pane.set_others({(1, 0, "overworld"): roster.sprite("bob")})
    with_bob = pane._render_viewport(_snap(0, 0), TILE_W * 5, TILE_H * 5 + 1)
    assert with_bob.plain == plain.plain  # glyphs unchanged; only colour differs
    assert with_bob.spans != plain.spans


def test_setting_others_invalidates_the_line_cache():
    """A stale cached Strip would leave a character painted where they no
    longer are."""
    roster = CharacterRoster(["alice", "bob"])
    pane = _pane()
    pane.update_snapshot(_snap(0, 0))
    pane._line_cache[3] = ("stale-signature", None)
    pane.set_others({(1, 0, "overworld"): roster.sprite("bob")})
    assert pane._line_cache == {}


def test_the_line_signature_changes_when_a_character_moves_onto_that_row():
    roster = CharacterRoster(["alice", "bob"])
    pane = _pane()
    pane.update_snapshot(_snap(0, 0))
    height = TILE_H * 5 + 1
    args = (1, height, (0, 0), pane._player_sprite(0.0), {})
    before = pane._line_signature(*args)
    pane.set_others({(0, -2, "overworld"): roster.sprite("bob")})
    assert pane._line_signature(*args) != before


def test_the_focused_character_wins_a_shared_tile():
    """set_others is given only non-focused characters, so the centre tile is
    always the focused one."""
    roster = CharacterRoster(["alice", "bob"])
    pane = _pane()
    pane.update_snapshot(_snap(0, 0))
    pane.set_others({(0, 0, "overworld"): roster.sprite("bob")})
    sprite, _terrain = pane._tile_sprite_and_terrain(
        0, 0, True, pane._player_sprite(0.0)
    )
    assert sprite is pane._player_sprite(0.0)
