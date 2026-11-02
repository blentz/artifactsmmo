"""The fight loop's XP rate read from the world
(`docs/PLAN_consumable_utility.md` increments 3-4)."""

from fractions import Fraction

import pytest

import artifactsmmo_cli.ai.loop_rate as loop_mod
from artifactsmmo_cli.ai.actions.cost_core import DEPOSIT_SECONDS_PER_CODE, travel_seconds
from artifactsmmo_cli.ai.boost_selection import project_equip
from artifactsmmo_cli.ai.chosen_loadout import CARRY_HORIZON_FIGHTS, food_carry, food_shares, potion_carry
from artifactsmmo_cli.ai.combat import combat_terms, fight_max_hp
from artifactsmmo_cli.ai.fight_odds_core import win_probability
from artifactsmmo_cli.ai.fight_outcome_core import fight_outcome
from artifactsmmo_cli.ai.fight_walk import fight_walk, odds_walk, walk_seconds
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.inventory_keep import CarriedKeep
from artifactsmmo_cli.ai.learned_drops import LearnedDrops
from artifactsmmo_cli.ai.learning.fight_seconds_model import committed_timing
from artifactsmmo_cli.ai.loop_rate import EAT_SECONDS, FoodOffer, LoopRate, food_menu, loop_rate
from artifactsmmo_cli.ai.loop_rate_core import consumed_seconds, recovery_choice, recovery_seconds, xp_per_second
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state

_CTX = NO_PROFILE_CONTEXT
_TIMING = committed_timing()[0]
"""The committed live capture's fight-seconds fit (spec 2026-10-18 §2.9)."""
_UTILITY = dict(level=1, type_="utility")
_NOTHING_KEPT = CarriedKeep(0, 0)
"""A bag the keep leaves empty through a deposit."""


def _gd() -> GameData:
    """One ogre: 100 HP, 30 fire a round. The player (20 fire, 100 HP) kills it in
    5 rounds and dies in 4 without help."""
    gd = GameData()
    gd._monster_level = {"ogre": 5}
    gd._monster_hp = {"ogre": 100}
    gd._monster_attack = {"ogre": {"fire": 30}}
    gd._monster_resistance = {"ogre": {}}
    fill_monster_stat_defaults(gd)
    gd._monster_locations = {"ogre": [(3, 4)]}
    gd._consumable_effect_codes = {"heal_potion": ["restore"], "splash_potion": ["splash_restore"]}
    gd._item_stats = {
        "heal_potion": ItemStats(code="heal_potion", hp_restore=40, **_UTILITY),
        "big_heal_potion": ItemStats(code="big_heal_potion", hp_restore=80, **_UTILITY),
        "fire_res_potion": ItemStats(code="fire_res_potion", resistance={"fire": 50}, **_UTILITY),
        "hp_potion": ItemStats(code="hp_potion", hp_bonus=60, **_UTILITY),
        "splash_potion": ItemStats(code="splash_potion", hp_restore=150, **_UTILITY),
        "apple": ItemStats(code="apple", level=1, type_="consumable", hp_restore=30),
        "bread": ItemStats(code="bread", level=1, type_="consumable", hp_restore=60),
        "sword": ItemStats(code="sword", level=1, type_="weapon", attack={"fire": 5}),
    }
    return gd


_FREE: dict[str, Fraction | None] = {
    code: Fraction(0) for code in ("heal_potion", "big_heal_potion", "fire_res_potion", "hp_potion",
                                   "splash_potion", "apple")}


def _rate(state: WorldState, gd: GameData, loadout: list[tuple[str, int]],
          prices: dict[str, Fraction | None] | None = None,
          food: tuple[FoodOffer, ...] = ()) -> LoopRate | None:
    return loop_rate(state, gd, "ogre", loadout, food, _FREE if prices is None else prices,
                     _TIMING, LearnedDrops.empty(), _NOTHING_KEPT)


def _state(**kw: object) -> WorldState:
    base: dict[str, object] = dict(level=5, hp=100, max_hp=100, attack={"fire": 20},
                                   initiative=1)
    base.update(kw)
    return make_state(**base)


class TestValidation:
    @pytest.mark.parametrize("loadout, match", [
        ([("heal_potion", 1), ("fire_res_potion", 1), ("hp_potion", 1)], "slots"),
        ([("heal_potion", 1), ("heal_potion", 2)], "one code per utility slot"),
        ([("apple", 1)], "not a utility potion"),
        ([("no_such_item", 1)], "not a utility potion"),
        ([("heal_potion", 0)], "stock of at least 1"),
        ([("heal_potion", 1), ("big_heal_potion", 1)], "two restore potions"),
        ([("splash_potion", 1)], "ANOTHER character"),
    ])
    def test_an_unwearable_loadout_raises(self, loadout: list[tuple[str, int]],
                                          match: str) -> None:
        with pytest.raises(ValueError, match=match):
            _rate(_state(), _gd(), loadout)


