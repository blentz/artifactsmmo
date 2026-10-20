"""The band's pick is the band target, not the unbounded projection (the grind
target is the gear objective's since spec 2026-10-18; the band is no longer
consulted for it, and Plan C deletes it)."""
from fractions import Fraction

import artifactsmmo_cli.ai.player as player_mod
import artifactsmmo_cli.ai.tiers.band_target as band_target_mod
import artifactsmmo_cli.ai.tiers.tier_progress as tier_progress_mod
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.learning.fight_seconds_model import committed_timing
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.tiers.band_target import BandTarget
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_strategy_driver import _make_planner_gd


def test_the_band_asks_the_band_target_not_the_unbounded_projection(monkeypatch):
    """`_path_aligned_monster` used `cheapest_path_to_level`, whose candidate
    floor is 1. It must consult `band_combat_target` instead."""
    player = GamePlayer(character="Robby")
    player._offline_timing = committed_timing()
    player.state = make_state(level=30)
    player.game_data = _make_planner_gd()

    monkeypatch.setattr(player_mod, "band_combat_target",
                        lambda state, game_data, history, price_of, loadout_of, party_of:
                        BandTarget("spider", Fraction(1), True))
    monkeypatch.setattr(GamePlayer, "_task_aligned_monster", lambda self: None)
    monkeypatch.setattr(GamePlayer, "_is_winnable", lambda self, code: True)

    assert player._path_aligned_monster() == BandTarget("spider", Fraction(1), True)


def test_no_band_target_yields_no_band_pick(monkeypatch):
    """A gear wall surfaces as None."""
    player = GamePlayer(character="Robby")
    player._offline_timing = committed_timing()
    player.state = make_state(level=30)
    player.game_data = _make_planner_gd()

    monkeypatch.setattr(player_mod, "band_combat_target",
                        lambda state, game_data, history, price_of, loadout_of, party_of: None)

    assert player._path_aligned_monster() is None


def test_an_unfightable_band_target_is_no_band_pick(monkeypatch):
    """GAP-8 / task 5.2 fix round 1: before `band_combat_target` applied
    `FIGHT_LEVEL_GAP_CEILING`, a stat-winnable-but-unfightable target (e.g.
    `highwayman` at char level 10) outranked tier 3 outright — `is_winnable`
    is a pure stat question, so `path_winnable` read True, the windowed
    picker (which HAS the correct `[char_level-1, char_level+2]` window and
    a fallback) never ran, and combat stopped entirely. This exercises the
    REAL `band_combat_target` (not a mock) end-to-end through
    `_winnable_farm_target`, so it would have caught GAP-8 itself: the
    band's only stat-winnable member (`highwayman`, L15) sits outside the
    executor's window at char level 10, so `band_combat_target` must return
    None, while the windowed picker finds `mushmush` (L10, in-window,
    winnable) rather than the unfightable `highwayman`."""
    def fake_is_winnable(s: object, g: object, c: str, h: object) -> bool:
        return c != "pig"  # pig stays unwinnable so tier 15 stays uncleared
    monkeypatch.setattr(band_target_mod, "is_winnable", fake_is_winnable)
    monkeypatch.setattr(tier_progress_mod, "is_winnable", fake_is_winnable)
    monkeypatch.setattr(player_mod, "is_winnable", fake_is_winnable)
    monkeypatch.setattr(GamePlayer, "_task_aligned_monster", lambda self: None)

    gd = GameData()
    gd._item_stats = {
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon"),
        "iron_sword": ItemStats(code="iron_sword", level=10, type_="weapon"),
        "steel_sword": ItemStats(code="steel_sword", level=15, type_="weapon"),
    }
    gd._monster_level = {"chicken": 1, "mushmush": 10, "highwayman": 15, "pig": 19}
    gd._monster_locations = {c: [(i, 0)] for i, c in enumerate(gd._monster_level)}
    gd._monster_type = {"chicken": "normal", "mushmush": "normal",
                        "highwayman": "normal", "pig": "normal"}
    gd._monster_hp = {"chicken": 60, "mushmush": 350, "highwayman": 500, "pig": 600}

    player = GamePlayer(character="Robby")

    player._offline_timing = committed_timing()

    player._offline_timing = committed_timing()
    player.state = make_state(level=10)
    player.game_data = gd

    assert player._path_aligned_monster() is None
    assert player._pick_winnable_monster() == "mushmush"


def test_unseeded_player_yields_no_path_aligned_monster():
    """`_path_aligned_monster` keeps its `state`/`game_data` guard: a player
    that has not yet been seeded must not reach `band_combat_target` (or
    `cheapest_path_to_level`) at all."""
    player = GamePlayer(character="Robby")
    player._offline_timing = committed_timing()
    assert player.state is None
    assert player.game_data is None
    assert player._path_aligned_monster() is None


def test_a_band_candidate_is_priced_as_the_grind_target(monkeypatch):
    """`_band_loadout` prices each band candidate's loadout as if it were the
    grind target: the band context names it, on this cycle's bank access."""
    player = GamePlayer(character="Robby")
    player._offline_timing = committed_timing()
    player.state = make_state(level=30)
    player.game_data = _make_planner_gd()
    seen = []

    def fake(state, game_data, ctx, monster, history):  # type: ignore[no-untyped-def]
        seen.append((ctx.combat_monster, ctx.bank_accessible, monster))
        return "loadout"

    monkeypatch.setattr(player_mod, "best_loadout", fake)
    assert player._band_loadout("spider") == "loadout"
    assert seen == [("spider", True, "spider")]
