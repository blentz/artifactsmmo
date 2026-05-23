"""Tests for the documented combat-outcome estimator."""

import pytest

from artifactsmmo_cli.ai.combat import (
    _element_damage,
    _expected_hit,
    _round_half_up,
    predict_win,
)
from artifactsmmo_cli.ai.game_data import GameData
from tests.test_ai.fixtures import make_state


def _gd(hp, attack=None, resist=None, crit=0, initiative=0, code="mob"):
    gd = GameData()
    gd._monster_hp = {code: hp}
    gd._monster_attack = {code: attack or {}}
    gd._monster_resistance = {code: resist or {}}
    gd._monster_critical_strike = {code: crit}
    gd._monster_initiative = {code: initiative}
    return gd


def test_round_half_up_rounds_half_upward():
    assert _round_half_up(2.5) == 3
    assert _round_half_up(2.4999) == 2
    assert _round_half_up(3.0) == 3


def test_element_damage_applies_bonus_then_resistance():
    # 100 attack + 30% damage = 130 output; 30% resistance blocks Round(130*0.3)=39
    assert _element_damage(100, 30, 30) == 130 - 39


def test_element_damage_clamps_to_zero():
    assert _element_damage(10, 0, 100) == 0


def test_expected_hit_sums_elements_and_applies_crit():
    # fire 10 + water 5 = 15 raw; crit 20% -> *1.10
    raw = _expected_hit({"fire": 10, "water": 5}, 0, {}, {}, 20)
    assert raw == pytest.approx(15 * 1.10)


def test_predict_win_true_when_player_kills_first():
    state = make_state(max_hp=100, attack={"fire": 30}, initiative=50)
    gd = _gd(hp=30, attack={"fire": 5}, initiative=10)
    assert predict_win(state, gd, "mob") is True


def test_predict_win_false_when_monster_kills_first():
    state = make_state(max_hp=10, attack={"fire": 1}, initiative=0)
    gd = _gd(hp=1000, attack={"fire": 50}, initiative=100)
    assert predict_win(state, gd, "mob") is False


def test_predict_win_false_when_player_cannot_damage():
    state = make_state(max_hp=100, attack={}, initiative=50)
    gd = _gd(hp=30, attack={"fire": 5})
    assert predict_win(state, gd, "mob") is False


def test_predict_win_true_when_monster_cannot_damage():
    state = make_state(max_hp=100, attack={"fire": 10}, initiative=0)
    gd = _gd(hp=30, attack={}, initiative=100)
    assert predict_win(state, gd, "mob") is True


def test_predict_win_false_when_kill_exceeds_turn_cap():
    state = make_state(max_hp=10000, attack={"fire": 1}, initiative=100)
    gd = _gd(hp=10000, attack={"fire": 1})
    assert predict_win(state, gd, "mob") is False


def test_predict_win_resistance_lets_defender_survive_longer():
    state = make_state(max_hp=100, attack={"fire": 20}, initiative=0)
    weak = _gd(hp=40, attack={"fire": 15}, initiative=100)
    armored = _gd(hp=40, attack={"fire": 15}, resist={"fire": 75}, initiative=100, code="mob")
    assert predict_win(state, weak, "mob") is True
    assert predict_win(state, armored, "mob") is False


def test_predict_win_initiative_tie_favors_player():
    state = make_state(max_hp=20, attack={"fire": 20}, initiative=50)
    gd = _gd(hp=20, attack={"fire": 20}, initiative=50)
    assert predict_win(state, gd, "mob") is True


def test_predict_win_player_resistance_reduces_monster_damage():
    # Monster does 20 fire; player has 75% fire resistance -> 5 net/turn,
    # surviving 20 turns at max_hp=100 while killing the mob in 2.
    state = make_state(max_hp=100, attack={"fire": 20}, initiative=0, resistance={"fire": 75})
    gd = _gd(hp=40, attack={"fire": 20}, initiative=100)
    assert predict_win(state, gd, "mob") is True


def test_predict_win_global_dmg_bonus_changes_outcome():
    # Without +100% global dmg the player needs 2 rounds and the faster monster
    # kills first; with it the player one-shots and wins. Proves state.dmg is wired.
    mob = _gd(hp=20, attack={"fire": 8}, initiative=100)
    slow = make_state(max_hp=10, attack={"fire": 10}, initiative=0)
    boosted = make_state(max_hp=10, attack={"fire": 10}, dmg=100, initiative=0)
    assert predict_win(slow, mob, "mob") is False
    assert predict_win(boosted, mob, "mob") is True
