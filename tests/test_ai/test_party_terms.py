"""Tests for the party split of the closed-form fight terms
(`combat.party_member` / `party_boss`, docs/PLAN_group_fights.md increment 1)."""

import pytest

from artifactsmmo_cli.ai.combat import boss_drain, combat_terms, party_boss, party_member
from artifactsmmo_cli.ai.fight_outcome_core import fight_outcome
from artifactsmmo_cli.ai.game_data import ItemStats
from artifactsmmo_cli.ai.group_fight_core import group_outcome
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_combat import _gd

_EVERY_EFFECT = {
    "lifesteal": 10, "poison": 7, "barrier": 40, "burn": 3, "healing": 2,
    "void_drain": 5, "berserker_rage": 6, "frenzy": 4, "protective_bubble": 3,
    "greed": 2, "enchanted_mirror": 5, "crit": 20, "initiative": 30,
}


def _gear():
    return {
        "vamp": ItemStats(code="vamp", level=1, type_="weapon", lifesteal=15, threat=4),
        "helm": ItemStats(code="helm", level=1, type_="helmet", threat=6),
        "cure": ItemStats(code="cure", level=1, type_="utility", antipoison=2),
    }


@pytest.mark.parametrize("effects", [{}, _EVERY_EFFECT, {"void_drain": 20, "poison": 30}])
def test_one_member_is_its_solo_terms(effects):
    """`net - drain` is `kill_step`, `hit + area` is `die_step`, and a
    one-member party walks exactly as `fight_outcome` does."""
    gd = _gd(hp=900, attack={"fire": 40, "water": 25}, resist={"fire": 10}, **effects)
    gd._item_stats = _gear()
    state = make_state(hp=300, max_hp=400, attack={"fire": 60, "earth": 20}, critical_strike=25,
                       initiative=20, equipment={"weapon_slot": "vamp", "helmet_slot": "helm",
                                                 "utility1_slot": "cure"})
    terms = combat_terms(state, gd, "mob")
    member = party_member(state, gd, "mob", 50, 3)
    boss = party_boss(gd, "mob")
    assert member.net - boss.drain == terms.kill_step
    assert member.hit + member.area == terms.die_step
    assert (boss.hp, boss.recon) == (900 + effects.get("barrier", 0), 0)
    assert member.threat == 10
    assert (member.hp, member.max_hp, member.first) == (300, 400, terms.player_first)
    solo = fight_outcome(terms, 300, 400, 50, 3)
    party = group_outcome(boss, [member])
    assert (party.win, party.turns, party.hp_end, party.used) == (
        solo.win, solo.turns, (solo.hp_end,), (solo.used,))


def test_hit_is_the_attack_area_is_what_every_member_pays():
    """Void drain and poison land on every member, targeted or not; one hit
    is the attack alone. Monster raw 50, no crit: hit = 50 * 50 * 200."""
    gd = _gd(hp=100, attack={"fire": 50}, void_drain=20, poison=30)
    state = make_state(max_hp=100, attack={"fire": 50})
    member = party_member(state, gd, "mob", 0, 0)
    assert member.hit == 50 * 50 * 200
    # void 20% of 100 HP (×100 scale ×100) + poison 30 (×10000)
    assert member.area == 20 * 100 * 100 + 30 * 10000


def test_boss_drain_is_its_lifesteal_and_healing():
    """crit 20 × lifesteal 10 × attack 50 + healing 2 × hp 100 × 100."""
    gd = _gd(hp=100, attack={"fire": 50}, crit=20, lifesteal=10, healing=2)
    assert boss_drain(gd, "mob") == 20 * 10 * 50 + 2 * 100 * 100
