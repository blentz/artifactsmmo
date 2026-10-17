"""The drop route's party arm (`party_win`, docs/PLAN_group_fights.md
increment 2), on the committed catalogue."""

import json
from dataclasses import replace
from pathlib import Path

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.factory import build_actions
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.obtain_model.drop_routes import drop_fight_winnable
from artifactsmmo_cli.ai.party_win import (
    party_chosen_loadout,
    party_loadout,
    party_participants,
    wears_party_loadout,
    winning_party,
    wins_as_a_party,
)
from artifactsmmo_cli.audit.craft_completeness import CraftCell, census_state

BUNDLE = Path("tests/test_ai/scenarios/fixtures/gamedata_bundle.json")


def _gd() -> GameData:
    gd = GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))
    gd.active_event_codes = {"out_of_the_ground"}
    return gd


def _hero(gd: GameData, level: int = 60):  # type: ignore[no-untyped-def]
    cell = CraftCell(level, "weaponcrafting", level, events=frozenset({"out_of_the_ground"}),
                     skills_at_level=True, gold=10**6, geared=True)
    return census_state("adamantite_sword", cell, gd)


def test_no_party_no_verdict() -> None:
    gd = _gd()
    hero = _hero(gd)
    assert hero.party == () and winning_party(hero, gd, "duskworm") is None


def test_a_party_beats_duskworm_where_one_cannot() -> None:
    """The hero's `greater_lifesteal_rune` (25%) heals 284 off each 1,134 crit
    (server rule, 2026-10-17; the mean model credited 9.75 a round). Alone it
    still loses; one joiner already wins, and two win in enhanced health."""
    gd = _gd()
    hero = _hero(gd)
    party = replace(hero, party=(hero, hero))
    assert not drop_fight_winnable(hero, gd, "duskworm")
    assert winning_party(party, gd, "duskworm") == (("enhanced_health_potion",), (0, 1))
    assert drop_fight_winnable(party, gd, "duskworm")
    assert wins_as_a_party(replace(hero, party=(hero,)), gd, "duskworm")


def test_only_bosses_take_a_party() -> None:
    """cultist_emperor is an elite: no party may fight it."""
    gd = _gd()
    hero = _hero(gd)
    assert gd.monsters.types["cultist_emperor"] == "elite"
    assert winning_party(replace(hero, party=(hero, hero)), gd, "cultist_emperor") is None


def test_a_joiner_that_cannot_stock_the_loadout_wears_none() -> None:
    """Level-1 joiners stock no level-60 potion and bring nothing: duskworm
    stays unbeaten, and a boss no party can hurt stays unbeaten."""
    gd = _gd()
    hero = _hero(gd)
    rookie = _hero(gd, level=1)
    assert winning_party(replace(hero, party=(rookie, rookie)), gd, "duskworm") is None
    assert winning_party(replace(hero, party=(hero, hero)), gd, "sandwhisper_empress") is None


def test_the_memo_tells_parties_apart() -> None:
    """One catalogue, one boss, two parties: the verdict follows the joiners."""
    gd = _gd()
    hero = _hero(gd)
    rookie = _hero(gd, level=1)
    assert winning_party(replace(hero, party=(rookie, rookie)), gd, "duskworm") is None
    assert winning_party(replace(hero, party=(hero, hero)), gd, "duskworm") is not None


def test_a_joiner_that_cannot_stock_a_potion_fights_without_it() -> None:
    """Joiners with no gold, no skill and no potion held stock nothing, so they
    fight duskworm bare: the party needs more of the hero than a party of heroes
    does (water resistance too, not enhanced health alone), and the model judged
    the joiners bare. (Before lifesteal healed its real share of crit damage,
    2026-10-17, this party lost outright.)"""
    gd = _gd()
    hero = _hero(gd)
    poor = replace(hero, skills=dict.fromkeys(hero.skills, 1), gold=0)
    codes = ("water_res_potion", "enhanced_health_potion")
    assert winning_party(replace(hero, party=(poor, poor)), gd, "duskworm") == (codes, (0, 1))
    assert winning_party(replace(hero, party=(hero, hero)), gd, "duskworm") == (codes[1:], (0, 1))
    assert wears_party_loadout(poor, gd, codes)


def test_every_member_is_judged_rested() -> None:
    """Route existence is not an HP question: joiners at 1 HP rest first."""
    gd = _gd()
    hero = _hero(gd)
    hurt = replace(hero, hp=1)
    assert winning_party(replace(hero, party=(hurt, hurt)), gd, "duskworm") is not None


