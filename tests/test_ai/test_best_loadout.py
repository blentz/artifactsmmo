"""The best consumable loadout read from the world
(`docs/PLAN_consumable_utility.md` increment 4)."""

from dataclasses import replace
from fractions import Fraction

import pytest

import artifactsmmo_cli.ai.best_loadout as best_mod
import artifactsmmo_cli.ai.loop_rate as loop_mod
from artifactsmmo_cli.ai.best_loadout import (
    best_loadout,
    candidate_potions,
    chosen,
    fight_ahead_loadout,
    loadout_for,
    loadouts,
    potion_effects_usable,
    units_used,
)
from artifactsmmo_cli.ai.chosen_loadout import ChosenLoadout
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.loop_rate import LoopRate, food_menu, loop_rate
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.thresholds import UTILITY_SLOT_MAX_STACK
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state

_CTX = NO_PROFILE_CONTEXT
_UTILITY = dict(level=1, type_="utility")


def _gd() -> GameData:
    """One ogre: 100 HP, 30 fire a round. The player (20 fire, 100 HP) kills it in
    5 rounds and dies in 4 without help."""
    gd = GameData()
    gd._monster_level = {"ogre": 5}
    gd._monster_hp = {"ogre": 100}
    gd._monster_attack = {"ogre": {"fire": 30}}
    gd._monster_resistance = {"ogre": {}}
    fill_monster_stat_defaults(gd)
    gd._consumable_effect_codes = {
        "heal_potion": ["restore"], "big_heal_potion": ["restore"],
        "fire_res_potion": ["boost_res_fire"], "hp_potion": ["boost_hp"],
        "splash_potion": ["splash_restore"], "antidote": ["antipoison"],
        "high_potion": ["boost_hp"], "mystery_potion": [], "apple": ["heal"]}
    gd._item_stats = {
        "heal_potion": ItemStats(code="heal_potion", hp_restore=40, **_UTILITY),
        "big_heal_potion": ItemStats(code="big_heal_potion", hp_restore=80, **_UTILITY),
        "fire_res_potion": ItemStats(code="fire_res_potion", resistance={"fire": 50}, **_UTILITY),
        "hp_potion": ItemStats(code="hp_potion", hp_bonus=60, **_UTILITY),
        "splash_potion": ItemStats(code="splash_potion", hp_restore=150, **_UTILITY),
        "antidote": ItemStats(code="antidote", **_UTILITY),
        "mystery_potion": ItemStats(code="mystery_potion", **_UTILITY),
        "high_potion": ItemStats(code="high_potion", level=9, type_="utility", hp_bonus=900),
        "apple": ItemStats(code="apple", level=1, type_="consumable", hp_restore=30),
    }
    return gd


def _state(**kw: object) -> WorldState:
    base: dict[str, object] = dict(level=5, hp=100, max_hp=100, attack={"fire": 20},
                                   initiative=1)
    base.update(kw)
    return make_state(**base)


def _prices(monkeypatch: pytest.MonkeyPatch, prices: dict[str, Fraction | None]) -> None:
    def price(code: str, *_: object) -> Fraction | None:
        return prices.get(code)
    monkeypatch.setattr(best_mod, "replacement_price_of", price)
    monkeypatch.setattr(loop_mod, "replacement_price_of", price)


