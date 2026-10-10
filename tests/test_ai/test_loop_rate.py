"""The fight loop's XP rate read from the world
(`docs/PLAN_consumable_utility.md` increments 3-4)."""

from fractions import Fraction

import pytest

import artifactsmmo_cli.ai.loop_rate as loop_mod
from artifactsmmo_cli.ai.boost_selection import project_equip
from artifactsmmo_cli.ai.combat import combat_terms, fight_max_hp
from artifactsmmo_cli.ai.fight_outcome_core import fight_outcome
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.loop_rate import EAT_SECONDS, FoodOffer, LoopRate, food_menu, loop_rate
from artifactsmmo_cli.ai.loop_rate_core import recovery_seconds
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
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
    return loop_rate(state, gd, "ogre", loadout, food, _FREE if prices is None else prices)


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
        assert rate.hp_end == 0
        assert rate.recovery_seconds == 100  # a whole bar rested off

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
        assert rate.fight_seconds == 30
        assert rate.recovery_seconds == recovery_seconds(100 - rate.hp_end, 100, [], EAT_SECONDS)
        assert rate.xp_per_second == Fraction(rate.xp_per_kill, 30 + rate.recovery_seconds)

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
        assert loop_mod.loop_rate(worn, gd, "ogre", [], (), {}).win is False  # type: ignore[union-attr]

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
