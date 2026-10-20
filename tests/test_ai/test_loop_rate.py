"""The fight loop's XP rate read from the world
(`docs/PLAN_consumable_utility.md` increments 3-4)."""

from fractions import Fraction

import pytest

import artifactsmmo_cli.ai.loop_rate as loop_mod
from artifactsmmo_cli.ai.actions.cost_core import travel_seconds
from artifactsmmo_cli.ai.boost_selection import project_equip
from artifactsmmo_cli.ai.combat import combat_terms, fight_max_hp
from artifactsmmo_cli.ai.fight_odds_core import win_probability
from artifactsmmo_cli.ai.fight_outcome_core import fight_outcome
from artifactsmmo_cli.ai.fight_walk import fight_walk, odds_walk, walk_seconds
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
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
                     _TIMING)


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
        assert rate.recovery_seconds == recovery_seconds(100 - rate.hp_end, 100, [], EAT_SECONDS)
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
        worn = project_equip(worn, "fire_res_potion", gd)
        assert loop_mod.loop_rate(worn, gd, "ogre", [], (), {}, _TIMING).win is False  # type: ignore[union-attr]

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
        state = _state(inventory={"heal_potion": 5})
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
        state = _state(inventory={"heal_potion": 1, "apple": 1})
        loadout = [("heal_potion", 5)]
        prices: dict[str, Fraction | None] = {"heal_potion": Fraction(7)}
        food = (FoodOffer("apple", 30, Fraction(3), 1),)
        outcome, max_hp, restore = fight_walk(state, gd, "ogre", loadout)
        assert outcome.win and restore == "heal_potion" and outcome.used > 1
        consumed = consumed_seconds([(outcome.used, Fraction(7), 1)])
        assert consumed is not None and consumed > 0
        recovery, counts = recovery_choice(max_hp - outcome.hp_end // 10_000, max_hp,
                                           [(30, Fraction(3), 1)], EAT_SECONDS)
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
                                                  100, [], EAT_SECONDS) for e in endings), Fraction(0))
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
                                slot="utility2_slot")
        assert boosted.equipment["utility2_slot"] == "hp_potion"
        assert fight_max_hp(boosted, gd, "ogre") == 160

    def test_project_equip_none_empties_the_slot(self) -> None:
        gd = _gd()
        worn = project_equip(_state(inventory={"hp_potion": 1}), "hp_potion", gd)
        assert worn.max_hp == 160
        emptied = project_equip(worn, None, gd)
        assert emptied.equipment["utility1_slot"] is None
        assert emptied.max_hp == 100
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
