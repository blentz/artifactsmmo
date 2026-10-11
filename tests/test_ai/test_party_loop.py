"""A party boss loop's XP rate (`party_loop`, docs/PLAN_group_fights.md
increment 3), on the committed catalogue."""

import json
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

from artifactsmmo_cli.ai.combat import party_boss
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.group_fight_core import group_outcome
from artifactsmmo_cli.ai.loadout_win import stockable_potions
from artifactsmmo_cli.ai.loop_rate import FoodOffer
from artifactsmmo_cli.ai.party_loop import SECONDS_PER_TURN, best_party_loop
from artifactsmmo_cli.ai.party_win import member_card
from artifactsmmo_cli.audit.craft_completeness import CraftCell, census_state

BUNDLE = Path("tests/test_ai/scenarios/fixtures/gamedata_bundle.json")


def _gd() -> GameData:
    gd = GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))
    gd.active_event_codes = {"out_of_the_ground"}
    return gd


def _hero(gd: GameData, level: int):  # type: ignore[no-untyped-def]
    cell = CraftCell(level, "weaponcrafting", level, events=frozenset({"out_of_the_ground"}),
                     skills_at_level=True, gold=10**6, geared=True)
    return census_state("adamantite_sword", cell, gd)


def _prices(state, gd: GameData) -> dict[str, Fraction | None]:  # type: ignore[no-untyped-def]
    return {code: Fraction(1) for code in stockable_potions(state, gd)}


def test_three_farm_duskworm_at_the_party_rate() -> None:
    """Level 45, three members: water resistance and a health potion; the
    fight takes 2 s per actor turn (four actors), the XP is duskworm's at 45."""
    gd = _gd()
    hero = _hero(gd, 45)
    party = replace(hero, party=(hero, hero))
    loop = best_party_loop(party, gd, "duskworm", _prices(hero, gd), ())
    assert loop is not None
    assert loop.loadout == ("water_res_potion", "enhanced_health_potion") and loop.joiners == (0, 1)
    cards = [member_card(m, gd, "duskworm", loop.loadout, stockable_potions(m, gd)) for m in (hero,) * 3]
    walk = group_outcome(party_boss(gd, "duskworm"), cards)
    assert loop.rate.fight_seconds == SECONDS_PER_TURN * walk.turns * 4
    assert loop.rate.xp_per_kill == gd.xp_per_kill("duskworm", 45, hero.wisdom)
    assert loop.rate.xp_per_second > 0 and loop.rate.win


def test_the_party_xp_reads_the_average_level() -> None:
    """A level-40 and a level-50 member against rosenblood (40): XP at 45, as
    a level-45 party — 473, not the 680 a level-40 character earns alone."""
    gd = _gd()
    low, high = _hero(gd, 40), _hero(gd, 50)
    loop = best_party_loop(replace(low, party=(high,)), gd, "rosenblood", _prices(low, gd), ())
    assert gd.xp_per_kill("rosenblood", 40, low.wisdom) == 680
    assert loop is not None and loop.rate.xp_per_kill == gd.xp_per_kill("rosenblood", 45, low.wisdom) == 473


def test_no_party_no_loop_and_only_bosses() -> None:
    gd = _gd()
    hero = _hero(gd, 45)
    prices = _prices(hero, gd)
    assert best_party_loop(hero, gd, "duskworm", prices, ()) is None
    party = replace(hero, party=(hero, hero))
    assert gd.monsters.types["pixie"] == "raid_boss"
    assert best_party_loop(party, gd, "pixie", prices, ()) is None
    assert best_party_loop(party, gd, "cultist_emperor", prices, ()) is None
    # a raid boss pays through the raid reward system: duskworm relabelled
    # raid_boss (no party beats the catalogue's raid bosses) has no XP loop
    assert best_party_loop(party, gd, "duskworm", prices, ()) is not None
    gd.monsters.types["duskworm"] = "raid_boss"
    assert best_party_loop(party, gd, "duskworm", prices, ()) is None


def test_a_boss_grey_to_the_party_pays_nothing() -> None:
    """king_slime (15) is grey to a level-45 party: no loop."""
    gd = _gd()
    hero = _hero(gd, 45)
    assert best_party_loop(replace(hero, party=(hero, hero)), gd, "king_slime",
                           _prices(hero, gd), ()) is None


def test_an_unpayable_drink_drops_the_loadout() -> None:
    """With no price and none held, a potion loop cannot run: duskworm, won
    only on potions, has no loop."""
    gd = _gd()
    hero = _hero(gd, 45)
    unpriced = dict.fromkeys(stockable_potions(hero, gd))
    assert best_party_loop(replace(hero, party=(hero, hero)), gd, "duskworm", unpriced, ()) is None


def test_recovery_eats_the_menu() -> None:
    """The loop's recovery eats food to full; the eaten units are reported."""
    gd = _gd()
    hero = _hero(gd, 45)
    food = (FoodOffer("cooked_trout", 75, Fraction(1), 0),)
    loop = best_party_loop(replace(hero, party=(hero, hero)), gd, "rosenblood", _prices(hero, gd), food)
    assert loop is not None
    missing = loop.rate.max_hp - loop.rate.hp_end
    assert (dict(loop.rate.eaten).get("cooked_trout", 0) > 0) == (missing > 0)