def test_the_participants_are_named_only_where_the_party_is_needed() -> None:
    """duskworm needs two joiners, named; king_slime is won alone, so it is
    fought alone; no party, no participants."""
    gd = _gd()
    hero = _hero(gd)
    party = replace(hero, party=(replace(hero, character="R2D2"), replace(hero, character="Lor")))
    assert party_participants(party, gd, "duskworm") == ("R2D2", "Lor")
    # three ready: the server takes two, the first winning pair
    crowd = replace(party, party=(*party.party, replace(hero, character="C3P0")))
    assert party_participants(crowd, gd, "duskworm") == ("R2D2", "Lor")
    assert party_participants(party, gd, "king_slime") == ()
    assert party_participants(hero, gd, "duskworm") == ()
    assert party_participants(party, gd, "cultist_emperor") == ()


def test_a_solo_fight_the_record_refuses_takes_the_party() -> None:
    """The stats win king_slime alone, but a learned record of losses
    (`WorldState.lost_fights`) voids both solo arms: alone the gate refuses
    it, and with siblings ready the fight takes a party. Live C3P0, 2026-10-12:
    41 of 44 solo king_slime fights lost while the cold gate kept admitting it."""
    gd = _gd()
    hero = _hero(gd)
    lost = replace(hero, lost_fights=frozenset({"king_slime"}))
    assert drop_fight_winnable(hero, gd, "king_slime")
    assert not drop_fight_winnable(lost, gd, "king_slime")
    party = replace(lost, party=(replace(hero, character="R2D2"), replace(hero, character="Lor")))
    assert drop_fight_winnable(party, gd, "king_slime")
    assert party_participants(party, gd, "king_slime") == ("R2D2",)
    # a record against another monster changes nothing here
    other = replace(party, lost_fights=frozenset({"duskworm"}))
    assert party_participants(other, gd, "king_slime") == ()


def test_the_party_names_its_loadout() -> None:
    """duskworm is won in enhanced health; king_slime alone, so no party and no
    loadout."""
    gd = _gd()
    hero = _hero(gd)
    party = replace(hero, party=(replace(hero, character="R2D2"), replace(hero, character="Lor")))
    assert party_loadout(party, gd, "duskworm") == ("enhanced_health_potion",)
    assert party_loadout(party, gd, "king_slime") == ()


def test_each_member_stocks_what_the_party_walk_drinks() -> None:
    gd = _gd()
    hero = _hero(gd)
    codes = ("water_res_potion", "enhanced_health_potion")
    mine = party_chosen_loadout(hero, [hero, hero], gd, "duskworm", codes)
    assert mine.monster == "duskworm" and mine.food == ()
    assert dict(mine.potions)["water_res_potion"] == 1
    assert dict(mine.potions)["enhanced_health_potion"] >= 1
    # a member who cannot stock them fights bare, as the model judged it
    poor = replace(hero, skills=dict.fromkeys(hero.skills, 1), gold=0)
    assert party_chosen_loadout(poor, [hero, hero], gd, "duskworm", codes).potions == ()
    # no loadout, nothing to stock
    assert party_chosen_loadout(hero, [hero], gd, "king_slime", ()).potions == ()


def test_a_member_fights_as_the_model_judged_it() -> None:
    gd = _gd()
    hero = _hero(gd)
    codes = ("water_res_potion", "enhanced_health_potion")
    assert not wears_party_loadout(hero, gd, codes)
    worn = replace(hero, equipment={**hero.equipment, "utility1_slot": "water_res_potion",
                                    "utility2_slot": "enhanced_health_potion"},
                   utility1_slot_quantity=5, utility2_slot_quantity=5)
    assert wears_party_loadout(worn, gd, codes)
    half = replace(worn, utility2_slot_quantity=0)
    assert not wears_party_loadout(half, gd, codes)
    poor = replace(hero, skills=dict.fromkeys(hero.skills, 1), gold=0)
    assert wears_party_loadout(poor, gd, codes)
    assert wears_party_loadout(hero, gd, ())


def test_the_factory_takes_the_party_to_the_boss() -> None:
    gd = _gd()
    hero = _hero(gd)
    party = replace(hero, party=(replace(hero, character="R2D2"), replace(hero, character="Lor")))
    fights = {a.monster_code: a for a in build_actions(gd, party, None, bank_accessible=True,
                                                         task_exchange_min_coins=0)
              if isinstance(a, FightAction)}
    assert fights["duskworm"].participants == ("R2D2", "Lor")
    assert fights["duskworm"].party_loadout == ("enhanced_health_potion",)
    assert fights["king_slime"].participants == () and fights["king_slime"].party_loadout == ()
