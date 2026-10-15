"""The crit split of a fight's round (spec 2026-10-15 fight-odds §1)."""

from dataclasses import replace

from artifactsmmo_cli.ai.combat import combat_terms, fight_split, win_probability, worn_restore
from artifactsmmo_cli.ai.fight_outcome_core import fight_outcome
from artifactsmmo_cli.ai.fight_terms_core import SCALE
from artifactsmmo_cli.ai.fight_walk import fight_walk, odds_walk
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state

_UTILITY = dict(level=1, type_="utility")


def _gd(healing: int = 0, m_crit: int = 5) -> GameData:
    gd = GameData()
    gd._monster_level = {"owl": 10}
    gd._monster_hp = {"owl": 1450}
    gd._monster_attack = {"owl": {"water": 83}}
    gd._monster_resistance = {"owl": {}}
    gd._monster_critical_strike = {"owl": m_crit}
    gd._monster_initiative = {"owl": 250}
    gd._monster_healing = {"owl": healing}
    fill_monster_stat_defaults(gd)
    gd._consumable_effect_codes = {"heal_potion": ["restore"], "splash_potion": ["splash_restore"],
                                   "res_potion": ["boost_res_fire"]}
    gd._item_stats = {
        "heal_potion": ItemStats(code="heal_potion", hp_restore=70, **_UTILITY),
        "splash_potion": ItemStats(code="splash_potion", hp_restore=70, **_UTILITY),
        "res_potion": ItemStats(code="res_potion", **_UTILITY),
    }
    return gd


def _state(crit: int = 45, **kw: object):  # type: ignore[no-untyped-def]
    base: dict[str, object] = dict(level=30, hp=785, max_hp=785, attack={"earth": 77, "fire": 64},
                                   critical_strike=crit, initiative=200)
    base.update(kw)
    return make_state(**base)


def _worn(code: str | None, quantity: int = 0, slot: str = "utility1_slot"):  # type: ignore[no-untyped-def]
    s = _state()
    return replace(s, equipment={**s.equipment, slot: code}, utility1_slot_quantity=quantity)


def test_the_crit_hit_rounds_half_up_per_element():
    _, d = fight_split(_state(), _gd(), "owl")
    assert d.kill_normal == 141 * SCALE
    assert d.kill_crit == 212 * SCALE
    assert d.die_normal == 83 * SCALE
    assert d.die_crit == 125 * SCALE
    assert (d.p_crit, d.m_crit, d.monster_hp) == (45, 5, 1450)


def test_the_split_agrees_with_the_terms():
    assert fight_split(_state(), _gd(), "owl")[0] == combat_terms(_state(), _gd(), "owl")


def test_a_heal_lands_in_both_amounts():
    _, bare = fight_split(_state(), _gd(), "owl")
    _, healed = fight_split(_state(), _gd(healing=200), "owl")
    drop = bare.kill_normal - healed.kill_normal
    assert drop > 0
    assert bare.kill_crit - healed.kill_crit == drop
    assert healed.kill_crit - healed.kill_normal == (212 - 141) * SCALE


def test_win_probability_reads_current_hp_and_the_worn_potion():
    p = win_probability(_state(), _gd(), "owl")
    assert round(float(p), 4) == 0.6308
    assert win_probability(_state(hp=1), _gd(), "owl") == 0
    # Not exactly 1: a run of crit rolls can still outrun a 70 HP drink (loss ~ 5e-11).
    assert float(win_probability(_worn("heal_potion", 100), _gd(), "owl")) > 1 - 1e-9


def test_worn_restore_skips_splash_and_non_healers():
    gd = _gd()
    assert worn_restore(_state(), gd) == (0, 0)
    assert worn_restore(_worn("splash_potion", 5), gd) == (0, 0)
    assert worn_restore(_worn("res_potion", 5), gd) == (0, 0)
    assert worn_restore(_worn("heal_potion", 7), gd) == (70, 7)
    assert worn_restore(_worn("heal_potion", 7, "utility2_slot"), gd) == (70, 0)


def test_odds_walk_with_no_crit_is_the_walk():
    gd = _gd(m_crit=0)
    state = _state(crit=0)
    endings, max_hp, code = odds_walk(state, gd, "owl", [])
    outcome, walk_hp, walk_code = fight_walk(state, gd, "owl", [])
    assert (max_hp, code) == (walk_hp, walk_code)
    assert len(endings) == 1
    e = endings[0]
    assert (e.win, e.turns, e.hp_end, e.used) == (outcome.win, outcome.turns, outcome.hp_end, outcome.used)
    assert fight_outcome(combat_terms(state, gd, "owl"), max_hp, max_hp, 0, 0) == outcome
