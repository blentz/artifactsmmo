"""Tests for combat_target_monsters winnable near-level set."""

from artifactsmmo_cli.ai.combat_targets import (
    LEVEL_BAND_BELOW, combat_target_monsters, _clear_cache,
)
from artifactsmmo_cli.ai.game_data import GameData
from tests.test_ai.fixtures import make_state
import artifactsmmo_cli.ai.combat_targets as ct


def _gd(levels):
    gd = GameData()
    gd._monster_level = dict(levels)
    return gd


def test_set_excludes_too_low_and_unwinnable(monkeypatch):
    _clear_cache()
    gd = _gd({"chick": 1, "wolf": 9, "dragon": 40})
    # winnable: everything <= level 10; dragon (40) unwinnable.
    monkeypatch.setattr(ct, "is_winnable",
                        lambda s, g, code, h=None: g._monster_level[code] <= 10)
    state = make_state(level=10)
    got = combat_target_monsters(state, gd)
    assert "wolf" in got              # level 9 >= 10-5 and winnable
    assert "chick" not in got         # level 1 < 10-5 (too low)
    assert "dragon" not in got        # unwinnable


def test_memoized_per_level_and_equipment(monkeypatch):
    _clear_cache()
    calls = {"n": 0}
    def fake(s, g, code, h=None):
        calls["n"] += 1
        return True
    monkeypatch.setattr(ct, "is_winnable", fake)
    gd = _gd({"wolf": 9})
    state = make_state(level=10)
    combat_target_monsters(state, gd)
    n_after_first = calls["n"]
    combat_target_monsters(state, gd)            # same key → cache hit
    assert calls["n"] == n_after_first
