"""The fleet's consumable floor (Phase 5-2c-iii-c-2 #5, `docs/PLAN_task_value.md`
§10). USER 2026-10-07: "Fishing feeds Cooking, Cooking feeds HP recovery or
provides stat bonuses. Both cases require pre-emptive crafting of an available
supply. The fleet can collectively maintain a minimum supply in the bank."
Proved core `Formal.ConsumableFloor`."""

import dataclasses

import artifactsmmo_cli.ai.consumable_floor as mod
from artifactsmmo_cli.ai.consumable_floor import (
    consumable_holdings,
    heal_candidates,
    supply_shortfall,
)
from artifactsmmo_cli.ai.consumable_floor_core import fleet_deficit, publish_share, tier_pick
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.task_worth import short_items
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem
from artifactsmmo_cli.ai.xp_demand import demand_roots
from tests.test_ai.fixtures import make_state


class TestCore:
    def test_the_best_restore_usable_at_the_level(self) -> None:
        assert tier_pick(30, [(20, 150), (30, 300), (40, 500)]) == 1
        assert tier_pick(10, [(20, 150)]) is None
        assert tier_pick(30, [(5, 0)]) is None  # restores nothing

    def test_ties_go_to_the_higher_level_then_catalogue_order(self) -> None:
        assert tier_pick(30, [(20, 300), (30, 300), (30, 300)]) == 1

    def test_the_deficit_and_the_share(self) -> None:
        assert fleet_deficit(5, 5, 7) == 18
        assert fleet_deficit(5, 5, 30) == 0
        assert publish_share(18, 5) == 4  # 5 x 4 = 20 >= 18
        assert publish_share(18, 1) == 18


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "cooked_chicken": ItemStats(code="cooked_chicken", level=1, type_="consumable", hp_restore=80),
        "cooked_trout": ItemStats(code="cooked_trout", level=20, type_="consumable", hp_restore=150),
        "cooked_bass": ItemStats(code="cooked_bass", level=30, type_="consumable", hp_restore=200),
        "small_health_potion": ItemStats(code="small_health_potion", level=5, type_="utility",
                                         hp_restore=40),
        "iron_sword": ItemStats(code="iron_sword", level=10, type_="weapon"),
    }
    return gd


def test_heal_candidates_by_class_in_catalogue_order() -> None:
    assert heal_candidates(_gd(), "consumable") == ["cooked_chicken", "cooked_trout", "cooked_bass"]
    assert heal_candidates(_gd(), "utility") == ["small_health_potion"]


def test_holdings_are_the_bag_and_the_utility_slots() -> None:
    state = make_state(inventory={"cooked_trout": 3, "iron_sword": 1, "cooked_bass": 0},
                       equipment={"utility1_slot": "small_health_potion", "utility2_slot": None},
                       utility1_slot_quantity=12)
    assert consumable_holdings(state, _gd()) == {"cooked_trout": 3, "small_health_potion": 12}


class TestShortfall:
    def test_the_tier_food_below_the_fleet_floor(self, monkeypatch) -> None:
        """Floor 5 x 5 = 25 cooked_bass; 4 carried, 3 at a sibling, 6 banked."""
        monkeypatch.setattr(mod, "heal_stock_target", lambda *a: 0)
        state = make_state(level=30, inventory={"cooked_bass": 4}, bank_items={"cooked_bass": 6})
        got = supply_shortfall(state, _gd(), None, None, 5, {"cooked_bass": 3})
        assert got == (("cooked_bass", 12),)

    def test_the_potion_floor_reads_the_fight_ahead(self, monkeypatch) -> None:
        seen = {}

        def target(state, gd, history, monster, code):  # type: ignore[no-untyped-def]
            seen.update(monster=monster, code=code)
            return 10

        monkeypatch.setattr(mod, "heal_stock_target", target)
        state = make_state(level=30, inventory={"cooked_bass": 25})
        got = supply_shortfall(state, _gd(), None, "ogre", 2, {})
        assert got == (("small_health_potion", 20),)
        assert seen == {"monster": "ogre", "code": "small_health_potion"}

    def test_a_met_floor_or_an_empty_class_owes_nothing(self, monkeypatch) -> None:
        monkeypatch.setattr(mod, "heal_stock_target", lambda *a: 0)
        state = make_state(level=0, inventory={})
        assert supply_shortfall(state, _gd(), None, None, 5, {}) == ()
        full = make_state(level=30, bank_items={"cooked_bass": 25})
        assert supply_shortfall(full, _gd(), None, None, 5, {}) == ()


class TestShortfallIsDemand:
    def test_it_seeds_the_dag_roots(self) -> None:
        ctx = dataclasses.replace(NO_PROFILE_CONTEXT, supply_shortfall=(("cooked_bass", 12),))
        assert demand_roots(None, make_state(), ctx) == [ObtainItem("cooked_bass", 12)]

    def test_it_makes_its_ingredients_short(self) -> None:
        gd = _gd()
        gd._crafting_recipes = {"cooked_bass": {"bass": 1}}
        gd._craft_yields = {"cooked_bass": 1}
        ctx = dataclasses.replace(NO_PROFILE_CONTEXT, supply_shortfall=(("cooked_bass", 12),))
        assert short_items(make_state(bank_items={"bass": 5}), gd, ctx) == {"cooked_bass", "bass"}
        enough = make_state(bank_items={"bass": 12})
        assert short_items(enough, gd, ctx) == {"cooked_bass"}