class TestLoop:
    def test_no_potions_loses_and_earns_nothing(self) -> None:
        rate = _rate(_state(), _gd(), [])
        assert rate is not None
        assert (rate.win, rate.xp_per_kill, rate.xp_per_second, rate.used) == (False, 0, 0, ())
        assert rate.p_win == 0
        assert rate.hp_end == loop_mod.LOSS_HP
        assert rate.recovery_seconds == 99  # the bar a loss leaves at 1 HP, rested off

    def test_a_held_restore_wins_the_fight_and_is_free(self) -> None:
        gd = _gd()
        state = _state(inventory={"heal_potion": 5})
        rate = _rate(state, gd, [("heal_potion", 5)], prices={"heal_potion": Fraction(99)})
        assert rate is not None
        expected = fight_outcome(combat_terms(state, gd, "ogre"), 100, 100, 40, 5)
        assert rate.win is expected.win is True
        assert rate.used == (("heal_potion", expected.used),)
        assert expected.used > 0
        assert rate.consumed_seconds == 0
        assert rate.hp_end == expected.hp_end // 10_000
        assert rate.xp_per_kill == gd.xp_per_kill("ogre", 5) > 0
        # Five rounds, the player first: the kill is the ninth server turn.
        fight = _TIMING.seconds(Fraction(9), 0)
        assert rate.fight_seconds == fight
        assert rate.recovery_seconds == recovery_seconds(100 - rate.hp_end, 100, [], EAT_SECONDS, 0, 0)
        assert rate.xp_per_second == rate.xp_per_kill / (fight + rate.recovery_seconds)

    def test_a_boost_is_projected_and_one_is_consumed(self) -> None:
        gd = _gd()
        state = _state(bank_items={"fire_res_potion": 3})
        rate = _rate(state, gd, [("fire_res_potion", 3)])
        assert rate is not None
        assert rate.win is True          # 15 a round: dies in 7, kills in 5
        assert rate.used == (("fire_res_potion", 1),)
        assert rate.hp_end == 100 - 4 * 15

    def test_two_boosts_fill_both_slots(self) -> None:
        gd = _gd()
        state = _state(inventory={"fire_res_potion": 1, "hp_potion": 1})
        rate = _rate(state, gd, [("fire_res_potion", 1), ("hp_potion", 1)])
        assert rate is not None
        assert rate.max_hp == 160
        assert rate.hp_end == 160 - 4 * 15

    def test_a_worn_boost_left_out_of_the_loadout_is_taken_off(self) -> None:
        gd = _gd()
        worn = _state(inventory={"fire_res_potion": 1})
        worn = project_equip(worn, "fire_res_potion", gd, stock=1)
        bare = loop_mod.loop_rate(worn, gd, "ogre", [], (), {}, _TIMING, LearnedDrops.empty(), _NOTHING_KEPT)
        assert bare is not None and bare.win is False

    def test_a_priced_consumable_costs_its_price(self) -> None:
        rate = _rate(_state(), _gd(), [("fire_res_potion", 1)], prices={"fire_res_potion": Fraction(7)})
        assert rate is not None
        assert rate.consumed_seconds == 7

    def test_held_drinks_are_free_and_further_ones_priced(self) -> None:
        gd = _gd()
        prices: dict[str, Fraction | None] = {"heal_potion": Fraction(5)}
        bare = _rate(_state(), gd, [("heal_potion", 9)], prices=prices)
        assert bare is not None
        drunk = dict(bare.used)["heal_potion"]
        assert drunk >= 2
        assert bare.consumed_seconds == 5 * drunk
        one_held = _rate(_state(inventory={"heal_potion": 1}), gd, [("heal_potion", 9)], prices=prices)
        assert one_held is not None
        assert one_held.consumed_seconds == 5 * (drunk - 1)
        all_held = _rate(_state(bank_items={"heal_potion": drunk}), gd, [("heal_potion", 9)],
                         prices=prices)
        assert all_held is not None and all_held.consumed_seconds == 0

    def test_an_unpriceable_drink_past_the_held_makes_the_loop_unrunnable(self) -> None:
        gd = _gd()
        assert _rate(_state(), gd, [("fire_res_potion", 1)], prices={"fire_res_potion": None}) is None
        held = _rate(_state(inventory={"fire_res_potion": 1}), gd, [("fire_res_potion", 1)],
                     prices={"fire_res_potion": None})
        assert held is not None and held.consumed_seconds == 0

    def test_an_undrunk_restore_is_not_priced(self) -> None:
        # Full resistance stops the drink: the restore is never needed, so its
        # (absent) price is never paid.
        gd = _gd()
        gd._item_stats["fire_res_potion"] = ItemStats(
            code="fire_res_potion", resistance={"fire": 100}, **_UTILITY)
        rate = _rate(_state(), gd, [("fire_res_potion", 1), ("heal_potion", 2)],
                     prices={"fire_res_potion": Fraction(0), "heal_potion": None})
        assert rate is not None
        assert rate.used == (("fire_res_potion", 1), ("heal_potion", 0))

    def test_foods_shorten_recovery_and_are_reported_eaten(self) -> None:
        gd = _gd()
        state = _state(inventory={"heal_potion": 5}, inventory_max=200)
        food = (FoodOffer("apple", 30, Fraction(0), 1), FoodOffer("bread", 60, None, 1))
        with_food = _rate(state, gd, [("heal_potion", 5)], food=food)
        without = _rate(state, gd, [("heal_potion", 5)])
        assert with_food is not None and without is not None
        assert with_food.recovery_seconds < without.recovery_seconds
        assert with_food.xp_per_second > without.xp_per_second
        assert without.eaten == ()
        assert with_food.eaten and all(code in ("apple", "bread") for code, _ in with_food.eaten)
        assert all(n > 0 for _, n in with_food.eaten)


