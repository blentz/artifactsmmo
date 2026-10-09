"""The fight loop's XP rate read from the world
(`docs/PLAN_consumable_utility.md` increment 3)."""

from dataclasses import replace
from fractions import Fraction

import pytest

import artifactsmmo_cli.ai.loop_rate as loop_mod
from artifactsmmo_cli.ai.boost_selection import project_equip
from artifactsmmo_cli.ai.combat import combat_terms, fight_max_hp
from artifactsmmo_cli.ai.fight_outcome_core import fight_outcome
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.loop_rate import EAT_SECONDS, held_foods, loop_rate
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
            loop_rate(_state(), _gd(), _CTX, "ogre", loadout)


class TestLoop:
    def test_no_potions_loses_and_earns_nothing(self) -> None:
        rate = loop_rate(_state(), _gd(), _CTX, "ogre", [])
        assert rate is not None
        assert (rate.win, rate.xp_per_kill, rate.xp_per_second, rate.used) == (False, 0, 0, ())
        assert rate.hp_end == 0
        assert rate.recovery_seconds == 100  # a whole bar rested off

    def test_a_held_restore_wins_the_fight_and_is_free(self) -> None:
        gd = _gd()
        state = _state(inventory={"heal_potion": 5})
        rate = loop_rate(state, gd, _CTX, "ogre", [("heal_potion", 5)])
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
        rate = loop_rate(state, gd, _CTX, "ogre", [("fire_res_potion", 3)])
        assert rate is not None
        assert rate.win is True          # 15 a round: dies in 7, kills in 5
        assert rate.used == (("fire_res_potion", 1),)
        assert rate.hp_end == 100 - 4 * 15

    def test_two_boosts_fill_both_slots(self) -> None:
        gd = _gd()
        state = _state(inventory={"fire_res_potion": 1, "hp_potion": 1})
        rate = loop_rate(state, gd, _CTX, "ogre", [("fire_res_potion", 1), ("hp_potion", 1)])
        assert rate is not None
        assert rate.max_hp == 160
        assert rate.hp_end == 160 - 4 * 15

    def test_a_worn_boost_left_out_of_the_loadout_is_taken_off(self) -> None:
        gd = _gd()
        worn = _state(inventory={"fire_res_potion": 1})
        worn = project_equip(worn, "fire_res_potion", gd)
        assert loop_mod.loop_rate(worn, gd, _CTX, "ogre", []).win is False  # type: ignore[union-attr]

    def test_a_priced_consumable_costs_its_price(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(loop_mod, "consumable_price_of", lambda *a: Fraction(7))
        rate = loop_rate(_state(), _gd(), _CTX, "ogre", [("fire_res_potion", 1)])
        assert rate is not None
        assert rate.consumed_seconds == 7

    def test_an_unpriceable_consumable_makes_the_loop_unrunnable(
            self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(loop_mod, "consumable_price_of", lambda *a: None)
        assert loop_rate(_state(), _gd(), _CTX, "ogre", [("fire_res_potion", 1)]) is None

    def test_an_undrunk_restore_is_not_priced(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Full resistance stops the drink: the restore is never needed, so its
        # (absent) price is never asked.
        gd = _gd()
        gd._item_stats["fire_res_potion"] = ItemStats(
            code="fire_res_potion", resistance={"fire": 100}, **_UTILITY)
        monkeypatch.setattr(loop_mod, "consumable_price_of",
                            lambda code, *a: None if code == "heal_potion" else Fraction(0))
        rate = loop_rate(_state(), gd, _CTX, "ogre", [("fire_res_potion", 1), ("heal_potion", 2)])
        assert rate is not None
        assert rate.used == (("fire_res_potion", 1), ("heal_potion", 0))

    def test_held_foods_shorten_recovery(self) -> None:
        gd = _gd()
        state = _state(inventory={"heal_potion": 5, "apple": 1}, bank_items={"bread": 1})
        assert held_foods(state, gd) == ["apple", "bread"]
        with_food = loop_rate(state, gd, _CTX, "ogre", [("heal_potion", 5)])
        without = loop_rate(replace(state, inventory={"heal_potion": 5}, bank_items={}),
                            gd, _CTX, "ogre", [("heal_potion", 5)])
        assert with_food is not None and without is not None
        assert with_food.recovery_seconds < without.recovery_seconds
        assert with_food.xp_per_second > without.xp_per_second


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
