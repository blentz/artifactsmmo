"""The fleet's consumable floor, rebuilt on the chosen loadouts
(`docs/PLAN_consumable_utility.md` increment 4). USER 2026-10-09: the minimum
banked quantity is "From the chosen loadouts" (units used per fight ×
`REFILL_HORIZON_FIGHTS`), shared by "Need ledger + API order". Proved core
`Formal.ConsumableFloor`."""

import dataclasses
from fractions import Fraction

import pytest

from artifactsmmo_cli.ai.best_loadout import fight_ahead_loadout
from artifactsmmo_cli.ai.chosen_loadout import ChosenLoadout
from artifactsmmo_cli.ai.consumable_floor import consumable_need, supply_shortfall
from artifactsmmo_cli.ai.consumable_floor_core import REFILL_HORIZON_FIGHTS, share
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.heal_catalog import FOOD, POTION, heal_candidates
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.task_worth import short_items
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem
from artifactsmmo_cli.ai.xp_demand import demand_roots
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_best_loadout import _gd as _ogre_gd
from tests.test_ai.test_best_loadout import _prices, _state

ORDER = ("Robby", "C3P0", "HAL")


class TestCore:
    def test_the_bank_goes_in_fleet_order(self) -> None:
        needs = {"Robby": 20, "C3P0": 20, "HAL": 20}
        assert [share(ORDER, needs, name, 25) for name in ORDER] == [0, 15, 20]
        assert [share(ORDER, needs, name, 0) for name in ORDER] == [20, 20, 20]
        assert [share(ORDER, needs, name, 100) for name in ORDER] == [0, 0, 0]

    def test_a_character_without_a_row_needs_nothing(self) -> None:
        assert share(ORDER, {"HAL": 30}, "HAL", 10) == 20
        assert share(ORDER, {"HAL": 30}, "Robby", 10) == 0

    def test_a_character_outside_the_account_order_fails(self) -> None:
        with pytest.raises(ValueError):
            share(ORDER, {"Lor": 5}, "Lor", 0)


def test_heal_candidates_by_class_in_catalogue_order() -> None:
    gd = GameData()
    gd._item_stats = {
        "cooked_chicken": ItemStats(code="cooked_chicken", level=1, type_=FOOD, hp_restore=80),
        "small_health_potion": ItemStats(code="small_health_potion", level=5, type_=POTION,
                                         hp_restore=40),
        "cooked_bass": ItemStats(code="cooked_bass", level=30, type_=FOOD, hp_restore=200),
        "iron_sword": ItemStats(code="iron_sword", level=10, type_="weapon"),
    }
    assert heal_candidates(gd, FOOD) == ["cooked_chicken", "cooked_bass"]
    assert heal_candidates(gd, POTION) == ["small_health_potion"]


class TestNeed:
    def test_no_fight_ahead_needs_nothing(self) -> None:
        assert consumable_need(None) == {}

    def test_the_chosen_loadout_over_the_refill_horizon(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A priced heal potion turns the ogre loss into a win; the need is what
        one fight drinks × 20."""
        _prices(monkeypatch, {"heal_potion": Fraction(2)})
        state, gd = _state(), _ogre_gd()
        ctx = dataclasses.replace(NO_PROFILE_CONTEXT, combat_monster="ogre")
        pick = fight_ahead_loadout(state, gd, ctx, None)
        assert pick is not None
        drunk = dict(pick.potions)["heal_potion"]
        assert drunk > 0
        assert consumable_need(pick) == {"heal_potion": drunk * REFILL_HORIZON_FIGHTS}

    def test_potions_and_food_both_count(self) -> None:
        pick = ChosenLoadout("wolf", (("heal_potion", 2),), (("apple", 3),))
        assert consumable_need(pick) == {"heal_potion": 40, "apple": 60}


class TestShortfall:
    def test_each_type_owes_its_share_of_the_banked_shortfall(self) -> None:
        """25 potions banked; Robby (ahead) needs 20, C3P0 needs 20: C3P0 owes 15.
        Bass: nobody ahead needs it, 0 banked: C3P0 owes all 40."""
        state = make_state(bank_items={"small_health_potion": 25})
        got = supply_shortfall(state, ORDER, "C3P0", {"small_health_potion": 20, "cooked_bass": 40},
                               {"Robby": {"small_health_potion": 20}, "HAL": {"cooked_bass": 99}})
        assert got == (("small_health_potion", 15), ("cooked_bass", 40))

    def test_a_met_floor_owes_nothing(self) -> None:
        state = make_state(bank_items={"small_health_potion": 40})
        got = supply_shortfall(state, ORDER, "C3P0", {"small_health_potion": 20},
                               {"Robby": {"small_health_potion": 20}})
        assert got == ()

    def test_the_stock_is_the_bank_only(self) -> None:
        """Units in the bag or a utility slot are not the banked minimum."""
        state = make_state(inventory={"small_health_potion": 50},
                           equipment={"utility1_slot": "small_health_potion"},
                           utility1_slot_quantity=50, bank_items={})
        assert supply_shortfall(state, ("C3P0",), "C3P0", {"small_health_potion": 20}, {}) == (
            ("small_health_potion", 20),)

    def test_no_need_owes_nothing(self) -> None:
        assert supply_shortfall(make_state(), ORDER, "C3P0", {}, {"HAL": {"cooked_bass": 9}}) == ()


class TestShortfallIsDemand:
    def test_it_seeds_the_dag_roots(self) -> None:
        ctx = dataclasses.replace(NO_PROFILE_CONTEXT, supply_shortfall=(("cooked_bass", 12),))
        assert demand_roots(None, make_state(), ctx) == [ObtainItem("cooked_bass", 12)]

    def test_it_makes_its_ingredients_short(self) -> None:
        gd = GameData()
        gd._item_stats = {"cooked_bass": ItemStats(code="cooked_bass", level=30, type_=FOOD,
                                                   hp_restore=200)}
        gd._crafting_recipes = {"cooked_bass": {"bass": 1}}
        gd._craft_yields = {"cooked_bass": 1}
        ctx = dataclasses.replace(NO_PROFILE_CONTEXT, supply_shortfall=(("cooked_bass", 12),))
        assert short_items(make_state(bank_items={"bass": 5}), gd, ctx) == {"cooked_bass", "bass"}
        enough = make_state(bank_items={"bass": 12})
        assert short_items(enough, gd, ctx) == {"cooked_bass"}
