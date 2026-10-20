"""Rest before a fight, or fight now, read from the world (`rest_first`)."""

from dataclasses import replace
from fractions import Fraction

from artifactsmmo_cli.ai.actions.cost_core import travel_seconds
from artifactsmmo_cli.ai.combat import predict_win, win_probability
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.fight_seconds_model import committed_timing
from artifactsmmo_cli.ai.rest_first import fight_kill_seconds, rest_pays
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state

TILE = (3, 4)
TIMING = committed_timing()[0]
"""The committed live capture's fight-seconds fit (spec 2026-10-18 §2.9)."""


def _gd() -> GameData:
    """The player moves first and kills in two hits; the mob lands one hit
    between them: 30, or 45 on its 50% crit."""
    gd = GameData()
    gd._monster_level = {"mob": 1}
    gd._monster_hp = {"mob": 100}
    gd._monster_attack = {"mob": {"fire": 30}}
    gd._monster_critical_strike = {"mob": 50}
    gd._monster_initiative = {"mob": 10}
    gd._monster_locations = {"mob": [TILE]}
    fill_monster_stat_defaults(gd)
    return gd


def _state(hp: int) -> WorldState:
    return make_state(hp=hp, max_hp=100, attack={"fire": 50}, initiative=90,
                      win_thresholds={"mob": Fraction(1, 2)})


def test_the_fixture_wins_half_at_40_hp_and_always_from_full() -> None:
    gd = _gd()
    assert win_probability(_state(40), gd, "mob") == Fraction(1, 2)
    assert win_probability(_state(100), gd, "mob") == 1


def test_kill_seconds_price_the_rest_after_and_the_walk_back() -> None:
    """At 40 HP: a win ends at 10 (90 s of rest), a loss at 1 (99 s) and walks
    back; from full a win ends at 70 or 55 (30 or 45 s). The fight lasts its
    learned seconds (spec §2.9): a win on the player's second hit is the third
    server turn, a loss on the mob's first hit the second, so the fight at 40
    HP averages 5/2 turns (the 5 s floor) and the one from full 3."""
    gd = _gd()
    walk = travel_seconds((0, 0), TILE)
    now = (TIMING.seconds(Fraction(5, 2), 0) + Fraction(90 + 99, 2) + walk / 2) / Fraction(1, 2)
    assert TIMING.seconds(Fraction(5, 2), 0) == TIMING.floor == 5
    assert fight_kill_seconds(_state(40), gd, "mob", TIMING) == now
    assert fight_kill_seconds(_state(100), gd, "mob", TIMING) == (TIMING.seconds(Fraction(3), 0)
                                                                 + Fraction(30 + 45, 2))


def test_a_fight_the_threshold_admits_still_rests_when_resting_pays() -> None:
    """θ 1/2 admits the 40-HP fight (P 1/2), yet a 60 s rest and a sure win
    cost less than the coin flip and its 99 s rest."""
    gd = _gd()
    assert predict_win(_state(40), gd, "mob")
    assert rest_pays(_state(40), gd, "mob", TIMING) is True


def test_a_sure_win_never_rests_first() -> None:
    """At 60 HP the mob cannot kill: resting first costs exactly the rest the
    fight would take after, so the fight runs."""
    gd = _gd()
    assert win_probability(_state(60), gd, "mob") == 1
    assert rest_pays(_state(60), gd, "mob", TIMING) is False


def test_full_hp_has_nothing_to_rest() -> None:
    assert rest_pays(_state(100), _gd(), "mob", TIMING) is False


def test_a_fight_full_hp_loses_is_not_a_rest_question() -> None:
    gd = _gd()
    weak = replace(_state(40), attack={"fire": 1})
    assert win_probability(replace(weak, hp=100), gd, "mob") == 0
    assert rest_pays(weak, gd, "mob", TIMING) is False
