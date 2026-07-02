"""Tests for the expected_damage_per_fight cold-start seed."""

import math

from artifactsmmo_cli.ai.combat import _expected_hit
from artifactsmmo_cli.ai.expected_damage import expected_damage_per_fight
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_combat import _gd


def test_expected_damage_exact_for_winnable_monster():
    """Damage equals round(monster_per_turn) * rounds_to_kill, computed from
    the same _expected_hit primitive as predict_win.

    Fixture: monster has 30 HP and 10 fire attack; player has 50 fire attack.
      monster_per_turn = _expected_hit({"fire": 10}, 0, {}, {}, 0) = 10.0
      player_kill_step = _expected_hit({"fire": 50}, 0, {}, {}, 0) = 50.0
      rounds_to_kill   = ceil(30 / 50.0) = 1
      result           = round(10.0) * 1 = 10
    """
    gd = _gd(hp=30, attack={"fire": 10}, code="slime")
    gd._monster_level = {"slime": 1}
    state = make_state(level=5, hp=200, max_hp=200, attack={"fire": 50})
    monster_per_turn = _expected_hit({"fire": 10}, 0, {}, {}, 0)
    player_kill_step = _expected_hit({"fire": 50}, 0, {}, {}, 0)
    rounds_to_kill = math.ceil(30 / player_kill_step)
    expected = round(monster_per_turn) * rounds_to_kill
    assert expected_damage_per_fight(state, gd, "slime") == expected


def test_expected_damage_zero_when_unknown_monster():
    """An unknown monster code returns 0 (caller won't fight it)."""
    gd = _gd(hp=30, code="slime")
    # "ghost" is not in gd._monster_level (never set) -> monster_levels is empty
    assert expected_damage_per_fight(make_state(), gd, "ghost") == 0


def test_expected_damage_zero_when_player_cannot_damage():
    """A player dealing 0 damage cannot kill the monster; return 0."""
    gd = _gd(hp=30, attack={"fire": 5}, code="mob")
    gd._monster_level = {"mob": 1}
    # make_state with no attack kwarg -> state.attack = {} -> player_kill_step = 0
    state = make_state(level=5, hp=100, max_hp=100)
    assert expected_damage_per_fight(state, gd, "mob") == 0
