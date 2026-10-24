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
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.grind_heal_prep import heal_prep_goal
from artifactsmmo_cli.ai.loop_rate import FoodOffer, LoopRate, food_menu, loop_rate
from artifactsmmo_cli.ai.strategy_driver import _fight_step_prep
from artifactsmmo_cli.ai.thresholds import UTILITY_SLOT_MAX_STACK
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import TIMED_NO_PROFILE_CONTEXT, make_state

_CTX = TIMED_NO_PROFILE_CONTEXT
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
    gd._monster_locations = {"ogre": [(3, 4)], "wolf": [(1, 1)]}
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
    # a priced potion is one something stocks (`potion_stockable`)
    monkeypatch.setattr(best_mod, "potion_stockable", lambda *a: True)


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


def _bare(state: WorldState, gd: GameData) -> LoopRate:
    """The no-potion loop over `state`'s food menu: what the pick ranks the
    potions against."""
    loop = loop_rate(state, gd, "ogre", [], food_menu(state, gd, _CTX), {}, _CTX.timing(),
                     _CTX.drops(), 0)
    assert loop is not None
    return loop


class TestBest:
    def test_no_candidates_is_the_bare_loop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _prices(monkeypatch, {})
        best = best_loadout(_state(), _gd(), _CTX, "ogre")
        assert best.loadout == ()
        assert best.rate == _bare(_state(), _gd())
        assert best.rate.win is False
        assert chosen(best, "ogre") == ChosenLoadout("ogre", (), (), ())

    def test_a_free_held_boost_wins_the_fight(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _prices(monkeypatch, {"apple": Fraction(1000)})
        gd = _gd()
        state = _state(bank_items={"fire_res_potion": 40, "apple": 2})
        best = best_loadout(state, gd, _CTX, "ogre")
        bare = _bare(state, gd)
        assert bare.win is False and bare.xp_per_second == 0
        assert best.loadout == ("fire_res_potion",)
        food = food_menu(state, gd, _CTX)
        expected = loop_rate(state, gd, "ogre", [("fire_res_potion", UTILITY_SLOT_MAX_STACK)],
                             food, {"fire_res_potion": None}, _CTX.timing(), _CTX.drops(), 0)
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

    def test_a_held_unpriced_restore_runs_on_its_expected_drinks(
            self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Final review I1: one held heal, no replacement; a rare deep ending
        # drinks two, the expectation one. The restore stays payable and is chosen.
        _prices(monkeypatch, {})
        gd = _gd()
        gd._monster_attack["ogre"] = {"fire": 15}
        gd._monster_critical_strike["ogre"] = 20
        state = _state(critical_strike=30, inventory={"heal_potion": 1})
        best = best_loadout(state, gd, _CTX, "ogre")
        assert best.loadout == ("heal_potion",)
        assert best.rate.used == (("heal_potion", 1),) and best.rate.consumed_seconds == 0
        assert best.rate.xp_per_second > _bare(state, gd).xp_per_second

    def test_a_priced_restore_beats_losing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _prices(monkeypatch, {"heal_potion": Fraction(2)})
        best = best_loadout(_state(), _gd(), _CTX, "ogre")
        assert best.loadout == ("heal_potion",)
        assert best.rate.win is True
        drunk = dict(best.rate.used)["heal_potion"]
        assert best.rate.consumed_seconds == 2 * drunk
        assert chosen(best, "ogre").potions == (("heal_potion", drunk),)

    def test_a_restore_potion_beats_a_risky_bare_fight(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # R2D2-shaped: the bare fight wins about two times in three and a loss
        # walks home; a priced restore potion makes the win certain.
        _prices(monkeypatch, {"heal_potion": Fraction(2)})
        gd = _gd()
        gd._item_stats["heal_potion"] = ItemStats(code="heal_potion", hp_restore=70, **_UTILITY)
        state = _state(critical_strike=50, inventory={"heal_potion": 5})
        best = best_loadout(state, gd, _CTX, "ogre")
        bare = _bare(state, gd)
        assert 0 < bare.p_win < 1
        assert best.rate.p_win == 1
        assert best.rate.xp_per_second > bare.xp_per_second
        assert ("heal_potion", dict(best.rate.used)["heal_potion"]) in chosen(best, "ogre").potions

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
                         {"water_boost": None, "fire_res_potion": None}, _CTX.timing(), _CTX.drops(), 0)
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
        bare = _bare(state, _gd())
        fire = loop_rate(state, _gd(), "ogre", [("fire_res_potion", UTILITY_SLOT_MAX_STACK)],
                         food_menu(state, _gd(), _CTX), {"fire_res_potion": None}, _CTX.timing(),
                         _CTX.drops(), 0)
        assert fire is not None
        assert seen == [[(bare.xp_per_second, units_used(bare)), (fire.xp_per_second, 3)]]


class TestChosen:
    """The pick as the one value every consumable decision reads (increment 5)."""

    def test_a_potion_the_fight_never_drinks_is_not_chosen(self) -> None:
        # `chosen` keeps only the potions one fight uses: a worn restore whose
        # walk drinks none carries no stock.
        best = best_mod.BestLoadout(("heal_potion",), _rate(used=(("heal_potion", 0),)),
                                    _rate(used=()))
        assert chosen(best, "ogre") == ChosenLoadout("ogre", (), (), ())

    def test_the_fight_ahead_comes_before_the_grind_target(self, monkeypatch: pytest.MonkeyPatch) -> None:
        asked: list[str] = []

        def fake(state: WorldState, gd: GameData, ctx: object, monster: str,
                 store: object = None) -> best_mod.BestLoadout:
            asked.append(monster)
            return best_mod.BestLoadout((), _rate(used=(), eaten=(("apple", 1),)),
                                        _rate(used=(), eaten=(("apple", 1),)))
        monkeypatch.setattr(best_mod, "best_loadout", fake)
        ctx = replace(_CTX, combat_monster="wolf", fight_monster="ogre")
        assert fight_ahead_loadout(_state(), _gd(), ctx, None) == ChosenLoadout(
            "ogre", (), (("apple", 1),), (("apple", 1),))
        ctx = replace(_CTX, combat_monster="wolf")
        assert fight_ahead_loadout(_state(), _gd(), ctx, None) == ChosenLoadout(
            "wolf", (), (("apple", 1),), (("apple", 1),))
        assert asked == ["ogre", "wolf"]

    def test_a_committed_monster_that_spawns_nowhere_is_no_fight_ahead(self) -> None:
        gd = _gd()
        gd._monster_locations = {}
        ctx = replace(_CTX, fight_monster="ogre")
        assert fight_ahead_loadout(_state(), gd, ctx, None) is None

    def test_a_committed_monster_fought_only_in_an_interior_is_a_fight_ahead(
            self, monkeypatch: pytest.MonkeyPatch) -> None:
        # rat-shaped (final review C1): no legacy spawn, one interior tile, and a
        # loss is possible, so the walk back is priced on the interior tile.
        _prices(monkeypatch, {})
        gd = _interior_gd()
        state = _state(critical_strike=30, bank_items={"apple": 3})
        ctx = replace(_CTX, fight_monster="ogre")
        got = fight_ahead_loadout(state, gd, ctx, None)
        assert got is not None and got == chosen(best_loadout(state, gd, _CTX, "ogre"), "ogre")
        assert 0 < best_loadout(state, gd, _CTX, "ogre").rate.p_win < 1
        assert loadout_for(state, gd, _CTX, "ogre") == got
        prep = heal_prep_goal(state, gd, replace(ctx, loadout=got), "ogre")
        assert repr(prep) == repr(GatherMaterialsGoal(target_item="apple", needed={"apple": 3},
                                                      carry=True))
        step = _fight_step_prep(state, gd, replace(ctx, loadout=got), "ogre")
        assert repr(step) == repr(prep)

    def test_no_fight_ahead_chooses_nothing(self) -> None:
        assert fight_ahead_loadout(_state(), _gd(), _CTX, None) is None

    def test_the_cycles_pick_is_reused_for_its_own_monster(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mine = ChosenLoadout("ogre", (("heal_potion", 3),), (), ())
        monkeypatch.setattr(best_mod, "best_loadout", _refuse)
        assert loadout_for(_state(), _gd(), replace(_CTX, loadout=mine), "ogre") is mine

    def test_another_monster_is_chosen_now(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _prices(monkeypatch, {})
        mine = ChosenLoadout("wolf", (("heal_potion", 3),), (), ())
        got = loadout_for(_state(), _gd(), replace(_CTX, loadout=mine), "ogre")
        assert got == chosen(best_loadout(_state(), _gd(), _CTX, "ogre"), "ogre")
        assert loadout_for(_state(), _gd(), _CTX, "ogre") == got


def _interior_gd() -> GameData:
    gd = _gd()
    gd._monster_locations = {"wolf": [(1, 1)]}
    gd.world.layered_content = {"ogre": [(-3, 12, "interior")]}
    gd._bank_location = (5, 5)
    return gd


def _refuse(*_args: object, **_kw: object) -> best_mod.BestLoadout:
    raise AssertionError("the cycle's own pick must be reused")


def _rate(used: tuple[tuple[str, int], ...], eaten: tuple[tuple[str, int], ...] = ()) -> LoopRate:
    return LoopRate(Fraction(0), 0, False, Fraction(0), Fraction(30), Fraction(0), Fraction(0), 100, 0,
                    used, eaten, True)


def test_a_priced_potion_nothing_stocks_is_no_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    """Live C3P0 2026-10-10: health_potion priced by a GE fill, unbrewable at
    alchemy 17 — chosen, and fought without."""
    _prices(monkeypatch, {"heal_potion": Fraction(9)})
    monkeypatch.setattr(best_mod, "potion_stockable", lambda *a: False)
    assert candidate_potions(_state(), _gd(), _CTX) == {}
    assert candidate_potions(_state(bank_items={"heal_potion": 1}), _gd(), _CTX) == {"heal_potion": Fraction(9)}


def test_made_food_is_the_recovery_with_nothing_held(monkeypatch: pytest.MonkeyPatch) -> None:
    """Spec 1: held food is eaten free, but the stock is MADE only when food
    still beats Rest at replacement price."""
    rates = iter([
        _rate(used=(), eaten=(("apple", 2),)),   # the pick, apples held free
        _rate(used=(), eaten=()),                 # nothing held: Rest wins
    ])
    monkeypatch.setattr(best_mod, "loop_rate", lambda *a, **k: next(rates))
    monkeypatch.setattr(best_mod, "loadouts", lambda prices, gd: [()])
    monkeypatch.setattr(best_mod, "candidate_potions", lambda *a, **k: {})
    monkeypatch.setattr(best_mod, "food_menu",
                        lambda *a, **k: (FoodOffer("apple", 50, Fraction(90), 10),))
    best = best_loadout(_state(), GameData(), _CTX, "wolf")
    picked = chosen(best, "wolf")
    assert picked.food == (("apple", 2),)
    assert picked.made_food == ()


def test_the_made_recovery_holds_nothing_and_drops_unpriced_food(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[FoodOffer, ...]] = []

    def fake_loop_rate(state: object, gd: object, monster: object, loadout: object,
                       food: tuple[FoodOffer, ...], prices: object, timing: object,
                       drops: object, carried: object) -> LoopRate:
        seen.append(tuple(food))
        return _rate(used=(), eaten=())

    monkeypatch.setattr(best_mod, "loop_rate", fake_loop_rate)
    monkeypatch.setattr(best_mod, "loadouts", lambda prices, gd: [()])
    monkeypatch.setattr(best_mod, "candidate_potions", lambda *a, **k: {})
    menu = (FoodOffer("apple", 50, Fraction(90), 10),
            FoodOffer("relic_bread", 80, None, 4))
    monkeypatch.setattr(best_mod, "food_menu", lambda *a, **k: menu)
    best_loadout(_state(), GameData(), _CTX, "wolf")
    assert seen == [menu, (FoodOffer("apple", 50, Fraction(90), 0),)]


def _scripted(monkeypatch: pytest.MonkeyPatch, codes: list[tuple[str, ...]],
              rates: list[LoopRate | None]) -> None:
    """`best_loadout` over `codes`, its loops answering `rates` in call order."""
    answers = iter(rates)
    monkeypatch.setattr(best_mod, "loop_rate", lambda *a, **k: next(answers))
    monkeypatch.setattr(best_mod, "loadouts", lambda prices, gd: list(codes))
    monkeypatch.setattr(best_mod, "candidate_potions", lambda *a, **k: {})
    monkeypatch.setattr(best_mod, "food_menu", lambda *a, **k: ())


class TestNoRoom:
    """Spec 2026-10-18 §2.10 (ruling T13c): a loop with drops and no room in the
    bag for them does not run. The pick is among the loops that run, and when
    none does it is still made, and flagged: never "no fight ahead"."""

    def test_no_loop_that_runs_still_picks_the_fewest_units(
            self, monkeypatch: pytest.MonkeyPatch) -> None:
        heavy = replace(_rate(used=(), eaten=(("apple", 3),)), runnable=False)
        light = replace(_rate(used=(("heal_potion", 1),)), runnable=False)
        _scripted(monkeypatch, [(), ("heal_potion",)], [heavy, light, light])
        best = best_loadout(_state(), _gd(), _CTX, "ogre")
        assert (best.loadout, best.rate, best.made) == (("heal_potion",), light, light)
        assert chosen(best, "ogre") == ChosenLoadout("ogre", (("heal_potion", 1),), (), (),
                                                     runnable=False)

    def test_a_loop_that_runs_beats_one_that_does_not(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The unrunnable loop uses fewer units; the runnable one is the pick."""
        stuck = replace(_rate(used=()), runnable=False)
        runs = _rate(used=(("heal_potion", 2),))
        _scripted(monkeypatch, [(), ("heal_potion",)], [stuck, runs, runs])
        best = best_loadout(_state(), _gd(), _CTX, "ogre")
        assert best.loadout == ("heal_potion",) and best.rate.runnable
        assert chosen(best, "ogre").runnable is True

    def test_the_loop_without_room_is_not_picked(self) -> None:
        """A bag of 0: the fire-res loop wins and drops a bone it has no room
        for, so it does not run; the bare loop loses, drops nothing and runs."""
        gd = _gd()
        gd._monster_drops = {"ogre": [("bone", 1, 1, 1)]}
        gd._item_stats["bone"] = ItemStats(code="bone", level=1, type_="resource")
        gd._bank_location = (5, 5)
        state = _state(bank_items={"fire_res_potion": 40}, inventory_max=0)
        best = best_loadout(state, gd, _CTX, "ogre")
        assert best.loadout == () and best.rate.p_win == 0 and best.rate.runnable
        roomy = best_loadout(replace(state, inventory_max=100), gd, _CTX, "ogre")
        assert roomy.loadout == ("fire_res_potion",)

    def test_what_the_keep_carries_takes_room(self) -> None:
        """A bag of 1 holding the one bone the step needs (its goal materials,
        `inventory_keep.carried_keep`): the fire-res loop wins a bone it has no
        room for, so the bare loop is the pick; with the bone not needed it
        is banked, and the fire-res loop has its room."""
        gd = _gd()
        gd._monster_drops = {"ogre": [("bone", 1, 1, 1)]}
        gd._item_stats["bone"] = ItemStats(code="bone", level=1, type_="resource")
        gd._bank_location = (5, 5)
        state = _state(bank_items={"fire_res_potion": 40}, inventory={"bone": 1}, inventory_max=1)
        kept = best_loadout(state, gd, replace(_CTX, step_profile={"bone": 1}), "ogre")
        assert kept.loadout == ()
        banked = best_loadout(state, gd, _CTX, "ogre")
        assert banked.loadout == ("fire_res_potion",)