class TestOdds:
    """The loop is priced by every crit ending of its fight (spec 2026-10-15 §2)."""

    def test_a_sure_win_with_no_crits_prices_as_the_one_walk_did(self) -> None:
        # No crit on either side: the fight has one ending, so the expectation
        # IS the one `fight_walk` walk, priced the way the loop was before the
        # odds (a held drink free, the rest at their price, the food menu).
        gd = _gd()
        state = _state(inventory={"heal_potion": 1, "apple": 1}, inventory_max=200)
        loadout = [("heal_potion", 5)]
        prices: dict[str, Fraction | None] = {"heal_potion": Fraction(7)}
        food = (FoodOffer("apple", 30, Fraction(3), 1),)
        outcome, max_hp, restore = fight_walk(state, gd, "ogre", loadout)
        assert outcome.win and restore == "heal_potion" and outcome.used > 1
        consumed = consumed_seconds([(outcome.used, Fraction(7), 1)])
        assert consumed is not None and consumed > 0
        # The bag's room for the apple: its cap less the potion carry past the
        # five worn, and its slots less the potion's stack.
        room = 200 - (potion_carry(outcome.used) - 5)
        recovery, counts = recovery_choice(max_hp - outcome.hp_end // 10_000, max_hp,
                                           [(30, Fraction(3), 1, room)], EAT_SECONDS, room, 19)
        xp = gd.xp_per_kill("ogre", 5)
        rate = _rate(state, gd, loadout, prices=prices, food=food)
        assert rate is not None and rate.p_win == 1
        fight = walk_seconds(state, gd, "ogre", loadout, _TIMING)
        assert rate.fight_seconds == fight
        assert rate.xp_per_second == xp_per_second(xp, fight, recovery, consumed)
        assert rate.used == (("heal_potion", outcome.used),)
        assert rate.eaten == tuple(("apple", k) for k in counts if k > 0)
        assert rate.hp_end == outcome.hp_end // 10_000

    def test_a_held_unpriced_potion_pays_on_its_expected_drinks(self) -> None:
        # Final review I1: one held potion, no replacement. A rare deep ending
        # drinks two, but the expected drinks round up to one: the loop runs and
        # the drinks are free.
        gd = _gd()
        gd._monster_attack["ogre"] = {"fire": 15}
        gd._monster_critical_strike["ogre"] = 20
        state = _state(critical_strike=30, inventory={"heal_potion": 1})
        loadout = [("heal_potion", 3)]
        endings, _, _ = odds_walk(state, gd, "ogre", loadout)
        assert max(e.used for e in endings) == 2
        rate = _rate(state, gd, loadout, prices={"heal_potion": None})
        assert rate is not None
        assert rate.used == (("heal_potion", 1),) and rate.consumed_seconds == 0

    def test_a_priced_potion_is_paid_per_ending(self) -> None:
        # The same fight with a replacement price: the deep ending's second
        # drink is paid, so the loop costs that ending's share of it.
        gd = _gd()
        gd._monster_attack["ogre"] = {"fire": 15}
        gd._monster_critical_strike["ogre"] = 20
        state = _state(critical_strike=30, inventory={"heal_potion": 1})
        loadout = [("heal_potion", 3)]
        endings, _, _ = odds_walk(state, gd, "ogre", loadout)
        deep = sum((e.prob for e in endings if e.used == 2), Fraction(0))
        rate = _rate(state, gd, loadout, prices={"heal_potion": Fraction(7)})
        assert rate is not None and 0 < deep < 1
        assert rate.consumed_seconds == 7 * deep

    def test_an_unpriced_potion_expected_past_the_held_is_unrunnable(self) -> None:
        gd = _gd()
        gd._monster_attack["ogre"] = {"fire": 25}
        gd._monster_critical_strike["ogre"] = 10
        state = _state(inventory={"heal_potion": 2})
        loadout = [("heal_potion", 3)]
        endings, _, _ = odds_walk(state, gd, "ogre", loadout)
        mean = sum((e.prob * e.used for e in endings), Fraction(0))
        assert 2 < mean < 3
        assert _rate(state, gd, loadout, prices={"heal_potion": None}) is None
        held = _rate(_state(inventory={"heal_potion": 3}), gd, loadout, prices={"heal_potion": None})
        assert held is not None and held.used == (("heal_potion", 3),)

    def test_a_risky_fight_pays_its_losses(self) -> None:
        gd = _gd()
        state = _state(critical_strike=30)
        rate = _rate(state, gd, [])
        endings, _, _ = odds_walk(state, gd, "ogre", [])
        p = win_probability(endings)
        assert 0 < p < 1
        recovery = sum((e.prob * recovery_seconds(100 - (e.hp_end // 10_000 if e.win else loop_mod.LOSS_HP),
                                                  100, [], EAT_SECONDS, 0, 0) for e in endings), Fraction(0))
        walk = travel_seconds((0, 0), (3, 4))
        assert rate is not None
        assert rate.p_win == p
        assert rate.xp_per_kill == gd.xp_per_kill("ogre", 5) > 0
        assert rate.recovery_seconds == recovery
        fight = walk_seconds(state, gd, "ogre", [], _TIMING)
        assert rate.xp_per_second == p * rate.xp_per_kill / (fight + recovery + (1 - p) * walk)

    def test_a_loss_still_pays_its_drinks(self) -> None:
        gd = _gd()
        gd._monster_attack["ogre"] = {"fire": 60}
        state = _state()
        loadout = [("heal_potion", 1)]
        endings, _, _ = odds_walk(state, gd, "ogre", loadout)
        assert all(not e.win and e.used > 0 for e in endings)
        rate = _rate(state, gd, loadout, prices={"heal_potion": Fraction(5)})
        assert rate is not None and rate.p_win == 0
        assert rate.consumed_seconds > 0
        assert rate.xp_per_kill == 0

    def test_expected_drinks_round_up(self) -> None:
        gd = _gd()
        gd._monster_attack["ogre"] = {"fire": 15}
        gd._monster_critical_strike["ogre"] = 20
        state = _state(critical_strike=30, inventory={"heal_potion": 3})
        loadout = [("heal_potion", 3)]
        endings, _, _ = odds_walk(state, gd, "ogre", loadout)
        mean = sum((e.prob * e.used for e in endings), Fraction(0))
        assert 0 < mean < 1
        rate = _rate(state, gd, loadout)
        assert rate is not None and rate.used == (("heal_potion", 1),)

    def test_expected_food_rounds_up(self) -> None:
        gd = _gd()
        state = _state(critical_strike=30)
        food = (FoodOffer("apple", 30, Fraction(0), 1),)
        rate = _rate(state, gd, [], food=food)
        assert rate is not None
        assert rate.eaten and all(isinstance(n, int) and n >= 1 for _, n in rate.eaten)

    def test_no_spawn_tile_raises(self) -> None:
        gd = _gd()
        gd._monster_locations = {}
        with pytest.raises(ValueError, match="no spawn tile"):
            _rate(_state(), gd, [])

    def test_a_sure_win_needs_no_spawn_tile(self) -> None:
        gd = _gd()
        gd._monster_locations = {}
        rate = _rate(_state(inventory={"heal_potion": 5}), gd, [("heal_potion", 5)])
        assert rate is not None and rate.p_win == 1 and rate.xp_per_second > 0

    def test_the_nearest_spawn_tile_to_the_respawn_prices_the_walk(self) -> None:
        gd = _gd()
        gd._monster_locations = {"ogre": [(9, 9), (3, 4), (4, 3)]}
        assert loop_mod.monster_tile(_state(), gd, "ogre") == (3, 4)

    def test_an_interior_only_monster_walks_back_to_its_interior_tile(self) -> None:
        # rat-shaped (final review C1): no legacy spawn, one interior tile, the
        # factory's fight tile. The walk back is priced on its (x, y).
        gd = _gd()
        gd._monster_locations = {}
        gd.world.layered_content = {"ogre": [(-3, 12, "interior")]}
        state = _state(critical_strike=30)
        rate = _rate(state, gd, [])
        assert rate is not None and 0 < rate.p_win < 1
        assert loop_mod.monster_tile(state, gd, "ogre") == (-3, 12)
        walk = travel_seconds((0, 0), (-3, 12))
        assert rate.xp_per_second == rate.p_win * rate.xp_per_kill / (
            walk_seconds(state, gd, "ogre", [], _TIMING) + rate.recovery_seconds
            + (1 - rate.p_win) * walk)


class TestFoodMenu:
    def test_held_or_priced_at_level_in_catalogue_order(self, monkeypatch: pytest.MonkeyPatch) -> None:
        gd = _gd()
        gd._item_stats["feast"] = ItemStats(code="feast", level=9, type_="consumable", hp_restore=500)
        gd._item_stats["rare_fruit"] = ItemStats(code="rare_fruit", level=1, type_="consumable",
                                                 hp_restore=20)
        prices = {"apple": Fraction(40), "bread": None, "feast": Fraction(1), "rare_fruit": None}
        monkeypatch.setattr(loop_mod, "replacement_price_of", lambda code, *a: prices[code])
        state = _state(bank_items={"bread": 2, "feast": 3})
        # apple priced (none held); bread held, no replacement; feast above the
        # level; rare_fruit neither held nor priced.
        assert food_menu(state, gd, _CTX) == (
            FoodOffer("apple", 30, Fraction(40), 0), FoodOffer("bread", 60, None, 2))


class TestProjection:
    def test_fight_max_hp_is_the_projected_loadouts(self) -> None:
        gd = _gd()
        assert fight_max_hp(_state(), gd, "ogre") == 100
        boosted = project_equip(_state(inventory={"hp_potion": 1}), "hp_potion", gd,
                                slot="utility2_slot", stock=1)
        assert boosted.equipment["utility2_slot"] == "hp_potion"
        assert fight_max_hp(boosted, gd, "ogre") == 160

    def test_project_equip_none_empties_the_slot(self) -> None:
        gd = _gd()
        worn = project_equip(_state(inventory={"hp_potion": 1}), "hp_potion", gd, stock=1)
        assert (worn.max_hp, fight_max_hp(worn, gd, "ogre")) == (100, 160)
        emptied = project_equip(worn, None, gd, stock=0)
        assert emptied.equipment["utility1_slot"] is None
        assert (emptied.max_hp, fight_max_hp(emptied, gd, "ogre")) == (100, 100)
        assert "hp_potion" not in emptied.inventory


def test_effect_codes_tell_a_splash_from_a_restore() -> None:
    gd = _gd()
    assert gd.effect_codes("heal_potion") == ("restore",)
    assert gd.effect_codes("splash_potion") == ("splash_restore",)
    assert gd.effect_codes("apple") == ()


class TestFightSeconds:
    """Spec 2026-10-18 §2.9: the loop's fight lasts the learned seconds at the
    walk's expected server turns, so a faster kill is a shorter fight."""

    def test_the_fight_is_its_turns_at_the_learned_seconds(self) -> None:
        """The ogre falls in 3 rounds to 40 fire with the player first: the
        kill is the fifth server turn."""
        rate = _rate(_state(attack={"fire": 40}), _gd(), [])
        assert rate is not None and rate.p_win == 1
        assert rate.fight_seconds == _TIMING.seconds(Fraction(5), 0)

    def test_a_faster_kill_is_a_shorter_fight_and_a_better_rate(self) -> None:
        """More attack, fewer rounds: fewer seconds a fight, more XP a second."""
        gd = _gd()
        slow = _rate(_state(attack={"fire": 25}), gd, [])
        fast = _rate(_state(attack={"fire": 40}), gd, [])
        assert slow is not None and fast is not None
        assert fast.fight_seconds < slow.fight_seconds
        assert fast.xp_per_second > slow.xp_per_second

    def test_haste_shortens_the_fight(self) -> None:
        gd = _gd()
        plain = _rate(_state(attack={"fire": 40}), gd, [])
        hasted = _rate(_state(attack={"fire": 40}, haste=20), gd, [])
        assert plain is not None and hasted is not None
        assert hasted.fight_seconds == _TIMING.seconds(Fraction(5), 20) < plain.fight_seconds


def _trip_gd() -> GameData:
    """`_gd`'s ogre dropping a `bone` on every win (1 in 1, one unit) and a
    `hide` on half of them (1 in 2, one to three): two units a win at the API
    prior, two distinct codes. Its twin `far_ogre` is the same monster spawning
    150 tiles further from the bank at (13, 4), which is 10 tiles (50 s) from
    the ogre's (3, 4). The `satchel` is a bag of 15."""
    gd = _gd()
    gd._monster_level = {"ogre": 5, "far_ogre": 5}
    gd._monster_hp = {"ogre": 100, "far_ogre": 100}
    gd._monster_attack = {"ogre": {"fire": 30}, "far_ogre": {"fire": 30}}
    gd._monster_resistance = {"ogre": {}, "far_ogre": {}}
    fill_monster_stat_defaults(gd)
    gd._monster_locations = {"ogre": [(3, 4)], "far_ogre": [(-27, -116)]}
    table = [("bone", 1, 1, 1), ("hide", 2, 1, 3)]
    gd._monster_drops = {"ogre": list(table), "far_ogre": list(table)}
    gd._bank_location = (13, 4)
    gd._item_stats = {**gd._item_stats,
                      "bone": ItemStats(code="bone", level=1, type_="resource"),
                      "hide": ItemStats(code="hide", level=1, type_="resource"),
                      "satchel": ItemStats(code="satchel", level=1, type_="bag",
                                           inventory_space=15)}
    return gd


def _trip_rate(state: WorldState, gd: GameData, monster: str = "ogre",
               loadout: list[tuple[str, int]] | None = None, food: tuple[FoodOffer, ...] = (),
               drops: LearnedDrops | None = None,
               carried: CarriedKeep = _NOTHING_KEPT) -> LoopRate | None:
    return loop_rate(state, gd, monster, loadout or [], food, _FREE, _TIMING,
                     LearnedDrops.empty() if drops is None else drops, carried)


_WINS = dict(attack={"fire": 40})
"""The ogre falls in 3 rounds to 40 fire: every fight is won (`TestFightSeconds`)."""


class TestBankTrips:
    """Spec 2026-10-18 §2.10: the drops fill the bag, and a full bag is a trip to
    the bank, so each fight carries `trip × drops / room` seconds of trips."""

    def test_each_fight_carries_its_share_of_the_trips(self) -> None:
        """Two units a win into a bag of 20: a trip every 10 fights. A trip walks
        50 s each way and deposits each of the two codes once."""
        rate = _trip_rate(_state(**_WINS), _trip_gd())
        assert rate is not None and rate.p_win == 1
        trip = 2 * 50 + 2 * Fraction(DEPOSIT_SECONDS_PER_CODE)
        assert rate.xp_per_second == rate.xp_per_kill / (
            rate.fight_seconds + rate.recovery_seconds + trip * 2 / 20)

    def test_the_bag_holds_less_what_the_keep_carries(self) -> None:
        rate = _trip_rate(_state(**_WINS), _trip_gd(), carried=CarriedKeep(5, 1))
        assert rate is not None
        trip = 2 * 50 + 2 * Fraction(DEPOSIT_SECONDS_PER_CODE)
        assert rate.xp_per_second == rate.xp_per_kill / (
            rate.fight_seconds + rate.recovery_seconds + trip * 2 / 15)

    def test_the_food_the_recovery_eats_is_carried(self) -> None:
        state = _state(**_WINS, inventory_max=100)
        rate = _trip_rate(state, _trip_gd(), food=(FoodOffer("apple", 30, Fraction(0), 9),))
        assert rate is not None
        [(_, eaten)] = rate.eaten
        trip = 2 * 50 + 2 * Fraction(DEPOSIT_SECONDS_PER_CODE)
        assert rate.xp_per_second == rate.xp_per_kill / (
            rate.fight_seconds + rate.recovery_seconds
            + trip * 2 / (100 - food_carry(eaten, 100, None)))

    def test_the_potion_carry_past_the_worn_stock_is_carried(self) -> None:
        """A heal potion worn one at a time: what the carry holds past it sits
        in the bag."""
        state = _state(**_WINS, inventory_max=200, critical_strike=30)
        rate = _trip_rate(state, _trip_gd(), loadout=[("heal_potion", 1)])
        assert rate is not None
        [(_, used)] = rate.used
        assert used >= 1
        trip = 2 * 50 + 2 * Fraction(DEPOSIT_SECONDS_PER_CODE)
        drops = rate.p_win * 2
        assert rate.xp_per_second == rate.p_win * rate.xp_per_kill / (
            rate.fight_seconds + rate.recovery_seconds + rate.consumed_seconds
            + (1 - rate.p_win) * travel_seconds((0, 0), (3, 4))
            + trip * drops / (200 - (potion_carry(used) - 1)))

    def test_a_worn_stock_past_the_carry_frees_no_room(self) -> None:
        """A full utility slot holds more than the carry: nothing of it sits in
        the bag, and the slot frees nothing in it either."""
        state = _state(**_WINS, inventory_max=20, critical_strike=30)
        rate = _trip_rate(state, _trip_gd(), loadout=[("heal_potion", 100)])
        assert rate is not None
        [(_, used)] = rate.used
        assert potion_carry(used) < 100
        trip = 2 * 50 + 2 * Fraction(DEPOSIT_SECONDS_PER_CODE)
        assert rate.xp_per_second == rate.p_win * rate.xp_per_kill / (
            rate.fight_seconds + rate.recovery_seconds + rate.consumed_seconds
            + (1 - rate.p_win) * travel_seconds((0, 0), (3, 4))
            + trip * rate.p_win * 2 / 20)

    def test_a_lost_fight_drops_nothing(self) -> None:
        """A fight won only sometimes drops its units only when won."""
        state = _state(critical_strike=30)
        rate = _trip_rate(state, _trip_gd())
        assert rate is not None and 0 < rate.p_win < 1
        trip = 2 * 50 + 2 * Fraction(DEPOSIT_SECONDS_PER_CODE)
        assert rate.xp_per_second == rate.p_win * rate.xp_per_kill / (
            rate.fight_seconds + rate.recovery_seconds
            + (1 - rate.p_win) * travel_seconds((0, 0), (3, 4))
            + trip * rate.p_win * 2 / 20)

    def test_a_loop_with_no_room_is_unrunnable(self) -> None:
        """No room for the drops: the loop does not run and earns nothing, but
        it is still the loop it would be (its fight and recovery), named by
        `runnable`, never a bare None."""
        gd = _trip_gd()
        stuck = _trip_rate(_state(**_WINS), gd, carried=CarriedKeep(20, 1))
        runs = _trip_rate(_state(**_WINS), gd, carried=CarriedKeep(19, 1))
        assert stuck is not None and runs is not None
        assert (stuck.runnable, stuck.xp_per_second) == (False, 0)
        assert runs.runnable and runs.xp_per_second > 0
        assert (stuck.fight_seconds, stuck.recovery_seconds, stuck.eaten) == (
            runs.fight_seconds, runs.recovery_seconds, runs.eaten)

    def test_a_loop_that_drops_nothing_needs_no_room_and_no_bank(self) -> None:
        gd = _gd()
        rate = _trip_rate(_state(**_WINS), gd, carried=CarriedKeep(20, 1))
        assert rate is not None
        assert rate.xp_per_second == rate.xp_per_kill / (rate.fight_seconds
                                                         + rate.recovery_seconds)

    def test_a_bag_has_a_gain(self) -> None:
        """A worn satchel raises the cap the loop's drops fill (35 against 20)."""
        gd = _trip_gd()
        bagged = _state(**_WINS, inventory_max=35,
                        equipment={**make_state().equipment, "bag_slot": "satchel"})
        with_bag = _trip_rate(bagged, gd)
        without = _trip_rate(_state(**_WINS), gd)
        assert with_bag is not None and without is not None
        assert with_bag.xp_per_second > without.xp_per_second

    def test_far_bank_values_the_bag_more(self) -> None:
        """The same fighter and bag against two monsters with the same drops:
        the one farther from the bank gives the bag the larger gain."""
        gd = _trip_gd()
        bagged = _state(**_WINS, inventory_max=35,
                        equipment={**make_state().equipment, "bag_slot": "satchel"})

        def gain(monster: str) -> Fraction:
            with_bag = _trip_rate(bagged, gd, monster)
            without = _trip_rate(_state(**_WINS), gd, monster)
            assert with_bag is not None and without is not None
            return with_bag.xp_per_second - without.xp_per_second

        assert gain("far_ogre") > gain("ogre") > 0

    def test_prospecting_adds_trips(self) -> None:
        """Spec §2.10: with a learned slope `k > 0` a higher prospecting lands
        more of the hides (1 in 2 at P = 0, sure at P = 100), so the bag fills
        sooner and `R` is lower: prospecting's benefit is on drop routes."""
        gd = _trip_gd()
        learned = LearnedDrops((), (), Fraction(1, 100))
        plain = _trip_rate(_state(**_WINS), gd, drops=learned)
        prospecting = _trip_rate(_state(**_WINS, prospecting=100), gd, drops=learned)
        assert plain is not None and prospecting is not None
        trip = 2 * 50 + 2 * Fraction(DEPOSIT_SECONDS_PER_CODE)
        assert prospecting.xp_per_second == prospecting.xp_per_kill / (
            prospecting.fight_seconds + prospecting.recovery_seconds + trip * 3 / 20)
        assert prospecting.xp_per_second < plain.xp_per_second

    def test_the_drops_are_read_on_the_cycle_evidence(self) -> None:
        """A hide seen on every one of 98 recorded wins: (1 + 98) / (2 + 98) a
        win, not the prior's 1 in 2; and the bone, seen on none of them, 1 in 99
        instead of every win."""
        gd = _trip_gd()
        learned = LearnedDrops((("ogre", 98),), ((("ogre", "hide"), 98),), Fraction(0))
        rate = _trip_rate(_state(**_WINS), gd, drops=learned)
        assert rate is not None
        trip = 2 * 50 + 2 * Fraction(DEPOSIT_SECONDS_PER_CODE)
        drops = Fraction(1, 99) + Fraction(99, 100) * 2
        assert rate.xp_per_second == rate.xp_per_kill / (
            rate.fight_seconds + rate.recovery_seconds + trip * drops / 20)

    def test_the_trip_starts_from_the_spawn_tile_nearest_the_bank(self) -> None:
        gd = _trip_gd()
        gd._monster_locations = {"ogre": [(3, 4), (12, 4), (40, 40)]}
        assert loop_mod.bank_walk(_state(), gd, "ogre") == travel_seconds((12, 4), (13, 4))

    def test_a_bank_trip_needs_a_spawn_tile(self) -> None:
        gd = _trip_gd()
        gd._monster_locations = {}
        with pytest.raises(ValueError, match="a bank trip cannot be priced"):
            loop_mod.bank_walk(_state(), gd, "ogre")


class TestKillsPerSecond:
    """Ruling C2-grey: the loop's kills a second, a kill paying one, from the
    same renewal-reward over the same seconds as its XP a second."""

    def test_the_xp_rate_is_the_kill_rate_times_the_kills_xp(self) -> None:
        rate = _rate(_state(inventory={"heal_potion": 5}), _gd(), [("heal_potion", 5)])
        assert rate is not None and rate.xp_per_kill > 0
        assert rate.kills_per_second > 0
        assert rate.xp_per_second == rate.kills_per_second * rate.xp_per_kill

    def test_a_grey_monster_still_has_a_kill_rate(self) -> None:
        """At level 30 the level-5 ogre pays no XP: no XP a second, and the
        same kills a second as the low-level character (`p_win` 1 either way)."""
        held = {"inventory": {"heal_potion": 5}}
        low = _rate(_state(**held), _gd(), [("heal_potion", 5)])
        grey = _rate(_state(level=30, **held), _gd(), [("heal_potion", 5)])
        assert low is not None and grey is not None
        assert (grey.xp_per_kill, grey.xp_per_second) == (0, 0)
        assert grey.kills_per_second == low.kills_per_second > 0

    def test_a_loop_with_no_room_kills_nothing(self) -> None:
        """No room for the drops: the loop does not run, so it kills nothing,
        though the same loop with one unit of room kills."""
        gd = _trip_gd()
        stuck = _trip_rate(_state(**_WINS), gd, carried=CarriedKeep(20, 1))
        runs = _trip_rate(_state(**_WINS), gd, carried=CarriedKeep(19, 1))
        assert stuck is not None and runs is not None
        assert (stuck.runnable, stuck.kills_per_second) == (False, 0)
        assert runs.kills_per_second > 0


class TestFoodRoom:
    """Task 8c (ruling C2-food): a food's carry is the least of the horizon
    demand, the bag's room for it and, with no replacement, the units held
    (`chosen_loadout.food_carry`), and the recovery eats no more of a food a
    fight than that room."""

    def test_a_held_food_eaten_several_a_fight_leaves_a_near_empty_bag_runnable(self) -> None:
        """An empty bag of 100 and 40 held 10-HP crumbs with no replacement: the
        recovery eats six a fight, whose horizon carry (120) is past the bag.
        The uncapped carry read the bag full and the loop `runnable=False`;
        bounded by the 40 held, it leaves 60 units of room for the drops."""
        state = _state(**_WINS, inventory_max=100)
        rate = _trip_rate(state, _trip_gd(), food=(FoodOffer("crumb", 10, None, 40),))
        assert rate is not None
        [(_, eaten)] = rate.eaten
        assert eaten >= 5 and eaten * CARRY_HORIZON_FIGHTS > 100
        assert rate.runnable and rate.xp_per_second > 0
        trip = 2 * 50 + 2 * Fraction(DEPOSIT_SECONDS_PER_CODE)
        assert rate.xp_per_second == rate.xp_per_kill / (
            rate.fight_seconds + rate.recovery_seconds + trip * 2 / (100 - 40))

    def test_the_recovery_eats_no_more_than_the_bag_carries(self) -> None:
        """A bag of 3 carries three free 10-HP crumbs: the recovery eats those
        three and rests off the rest — Rest is the priced fallback, not a veto.
        The crumbs fill the bag, so the loop does not run."""
        state = _state(**_WINS, inventory_max=3)
        rate = _trip_rate(state, _trip_gd(), food=(FoodOffer("crumb", 10, Fraction(0), 0),))
        assert rate is not None
        missing = rate.max_hp - rate.hp_end
        assert missing > 30
        assert rate.eaten == (("crumb", 3),)
        assert rate.recovery_seconds == recovery_seconds(missing, rate.max_hp,
                                                         [(10, Fraction(0), 0, 3)], EAT_SECONDS, 3, 20)
        assert rate.recovery_seconds > recovery_seconds(missing, rate.max_hp,
                                                        [(10, Fraction(0), 0, 99)], EAT_SECONDS, 99, 20)
        assert not rate.runnable

    def test_a_food_with_no_slot_falls_back_to_rest(self) -> None:
        """The keep's stacks fill every slot: a food the bag holds no stack of
        has no room, so the recovery rests; one free slot and it eats."""
        state = _state(**_WINS, inventory_max=100, inventory_slots_max=2)
        food = (FoodOffer("crumb", 10, Fraction(0), 0),)
        full = _trip_rate(state, _trip_gd(), food=food, carried=CarriedKeep(5, 2))
        slot = _trip_rate(state, _trip_gd(), food=food, carried=CarriedKeep(5, 1))
        assert full is not None and slot is not None
        assert full.eaten == () and slot.eaten
        assert full.recovery_seconds > slot.recovery_seconds

    def test_one_free_slot_is_one_food_never_two(self) -> None:
        """Fix round 1, review scenario A: one slot free past the keep and 95
        units of room; 3 held 10-HP crumbs with no replacement and 30-HP pies
        at 5 s. With two stacks the recovery would eat three crumbs and a pie;
        with one it eats the pies alone (3 + 2 × 5 s), and they carry: the loop
        never prices a crumb the bag has no stack for. (c4b909fc priced the
        crumbs AND a pie, the pie's carry 0.)"""
        state = _state(**_WINS, inventory_max=100, inventory_slots_max=2)
        food = (FoodOffer("crumb", 10, None, 3), FoodOffer("pie", 30, Fraction(5), 0))
        rate = _trip_rate(state, _trip_gd(), food=food, carried=CarriedKeep(5, 1))
        assert rate is not None
        missing = rate.max_hp - rate.hp_end
        offers = [(10, None, 3, 95), (30, Fraction(5), 0, 95)]
        assert recovery_choice(missing, rate.max_hp, offers, EAT_SECONDS, 95, 2)[1] == (3, 1)
        assert rate.eaten == (("pie", 2),)
        assert rate.recovery_seconds == recovery_seconds(missing, rate.max_hp, offers, EAT_SECONDS, 95, 1)
        assert rate.runnable
        trip = 2 * 50 + 2 * Fraction(DEPOSIT_SECONDS_PER_CODE)
        assert rate.xp_per_second == rate.xp_per_kill / (
            rate.fight_seconds + rate.recovery_seconds + trip * 2 / (95 - 2 * CARRY_HORIZON_FIGHTS))

    def test_five_units_of_room_eat_five_units_a_fight(self) -> None:
        """Review scenario B: a bag of five and two 10-HP foods at 1 s. The
        foods a fight eats fit the bag together — five units in all, every food
        eaten carrying its fight (`food_shares`) — where c4b909fc priced six
        a fight (five of one and one of the other) in a bag of five. The five
        fill the bag, so the loop does not run (the named residual)."""
        state = _state(**_WINS, inventory_max=5)
        food = (FoodOffer("crumb", 10, Fraction(1), 0), FoodOffer("rusk", 10, Fraction(1), 0))
        rate = _trip_rate(state, _trip_gd(), food=food)
        assert rate is not None
        assert sum(n for _, n in rate.eaten) == 5
        eaten = [n for _, n in rate.eaten]
        assert all(share >= n for share, n in zip(food_shares([(n, 0) for n in eaten], 20, 5), eaten,
                                                  strict=True))
        assert not rate.runnable

    def test_every_ending_eats_within_the_deepest_endings_allotment(self) -> None:
        """One slot, and a fight that ends 60 or 30 HP short. The deepest
        ending's cheapest recovery in the bag is one 60-HP pie (3 + 2 s); the
        shallow one alone would eat three free crumbs, a second food the one
        slot cannot hold. The bag is allotted the pie, and every ending eats
        within it, so the loop eats pies only and never a crumb it has no stack
        for."""
        state = _state(attack={"fire": 40}, critical_strike=50, inventory_max=100,
                       inventory_slots_max=1)
        endings, _, _ = odds_walk(state, _trip_gd(), "ogre", [])
        assert sorted({e.hp_end // 10_000 for e in endings}) == [40, 70]
        food = (FoodOffer("pie", 60, Fraction(2), 0), FoodOffer("crumb", 10, None, 3))
        rate = _trip_rate(state, _trip_gd(), food=food)
        assert rate is not None
        assert recovery_choice(30, 100, [(60, Fraction(2), 0, 100), (10, None, 3, 100)],
                               EAT_SECONDS, 100, 1)[1] == (0, 3)
        assert rate.eaten == (("pie", 1),)
        assert rate.recovery_seconds == 5

    def test_two_foods_with_two_slots_share_the_room(self) -> None:
        """Two held foods with no replacement, both eaten a fight, and two
        slots free past the keep: both carry their fight."""
        state = _state(**_WINS, inventory_max=8, inventory_slots_max=3)
        food = (FoodOffer("bread", 50, None, 1), FoodOffer("crumb", 10, None, 1))
        rate = _trip_rate(state, _trip_gd(), food=food, carried=CarriedKeep(5, 1))
        assert rate is not None
        assert rate.eaten == (("bread", 1), ("crumb", 1))
        assert rate.runnable
        trip = 2 * 50 + 2 * Fraction(DEPOSIT_SECONDS_PER_CODE)
        assert rate.xp_per_second == rate.xp_per_kill / (
            rate.fight_seconds + rate.recovery_seconds + trip * 2 / (8 - 5 - 2))
