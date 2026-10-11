"""Unit tests for the party boss-fight walk (`group_fight_core`; proved model
`formal/Formal/GroupFight.lean`, differential `formal/diff/test_group_fight_diff.py`)."""

import pytest

from artifactsmmo_cli.ai.fight_terms_core import FightExit
from artifactsmmo_cli.ai.group_fight_core import GroupOutcome, PartyBoss, PartyMember, group_outcome, party_exit


def _m(net: int = 20_000, hit: int = 400_000, area: int = 0, hp: int = 100, max_hp: int = 100,
       first: bool = True, threat: int = 0, restore: int = 0, stock: int = 0,
       raw: int = 10) -> PartyMember:
    return PartyMember(raw, net, hit, area, hp, max_hp, first, threat, restore, stock)


@pytest.mark.parametrize(("boss", "members", "exit_"), [
    (PartyBoss(20, 0, 0), [], FightExit.NO_DAMAGE),
    (PartyBoss(20, 0, 0), [_m(raw=0)], FightExit.NO_DAMAGE),
    (PartyBoss(20, 0, 30_000), [_m()], FightExit.UNKILLABLE),
    # 101 rounds alone = 202 actor turns > 200
    (PartyBoss(202, 0, 0), [_m()], FightExit.OVER_CAP),
    # 70 rounds for two = 210 actor turns > 200
    (PartyBoss(140, 0, 0), [_m(net=10_000), _m(net=10_000)], FightExit.OVER_CAP),
    # 10 rounds alone = 20 turns; reconstitution at 10 turns
    (PartyBoss(20, 10, 0), [_m()], FightExit.RECONSTITUTED),
    (PartyBoss(20, 0, 0), [_m(hit=0), _m(hit=5, area=-5)], FightExit.OUT_SUSTAIN),
    (PartyBoss(20, 0, 0), [_m(hit=0), _m(hit=5)], FightExit.NONE),
])
def test_the_guard_ladder(boss, members, exit_):
    assert party_exit(boss, members) is exit_


def test_out_sustain_wins_at_the_kill_round_untouched():
    out = group_outcome(PartyBoss(20, 0, 0), [_m(hit=0), _m(hit=0, hp=50)])
    assert out == GroupOutcome(True, 5, (1_000_000, 500_000), (0, 0))


def test_a_guard_exit_and_a_dead_start_lose_unwalked():
    assert not group_outcome(PartyBoss(20, 0, 30_000), [_m()]).win
    dead = group_outcome(PartyBoss(20, 0, 0), [_m(), _m(hp=0)])
    assert (dead.win, dead.turns, dead.hp_end) == (False, 0, (0, 0))


def test_negative_stock_or_restore_is_refused():
    with pytest.raises(ValueError, match="non-negative"):
        group_outcome(PartyBoss(20, 0, 0), [_m(stock=-1)])
    with pytest.raises(ValueError, match="non-negative"):
        group_outcome(PartyBoss(20, 0, 0), [_m(restore=-1)])


def test_equal_threat_focuses_the_lowest_pool_and_the_rest_fight_on():
    """The weak member takes every hit (400k on a 1M pool) and dies in round
    3; the strong one fights on alone (20k a round) and wins in round 7
    (live probe 2026-10-11: a dead member leaves, the fight goes on)."""
    out = group_outcome(PartyBoss(20, 0, 0), [_m(hp=200, max_hp=200), _m()])
    assert (out.win, out.turns, out.hp_end) == (True, 7, (800_000, 0))


def test_the_fight_is_lost_when_every_member_is_dead():
    out = group_outcome(PartyBoss(40, 0, 0), [_m(hp=200, max_hp=200), _m()])
    assert (out.win, out.hp_end) == (False, (0, 0))


def test_a_late_mover_killed_by_the_boss_deals_no_damage_that_round():
    """A late mover dead after the boss's turn does not act; a first mover
    killed in the same turn already has."""
    late = group_outcome(PartyBoss(3, 0, 0), [_m(first=False, hp=40), _m(hp=200, max_hp=200)])
    early = group_outcome(PartyBoss(3, 0, 0), [_m(hp=40), _m(hp=200, max_hp=200)])
    assert (late.win, late.turns) == (True, 2)
    assert (early.win, early.turns) == (True, 1)


def test_a_delayed_kill_meets_the_deadline():
    """Reconstitution at 10 turns: the weak member's death pushes the kill to
    round 7 (21 actor turns), so the fight is lost at the end of round 6."""
    out = group_outcome(PartyBoss(20, 10, 0), [_m(hp=200, max_hp=200), _m()])
    assert (out.win, out.turns, out.hp_end) == (False, 6, (800_000, 0))


def test_a_zero_hp_boss_is_won_unwalked():
    out = group_outcome(PartyBoss(0, 0, 0), [_m(hp=60)])
    assert out == GroupOutcome(True, 0, (600_000,), (0,))


def test_the_tank_takes_ninety_the_weakest_ten():
    """All move first: the boss acts 4 times before the round-5 kill."""
    out = group_outcome(PartyBoss(20, 0, 0), [_m(), _m(hp=200, max_hp=200, threat=5)])
    assert (out.win, out.turns, out.hp_end) == (True, 5, (840_000, 560_000))


def test_a_threat_tie_goes_to_the_lower_pool_then_the_first():
    out = group_outcome(PartyBoss(10, 0, 0),
                        [_m(threat=3), _m(threat=3), _m(threat=3, hp=50)])
    # kill in 2 rounds (60k a round on 100k): one boss turn, all on member 3
    assert out.hp_end == (1_000_000, 1_000_000, 100_000)


def test_area_heal_is_capped_and_second_movers_drink():
    """Lifesteal heals a non-target to max; a late mover drinks below half."""
    out = group_outcome(PartyBoss(20, 0, 0), [
        _m(hp=90, area=-200_000, hit=0),
        _m(hp=40, first=False, hit=0, area=10_000, restore=50, stock=1),
    ])
    assert out.win and out.hp_end[0] == 1_000_000 and out.used == (0, 1)