class TestCandidates:
    def test_effects(self) -> None:
        assert potion_effects_usable(("restore",))
        assert potion_effects_usable(("boost_dmg_fire", "boost_dmg_air"))
        assert not potion_effects_usable(())
        assert not potion_effects_usable(("splash_restore",))
        assert not potion_effects_usable(("antipoison",))
        assert not potion_effects_usable(("restore", "antipoison"))

    def test_usable_held_or_priced_in_catalogue_order(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _prices(monkeypatch, {"heal_potion": Fraction(9), "splash_potion": Fraction(1),
                              "antidote": Fraction(1), "high_potion": Fraction(1)})
        state = _state(bank_items={"hp_potion": 2, "high_potion": 5})
        # heal priced; big_heal neither held nor priced; fire_res neither;
        # hp_potion held (no replacement); splash/antidote not a solo fight's
        # effect; high_potion above the level; mystery has no effect.
        assert candidate_potions(state, _gd(), _CTX) == {"heal_potion": Fraction(9), "hp_potion": None}

    def test_loadouts_hold_at_most_one_restore(self) -> None:
        gd = _gd()
        assert loadouts(["heal_potion", "big_heal_potion", "fire_res_potion"], gd) == [
            (), ("heal_potion",), ("big_heal_potion",), ("fire_res_potion",),
            ("heal_potion", "fire_res_potion"), ("big_heal_potion", "fire_res_potion")]


class TestBest:
    def test_no_candidates_is_the_bare_loop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _prices(monkeypatch, {})
        best = best_loadout(_state(), _gd(), _CTX, "ogre")
        assert best.loadout == ()
        assert best.rate == best.bare
        assert best.rate.win is False
        assert chosen(best, "ogre") == ChosenLoadout("ogre", (), ())

    def test_a_free_held_boost_wins_the_fight(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _prices(monkeypatch, {"apple": Fraction(1000)})
        gd = _gd()
        state = _state(bank_items={"fire_res_potion": 40, "apple": 2})
        best = best_loadout(state, gd, _CTX, "ogre")
        assert best.bare.win is False and best.bare.xp_per_second == 0
        assert best.loadout == ("fire_res_potion",)
        food = food_menu(state, gd, _CTX)
        expected = loop_rate(state, gd, "ogre", [("fire_res_potion", UTILITY_SLOT_MAX_STACK)],
                             food, {"fire_res_potion": None})
        assert best.rate == expected
        assert best.rate.win is True
        # one boost a fight, and the held apples the recovery eats
        pick = chosen(best, "ogre")
        assert pick.potions == (("fire_res_potion", 1),)
        assert pick.food == best.rate.eaten == (("apple", 2),)
        assert units_used(best.rate) == 3

    def test_an_unpayable_restore_is_skipped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # One held heal, no replacement: the walk drinks more than one, so that
        # loadout cannot run; the bare loop remains.
        _prices(monkeypatch, {})
        best = best_loadout(_state(inventory={"heal_potion": 1}), _gd(), _CTX, "ogre")
        assert best.loadout == ()

    def test_a_priced_restore_beats_losing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _prices(monkeypatch, {"heal_potion": Fraction(2)})
        best = best_loadout(_state(), _gd(), _CTX, "ogre")
        assert best.loadout == ("heal_potion",)
        assert best.rate.win is True
        drunk = dict(best.rate.used)["heal_potion"]
        assert best.rate.consumed_seconds == 2 * drunk
        assert chosen(best, "ogre").potions == (("heal_potion", drunk),)

    def test_equal_rates_prefer_fewer_units(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # A water boost changes nothing for a fire attacker: fire_res + water
        # runs at exactly fire_res's rate on one more unit a fight, so the
        # single wins the tie (and comes first only by the fewer units: the
        # water boost is EARLIER in the catalogue).
        _prices(monkeypatch, {})
        gd = _gd()
        gd._consumable_effect_codes["water_boost"] = ["boost_dmg_water"]
        gd._item_stats = {"water_boost": ItemStats(code="water_boost", dmg_elements={"water": 12},
                                                   **_UTILITY), **gd._item_stats}
        state = _state(bank_items={"fire_res_potion": 40, "water_boost": 40})
        assert list(candidate_potions(state, gd, _CTX)) == ["water_boost", "fire_res_potion"]
        pair = loop_rate(state, gd, "ogre", [("water_boost", 1), ("fire_res_potion", 1)], (),
                         {"water_boost": None, "fire_res_potion": None})
        best = best_loadout(state, gd, _CTX, "ogre")
        assert pair is not None and pair.xp_per_second == best.rate.xp_per_second > 0
        assert best.loadout == ("fire_res_potion",)

    def test_the_pick_scores_rate_and_units(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # The core breaks a rate tie on the units one fight uses (potions drunk
        # plus food eaten): the reader must hand it both.
        _prices(monkeypatch, {"apple": Fraction(1000)})
        seen: list[list[tuple[Fraction, int]]] = []

        def record(cands: list[tuple[Fraction, int]]) -> int:
            seen.append(list(cands))
            return 0
        monkeypatch.setattr(best_mod, "pick_best", record)
        state = _state(bank_items={"fire_res_potion": 40, "apple": 2})
        best = best_loadout(state, _gd(), _CTX, "ogre")
        assert best.loadout == ()
        bare_units = units_used(best.bare)
        fire = loop_rate(state, _gd(), "ogre", [("fire_res_potion", UTILITY_SLOT_MAX_STACK)],
                         food_menu(state, _gd(), _CTX), {"fire_res_potion": None})
        assert fire is not None
        assert seen == [[(best.bare.xp_per_second, bare_units), (fire.xp_per_second, 3)]]


class TestChosen:
    """The pick as the one value every consumable decision reads (increment 5)."""

    def test_a_potion_the_fight_never_drinks_is_not_chosen(self) -> None:
        # `chosen` keeps only the potions one fight uses: a worn restore whose
        # walk drinks none carries no stock.
        best = best_mod.BestLoadout(("heal_potion",), _rate(used=(("heal_potion", 0),)),
                                    _rate(used=()))
        assert chosen(best, "ogre") == ChosenLoadout("ogre", (), ())

    def test_the_fight_ahead_comes_before_the_grind_target(self, monkeypatch: pytest.MonkeyPatch) -> None:
        asked: list[str] = []

        def fake(state: WorldState, gd: GameData, ctx: object, monster: str,
                 store: object = None) -> best_mod.BestLoadout:
            asked.append(monster)
            return best_mod.BestLoadout((), _rate(used=(), eaten=(("apple", 1),)), _rate(used=()))
        monkeypatch.setattr(best_mod, "best_loadout", fake)
        ctx = replace(_CTX, combat_monster="wolf", fight_monster="ogre")
        assert fight_ahead_loadout(_state(), _gd(), ctx, None) == ChosenLoadout(
            "ogre", (), (("apple", 1),))
        ctx = replace(_CTX, combat_monster="wolf")
        assert fight_ahead_loadout(_state(), _gd(), ctx, None) == ChosenLoadout(
            "wolf", (), (("apple", 1),))
        assert asked == ["ogre", "wolf"]

    def test_no_fight_ahead_chooses_nothing(self) -> None:
        assert fight_ahead_loadout(_state(), _gd(), _CTX, None) is None

    def test_the_cycles_pick_is_reused_for_its_own_monster(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mine = ChosenLoadout("ogre", (("heal_potion", 3),), ())
        monkeypatch.setattr(best_mod, "best_loadout", _refuse)
        assert loadout_for(_state(), _gd(), replace(_CTX, loadout=mine), "ogre") is mine

    def test_another_monster_is_chosen_now(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _prices(monkeypatch, {})
        mine = ChosenLoadout("wolf", (("heal_potion", 3),), ())
        got = loadout_for(_state(), _gd(), replace(_CTX, loadout=mine), "ogre")
        assert got == chosen(best_loadout(_state(), _gd(), _CTX, "ogre"), "ogre")
        assert loadout_for(_state(), _gd(), _CTX, "ogre") == got


def _refuse(*_args: object, **_kw: object) -> best_mod.BestLoadout:
    raise AssertionError("the cycle's own pick must be reused")


def _rate(used: tuple[tuple[str, int], ...], eaten: tuple[tuple[str, int], ...] = ()) -> LoopRate:
    return LoopRate(Fraction(0), 0, False, Fraction(30), Fraction(0), Fraction(0), 100, 0,
                    used, eaten)
